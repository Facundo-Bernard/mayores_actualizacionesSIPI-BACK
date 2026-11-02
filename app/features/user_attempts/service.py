import calendar
import logging
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from fastapi import HTTPException
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError

from app.core.database import get_database
from app.features.user_attempts.schemas import (
    UserAttemptCreateRequest,
    UserAttemptResponse,
    UserAttemptsListResponse
)
from app.features.user_attempts.validation import (
    Submission,
    is_enforcement_enabled,
    validate_submission,
)
from app.shared.ledger import LedgerKey, get_points_ledger

logger = logging.getLogger(__name__)

_DIFFICULTY_PATTERN = re.compile(r"^[a-z0-9_-]{1,32}$")
_COMPLETED_STATUSES = ("completed", "won")
_TIME_SUSPECT_MIN_SERVER_SECONDS = 30
_TIME_SUSPECT_MIN_DIFF_SECONDS = 10


def _tier_value(tier: Any, name: str, default: Any) -> Any:
    if isinstance(tier, dict):
        return tier.get(name, default)
    return getattr(tier, name, default)


def _parse_errors(game_data: Optional[Dict[str, Any]]) -> int:
    data = game_data or {}
    raw = data.get("errors", data.get("mistakes", data.get("fallos", 0)))
    if raw is None or raw == "":
        return 0
    if isinstance(raw, bool):
        raise HTTPException(
            status_code=400,
            detail="'game_data.errors' debe ser un número entero.",
        )
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="'game_data.errors' debe ser un número entero.",
        )
    if value < 0:
        raise HTTPException(
            status_code=400,
            detail="'game_data.errors' no puede ser negativo.",
        )
    return value


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
            key=lambda item: _tier_value(item, "tiempo_max_segundos", 999999)
        )
        matched_tier = None
        for tier in escalas_ordenadas:
            if time_taken_seconds <= _tier_value(tier, "tiempo_max_segundos", 999999):
                matched_tier = tier
                break
        if not matched_tier and escalas_ordenadas:
            matched_tier = escalas_ordenadas[-1]

        if matched_tier:
            grade = _tier_value(matched_tier, "grade", "C")
            score = _tier_value(matched_tier, "puntos", 50)
            stars = _tier_value(matched_tier, "estrellas", 1)
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

    # 3. Si no vino calificación explícita, evaluar por juego y vidas/errores
    errors = _parse_errors(game_data)

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
        # Sudoku: los errores mandan; 0 vidas restantes nunca es S
        if errors == 0 and remaining_attempts >= 3:
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


def _normalize_difficulty(req: UserAttemptCreateRequest) -> str:
    raw = req.difficulty or (req.game_data or {}).get("difficulty") or "standard"
    difficulty = str(raw).strip().lower()
    if not _DIFFICULTY_PATTERN.match(difficulty):
        raise HTTPException(
            status_code=400,
            detail="La dificultad informada no es válida.",
        )
    return difficulty


def _doc_difficulty(doc: dict) -> str:
    return str(doc.get("difficulty") or "standard").strip().lower()


def _is_completed_attempt(doc: Optional[dict]) -> bool:
    if not doc:
        return False
    return (
        doc.get("status") in _COMPLETED_STATUSES
        and doc.get("validation_status") != "rejected"
    )


def _difficulty_is_completed(doc: Optional[dict], difficulty: str) -> bool:
    if not doc:
        return False
    by_difficulty = doc.get("by_difficulty") or {}
    sub = by_difficulty.get(difficulty)
    if sub:
        return _is_completed_attempt(sub)
    # Documentos históricos sin by_difficulty: se interpretan como su dificultad declarada.
    if _doc_difficulty(doc) == difficulty:
        return _is_completed_attempt(doc)
    return False


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _attempt_started_at(doc: Optional[dict], difficulty: str) -> Optional[datetime]:
    if not doc:
        return None
    sub = (doc.get("by_difficulty") or {}).get(difficulty)
    if sub and isinstance(sub.get("started_at"), datetime):
        return _as_utc(sub["started_at"])
    if _doc_difficulty(doc) == difficulty and isinstance(doc.get("started_at"), datetime):
        return _as_utc(doc["started_at"])
    return None


def _server_elapsed_seconds(
    started_at: Optional[datetime],
    now: datetime,
    client_seconds: Optional[int],
) -> Tuple[Optional[int], bool]:
    """Tiempo medido por el servidor y sospecha de tiempo cliente subdeclarado."""
    if started_at is None:
        return None, False
    elapsed = int((now - started_at).total_seconds())
    if elapsed < 0:
        return None, False
    suspect = (
        client_seconds is not None
        and elapsed >= _TIME_SUSPECT_MIN_SERVER_SECONDS
        and elapsed - client_seconds >= _TIME_SUSPECT_MIN_DIFF_SECONDS
        and client_seconds < elapsed * 0.5
    )
    return elapsed, suspect


