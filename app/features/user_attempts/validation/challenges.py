"""Búsqueda de la configuración oficial del desafío diario."""

from typing import Any, Dict, Optional

from app.core.database import get_database


async def load_challenge_config(
    game_id: str,
    date: str,
    difficulty: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Devuelve la config del desafío para (juego, fecha, dificultad).

    Crucigrama publica dos desafíos por fecha, así que exige coincidencia exacta
    de dificultad. El resto de juegos acepta el fallback histórico sin dificultad.
    """
    db = get_database()
    base = {"game_id": game_id, "date": date}
    difficulty = (difficulty or "").strip().lower()

    if difficulty:
        doc = await db["daily_challenges"].find_one({**base, "difficulty": difficulty})
        if doc:
            return doc.get("config") or {}

    if game_id == "crucigrama":
        return None

    doc = await db["daily_challenges"].find_one({**base, "difficulty": "standard"})
    if doc:
        return doc.get("config") or {}

    doc = await db["daily_challenges"].find_one(base)
    return (doc.get("config") or {}) if doc else None
