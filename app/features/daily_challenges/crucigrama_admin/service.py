"""Persistencia y ciclo de vida de las máscaras de crucigrama del panel admin."""

import concurrent.futures
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from pymongo import DESCENDING
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.core.database import get_database
from app.core.rae_client import get_masked_definition
from app.features.daily_challenges.crucigrama.bans import (
    get_global_bans_doc,
    get_global_banned_words,
    set_global_banned_words,
)
from app.features.daily_challenges.crucigrama.generator import build_challenge_from_solution
from app.features.daily_challenges.crucigrama.solver import (
    _parse_template_slots,
    is_known_word,
    normalize_word,
)
from app.features.daily_challenges.crucigrama.validator import (
    validate_pattern,
    validate_structure,
)
from app.features.daily_challenges.crucigrama.published_templates import (
    get_recurring_published_config,
    get_scheduled_published_config,
    prefer_curated as _prefer_curated,
)
from app.features.daily_challenges.crucigrama_admin.schemas import (
    CrucigramaTemplateCreate,
    CrucigramaTemplateUpdate,
)

logger = logging.getLogger(__name__)

COLLECTION = "crucigrama_templates"
GAME_ID = "crucigrama"
STATUS_DRAFT = "draft"
STATUS_PUBLISHED = "published"
STATUS_ARCHIVED = "archived"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: Any) -> Optional[str]:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value) if value else None


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _user_label(user: Optional[Dict[str, Any]]) -> str:
    user = user or {}
    return str(user.get("email") or user.get("name") or user.get("id") or "sistema")


def _to_summary(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc.get("id"),
        "name": doc.get("name"),
        "theme": doc.get("theme") or "Palabras Cruzadas",
        "difficulty": doc.get("difficulty"),
        "size": doc.get("size") or len(doc.get("pattern") or []),
        "status": doc.get("status"),
        "scheduled_date": doc.get("scheduled_date"),
        "monthly_day": doc.get("monthly_day"),
        "total_words": doc.get("total_words") or 0,
        "anchors": doc.get("anchors") or {},
        "created_by": doc.get("created_by"),
        "created_at": _iso(doc.get("created_at")),
        "updated_at": _iso(doc.get("updated_at")),
        "published_at": _iso(doc.get("published_at")),
        "archived_at": _iso(doc.get("archived_at")),
    }


def _to_detail(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        **_to_summary(doc),
        "pattern": doc.get("pattern") or [],
        "banned_words": doc.get("banned_words") or [],
        "clue_overrides": doc.get("clue_overrides") or {},
        "solution_grid": doc.get("solution_grid"),
        "clues": doc.get("clues") or {},
        "published_config": doc.get("published_config"),
        "last_seed": doc.get("last_seed"),
        "notes": doc.get("notes"),
        "published_by": doc.get("published_by"),
        "archived_by": doc.get("archived_by"),
    }


async def _get_doc(template_id: str) -> Dict[str, Any]:
    doc = await get_database()[COLLECTION].find_one({"id": template_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"No existe la plantilla '{template_id}'.")
    return doc


def _assert_structure(pattern: List[str], anchors: Dict[str, str]) -> Dict[str, Any]:
    report = validate_structure(pattern, anchors)
    if not report["valid"]:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "La máscara no es válida.",
                "errors": report["errors"],
            },
        )
    return report


def _assert_future_date(date_str: str) -> None:
    if date_str < _today():
        raise HTTPException(
            status_code=400,
            detail=f"La fecha {date_str} ya pasó; elegí hoy o una fecha futura.",
        )


async def _assert_free_schedule(
    scheduled_date: str, difficulty: str, exclude_id: Optional[str] = None
) -> None:
    query: Dict[str, Any] = {
        "status": STATUS_PUBLISHED,
        "scheduled_date": scheduled_date,
        "difficulty": difficulty,
    }
    if exclude_id:
        query["id"] = {"$ne": exclude_id}
    existing = await get_database()[COLLECTION].find_one(query)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Ya existe la plantilla publicada '{existing.get('name')}' ({existing.get('id')}) "
                f"para {scheduled_date} en dificultad {difficulty}. Archivá esa plantilla primero."
            ),
        )