def _should_replace_top_level(existing: dict, final_status: str) -> bool:
    """El nivel superior refleja la última partida, salvo que ya esté completada."""
    if existing.get("validation_status") == "rejected":
        return True
    if existing.get("status") in _COMPLETED_STATUSES:
        return final_status == "completed"
    return True


def _attempt_snapshot(doc: dict) -> dict:
    """Copia un intento para guardarlo dentro de by_difficulty (sin _id ni anidamientos)."""
    return {
        key: value
        for key, value in doc.items()
        if key not in ("_id", "created_at", "by_difficulty")
    }


def _preserve_existing_difficulty(existing: dict, difficulty: str, update_fields: dict) -> None:
    """Materializa by_difficulty si el documento histórico no lo tenía."""
    existing_difficulty = _doc_difficulty(existing)
    if existing_difficulty == difficulty:
        return
    if existing_difficulty not in (existing.get("by_difficulty") or {}):
        update_fields[f"by_difficulty.{existing_difficulty}"] = _attempt_snapshot(existing)


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


async def _register_replay_rejection(
    user_id: int, game_id: str, date: str, difficulty: str, status: str
) -> None:
    try:
        await get_points_ledger().record_event(
            user_id=user_id,
            motivo="replay_rejected",
            puntos=0,
            idempotency_key=f"replay:{user_id}:{game_id}:{date}:{difficulty}:{status}",
            metadata={
                "game_id": game_id,
                "date": date,
                "difficulty": difficulty,
                "status": status,
                "actor": "system",
            },
            status="rejected",
        )
    except Exception as e:
        logger.warning(f"No se pudo auditar el replay de {user_id}/{game_id}/{date}: {e}")


