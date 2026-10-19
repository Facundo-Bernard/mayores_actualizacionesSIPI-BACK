"""
endings_service.py
Gestión de desenlaces de partida (victoria en Mes 12 o derrota por colapso de recursos)
y sincronización del intento del alumno con la colección user_attempts para progreso y rachas.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from app.core.database import get_database
from app.features.narrative.constants import (
    COLL_SETTINGS,
    COLL_ENDINGS,
    COLL_USER_ATTEMPTS
)
from app.features.narrative.enums import (
    RunPhaseEnum,
    TipoFinalizacionEnum
)

logger = logging.getLogger(__name__)

async def verificar_colapso_recursos(run_doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Verifica si algún recurso vital (oro, comida, moral, defensa) llegó a <= 0.
    En tal caso, asocia la finalización correspondiente al recurso agotado, marca la run
    como 'game_over' y 'FINALIZADA', persistiendo el epílogo de la derrota.
    """
    recursos = run_doc.get("recursos", {})
    recurso_agotado = None
    for k, val in recursos.items():
        if val is not None and float(val) <= 0:
            recurso_agotado = k
            break

    if not recurso_agotado:
        return None

    universo_id = run_doc.get("universo_id")
    db = get_database()

    # Búsqueda ESTRICTA por universo_id y recurso_clave (cada universo tiene sus propios finales)
    fin_doc = await db[COLL_ENDINGS].find_one({
        "universo_id": universo_id,
        "recurso_clave": recurso_agotado
    })

    # Cargar metadatos del universo para contextualizar título y relato sin asumir temáticas ajenas
    universo_doc = await db[COLL_SETTINGS].find_one({"_id": universo_id})
    universo_nombre = universo_doc.get("nombre", universo_id) if universo_doc else universo_id
    recurso_meta = next((r for r in universo_doc.get("recursos", []) if r.get("clave") == recurso_agotado), None) if universo_doc else None
    recurso_nombre = recurso_meta.get("nombre", recurso_agotado.capitalize()) if recurso_meta else recurso_agotado.capitalize()

    if not fin_doc:
        fin_doc = {
            "_id": f"fin_{universo_id}_{recurso_agotado}_cero",
            "universo_id": universo_id,
            "recurso_clave": recurso_agotado,
            "tipo": TipoFinalizacionEnum.DERROTA_RECURSO.value,
            "titulo": f"Colapso por {recurso_nombre} ({universo_nombre})",
            "texto": f"El recurso '{recurso_nombre}' ha llegado a cero en {universo_nombre}, provocando el fin irreversible de tu partida.",
            "imagen": "/assets/narrative/finalizaciones/default.webp",
            "rango": "F"
        }

    mes_caida = run_doc.get("mes_actual", 1)
    finalizacion_data = {
        "_id": fin_doc.get("_id"),
        "universo_id": universo_id,
        "recurso_clave": recurso_agotado,
        "tipo": fin_doc.get("tipo", TipoFinalizacionEnum.DERROTA_RECURSO.value),
        "titulo": fin_doc.get("titulo", f"Derrota en {universo_nombre}"),
        "texto": fin_doc.get("texto", ""),
        "imagen": fin_doc.get("imagen", "/assets/narrative/finalizaciones/default.webp"),
        "rango": fin_doc.get("rango", "F"),
        "mes_derrota": mes_caida
    }

    run_doc["status"] = "game_over"
    run_doc["fase_actual"] = RunPhaseEnum.FINALIZADA.value
    run_doc["finalizacion"] = finalizacion_data

    return finalizacion_data

def calcular_finalizacion_victoria(
    run_data: Dict[str, Any],
    universo_doc: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Calcula el epílogo y rango de victoria (S, A, B, C) al sobrevivir con éxito
    a los 12 meses de gobierno según el promedio final de los recursos del reino.
    """
    recursos = run_data.get("recursos", {})
    promedio = sum(recursos.values()) / max(1, len(recursos))
    nombre_u = universo_doc.get("nombre", "este reino") if universo_doc else "este reino"
    universo_id = run_data.get("universo_id", "corte_medieval")

    if promedio >= 75:
        rango = "S"
        titulo = "Era Dorada y Prosperidad Suprema"
        texto = f"Tus sabias decisiones y admirable gestión permitieron que {nombre_u} alcanzara su máximo esplendor histórico."
    elif promedio >= 55:
        rango = "A"
        titulo = "Gran Estabilidad y Triunfo"
        texto = f"Superaste las crisis con solvencia y aseguraste un porvenir seguro y próspero en {nombre_u}."
    elif promedio >= 35:
        rango = "B"
        titulo = "Tiempos Difíciles pero Superados"
        texto = f"El ciclo anual fue duro y las pérdidas se hicieron sentir, pero lograste salir adelante en {nombre_u}."
    else:
        rango = "C"
        titulo = "Supervivencia Crítica"
        texto = f"Apenas lograste sostener el control en {nombre_u}. Las tensiones acumuladas amenazan lo poco que pudiste preservar."

    return {
        "_id": f"fin_{universo_id}_victoria",
        "universo_id": universo_id,
        "recurso_clave": None,
        "tipo": TipoFinalizacionEnum.VICTORIA_TIEMPO.value,
        "titulo": titulo,
        "texto": texto,
        "imagen": "/assets/narrative/finalizaciones/default.webp",
        "rango": rango
    }

async def sincronizar_intento_usuario(run_doc: Dict[str, Any]):
    """
    Registra el intento diario en la colección user_attempts con el puntaje normalizado
    (1000, 850, 700, 500, 250) y estrellas (3, 2, 1) para impactar en el progreso del alumno.
    """
    try:
        db = get_database()
        user_id = run_doc.get("user_id")
        date_str = run_doc.get("date")
        if not user_id or not date_str:
            return

        is_completed = run_doc.get("status") == "completed"
        status_str = "completed" if is_completed else "failed"
        rango = run_doc.get("finalizacion", {}).get("rango", "F")

        scores_map = {"S": 1000, "A": 850, "B": 700, "C": 500, "F": 250}
        stars_map = {"S": 3, "A": 3, "B": 2, "C": 1, "F": 1}
        score = scores_map.get(rango, 250)
        stars = stars_map.get(rango, 1)

        await db[COLL_USER_ATTEMPTS].find_one_and_update(
            {"user_id": user_id, "game_id": "narrativo", "date": date_str},
            {
                "$set": {
                    "user_id": user_id,
                    "game_id": "narrativo",
                    "date": date_str,
                    "mode": "daily",
                    "status": status_str,
                    "attempts": run_doc.get("mes_actual", 1),
                    "stars": stars,
                    "score": score,
                    "game_data": {
                        "rango": rango,
                        "mes_final": run_doc.get("mes_actual", 1),
                        "recursos_finales": run_doc.get("recursos", {}),
                        "finalizacion": run_doc.get("finalizacion")
                    },
                    "updated_at": datetime.now(timezone.utc)
                }
            },
            upsert=True
        )
    except Exception as e:
        logger.warning(f"Aviso al sincronizar partida narrativa con user_attempts: {e}")