async def _assert_free_monthly_day(
    monthly_day: int, difficulty: str, exclude_id: Optional[str] = None
) -> None:
    query: Dict[str, Any] = {
        "status": STATUS_PUBLISHED,
        "monthly_day": monthly_day,
        "difficulty": difficulty,
    }
    if exclude_id:
        query["id"] = {"$ne": exclude_id}
    existing = await get_database()[COLLECTION].find_one(query)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Ya existe la plantilla publicada '{existing.get('name')}' ({existing.get('id')}) "
                f"para el día {monthly_day} de cada mes en dificultad {difficulty}. "
                "Archivá esa plantilla primero."
            ),
        )


def validate_mask(
    payload: Any, global_banned_words: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Valida estructura + solubilidad sin persistir nada.

    Los vetos globales se suman a los de la plantilla: el reporte devuelve ambos
    por separado para que el panel distinga cuáles puede quitar.
    """
    global_bans = sorted(
        {normalize_word(w) for w in (global_banned_words or []) if normalize_word(w)}
    )
    prefer_curated = _prefer_curated(payload.difficulty or "facil", payload.prefer_curated)
    report = validate_pattern(
        payload.pattern,
        prefer_curated=prefer_curated,
        attempt_budgets=tuple(payload.attempt_budgets) if payload.attempt_budgets else None,
        anchors=payload.anchors,
        fixed_words=payload.fixed_words,
        seed=payload.seed,
        banned_words=[*payload.banned_words, *global_bans],
        engine="bitset",
    )
    excluidas = set(global_bans)
    report["banned_words"] = [
        word for word in report.get("banned_words", []) if word not in excluidas
    ]
    report["global_banned_words"] = global_bans
    report["prefer_curated"] = prefer_curated
    report["difficulty"] = payload.difficulty
    return report


async def get_global_bans() -> Dict[str, Any]:
    return await get_global_bans_doc()


async def update_global_bans(payload: Any, user: Dict[str, Any]) -> Dict[str, Any]:
    words = await set_global_banned_words(
        payload.banned_words, updated_by=_user_label(user)
    )
    logger.info(
        f"[CRUCIGRAMA] Vetos globales actualizados ({len(words)}) por {_user_label(user)}."
    )
    return await get_global_bans_doc()


async def list_templates(
    status: Optional[str] = None,
    difficulty: Optional[str] = None,
    size: Optional[int] = None,
    limit: int = 50,
    skip: int = 0,
) -> Dict[str, Any]:
    query: Dict[str, Any] = {}
    if status:
        query["status"] = status
    if difficulty:
        query["difficulty"] = difficulty
    if size:
        query["size"] = size

    collection = get_database()[COLLECTION]
    total = await collection.count_documents(query)
    cursor = (
        collection.find(query).sort("updated_at", DESCENDING).skip(skip).limit(limit)
    )
    items = [_to_summary(doc) async for doc in cursor]
    return {"total": total, "limit": limit, "skip": skip, "items": items}


async def get_template(template_id: str) -> Dict[str, Any]:
    doc = await _get_doc(template_id)
    return _to_detail(doc)


async def create_template(payload: CrucigramaTemplateCreate, user: Dict[str, Any]) -> Dict[str, Any]:
    report = _assert_structure(payload.pattern, payload.anchors)
    if payload.scheduled_date:
        _assert_future_date(payload.scheduled_date)

    now = _now()
    doc: Dict[str, Any] = {
        "id": uuid.uuid4().hex[:16],
        "name": payload.name.strip(),
        "theme": payload.theme.strip() or "Palabras Cruzadas",
        "pattern": payload.pattern,
        "size": len(payload.pattern),
        "difficulty": payload.difficulty,
        "anchors": report["anchors"],
        "banned_words": payload.banned_words,
        "clue_overrides": payload.clue_overrides,
        "status": STATUS_DRAFT,
        "scheduled_date": payload.scheduled_date,
        "monthly_day": payload.monthly_day,
        "total_words": report["words"],
        "solution_grid": None,
        "clues": {},
        "published_config": None,
        "last_seed": None,
        "notes": payload.notes,
        "created_by": _user_label(user),
        "created_at": now,
        "updated_at": now,
        "published_at": None,
        "published_by": None,
        "archived_at": None,
        "archived_by": None,
    }
    await get_database()[COLLECTION].insert_one(doc)
    return _to_detail(doc)


async def update_template(
    template_id: str, payload: CrucigramaTemplateUpdate, user: Dict[str, Any]
) -> Dict[str, Any]:
    doc = await _get_doc(template_id)
    if doc.get("status") == STATUS_PUBLISHED:
        raise HTTPException(
            status_code=409,
            detail="La plantilla está publicada. Archivala antes de editarla.",
        )

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return _to_detail(doc)
    if data.get("banned_words") is None:
        data.pop("banned_words", None)

    if data.get("scheduled_date"):
        _assert_future_date(data["scheduled_date"])

    pattern = data.get("pattern", doc.get("pattern") or [])
    anchors = data.get("anchors", doc.get("anchors") or {})
    if "pattern" in data or "anchors" in data or "banned_words" in data:
        report = _assert_structure(pattern, anchors)
        data["anchors"] = report["anchors"]
        data["size"] = len(pattern)
        data["total_words"] = report["words"]
        # La solución cacheada deja de ser válida al cambiar máscara, anclas o vetos.
        data["solution_grid"] = None
        data["clues"] = {}
        data["published_config"] = None
        data["last_seed"] = None
        data["published_at"] = None
        data["published_by"] = None

    if "name" in data and data["name"] is not None:
        data["name"] = data["name"].strip()
    if "theme" in data and data["theme"] is not None:
        data["theme"] = data["theme"].strip() or "Palabras Cruzadas"

    data["updated_at"] = _now()
    await get_database()[COLLECTION].update_one({"id": template_id}, {"$set": data})
    doc.update(data)
    return _to_detail(doc)


async def archive_template(template_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
    doc = await _get_doc(template_id)
    if doc.get("status") == STATUS_ARCHIVED:
        return _to_detail(doc)

    now = _now()
    changes = {
        "status": STATUS_ARCHIVED,
        "archived_at": now,
        "archived_by": _user_label(user),
        "updated_at": now,
    }
    await get_database()[COLLECTION].update_one({"id": template_id}, {"$set": changes})
    doc.update(changes)
    return _to_detail(doc)


async def delete_template(template_id: str) -> Dict[str, Any]:
    doc = await _get_doc(template_id)
    if doc.get("status") == STATUS_PUBLISHED:
        raise HTTPException(
            status_code=409,
            detail="No se puede eliminar una plantilla publicada. Archivala primero.",
        )
    await get_database()[COLLECTION].delete_one({"id": template_id})
    return {"success": True, "deleted_id": template_id}


def _assert_solution_matches_pattern(pattern: List[str], solution: List[str]) -> None:
    if len(solution) != len(pattern):
        raise HTTPException(status_code=500, detail="La solución no coincide con la máscara.")
    for r, row in enumerate(pattern):
        if len(solution[r]) != len(row):
            raise HTTPException(status_code=500, detail="La solución no coincide con la máscara.")
        for c, ch in enumerate(row):
            es_bloque = solution[r][c] == "#"
            if (ch == "#") != es_bloque:
                raise HTTPException(
                    status_code=500,
                    detail=f"La solución no respeta los bloques de la máscara en ({r}, {c}).",
                )


def _validate_solution_grid(
    pattern: List[str],
    solution: List[str],
    anchors: Dict[str, str],
    banned_words: List[str],
) -> Tuple[List[str], Dict[str, str]]:
    """
    Valida una solución aprobada por el operador: respeta bloques, usa solo
    letras, todas las palabras existen en el léxico, no se repiten, no están
    vetadas y respetan las anclas fijadas.
    """
    if not isinstance(solution, list) or len(solution) != len(pattern):
        raise HTTPException(
            status_code=400,
            detail="La solución no coincide con la máscara; volvé a resolverla antes de publicar.",
        )

    R = len(pattern)
    C = len(pattern[0]) if R else 0
    grid: List[str] = []
    for r in range(R):
        fila = solution[r]
        if not isinstance(fila, str) or len(fila) != C:
            raise HTTPException(
                status_code=400,
                detail=f"La fila {r + 1} de la solución no tiene el ancho de la máscara.",
            )
        letras: List[str] = []
        for c in range(C):
            if pattern[r][c] == "#":
                if fila[c] != "#":
                    raise HTTPException(
                        status_code=400,
                        detail=f"La solución no respeta el bloque de la máscara en ({r}, {c}).",
                    )
                letras.append("#")
                continue
            letra = normalize_word(fila[c])
            if len(letra) != 1 or not letra.isalpha():
                raise HTTPException(
                    status_code=400,
                    detail=f"La celda ({r}, {c}) de la solución no es una letra válida.",
                )
            letras.append(letra)
        grid.append("".join(letras))

    slots, _ = _parse_template_slots(pattern)
    banned = {normalize_word(word) for word in (banned_words or [])}
    vistas = set()
    asignacion: Dict[str, str] = {}
    for slot in slots:
        word = "".join(grid[r][c] for r, c in slot["coords"])
        if not is_known_word(word):
            raise HTTPException(
                status_code=400,
                detail=f"La palabra '{word}' del slot '{slot['id']}' no está en el léxico del juego.",
            )
        if word in vistas:
            raise HTTPException(
                status_code=400, detail=f"La palabra '{word}' aparece más de una vez en la solución."
            )
        if word in banned:
            raise HTTPException(
                status_code=400, detail=f"La palabra '{word}' está vetada y no puede publicarse."
            )
        vistas.add(word)
        asignacion[slot["id"]] = word

    for slot_id, word in (anchors or {}).items():
        if asignacion.get(slot_id) != word:
            raise HTTPException(
                status_code=400,
                detail=f"La solución no respeta el ancla '{word}' del slot '{slot_id}'.",
            )

    return grid, asignacion


async def publish_template(
    template_id: str, payload: Any, user: Dict[str, Any]
) -> Dict[str, Any]:
    doc = await _get_doc(template_id)
    pattern = doc.get("pattern") or []
    difficulty = doc.get("difficulty") or "facil"

    report = _assert_structure(pattern, doc.get("anchors") or {})
    prefer_curated = _prefer_curated(difficulty, payload.prefer_curated)
    banned_words = (
        payload.banned_words
        if "banned_words" in payload.model_fields_set
        else (doc.get("banned_words") or [])
    )
    global_bans = await get_global_banned_words()
    banned_validacion = sorted(
        {normalize_word(word) for word in [*banned_words, *global_bans]}
    )

    if payload.solution_grid:
        solution_grid, _ = _validate_solution_grid(
            pattern, payload.solution_grid, report["anchors"], banned_validacion
        )
        validation = {
            "solution": solution_grid,
            "errors": [],
            "warnings": [],
            "attempts": 0,
            "elapsed_ms": 0.0,
        }
    else:
        validation = validate_pattern(
            pattern,
            prefer_curated=prefer_curated,
            anchors=report["anchors"],
            seed=payload.seed,
            banned_words=banned_validacion,
            engine="bitset",
        )
        if not validation["solvable"]:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "La máscara no tiene solución con los intentos disponibles; no se publicó.",
                    "errors": validation["errors"],
                    "warnings": validation["warnings"],
                    "attempts": validation["attempts"],
                    "elapsed_ms": validation["elapsed_ms"],
                },
            )

        solution_grid = validation["solution"]
        _assert_solution_matches_pattern(pattern, solution_grid)

    theme = doc.get("theme") or "Palabras Cruzadas"
    config = build_challenge_from_solution(
        theme,
        solution_grid,
        prefer_curated=prefer_curated,
        clue_overrides=doc.get("clue_overrides") or {},
    )
    clues = {word["word"]: word["clue"] for word in config["words"]}

    scheduled_date = payload.scheduled_date or doc.get("scheduled_date")
    if scheduled_date:
        _assert_future_date(scheduled_date)
        await _assert_free_schedule(scheduled_date, difficulty, exclude_id=template_id)

    monthly_day = payload.monthly_day or doc.get("monthly_day")
    if monthly_day:
        await _assert_free_monthly_day(monthly_day, difficulty, exclude_id=template_id)

    now = _now()
    changes = {
        "status": STATUS_PUBLISHED,
        "anchors": report["anchors"],
        "banned_words": banned_words,
        "last_seed": payload.seed,
        "solution_grid": solution_grid,
        "clues": clues,
        "published_config": config,
        "total_words": config["total_words"],
        "scheduled_date": scheduled_date,
        "monthly_day": monthly_day,
        "published_at": now,
        "published_by": _user_label(user),
        "archived_at": None,
        "archived_by": None,
        "updated_at": now,
    }
    try:
        await get_database()[COLLECTION].update_one({"id": template_id}, {"$set": changes})
    except DuplicateKeyError:
        raise HTTPException(
            status_code=409,
            detail=(
                "Ya hay una plantilla publicada para esa fecha o ese día del mes "
                f"en dificultad {difficulty}."
            ),
        )
    doc.update(changes)

    applied_to = None
    if scheduled_date:
        applied_to = await _apply_config_to_date(
            scheduled_date, difficulty, config, force=True, user=user
        )

    return {"template": _to_detail(doc), "applied_to": applied_to}


async def _apply_config_to_date(
    date_str: str,
    difficulty: str,
    config: Dict[str, Any],
    force: bool,
    user: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    db = get_database()
    query = {"game_id": GAME_ID, "date": date_str, "difficulty": difficulty}
    existing = await db["daily_challenges"].find_one(query)
    if existing and not force:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Ya existe un desafío de crucigrama para {date_str} ({difficulty}). "
                "Usá force=true para sobrescribirlo."
            ),
        )

    stored = {k: v for k, v in config.items() if k != "date"}
    stored["date"] = date_str
    now = _now()
    doc = {
        "game_id": GAME_ID,
        "date": date_str,
        "difficulty": difficulty,
        "title": f"Crucigrama ({difficulty.capitalize()}): {stored.get('theme', 'Palabras Cruzadas')} ({date_str})",
        "config": stored,
        "source": "admin_template",
        "updated_by": _user_label(user),
        "updated_at": now,
    }
    await db["daily_challenges"].update_one(
        query,
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return {
        "game_id": GAME_ID,
        "date": date_str,
        "difficulty": difficulty,
        "overwritten": bool(existing),
        "total_words": stored.get("total_words", 0),
    }


async def apply_template(
    template_id: str, date_str: str, force: bool, user: Dict[str, Any]
) -> Dict[str, Any]:
    doc = await _get_doc(template_id)
    if doc.get("status") != STATUS_PUBLISHED:
        raise HTTPException(
            status_code=409, detail="Solo se pueden aplicar plantillas publicadas."
        )
    config = doc.get("published_config")
    if not config:
        raise HTTPException(
            status_code=409, detail="La plantilla no tiene una configuración publicada."
        )
    _assert_future_date(date_str)

    applied = await _apply_config_to_date(
        date_str, doc.get("difficulty") or "facil", config, force=force, user=user
    )
    return {"success": True, "template_id": template_id, **applied}


def lookup_definition(word: str) -> Dict[str, Any]:
    """Definición RAE (con la palabra tapada) para una palabra del diseñador."""
    limpia = normalize_word(word)
    if not limpia or not limpia.isalpha() or not (2 <= len(limpia) <= 15):
        raise HTTPException(
            status_code=400, detail="La palabra debe tener entre 2 y 15 letras."
        )
    definition = get_masked_definition(limpia)
    return {"word": limpia, "definition": definition, "found": bool(definition)}


def lookup_definitions(words: List[str]) -> Dict[str, Any]:
    """
    Definiciones RAE en lote para autocompletar pistas. La caché local evita
    consultar dos veces la misma palabra y la concurrencia queda acotada por
    RAE_MAX_CONCURRENCY, con espaciado global en el cliente.
    """
    unicas: List[str] = []
    for raw in words:
        word = normalize_word(raw)
        if word and word not in unicas:
            unicas.append(word)
    if not unicas:
        return {"definitions": {}, "missing": []}

    trabajadores = max(1, min(settings.RAE_MAX_CONCURRENCY, len(unicas)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=trabajadores) as executor:
        resultados = list(executor.map(get_masked_definition, unicas))

    definitions = {
        word: definition
        for word, definition in zip(unicas, resultados)
        if definition
    }
    missing = [word for word, definition in zip(unicas, resultados) if not definition]
    return {"definitions": definitions, "missing": missing}