async def save_user_attempt(
    req: UserAttemptCreateRequest,
    authenticated_user_id: Optional[int] = None
) -> UserAttemptResponse:
    """Guarda o actualiza un intento de partida de forma atómica e idempotente."""
    if authenticated_user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Se requiere iniciar sesión para guardar progreso en la nube.",
        )

    db = get_database()
    ledger = get_points_ledger()
    user_id = int(authenticated_user_id)
    game_id = req.game_id.lower().strip()
    date = req.date.strip()
    difficulty = _normalize_difficulty(req)
    now = datetime.now(timezone.utc)

    filter_query = {"user_id": user_id, "game_id": game_id, "date": date}

    # Obtener configuración de economía para puntos por calificación
    from app.features.economy.service import get_economy_config
    econ_config = None
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
        except (TypeError, ValueError):
            time_taken = None
        if time_taken is not None and time_taken < 0:
            time_taken = None

    escalas_juego = None
    if hasattr(econ_config, "escalas_tiempo_por_juego") and econ_config.escalas_tiempo_por_juego:
        escalas_juego = econ_config.escalas_tiempo_por_juego.get(game_id)

    status_normalized = req.status.lower().strip()
    if status_normalized in ("completed", "won"):
        final_status = "completed"
    elif status_normalized in ("failed", "lost"):
        final_status = "failed"
    else:
        final_status = "in_progress"

    def _replay_response(existing: dict, saldo: Optional[int] = None) -> UserAttemptResponse:
        return _serialize_attempt(
            existing,
            puntos_ganados=0,
            puntos_totales_usuario=saldo,
        )

    existing = await db["user_attempts"].find_one(filter_query)

    # Replay: esa dificultad ya está completada; no se toca estado ni se recalcula grado.
    if _difficulty_is_completed(existing, difficulty):
        await _register_replay_rejection(user_id, game_id, date, difficulty, final_status)
        return _replay_response(existing, await ledger.saldo(user_id))

    # Tiempo autoritativo del servidor: arranca en el primer guardado en curso.
    started_at = _attempt_started_at(existing, difficulty)
    if final_status == "in_progress" and started_at is None:
        started_at = now
    server_elapsed, time_suspect = _server_elapsed_seconds(started_at, now, time_taken)

    validation_status: Optional[str] = None
    validation_reason: Optional[str] = None
    attempts_value = req.attempts
    enforce = final_status == "completed" and is_enforcement_enabled(game_id)

    if enforce:
        errors = _parse_errors(req.game_data)
        submission = Submission(
            word=req.word,
            guesses=req.guesses or [],
            attempts=req.attempts,
            errors=errors,
            game_data=req.game_data or {},
        )
        validation = await validate_submission(game_id, date, difficulty, submission)
        if not validation.valid:
            # Se persiste como intento rechazado: no acredita y habilita un reintento legítimo.
            validation_status = "rejected"
            validation_reason = validation.reason
            grade, score, stars = "F", 0, 0
            logger.info(
                f"[VALIDACION] Intento rechazado {user_id}/{game_id}/{date}/{difficulty}: "
                f"{validation.reason}"
            )
        else:
            validation_status = "validated"
            attempts_value = validation.attempts if validation.attempts is not None else req.attempts
            effective_errors = validation.errors if validation.errors is not None else errors
            effective_time = time_taken
            if time_suspect or effective_time is None:
                effective_time = server_elapsed if server_elapsed is not None else effective_time
            grade, score, stars = calculate_grade_and_score(
                game_id=game_id,
                status=req.status,
                attempts=attempts_value,
                remaining_attempts=req.remaining_attempts or 0,
                provided_grade=None,
                provided_score=None,
                provided_stars=None,
                puntos_por_calificacion=puntos_config,
                game_data={**(req.game_data or {}), "errors": effective_errors},
                time_taken_seconds=effective_time,
                escalas_tiempo=escalas_juego,
            )
    else:
        # Flags apagados: se conserva el contrato histórico (cliente y tiempo enviados).
        grade, score, stars = calculate_grade_and_score(
            game_id=game_id,
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

    doc = {
        "user_id": user_id,
        "game_id": game_id,
        "date": date,
        "difficulty": difficulty,
        "mode": req.mode.lower().strip(),
        "status": final_status,
        "word": req.word.strip() if req.word else None,
        "attempts": attempts_value,
        "stars": stars,
        "score": score,
        "grade": grade,
        "guesses": req.guesses or [],
        "game_data": req.game_data,
        "remaining_attempts": req.remaining_attempts or 0,
        "time_taken_seconds": time_taken,
        "updated_at": now,
    }
    if started_at is not None:
        doc["started_at"] = started_at
    if server_elapsed is not None:
        doc["server_elapsed_seconds"] = server_elapsed
    if time_suspect:
        doc["time_suspect"] = True
    if validation_status:
        doc["validation_status"] = validation_status
        if validation_reason:
            doc["validation_reason"] = validation_reason

    if existing:
        update_fields: Dict[str, Any] = {
            f"by_difficulty.{difficulty}": doc,
            "updated_at": now,
        }
        _preserve_existing_difficulty(existing, difficulty, update_fields)
        if _should_replace_top_level(existing, final_status):
            update_fields.update(doc)
        result = await db["user_attempts"].find_one_and_update(
            filter_query,
            {"$set": update_fields},
            return_document=True,
        )
        if result is None:
            raise HTTPException(
                status_code=409,
                detail="No se pudo actualizar la partida por un conflicto concurrente.",
            )
    else:
        initial = dict(doc)
        initial["by_difficulty"] = {difficulty: dict(doc)}
        try:
            result = await db["user_attempts"].find_one_and_update(
                filter_query,
                {"$set": initial, "$setOnInsert": {"created_at": now}},
                upsert=True,
                return_document=True,
            )
        except DuplicateKeyError:
            # Otra request insertó el mismo slot: se resuelve como replay o actualización.
            existing = await db["user_attempts"].find_one(filter_query)
            if _difficulty_is_completed(existing, difficulty):
                await _register_replay_rejection(user_id, game_id, date, difficulty, final_status)
                return _replay_response(existing, await ledger.saldo(user_id))
            update_fields = {f"by_difficulty.{difficulty}": doc, "updated_at": now}
            if existing:
                _preserve_existing_difficulty(existing, difficulty, update_fields)
                if _should_replace_top_level(existing, final_status):
                    update_fields.update(doc)
            result = await db["user_attempts"].find_one_and_update(
                filter_query,
                {"$set": update_fields},
                return_document=True,
            )
            if result is None:
                raise HTTPException(
                    status_code=409,
                    detail="No se pudo guardar la partida por un conflicto concurrente.",
                )

    puntos_ganados = 0
    puntos_totales_usuario: Optional[int] = None

    if final_status == "completed" and validation_status != "rejected":
        ledger_result = await ledger.credit(
            LedgerKey(
                user_id=user_id,
                motivo="attempt",
                game_id=game_id,
                date=date,
                difficulty=difficulty,
            ),
            score,
            metadata={"grade": grade, "difficulty": difficulty},
        )
        if ledger_result.applied:
            puntos_ganados = score
            logger.info(
                f"[PUNTOS] Usuario {user_id} ganó {puntos_ganados} pts "
                f"(calificación {grade}, dificultad {difficulty}) en {game_id}. "
                f"Saldo: {ledger_result.saldo}"
            )
        else:
            logger.info(
                f"[PUNTOS] Acreditación ya aplicada para {user_id}/{game_id}/{date}/{difficulty}; no se suman puntos."
            )
        puntos_totales_usuario = ledger_result.saldo

    if puntos_totales_usuario is None:
        puntos_totales_usuario = await ledger.saldo(user_id)

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
