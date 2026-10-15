import calendar
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import HTTPException
from pymongo import ASCENDING

from app.core.database import get_database
from app.features.daily_challenges.schemas import (
    DailyChallengeCreateRequest,
    DailyChallengeResponse,
    MonthChallengesResponse,
    ChallengeRangeResponse
)
from app.features.daily_challenges.sudoku_generator import generate_sudoku_for_date
from app.features.daily_challenges.wordle_generator import (
    generate_wordle_challenge,
    generate_wordle_hints
)
from app.features.daily_challenges.sopa_generator import generate_sopa_challenge_for_date
from app.features.daily_challenges.crucigrama_generator import generate_crucigrama_challenge_for_date

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

    # Calcula la cantidad exacta de días del mes solicitado (ej. 31 en octubre, 28/29 en febrero)
    _, days_in_month = calendar.monthrange(year, month)

    start_date = f"{year:04d}-{month:02d}-01"
    end_date = f"{year:04d}-{month:02d}-{days_in_month:02d}"
    today_str = datetime.now().strftime("%Y-%m-%d")

    # Si se solicita solo hasta el día de hoy y el mes consultado incluye la fecha actual o futura
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

    # Se ordena de forma ascendente (del día 1 en adelante) y se limita estrictamente a days_in_month
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

MONTH_NAMES_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]

