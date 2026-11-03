"""Fachada de desafíos diarios: lectura, upsert y orquestación de generación.

La generación por juego vive en ``app.features.daily_challenges.games``.
Se reexportan los generadores para conservar los imports existentes (router,
``main`` y seeds).
"""

import calendar
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from pymongo import ASCENDING

from app.core.database import get_database
from app.features.daily_challenges.games.common import (  # noqa: F401
    CRUCIGRAMA_DIFFICULTIES,
    MONTH_NAMES_ES,
    assert_month_regenerable,
)
from app.features.daily_challenges.games.coverage import get_challenges_monthly_status  # noqa: F401
from app.features.daily_challenges.games.crucigrama import generate_and_save_crucigrama_month  # noqa: F401
from app.features.daily_challenges.games.sopa import generate_and_save_sopa_month  # noqa: F401
from app.features.daily_challenges.games.sudoku import generate_and_save_sudoku_month  # noqa: F401
from app.features.daily_challenges.games.wordle import generate_and_save_wordle_month  # noqa: F401
from app.features.daily_challenges.schemas import (
    ChallengeRangeResponse,
    DailyChallengeCreateRequest,
    DailyChallengeResponse,
    MonthChallengesResponse,
)

logger = logging.getLogger(__name__)


def _serialize_challenge(doc: dict, today_str: Optional[str] = None) -> DailyChallengeResponse:
    if today_str is None:
        today_str = datetime.now().strftime("%Y-%m-%d")

    doc_date = doc.get("date", "")
    created_at = doc.get("created_at")
    if isinstance(created_at, datetime):
        created_at_str = created_at.isoformat()
    else:
        created_at_str = str(created_at) if created_at else None

    return DailyChallengeResponse(
        id=str(doc.get("_id", "")),
        game_id=doc.get("game_id", ""),
        date=doc_date,
        difficulty=doc.get("difficulty", "standard"),
        title=doc.get("title"),
        config=doc.get("config", {}),
        is_today=(doc_date == today_str),
        is_past=(doc_date < today_str),
        is_future=(doc_date > today_str),
        created_at=created_at_str
    )


async def get_challenge_by_date(
    game_id: str = "wordle",
    target_date: Optional[str] = None,
    difficulty: str = "standard"
) -> DailyChallengeResponse:
    """Busca el desafío de una fecha específica para un juego determinado."""
    db = get_database()
    today_str = datetime.now().strftime("%Y-%m-%d")
    date_to_query = target_date or today_str

    challenge = await db["daily_challenges"].find_one({
        "game_id": game_id,
        "date": date_to_query,
        "difficulty": difficulty
    })

    if not challenge:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontró desafío para el juego '{game_id}' en la fecha {date_to_query}"
        )

    return _serialize_challenge(challenge, today_str)


