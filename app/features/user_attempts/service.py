import calendar
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from fastapi import HTTPException
from pymongo import ASCENDING

from app.core.database import get_database
from app.features.user_attempts.schemas import (
    UserAttemptCreateRequest,
    UserAttemptResponse,
    UserAttemptsListResponse
)

logger = logging.getLogger(__name__)

def calculate_grade_and_score(
    game_id: str,
    status: str,
    attempts: int,
    remaining_attempts: int,
    provided_grade: Optional[str] = None,
    provided_score: Optional[int] = None,
    provided_stars: Optional[int] = None,
    puntos_por_calificacion: Optional[Dict[str, int]] = None,
    game_data: Optional[dict] = None,
    time_taken_seconds: Optional[int] = None,
    escalas_tiempo: Optional[List[Any]] = None
) -> Tuple[str, int, int]:
    """
    Calcula (grade, score, stars) en base al desempeño o configuración.
    Prioriza la calificación (S, A, B, C, F) enviada por el cliente si existe.
    """
    status_clean = (status or "").lower().strip()
    config_pts = puntos_por_calificacion or {
        "S": 100,
        "A": 90,
        "B": 75,
        "C": 50,
        "F": 0,
    }

    # Si la partida falló o se agotaron los intentos/vidas
    if status_clean in ("failed", "lost"):
        return ("F", 0, 0)

    # Si es solo un guardado intermedio
    if status_clean not in ("completed", "won"):
        return (provided_grade or "C", 0, 0)

    # 1. Calificación por Tiempo (para juegos cronometrados: sudoku, crucigrama, sopa_letras)
    gid = (game_id or "").lower().strip()
    if gid in ("sudoku", "crucigrama", "sopa_letras") and time_taken_seconds is not None and time_taken_seconds >= 0 and escalas_tiempo:
        escalas_ordenadas = sorted(
            escalas_tiempo,
            key=lambda item: getattr(item, "tiempo_max_segundos", item.get("tiempo_max_segundos", 999999) if isinstance(item, dict) else 999999)
        )
        matched_tier = None
        for tier in escalas_ordenadas:
            t_max = getattr(tier, "tiempo_max_segundos", tier.get("tiempo_max_segundos") if isinstance(tier, dict) else 999999)
            if time_taken_seconds <= t_max:
                matched_tier = tier
                break
        if not matched_tier and escalas_ordenadas:
            matched_tier = escalas_ordenadas[-1]

        if matched_tier:
            grade = getattr(matched_tier, "grade", matched_tier.get("grade") if isinstance(tier, dict) else "C")
            score = getattr(matched_tier, "puntos", matched_tier.get("puntos", 50) if isinstance(tier, dict) else 50)
            stars = getattr(matched_tier, "estrellas", matched_tier.get("estrellas", 1) if isinstance(tier, dict) else 1)
            return (grade, score, stars)

    # 2. Si el frontend envía una calificación por letra explícita
    if provided_grade and provided_grade.upper().strip() in config_pts:
        grade = provided_grade.upper().strip()
        # Los puntos se rigen por la configuración del Administrador para esa calificación
        score = config_pts.get(grade, provided_score if (provided_score is not None and provided_score > 0) else 50)
        if provided_stars is not None and provided_stars > 0:
            stars = min(3, max(1, provided_stars))
        else:
            stars = 3 if grade in ("S", "A") else (2 if grade == "B" else 1)
        return (grade, score, stars)

    # 2. Si no vino calificación explícita, evaluar por juego y vidas/errores
    gid = (game_id or "").lower().strip()
    data = game_data or {}
    errors = int(data.get("errors") or data.get("mistakes") or data.get("fallos") or 0)

    if gid == "wordle":
        # Wordle tiene 6 intentos máximos
        if attempts <= 2:
            grade = "S"
            stars = 3
        elif attempts <= 4:
            grade = "B"
            stars = 2
        else:
            grade = "C"
            stars = 1

    elif gid == "sudoku":
        # Sudoku: errores cometidos o vidas restantes (base 3)
        if errors == 0 and (remaining_attempts >= 3 or remaining_attempts == 0):
            grade = "S"
            stars = 3
        elif errors <= 1 or remaining_attempts == 2:
            grade = "B"
            stars = 2
        else:
            grade = "C"
            stars = 1

    elif gid == "crucigrama":
        # Crucigrama: errores al verificar
        if errors == 0:
            grade = "S"
            stars = 3
        elif errors <= 2:
            grade = "B"
            stars = 2
        else:
            grade = "C"
            stars = 1

    elif gid == "sopa_letras":
        # Sopa de letras: errores de selección
        if errors == 0:
            grade = "S"
            stars = 3
        elif errors <= 2:
            grade = "B"
            stars = 2
        else:
            grade = "C"
            stars = 1

    else:
        # Genérico
        if remaining_attempts >= 3 or attempts <= 2:
            grade = "S"
            stars = 3
        elif remaining_attempts >= 1 or attempts <= 4:
            grade = "B"
            stars = 2
        else:
            grade = "C"
            stars = 1

    score = config_pts.get(grade, provided_score if (provided_score is not None and provided_score > 0) else 50)
    if provided_stars is not None and provided_stars > 0:
        stars = min(3, max(1, provided_stars))

    return (grade, score, stars)