async def generate_and_save_sudoku_month(year: int, month: int, force: bool = False) -> dict:
    """
    Genera y guarda de forma atómica e idempotente los desafíos diarios de Sudoku.
    Verifica primero si el mes o día ya existen en la base de datos; si ya existen,
    los saltea instantáneamente para no bloquear ni demorar el arranque del backend.
    """
    if not (1 <= month <= 12):
        raise HTTPException(status_code=400, detail="El mes debe estar comprendido entre 1 y 12.")

    db = get_database()
    now_utc = datetime.now(timezone.utc)
    _, days_in_month = calendar.monthrange(year, month)

    start_date = f"{year:04d}-{month:02d}-01"
    end_date = f"{year:04d}-{month:02d}-{days_in_month:02d}"

    # Si no es forzado, revisar si el mes ya está 100% completo
    if not force:
        existing_count = await db["daily_challenges"].count_documents({
            "game_id": "sudoku",
            "date": {"$gte": start_date, "$lte": end_date}
        })
        if existing_count >= days_in_month:
            logger.info(f"[SUDOKU] Mes {year}-{month:02d} ya está completamente generado ({existing_count}/{days_in_month}). Saltando en 0ms.")
            return {
                "success": True,
                "game_id": "sudoku",
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

        # Revisar si el día ya existe para no recalcular
        if not force:
            existing = await db["daily_challenges"].find_one({
                "game_id": "sudoku",
                "date": date_str
            })
            if existing and existing.get("config", {}).get("solution"):
                continue

        sudoku_data = generate_sudoku_for_date(date_str)

        doc = {
            "game_id": "sudoku",
            "date": date_str,
            "difficulty": "standard",
            "title": f"Sudoku del Día ({date_str})",
            "config": sudoku_data,
            "updated_at": now_utc
        }

        await db["daily_challenges"].update_one(
            {
                "game_id": "sudoku",
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

    logger.info(f"[SUDOKU] {generated_count} nuevos desafíos de Sudoku generados para {year}-{month:02d}.")
    return {
        "success": True,
        "game_id": "sudoku",
        "year": year,
        "month": month,
        "month_name": MONTH_NAMES_ES[month - 1],
        "days_in_month": days_in_month,
        "generated_count": generated_count
    }

async def get_challenges_monthly_status(year: int, game_id: str = "sudoku") -> dict:
    """
    Calcula el estado de cobertura de desafíos para cada uno de los 12 meses de un año.
    Permite a la Torre de Control auditar y generar meses faltantes.
    """
    db = get_database()
    months_status = []

    for m in range(1, 13):
        _, days_in_month = calendar.monthrange(year, m)
        start_date = f"{year:04d}-{m:02d}-01"
        end_date = f"{year:04d}-{m:02d}-{days_in_month:02d}"

        count = await db["daily_challenges"].count_documents({
            "game_id": game_id,
            "date": {"$gte": start_date, "$lte": end_date}
        })

        if count >= days_in_month:
            status = "completed"
        elif count > 0:
            status = "partial"
        else:
            status = "pending"

        months_status.append({
            "month": m,
            "name": MONTH_NAMES_ES[m - 1],
            "days_in_month": days_in_month,
            "generated_count": count,
            "status": status,
            "is_complete": count >= days_in_month
        })

    return {
        "game_id": game_id,
        "year": year,
        "months": months_status
    }

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

    # Si no es forzado, revisar si el mes ya está 100% completo
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

    # 1. Recuperar todas las palabras ya usadas en Wordle para no repetir
    cursor = db["daily_challenges"].find({"game_id": "wordle"}, {"config.solution": 1})
    used_words = set()
    async for doc in cursor:
        sol = doc.get("config", {}).get("solution")
        if sol:
            used_words.add(sol.upper().strip())

    generated_count = 0

    # 2. Iterar por cada día del mes
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
            # Respetar la solución original asignada pero refrescar pistas y definición RAE
            sol = existing["config"]["solution"].upper().strip()
            hints = generate_wordle_hints(sol)
            challenge_config = {
                "solution": sol,
                "word_length": 5,
                "max_attempts": 6,
                "hints": hints
            }
        else:
            challenge_config = generate_wordle_challenge(date_str, used_words, index=day)
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

        sopa_data = generate_sopa_challenge_for_date(date_str)

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

async def generate_and_save_crucigrama_month(year: int, month: int, force: bool = False) -> dict:
    """
    Genera y guarda de forma atómica e idempotente los desafíos diarios de Crucigrama (7x7)
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
            "game_id": "crucigrama",
            "date": {"$gte": start_date, "$lte": end_date}
        })
        if existing_count >= days_in_month:
            logger.info(f"[CRUCIGRAMA] Mes {year}-{month:02d} ya está completamente generado ({existing_count}/{days_in_month}). Saltando en 0ms.")
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

    for day in range(1, days_in_month + 1):
        date_str = f"{year:04d}-{month:02d}-{day:02d}"

        if not force:
            existing = await db["daily_challenges"].find_one({
                "game_id": "crucigrama",
                "date": date_str
            })
            if existing and existing.get("config", {}).get("cells"):
                continue

        crucigrama_data = generate_crucigrama_challenge_for_date(date_str)

        doc = {
            "game_id": "crucigrama",
            "date": date_str,
            "difficulty": "standard",
            "title": f"Crucigrama: {crucigrama_data['theme']} ({date_str})",
            "config": crucigrama_data,
            "updated_at": now_utc
        }

        await db["daily_challenges"].update_one(
            {
                "game_id": "crucigrama",
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

async def ensure_current_and_next_month_generated(game_id: Optional[str] = None):
    """
    Verifica que el mes actual y el mes siguiente estén completamente generados
    para Sudoku, Wordle, Sopa de Letras y Crucigrama. Si falta algún día en el mes actual o en el siguiente,
    dispara automáticamente la generación correspondiente sin bloquear el arranque.
    """
    games = [game_id] if game_id else ["sudoku", "wordle", "sopa_letras", "crucigrama"]

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

            count = await db["daily_challenges"].count_documents({
                "game_id": g,
                "date": {"$gte": start_date, "$lte": end_date}
            })

            if count < days_in_month:
                logger.info(f"[AUTOGENERACIÓN] Juego '{g}' mes {y}-{m:02d} tiene {count}/{days_in_month} días. Generando...")
                if g == "sudoku":
                    await generate_and_save_sudoku_month(y, m)
                elif g == "wordle":
                    await generate_and_save_wordle_month(y, m)
                elif g == "sopa_letras":
                    await generate_and_save_sopa_month(y, m)
                elif g == "crucigrama":
                    await generate_and_save_crucigrama_month(y, m)