async def get_today_challenge(
    game_id: str = "wordle",
    difficulty: str = "standard"
) -> DailyChallengeResponse:
    """Obtiene el desafío de hoy para el juego especificado."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    return await get_challenge_by_date(game_id=game_id, target_date=today_str, difficulty=difficulty)


async def get_month_challenges(
    year: int,
    month: int,
    game_id: str = "wordle",
    difficulty: str = "standard",
    until_today: bool = False
) -> MonthChallengesResponse:
    """
    Obtiene los desafíos de un mes específico.
    Parametriza y valida que no puedan solicitarse ni devolverse más días de los que tiene el mes.
    """
    if not (1 <= month <= 12):
        raise HTTPException(status_code=400, detail="El mes debe estar comprendido entre 1 y 12.")

    if not (2020 <= year <= 2050):
        raise HTTPException(status_code=400, detail="Año fuera del rango admitido (2020-2050).")

    _, days_in_month = calendar.monthrange(year, month)

    start_date = f"{year:04d}-{month:02d}-01"
    end_date = f"{year:04d}-{month:02d}-{days_in_month:02d}"
    today_str = datetime.now().strftime("%Y-%m-%d")

    if until_today and today_str < end_date:
        effective_end_date = today_str
    else:
        effective_end_date = end_date

    db = get_database()
    query = {
        "game_id": game_id,
        "difficulty": difficulty,
        "date": {
            "$gte": start_date,
            "$lte": effective_end_date
        }
    }

    cursor = db["daily_challenges"].find(query).sort("date", ASCENDING).limit(days_in_month)
    results = await cursor.to_list(length=days_in_month)

    challenges = [_serialize_challenge(doc, today_str) for doc in results]

    return MonthChallengesResponse(
        year=year,
        month=month,
        days_in_month=days_in_month,
        total_challenges=len(challenges),
        challenges=challenges
    )


async def upsert_challenge(req: DailyChallengeCreateRequest) -> DailyChallengeResponse:
    """Crea o actualiza un desafío diario de forma idempotente."""
    db = get_database()
    now_utc = datetime.now(timezone.utc)
    today_str = datetime.now().strftime("%Y-%m-%d")

    doc = {
        "game_id": req.game_id.lower().strip(),
        "date": req.date.strip(),
        "difficulty": req.difficulty.lower().strip(),
        "title": req.title,
        "config": req.config,
        "updated_at": now_utc
    }

    result = await db["daily_challenges"].find_one_and_update(
        {
            "game_id": doc["game_id"],
            "date": doc["date"],
            "difficulty": doc["difficulty"]
        },
        {
            "$set": doc,
            "$setOnInsert": {"created_at": now_utc}
        },
        upsert=True,
        return_document=True
    )

    return _serialize_challenge(result, today_str)


async def get_challenge_date_range(game_id: str = "wordle") -> ChallengeRangeResponse:
    """Busca la fecha mínima y máxima con desafíos disponibles para un juego."""
    db = get_database()
    first_doc = await db["daily_challenges"].find_one(
        {"game_id": game_id},
        sort=[("date", ASCENDING)]
    )
    last_doc = await db["daily_challenges"].find_one(
        {"game_id": game_id},
        sort=[("date", -1)]
    )
    return ChallengeRangeResponse(
        game_id=game_id,
        min_date=first_doc.get("date") if first_doc else None,
        max_date=last_doc.get("date") if last_doc else None
    )


async def ensure_current_and_next_month_generated(game_id: Optional[str] = None):
    """
    Verifica que el mes actual y el mes siguiente estén completamente generados
    para Sudoku, Wordle, Sopa de Letras y Crucigrama. Si falta algún día en el mes actual o en el siguiente,
    dispara automáticamente la generación correspondiente sin bloquear el arranque.
    """
    games = [game_id] if game_id else ["sudoku", "wordle", "sopa_letras", "crucigrama", "narrativo"]

    now = datetime.now()
    cur_year = now.year
    cur_month = now.month

    next_month = cur_month + 1
    next_year = cur_year
    if next_month > 12:
        next_month = 1
        next_year += 1

    targets = [(cur_year, cur_month), (next_year, next_month)]
    db = get_database()

    for g in games:
        for y, m in targets:
            _, days_in_month = calendar.monthrange(y, m)
            start_date = f"{y:04d}-{m:02d}-01"
            end_date = f"{y:04d}-{m:02d}-{days_in_month:02d}"

            if g == "crucigrama":
                incomplete = False
                for diff in CRUCIGRAMA_DIFFICULTIES:
                    count = await db["daily_challenges"].count_documents({
                        "game_id": g,
                        "difficulty": diff,
                        "date": {"$gte": start_date, "$lte": end_date}
                    })
                    if count < days_in_month:
                        incomplete = True
                        break
            else:
                count = await db["daily_challenges"].count_documents({
                    "game_id": g,
                    "date": {"$gte": start_date, "$lte": end_date}
                })
                incomplete = count < days_in_month

            if incomplete:
                logger.info(f"[AUTOGENERACIÓN] Juego '{g}' mes {y}-{m:02d} incompleto. Generando...")
                if g == "sudoku":
                    await generate_and_save_sudoku_month(y, m)
                elif g == "wordle":
                    await generate_and_save_wordle_month(y, m)
                elif g == "sopa_letras":
                    await generate_and_save_sopa_month(y, m)
                elif g == "crucigrama":
                    await generate_and_save_crucigrama_month(y, m)
                elif g == "narrativo":
                    try:
                        from app.features.narrative.admin.challenge_service import generar_mes_narrativo
                        await generar_mes_narrativo(year=y, month=m, universo_id="corte_medieval")
                    except Exception as e_narr:
                        logger.warning(f"Error autogenerando mes narrativo {y}-{m:02d}: {e_narr}")
