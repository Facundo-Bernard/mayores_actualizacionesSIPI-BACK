"""Generación y persistencia de desafíos diarios de Sopa de Letras."""

import asyncio
import calendar
import logging
from datetime import datetime, timezone

from fastapi import HTTPException

from app.core.database import get_database
from app.features.daily_challenges.games.common import MONTH_NAMES_ES
from app.features.daily_challenges.sopa_generator import generate_sopa_challenge_for_date

logger = logging.getLogger(__name__)


async def generate_and_save_sopa_month(year: int, month: int, force: bool = False) -> dict:
    """
    Genera y guarda de forma atómica e idempotente los desafíos diarios de Sopa de Letras
    para el mes y año especificados, enriqueciendo las pistas con definiciones de la RAE.
    Si force=False, saltea instantáneamente en 0ms si el mes ya está completo.
    """
    if not (1 <= month <= 12):
        raise HTTPException(status_code=400, detail="El mes debe estar comprendido entre 1 y 12.")

    db = get_database()
    now_utc = datetime.now(timezone.utc)
    _, days_in_month = calendar.monthrange(year, month)

    start_date = f"{year:04d}-{month:02d}-01"
    end_date = f"{year:04d}-{month:02d}-{days_in_month:02d}"

    if not force:
        existing_count = await db["daily_challenges"].count_documents({
            "game_id": "sopa_letras",
            "date": {"$gte": start_date, "$lte": end_date}
        })
        if existing_count >= days_in_month:
            logger.info(f"[SOPA_LETRAS] Mes {year}-{month:02d} ya está completamente generado ({existing_count}/{days_in_month}). Saltando en 0ms.")
            return {
                "success": True,
                "game_id": "sopa_letras",
                "year": year,
                "month": month,
                "month_name": MONTH_NAMES_ES[month - 1],
                "days_in_month": days_in_month,
                "generated_count": 0,
                "already_complete": True
            }

    generated_count = 0

    for day in range(1, days_in_month + 1):
        date_str = f"{year:04d}-{month:02d}-{day:02d}"

        if not force:
            existing = await db["daily_challenges"].find_one({
                "game_id": "sopa_letras",
                "date": date_str
            })
            if existing and existing.get("config", {}).get("grid"):
                continue

        sopa_data = await asyncio.to_thread(generate_sopa_challenge_for_date, date_str)

        doc = {
            "game_id": "sopa_letras",
            "date": date_str,
            "difficulty": "standard",
            "title": f"Sopa de Letras: {sopa_data['theme']} ({date_str})",
            "config": sopa_data,
            "updated_at": now_utc
        }

        await db["daily_challenges"].update_one(
            {
                "game_id": "sopa_letras",
                "date": date_str,
                "difficulty": "standard"
            },
            {
                "$set": doc,
                "$setOnInsert": {"created_at": now_utc}
            },
            upsert=True
        )
        generated_count += 1
        await asyncio.sleep(0.15)

    logger.info(f"[SOPA_LETRAS] {generated_count} desafíos de Sopa de Letras generados para {year}-{month:02d}.")
    return {
        "success": True,
        "game_id": "sopa_letras",
        "year": year,
        "month": month,
        "month_name": MONTH_NAMES_ES[month - 1],
        "days_in_month": days_in_month,
        "generated_count": generated_count
    }
