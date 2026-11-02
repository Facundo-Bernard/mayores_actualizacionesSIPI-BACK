"""Backfill de dificultad en user_attempts (Fase 1).

Reglas:
- ``difficulty`` sale de ``game_data.difficulty`` si existe; si no, ``standard``.
- Si el documento no tiene ``by_difficulty``, se materializa su intento actual.
- Las colisiones históricas de Crucigrama (fácil y difícil bajo la misma clave)
  no son recuperables: el documento se interpreta como su dificultad declarada
  o ``standard``.

Uso local:
    .venv/Scripts/python.exe -m app.scripts.backfill_attempt_difficulty
"""

import asyncio
import logging

from app.core.database import close_mongo_connection, connect_to_mongo, get_database

logger = logging.getLogger("BackfillDifficulty")


async def backfill_attempt_difficulty() -> int:
    db = get_database()
    actualizados = 0

    cursor = db["user_attempts"].find(
        {
            "$or": [
                {"difficulty": {"$exists": False}},
                {"by_difficulty": {"$exists": False}},
            ]
        }
    )

    async for doc in cursor:
        difficulty = str(
            (doc.get("game_data") or {}).get("difficulty") or "standard"
        ).strip().lower()
        if not difficulty:
            difficulty = "standard"

        snapshot = {
            key: value
            for key, value in doc.items()
            if key not in ("_id", "created_at", "by_difficulty")
        }
        snapshot["difficulty"] = difficulty

        update = {"difficulty": difficulty}
        if not doc.get("by_difficulty"):
            update["by_difficulty"] = {difficulty: snapshot}

        await db["user_attempts"].update_one({"_id": doc["_id"]}, {"$set": update})
        actualizados += 1

    logger.info(f"[BACKFILL] user_attempts actualizados: {actualizados}")
    return actualizados


async def _main() -> None:
    await connect_to_mongo()
    try:
        await backfill_attempt_difficulty()
    finally:
        await close_mongo_connection()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main())