def _serialize_attempt(
    doc: dict,
    puntos_ganados: int = 0,
    puntos_totales_usuario: Optional[int] = None
) -> UserAttemptResponse:
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
        grade=doc.get("grade"),
        remaining_attempts=int(doc.get("remaining_attempts", 0)),
        time_taken_seconds=doc.get("time_taken_seconds"),
        puntos_ganados=puntos_ganados,
        puntos_totales_usuario=puntos_totales_usuario,
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

    # Obtener configuración de economía para puntos por calificación
    from app.features.economy.service import get_economy_config
    try:
        econ_config = await get_economy_config()
        puntos_config = econ_config.puntos_por_calificacion
    except Exception as e:
        logger.warning(f"No se pudo cargar la configuración de economía: {e}")
        puntos_config = {"S": 100, "A": 90, "B": 75, "C": 50, "F": 0}

    # Extraer tiempo transcurrido si viene informado
    time_taken = req.time_taken_seconds
    if time_taken is None and req.game_data:
        time_taken = (
            req.game_data.get("timeTaken")
            or req.game_data.get("time_taken_seconds")
            or req.game_data.get("elapsedSeconds")
            or req.game_data.get("elapsed_seconds")
        )
    if time_taken is not None:
        try:
            time_taken = int(time_taken)
        except Exception:
            time_taken = None

    escalas_juego = None
    if hasattr(econ_config, "escalas_tiempo_por_juego") and econ_config.escalas_tiempo_por_juego:
        escalas_juego = econ_config.escalas_tiempo_por_juego.get(req.game_id.lower().strip())

    # Calcular calificación, puntaje y estrellas según desempeño o datos provistos
    grade, score, stars = calculate_grade_and_score(
        game_id=req.game_id,
        status=req.status,
        attempts=req.attempts,
        remaining_attempts=req.remaining_attempts or 0,
        provided_grade=req.grade,
        provided_score=req.score,
        provided_stars=req.stars,
        puntos_por_calificacion=puntos_config,
        game_data=req.game_data,
        time_taken_seconds=time_taken,
        escalas_tiempo=escalas_juego
    )

    status_normalized = req.status.lower().strip()
    if status_normalized in ("completed", "won"):
        final_status = "completed"
    elif status_normalized in ("failed", "lost"):
        final_status = "failed"
    else:
        final_status = "in_progress"

    doc = {
        "user_id": effective_user_id,
        "game_id": req.game_id.lower().strip(),
        "date": req.date.strip(),
        "mode": req.mode.lower().strip(),
        "status": final_status,
        "word": req.word.strip() if req.word else None,
        "attempts": req.attempts,
        "stars": stars,
        "score": score,
        "grade": grade,
        "guesses": req.guesses or [],
        "game_data": req.game_data,
        "remaining_attempts": req.remaining_attempts or 0,
        "time_taken_seconds": time_taken,
        "updated_at": now_utc
    }

    existing = await db["user_attempts"].find_one(filter_query)
    was_already_completed = existing and existing.get("status") in ("completed", "won")
    is_new_victory = final_status == "completed" and not was_already_completed

    result = await db["user_attempts"].find_one_and_update(
        filter_query,
        {
            "$set": doc,
            "$setOnInsert": {"created_at": now_utc}
        },
        upsert=True,
        return_document=True
    )

    puntos_ganados = 0
    puntos_totales_usuario = None

    # Si es una victoria nueva y válida, sumar puntos al usuario
    if is_new_victory:
        puntos_ganados = score
        try:
            if puntos_ganados > 0:
                user_updated = await db["usuarios"].find_one_and_update(
                    {"id": effective_user_id},
                    {
                        "$inc": {"puntos": puntos_ganados},
                        "$set": {"updated_at": now_utc}
                    },
                    return_document=True
                )
                if user_updated:
                    puntos_totales_usuario = int(user_updated.get("puntos", 0))
                logger.info(f"[PUNTOS] Usuario {effective_user_id} ganó {puntos_ganados} pts (calificación {grade}) en {req.game_id}. Saldo actual: {puntos_totales_usuario}")
        except Exception as e:
            logger.warning(f"No se pudieron actualizar los puntos del usuario {effective_user_id}: {e}")

    # Si no hubo acreditación nueva (ej: partida ya completada o in_progress), consultar saldo
    if puntos_totales_usuario is None:
        try:
            user_doc = await db["usuarios"].find_one({"id": effective_user_id})
            if user_doc:
                puntos_totales_usuario = int(user_doc.get("puntos", 0))
        except Exception:
            pass

    return _serialize_attempt(
        result,
        puntos_ganados=puntos_ganados,
        puntos_totales_usuario=puntos_totales_usuario
    )

async def get_user_attempt_by_date(
    user_id: int,
    game_id: str,
    date: Optional[str] = None,
    date_str: Optional[str] = None
) -> Optional[UserAttemptResponse]:
    """Obtiene el intento de un usuario para un juego y fecha específicos."""
    target_date = (date or date_str or "").strip()
    db = get_database()
    doc = await db["user_attempts"].find_one({
        "user_id": user_id,
        "game_id": game_id.lower().strip(),
        "date": target_date
    })
    return _serialize_attempt(doc) if doc else None

async def get_user_attempts_by_month(
    user_id: int,
    game_id: str,
    year: int,
    month: int
) -> UserAttemptsListResponse:
    """Obtiene todos los intentos de un usuario para un mes calendario."""
    db = get_database()
    days_in_month = calendar.monthrange(year, month)[1]
    start_date = f"{year:04d}-{month:02d}-01"
    end_date = f"{year:04d}-{month:02d}-{days_in_month:02d}"

    cursor = db["user_attempts"].find({
        "user_id": user_id,
        "game_id": game_id.lower().strip(),
        "date": {"$gte": start_date, "$lte": end_date}
    }).sort("date", ASCENDING)

    docs = await cursor.to_list(length=31)
    items = [_serialize_attempt(d) for d in docs]
    return UserAttemptsListResponse(
        user_id=user_id,
        game_id=game_id,
        year=year,
        month=month,
        total=len(items),
        attempts=items
    )
