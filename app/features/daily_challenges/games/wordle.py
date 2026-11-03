"""Generación y persistencia de desafíos diarios de Wordle."""

import asyncio
import calendar
import logging
from datetime import datetime, timezone

from fastapi import HTTPException

from app.core.database import get_database
from app.features.daily_challenges.games.common import MONTH_NAMES_ES
from app.features.daily_challenges.wordle_generator import (
    generate_wordle_challenge,
    generate_wordle_hints,
)

logger = logging.getLogger(__name__)


async def generate_and_save_wordle_month(year: int, month: int, force: bool = False) -> dict:
    """
    Genera y guarda de forma atómica e idempotente los desafíos diarios de Wordle
    para el mes y año especificados, extrayendo palabras del pool de 4.933 palabras frecuentes.
    Si force=False, saltea instantáneamente en 0ms si el mes ya está completo.
    Si force=True, refresca las pistas y definiciones de la RAE respetando las soluciones existentes.
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
            "game_id": "wordle",
            "date": {"$gte": start_date, "$lte": end_date}
        })
        if existing_count >= days_in_month:
            logger.info(f"[WORDLE] Mes {year}-{month:02d} ya está completamente generado ({existing_count}/{days_in_month}). Saltando en 0ms.")
            return {
                "success": True,
                "game_id": "wordle",
                "year": year,
                "month": month,
                "month_name": MONTH_NAMES_ES[month - 1],
                "days_in_month": days_in_month,
                "generated_count": 0,
                "already_complete": True
            }

    cursor = db["daily_challenges"].find({"game_id": "wordle"}, {"config.solution": 1})
    used_words = set()
    async for doc in cursor:
        sol = doc.get("config", {}).get("solution")
        if sol:
            used_words.add(sol.upper().strip())

    generated_count = 0

    for day in range(1, days_in_month + 1):
        date_str = f"{year:04d}-{month:02d}-{day:02d}"

        existing = await db["daily_challenges"].find_one({
            "game_id": "wordle",
            "date": date_str
        })

        if not force and existing and existing.get("config", {}).get("solution"):
            used_words.add(existing["config"]["solution"].upper().strip())
            continue

        if existing and existing.get("config", {}).get("solution"):
            sol = existing["config"]["solution"].upper().strip()
            hints = await asyncio.to_thread(generate_wordle_hints, sol)
            challenge_config = {
                "solution": sol,
                "word_length": 5,
                "max_attempts": 6,
                "hints": hints
            }
        else:
            challenge_config = await asyncio.to_thread(
                generate_wordle_challenge, date_str, used_words, index=day
            )
            used_words.add(challenge_config["solution"])

        doc = {
            "game_id": "wordle",
            "date": date_str,
            "difficulty": "standard",
            "title": f"Palabra del Día ({date_str})",
            "config": challenge_config,
            "updated_at": now_utc
        }

        await db["daily_challenges"].update_one(
            {
                "game_id": "wordle",
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
        await asyncio.sleep(0.2)

    logger.info(f"[WORDLE] {generated_count} desafíos de Wordle actualizados/generados para {year}-{month:02d}.")
    return {
        "success": True,
        "game_id": "wordle",
        "year": year,
        "month": month,
        "month_name": MONTH_NAMES_ES[month - 1],
        "days_in_month": days_in_month,
        "generated_count": generated_count
    }
