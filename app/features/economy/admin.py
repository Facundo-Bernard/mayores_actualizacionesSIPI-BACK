"""Operaciones administrativas sobre la economía de un usuario."""

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from pymongo import ReturnDocument

from app.core.database import get_database
from app.shared.ledger import get_points_ledger

logger = logging.getLogger("EconomyService")


async def find_user_by_identifier(identificador: str) -> Dict[str, Any]:
    """Busca un usuario por email (case-insensitive), código PIN o ID numérico."""
    db = get_database()
    ident = identificador.strip()
    if not ident:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe ingresar un email, código de acceso PIN o ID de usuario.",
        )

    conds = [
        {"email": {"$regex": f"^{re.escape(ident)}$", "$options": "i"}},
        {"codigo_acceso": ident},
        {"codigoAcceso": ident},
    ]
    if ident.isdigit():
        conds.append({"id": int(ident)})

    user = await db["usuarios"].find_one({"$or": conds})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró ningún usuario con el identificador '{ident}'.",
        )

    return {
        "id": user["id"],
        "name": user.get("name", "Usuario"),
        "email": user.get("email"),
        "codigoAcceso": user.get("codigo_acceso", user.get("codigoAcceso")),
        "vidas": int(user.get("vidas", 5)),
        "puntos": int(user.get("puntos", 0)),
        "suscripcion": user.get("suscripcion", "basica"),
        "dias_desbloqueados": user.get("dias_desbloqueados", []),
    }


async def adjust_user_economy(
    identificador: str,
    vidas_sumar: Optional[int] = None,
    puntos_sumar: Optional[int] = None,
    vidas_set: Optional[int] = None,
    puntos_set: Optional[int] = None,
    suscripcion_set: Optional[str] = None,
    actor_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Asigna o ajusta vidas y/o puntos en un único update atómico (administración)."""
    user = await find_user_by_identifier(identificador)
    user_id = user["id"]
    db = get_database()

    set_stage: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
    operations: Dict[str, Any] = {}

    if vidas_set is not None:
        set_stage["vidas"] = max(0, int(vidas_set))
        operations["vidas_set"] = int(vidas_set)
    elif vidas_sumar is not None and vidas_sumar != 0:
        set_stage["vidas"] = {
            "$max": [0, {"$add": [{"$ifNull": ["$vidas", 0]}, int(vidas_sumar)]}]
        }
        operations["vidas_sumar"] = int(vidas_sumar)

    if puntos_set is not None:
        set_stage["puntos"] = max(0, int(puntos_set))
        operations["puntos_set"] = int(puntos_set)
    elif puntos_sumar is not None and puntos_sumar != 0:
        set_stage["puntos"] = {
            "$max": [0, {"$add": [{"$ifNull": ["$puntos", 0]}, int(puntos_sumar)]}]
        }
        operations["puntos_sumar"] = int(puntos_sumar)

    if suscripcion_set:
        set_stage["suscripcion"] = suscripcion_set.lower().strip()
        operations["suscripcion_set"] = suscripcion_set.lower().strip()

    if not operations:
        return {
            "success": True,
            "user_id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "codigoAcceso": user["codigoAcceso"],
            "vidas": user["vidas"],
            "puntos": user["puntos"],
            "message": "Sin cambios solicitados.",
        }

    updated = await db["usuarios"].find_one_and_update(
        {"id": user_id},
        [{"$set": set_stage}],
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario {user_id} no encontrado.",
        )

    final_vidas = int(updated.get("vidas", 0))
    final_puntos = int(updated.get("puntos", 0))

    try:
        await get_points_ledger().record_event(
            user_id=user_id,
            motivo="admin_adjust",
            puntos=int(puntos_sumar or 0),
            idempotency_key=f"admin_adjust:{uuid.uuid4().hex}",
            metadata={
                "actor": actor_id,
                "operations": operations,
                "saldo_despues": final_puntos,
            },
            status="applied",
        )
    except Exception as e:
        logger.warning(f"No se pudo auditar el ajuste admin de {user_id}: {e}")

    logger.info(
        f"[ECONOMIA ADMIN] Ajuste realizado a usuario {user_id} ({user.get('name')}) "
        f"por actor {actor_id}: {final_vidas} vidas, {final_puntos} pts."
    )

    return {
        "success": True,
        "user_id": updated.get("id"),
        "name": updated.get("name", ""),
        "email": updated.get("email"),
        "codigoAcceso": updated.get("codigo_acceso", updated.get("codigoAcceso")),
        "vidas": final_vidas,
        "puntos": final_puntos,
        "suscripcion": updated.get("suscripcion", "basica"),
        "message": f"¡Listo! {updated.get('name', 'Usuario')} ahora tiene {final_vidas} vidas y {final_puntos} puntos.",
    }


async def change_user_subscription(usuario_id: int, nueva_suscripcion: str) -> Dict[str, Any]:
    """Actualiza el nivel de suscripción del usuario ('basica' o 'premium')."""
    sub = nueva_suscripcion.lower().strip()
    if sub not in ("basica", "premium"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La suscripción debe ser 'basica' o 'premium'."
        )

    db = get_database()
    updated = await db["usuarios"].find_one_and_update(
        {"id": usuario_id},
        {"$set": {"suscripcion": sub, "updated_at": datetime.now(timezone.utc)}},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario {usuario_id} no encontrado."
        )

    return {
        "success": True,
        "user_id": updated["id"],
        "name": updated.get("name", ""),
        "email": updated.get("email"),
        "suscripcion": sub,
        "message": f"Suscripción de {updated.get('name', 'usuario')} actualizada a '{sub}'.",
    }
