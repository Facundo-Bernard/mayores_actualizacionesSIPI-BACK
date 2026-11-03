"""Generación y persistencia de desafíos diarios de Crucigrama (fácil y difícil)."""

import asyncio
import calendar
import logging
from datetime import datetime, timezone

from fastapi import HTTPException

from app.core.database import get_database
from app.features.daily_challenges.crucigrama import generate_crucigrama_challenge_for_date
from app.features.daily_challenges.crucigrama.bans import get_global_banned_words
from app.features.daily_challenges.crucigrama.published_templates import (
    get_recurring_published_config,
    get_scheduled_published_config,
)
from app.features.daily_challenges.games.common import (
    CRUCIGRAMA_DIFFICULTIES,
    MONTH_NAMES_ES,
)

logger = logging.getLogger(__name__)


async def generate_and_save_crucigrama_month(year: int, month: int, force: bool = False) -> dict:
    """
    Genera y guarda de forma atómica e idempotente los desafíos diarios de Crucigrama
    en sus dos dificultades (facil 7x7 y dificil 11x11) para el mes y año especificados.
    Si force=False, saltea instantáneamente en 0ms si el mes ya está completo para ambas.
    """
    if not (1 <= month <= 12):
        raise HTTPException(status_code=400, detail="El mes debe estar comprendido entre 1 y 12.")

    db = get_database()
    now_utc = datetime.now(timezone.utc)
    _, days_in_month = calendar.monthrange(year, month)

    start_date = f"{year:04d}-{month:02d}-01"
    end_date = f"{year:04d}-{month:02d}-{days_in_month:02d}"

    if not force:
        complete = True
        for diff in CRUCIGRAMA_DIFFICULTIES:
            existing_count = await db["daily_challenges"].count_documents({
                "game_id": "crucigrama",
                "difficulty": diff,
                "date": {"$gte": start_date, "$lte": end_date}
            })
            if existing_count < days_in_month:
                complete = False
                break
        if complete:
            logger.info(f"[CRUCIGRAMA] Mes {year}-{month:02d} ya está completamente generado en {len(CRUCIGRAMA_DIFFICULTIES)} dificultades. Saltando en 0ms.")
            return {
                "success": True,
                "game_id": "crucigrama",
                "year": year,
                "month": month,
                "month_name": MONTH_NAMES_ES[month - 1],
                "days_in_month": days_in_month,
                "generated_count": 0,
                "already_complete": True
            }

    generated_count = 0
    global_bans = await get_global_banned_words()

    for day in range(1, days_in_month + 1):
        date_str = f"{year:04d}-{month:02d}-{day:02d}"

        for diff in CRUCIGRAMA_DIFFICULTIES:
            if not force:
                existing = await db["daily_challenges"].find_one({
                    "game_id": "crucigrama",
                    "date": date_str,
                    "difficulty": diff
                })
                if existing and existing.get("config", {}).get("cells"):
                    continue

            crucigrama_data = await get_scheduled_published_config(date_str, diff)
            if not crucigrama_data:
                crucigrama_data = await get_recurring_published_config(
                    date_str, diff, global_bans
                )
            if crucigrama_data:
                crucigrama_data = dict(crucigrama_data)
                crucigrama_data["date"] = date_str
            else:
                crucigrama_data = await asyncio.to_thread(
                    generate_crucigrama_challenge_for_date,
                    date_str,
                    diff,
                    banned_words=global_bans,
                )

            doc = {
                "game_id": "crucigrama",
                "date": date_str,
                "difficulty": diff,
                "title": f"Crucigrama ({diff.capitalize()}): {crucigrama_data['theme']} ({date_str})",
                "config": crucigrama_data,
                "updated_at": now_utc
            }

            await db["daily_challenges"].update_one(
                {
                    "game_id": "crucigrama",
                    "date": date_str,
                    "difficulty": diff
                },
                {
                    "$set": doc,
                    "$setOnInsert": {"created_at": now_utc}
                },
                upsert=True
            )
            generated_count += 1

        await asyncio.sleep(0.1)

    logger.info(f"[CRUCIGRAMA] {generated_count} desafíos de Crucigrama generados para {year}-{month:02d}.")
    return {
        "success": True,
        "game_id": "crucigrama",
        "year": year,
        "month": month,
        "month_name": MONTH_NAMES_ES[month - 1],
        "days_in_month": days_in_month,
        "generated_count": generated_count
    }
