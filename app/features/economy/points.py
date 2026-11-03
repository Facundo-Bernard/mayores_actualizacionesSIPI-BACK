"""Puntos: migración única del saldo de invitado con auditoría."""

import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status
from pymongo import ReturnDocument

from app.core.database import get_database
from app.features.economy.config import get_economy_config
from app.features.economy.schemas import GuestMigrationResponse
from app.shared.clock import today_str
from app.shared.ledger import get_points_ledger

logger = logging.getLogger("EconomyService")


async def migrate_guest_points(user_id: int, guest_id: str, puntos_solicitados: int) -> GuestMigrationResponse:
    """
    Migra una única vez los puntos acumulados como invitado a la cuenta autenticada.

    El cliente informa cuántos puntos tenía en localStorage; el servidor aplica el
    tope configurado (``guest_migration_max_points``) y registra el movimiento en
    el ledger para auditoría. La marca ``guest_migration_applied`` en el usuario es
    la guarda atómica que impide reclamar dos veces con la misma cuenta.
    """
    db = get_database()
    config = await get_economy_config()
    tope = max(0, int(config.guest_migration_max_points))
    solicitados = max(0, int(puntos_solicitados))
    aplicado = min(solicitados, tope)

    user = await db["usuarios"].find_one({"id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con ID {user_id} no encontrado",
        )

    if user.get("guest_migration_applied"):
        return GuestMigrationResponse(
            success=False,
            ya_migrado=True,
            puntos_solicitados=solicitados,
            puntos_migrados=0,
            tope=tope,
            puntos_totales=int(user.get("puntos", 0)),
            message="Esta cuenta ya reclamó puntos de invitado.",
        )

    if solicitados <= 0:
        return GuestMigrationResponse(
            success=False,
            ya_migrado=False,
            puntos_solicitados=0,
            puntos_migrados=0,
            tope=tope,
            puntos_totales=int(user.get("puntos", 0)),
            message="No hay puntos de invitado para migrar.",
        )

    now = datetime.now(timezone.utc)
    resultado = await db["usuarios"].find_one_and_update(
        {"id": user_id, "guest_migration_applied": {"$ne": True}},
        {
            "$inc": {"puntos": aplicado},
            "$set": {
                "guest_migration_applied": True,
                "guest_migration_guest_id": guest_id,
                "guest_migration_at": now,
                "updated_at": now,
            },
        },
        return_document=ReturnDocument.AFTER,
    )

    if not resultado:
        actual = await db["usuarios"].find_one({"id": user_id}) or user
        return GuestMigrationResponse(
            success=False,
            ya_migrado=True,
            puntos_solicitados=solicitados,
            puntos_migrados=0,
            tope=tope,
            puntos_totales=int(actual.get("puntos", 0)),
            message="Esta cuenta ya reclamó puntos de invitado.",
        )

    total = int(resultado.get("puntos", 0))
    await get_points_ledger().record_event(
        user_id=user_id,
        motivo="guest_migration",
        puntos=aplicado,
        idempotency_key=f"guest_migration:{user_id}",
        metadata={
            "guest_id": guest_id,
            "game_id": "guest",
            "date": today_str(),
            "difficulty": "standard",
            "solicitado": solicitados,
            "aplicado": aplicado,
            "tope": tope,
        },
        status="applied",
    )
    logger.info(
        f"[ECONOMIA] Usuario {user_id} migró {aplicado} pts de invitado {guest_id} "
        f"(solicitados {solicitados}, tope {tope}). Saldo: {total} pts."
    )

    mensaje = f"Se migraron {aplicado} puntos de invitado."
    if solicitados > aplicado:
        mensaje += f" Se aplicó el tope de {tope} puntos."

    return GuestMigrationResponse(
        success=True,
        ya_migrado=False,
        puntos_solicitados=solicitados,
        puntos_migrados=aplicado,
        tope=tope,
        puntos_totales=total,
        message=mensaje,
    )
