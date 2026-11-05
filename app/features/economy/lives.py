"""Vidas: estado del usuario, consumo, compra y recarga de partida."""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, status
from pymongo import ReturnDocument

from app.core.database import get_database
from app.features.economy.config import get_economy_config
from app.features.economy.schemas import (
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
