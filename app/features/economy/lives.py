"""Vidas: estado del usuario, consumo, compra y recarga de partida."""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, status
from pymongo import ReturnDocument

from app.core.database import get_database
from app.features.economy.config import get_economy_config
from app.features.economy.schemas import (
    BuyLivesRequest,
    BuyLivesResponse,
    ConsumeLifeResponse,
    RefillLivesResponse,
    UserEconomyResponse,
)
from app.shared.streak import calcular_racha

logger = logging.getLogger("EconomyService")

REFILL_LIVES_COST = 50


async def get_user_economy(user_id: int) -> UserEconomyResponse:
    """
    Obtiene el estado económico (vidas, puntos, racha) del usuario.
    Si el usuario no tiene vidas inicializadas, le otorga las vidas por defecto.
    """
    db = get_database()
    config = await get_economy_config()
    user = await db["usuarios"].find_one({"id": user_id})

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con ID {user_id} no encontrado",
        )

    if "vidas" not in user:
        await db["usuarios"].update_one(
            {"id": user_id},
            {
                "$set": {"vidas": config.vidas_iniciales},
                "$setOnInsert": {"puntos": 0},
            },
        )
        user["vidas"] = config.vidas_iniciales

    vidas = int(user.get("vidas", config.vidas_iniciales))
    puntos = int(user.get("puntos", 0))
    racha = await calcular_racha(user_id)

    suscripcion = str(user.get("suscripcion", "basica")).lower()
    dias_desbloqueados = user.get("dias_desbloqueados", [])

    return UserEconomyResponse(
        user_id=user_id,
        vidas=vidas,
        puntos=puntos,
        racha=racha.actual,
        racha_ultima_fecha=racha.ultima_fecha,
        racha_hoy_jugada=racha.hoy_jugada,
        suscripcion=suscripcion,
        dias_desbloqueados=dias_desbloqueados,
        costo_pista_puntos=int(config.costo_pista_puntos or 20),
    )


async def consume_life(
    user_id: int, game_id: Optional[str] = None, motivo: Optional[str] = "error"
) -> ConsumeLifeResponse:
    """
    Resta 1 vida global de forma estrictamente atómica.
    Lanza HTTP 400 si el usuario no tiene vidas disponibles.
    """
    db = get_database()
    config = await get_economy_config()

    await db["usuarios"].update_one(
        {"id": user_id, "vidas": {"$exists": False}},
        {"$set": {"vidas": config.vidas_iniciales}},
    )

    result = await db["usuarios"].find_one_and_update(
        {"id": user_id, "vidas": {"$gt": 0}},
        {
            "$inc": {"vidas": -1},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
        return_document=ReturnDocument.AFTER,
    )

    if not result:
        user_actual = await db["usuarios"].find_one({"id": user_id})
        vidas_actuales = user_actual.get("vidas", 0) if user_actual else 0
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No tienes vidas restantes. Podés recargar vidas en la mini-tienda usando tus puntos.",
        )

    nuevas_vidas = int(result.get("vidas", 0))
    logger.info(f"[ECONOMIA] Usuario {user_id} consumió 1 vida en {game_id or 'general'}. Restan: {nuevas_vidas}")

    return ConsumeLifeResponse(
        success=True,
        vidas_restantes=nuevas_vidas,
        consumidas=1,
        message="Vida consumida exitosamente.",
    )


async def buy_lives(user_id: int, req: BuyLivesRequest) -> BuyLivesResponse:
    """
    Canjea puntos acumulados por vidas según la tasa del catálogo o paquete elegido.
    Operación atómica fail-safe: decrementa puntos e incrementa vidas en un solo paso.
    """
    config = await get_economy_config()
    db = get_database()

    vidas_a_sumar = 1
    costo_puntos = config.costo_vida_puntos

    if req.package_id:
        paquete = next((p for p in config.paquetes_tienda if p.id == req.package_id), None)
        if not paquete:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Paquete de tienda '{req.package_id}' no encontrado.",
            )
        vidas_a_sumar = paquete.vidas
        costo_puntos = paquete.puntos

    max_vidas = config.vidas_maximas
    if max_vidas is not None:
        update_query: Any = [
            {
                "$set": {
                    "puntos": {"$subtract": ["$puntos", costo_puntos]},
                    "vidas": {
                        "$min": [
                            {"$add": [{"$ifNull": ["$vidas", 0]}, vidas_a_sumar]},
                            max_vidas,
                        ]
                    },
                    "updated_at": datetime.now(timezone.utc),
                }
            }
        ]
    else:
        update_query = {
            "$inc": {"puntos": -costo_puntos, "vidas": vidas_a_sumar},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        }

    result = await db["usuarios"].find_one_and_update(
        {"id": user_id, "puntos": {"$gte": costo_puntos}},
        update_query,
        return_document=ReturnDocument.AFTER,
    )

    if not result:
        user_actual = await db["usuarios"].find_one({"id": user_id})
        puntos_actuales = user_actual.get("puntos", 0) if user_actual else 0
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Puntos insuficientes. Necesitás {costo_puntos} pts y tenés {puntos_actuales} pts.",
        )

    nuevas_vidas = int(result.get("vidas", 0))
    nuevos_puntos = int(result.get("puntos", 0))

    logger.info(
        f"[ECONOMIA] Canje exitoso para usuario {user_id}: +{vidas_a_sumar} vidas por {costo_puntos} pts. "
        f"Saldo final: {nuevas_vidas} vidas, {nuevos_puntos} pts."
    )

    return BuyLivesResponse(
        success=True,
        vidas=nuevas_vidas,
        puntos=nuevos_puntos,
        compradas=vidas_a_sumar,
        costo=costo_puntos,
        message=f"¡Canje exitoso! Sumaste {vidas_a_sumar} {'vida' if vidas_a_sumar == 1 else 'vidas'}.",
    )


async def refill_lives(user_id: int) -> RefillLivesResponse:
    """
    Recarga de vidas de partida con precio y beneficio fijados por el servidor.

    Las vidas de partida son locales: el backend cobra 50 puntos y el cliente
    reinicia su contador. Cualquier cantidad, costo o vidas enviada por el
    cliente se ignora porque el endpoint no acepta body.
    """
    db = get_database()

    await db["usuarios"].update_one(
        {"id": user_id, "puntos": {"$exists": False}},
        {"$set": {"puntos": 0}},
    )

    result = await db["usuarios"].find_one_and_update(
        {"id": user_id, "puntos": {"$gte": REFILL_LIVES_COST}},
        {
            "$inc": {"puntos": -REFILL_LIVES_COST},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
        return_document=ReturnDocument.AFTER,
    )

    if not result:
        user = await db["usuarios"].find_one({"id": user_id})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario {user_id} no encontrado.",
            )
        puntos_actuales = int(user.get("puntos", 0))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Puntos insuficientes. Necesitás {REFILL_LIVES_COST} pts "
                f"y tenés {puntos_actuales} pts."
            ),
        )

    nuevos_puntos = int(result.get("puntos", 0))
    logger.info(
        f"[ECONOMIA] Usuario {user_id} recargó vidas por {REFILL_LIVES_COST} pts. "
        f"Saldo restante: {nuevos_puntos} pts."
    )

    return RefillLivesResponse(
        success=True,
        puntos=nuevos_puntos,
        message=f"Vidas recargadas por {REFILL_LIVES_COST} puntos.",
    )
