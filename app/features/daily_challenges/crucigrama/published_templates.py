"""Configuraciones de crucigrama publicadas por el diseñador.

Vive fuera de `crucigrama_admin` para que la generación diaria consuma plantillas
sin depender del panel administrativo. El panel reexporta estas funciones.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from pymongo import ASCENDING

from app.core.database import get_database
from app.features.daily_challenges.crucigrama.generator import build_challenge_from_solution
from app.features.daily_challenges.crucigrama.solver import normalize_word
from app.features.daily_challenges.crucigrama.validator import validate_pattern

logger = logging.getLogger(__name__)

COLLECTION = "crucigrama_templates"
STATUS_PUBLISHED = "published"


def prefer_curated(difficulty: str, override: Optional[bool]) -> bool:
    if override is not None:
        return override
    return difficulty != "dificil"


async def get_scheduled_published_config(
    date_str: str, difficulty: str
) -> Optional[Dict[str, Any]]:
    """
    Configuración fijada por una plantilla publicada para (fecha, dificultad).
    Devuelve None si no hay plantilla o si su configuración no es utilizable.
    """
    doc = await get_database()[COLLECTION].find_one(
        {
            "status": STATUS_PUBLISHED,
            "scheduled_date": date_str,
            "difficulty": difficulty,
        }
    )
    if not doc:
        return None

    config = doc.get("published_config")
    pattern = doc.get("pattern") or []
    if not isinstance(config, dict) or not isinstance(config.get("cells"), list):
        logger.warning(
            f"[CRUCIGRAMA] Plantilla publicada {doc.get('id')} sin configuración usable para {date_str}."
        )
        return None
    if pattern and config.get("grid_size") != len(pattern):
        logger.warning(
            f"[CRUCIGRAMA] Plantilla {doc.get('id')} con grid_size inconsistente para {date_str}."
        )
        return None
    return config


async def get_recurring_published_config(
    date_str: str,
    difficulty: str,
    global_banned_words: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Configuración para una plantilla publicada que se repite el día del mes de
    `date_str`. La solución se re-resuelve con semilla derivada de la fecha para
    no repetir el mismo tablero todos los meses; devuelve None si no hay
    plantilla o si no se encontró solución (el llamador cae al generador).
    """
    try:
        day = int(date_str[-2:])
    except (TypeError, ValueError):
        return None

    doc = await get_database()[COLLECTION].find_one(
        {
            "status": STATUS_PUBLISHED,
            "monthly_day": day,
            "difficulty": difficulty,
        },
        sort=[("published_at", ASCENDING)],
    )
    if not doc:
        return None

    pattern = doc.get("pattern") or []
    if not pattern:
        logger.warning(
            f"[CRUCIGRAMA] Plantilla recurrente {doc.get('id')} sin máscara para {date_str}."
        )
        return None

    banned = sorted(
        {
            normalize_word(word)
            for word in [
                *(doc.get("banned_words") or []),
                *(global_banned_words or []),
            ]
            if normalize_word(word)
        }
    )
    curated = prefer_curated(difficulty, None)
    report = await asyncio.to_thread(
        validate_pattern,
        pattern,
        prefer_curated=curated,
        anchors=doc.get("anchors") or {},
        seed=date_str,
        banned_words=banned,
        engine="bitset",
    )
    if not report.get("solvable") or not report.get("solution"):
        logger.warning(
            f"[CRUCIGRAMA] La plantilla recurrente {doc.get('id')} no pudo resolverse "
            f"para {date_str} ({difficulty}); se usa el generador."
        )
        return None

    return await asyncio.to_thread(
        build_challenge_from_solution,
        doc.get("theme") or "Palabras Cruzadas",
        report["solution"],
        prefer_curated=curated,
        clue_overrides=doc.get("clue_overrides") or {},
    )
