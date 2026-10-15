import calendar
import logging
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import HTTPException
from pymongo import ASCENDING

from app.core.database import get_database
from app.features.user_attempts.schemas import (
    UserAttemptCreateRequest,
    UserAttemptResponse,
    UserAttemptsListResponse
)

logger = logging.getLogger(__name__)

def _serialize_attempt(doc: dict) -> UserAttemptResponse:
    updated_at = doc.get("updated_at")
    if isinstance(updated_at, datetime):
        updated_at_str = updated_at.isoformat()
    else:
        updated_at_str = str(updated_at) if updated_at else None

    return UserAttemptResponse(
        id=str(doc.get("_id", "")),
        user_id=doc.get("user_id"),
        game_id=doc.get("game_id", "wordle"),
        date=doc.get("date", ""),
        mode=doc.get("mode", "daily"),
        status=doc.get("status", "completed"),
        word=doc.get("word"),
        attempts=int(doc.get("attempts", 1)),
        stars=int(doc.get("stars", 1)),
        score=int(doc.get("score", 100)),
        guesses=doc.get("guesses", []),
        game_data=doc.get("game_data"),
        updated_at=updated_at_str
    )

async def save_user_attempt(
    req: UserAttemptCreateRequest,
    authenticated_user_id: Optional[int] = None
) -> UserAttemptResponse:
    """Guarda o actualiza un intento de partida de forma atómica e idempotente."""
    db = get_database()
    effective_user_id = authenticated_user_id or req.user_id or 1
    now_utc = datetime.now(timezone.utc)

    filter_query = {
        "user_id": effective_user_id,
        "game_id": req.game_id.lower().strip(),
        "date": req.date.strip()
    }

    doc = {
        "user_id": effective_user_id,
        "game_id": req.game_id.lower().strip(),
        "date": req.date.strip(),
        "mode": req.mode.lower().strip(),
        "status": req.status.lower().strip(),
        "word": req.word.strip() if req.word else None,
        "attempts": req.attempts,
        "stars": req.stars,
        "score": req.score,
        "guesses": req.guesses or [],
        "game_data": req.game_data,
        "remaining_attempts": req.remaining_attempts or 0,
        "updated_at": now_utc
    }

    existing = await db["user_attempts"].find_one(filter_query)
    was_already_completed = existing and existing.get("status") == "completed"

    result = await db["user_attempts"].find_one_and_update(
        filter_query,
        {
            "$set": doc,
            "$setOnInsert": {"created_at": now_utc}
        },
        upsert=True,
        return_document=True
    )

    # Si es una victoria nueva y válida, sumar puntos al usuario
    if req.status.lower().strip() == "completed" and not was_already_completed and req.score > 0:
        try:
            await db["usuarios"].update_one(
                {"id": effective_user_id},
                {
                    "$inc": {"puntos": req.score},
                    "$set": {"updated_at": now_utc}
                }
            )
        except Exception as e:
            logger.warning(f"No se pudieron actualizar los puntos del usuario {effective_user_id}: {e}")

    return _serialize_attempt(result)

async def get_user_attempt_by_date(
    user_id: int,
    game_id: str = "wordle",
    date: str = "2026-10-09"
) -> Optional[UserAttemptResponse]:
    """Retorna el progreso o intento de un usuario para una fecha determinada si existe."""
    db = get_database()
    doc = await db["user_attempts"].find_one({
        "user_id": user_id,
        "game_id": game_id.lower().strip(),
        "date": date.strip()
    })
    if not doc:
        return None
    return _serialize_attempt(doc)

async def get_user_attempts_by_month(
    user_id: int,
    game_id: str = "wordle",
    year: int = 2026,
    month: int = 10
) -> UserAttemptsListResponse:
    """Retorna los intentos registrados de un usuario en un mes determinado."""
    if not (1 <= month <= 12):
        raise HTTPException(status_code=400, detail="Mes inválido (1-12).")

    _, days_in_month = calendar.monthrange(year, month)
    start_date = f"{year:04d}-{month:02d}-01"
    end_date = f"{year:04d}-{month:02d}-{days_in_month:02d}"

    db = get_database()
    query = {
        "user_id": user_id,
        "game_id": game_id.lower().strip(),
        "date": {"$gte": start_date, "$lte": end_date}
    }

    cursor = db["user_attempts"].find(query).sort("date", ASCENDING)
    results = await cursor.to_list(length=days_in_month)

    items = [_serialize_attempt(doc) for doc in results]

    return UserAttemptsListResponse(
        user_id=user_id,
        game_id=game_id,
        year=year,
        month=month,
        total=len(items),
        attempts=items
    )
