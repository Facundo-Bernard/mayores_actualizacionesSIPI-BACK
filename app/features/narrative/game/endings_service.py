"""
endings_service.py
Gestión común de desenlaces de partida (victoria en Mes 12 o derrota por colapso de recursos)
y sincronización del intento del alumno con la colección user_attempts para progreso y rachas.
Compartido por los motores V1 y V2.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from pymongo.errors import DuplicateKeyError

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
from app.shared.economy_points import DEFAULT_PUNTOS_POR_CALIFICACION, obtener_puntos_por_calificacion
from app.shared.ledger import LedgerKey, get_points_ledger

logger = logging.getLogger(__name__)

async def verificar_colapso_recursos(run_doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Verifica si algún recurso vital (oro, comida, moral, defensa) llegó a <= 0.
    En tal caso, asocia la finalización correspondiente al recurso agotado, marca la run
    como 'game_over' y 'FINALIZADA', persistiendo el epílogo de la derrota.
    """
    recursos = run_doc.get("recursos", {})
    limites = run_doc.get("limites", {})
    recurso_agotado = None
    for k, val in recursos.items():
        limite_min = 0.0
        if isinstance(limites.get(k), dict) and "min" in limites[k]:
            limite_min = float(limites[k]["min"])
        if val is not None and float(val) <= limite_min:
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

# Estrellas por rango: mismo criterio que muestra el panel de administración.
ESTRELLAS_POR_RANGO = {"S": 3, "A": 3, "B": 2, "C": 1, "F": 0}


def estrellas_por_rango(rango: str) -> int:
    return ESTRELLAS_POR_RANGO.get(rango, 0)


def calificar_intento(
    rango: str,
    puntos_por_calificacion: Dict[str, int],
    *,
    completado: bool,
) -> tuple[int, int]:
    """Puntaje y estrellas del intento según el catálogo editable del panel."""
    if not completado:
        return 0, 0
    return int(puntos_por_calificacion.get(rango, 0)), estrellas_por_rango(rango)


async def registrar_intento_narrativo(
    user_id: int,
    date_str: str,
    *,
    status_str: str,
    attempts: int,
    stars: int,
    score: int,
    grade: str,
    game_data: Dict[str, Any],
) -> None:
    """Upsert del intento diario; el primer intento completado no se degrada.

    El filtro con ``status != completed`` y el upsert dejan que una derrota
    cree el intento o actualice uno fallido, pero nunca pise uno completado:
    un reinicio en el mismo día no puede quitar la racha ni bajar el score.
    """
    try:
        await get_database()[COLL_USER_ATTEMPTS].update_one(
            {
                "user_id": user_id,
                "game_id": "narrativo",
                "date": date_str,
                "status": {"$ne": "completed"},
            },
            {
                "$set": {
                    "user_id": user_id,
                    "game_id": "narrativo",
                    "date": date_str,
                    "difficulty": "normal",
                    "mode": "daily",
                    "status": status_str,
                    "attempts": attempts,
                    "stars": stars,
                    "score": score,
                    "grade": grade,
                    "game_data": game_data,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
    except DuplicateKeyError:
        # Ya existe el intento completado del día; se conserva sin degradar.
        pass


async def sincronizar_intento_usuario(run_doc: Dict[str, Any]) -> int:
    """
    Registra el intento narrativo y acredita puntos al cerrar la partida.

    - Autenticados: intento en ``user_attempts`` + asiento idempotente en el ledger
      con clave ``(usuario, narrativo, fecha, normal)``.
    - Invitados (``guest_id``): no se escribe ``user_attempts`` ni se toca ``usuarios``;
      se devuelven los puntos para que el cliente los guarde localmente y se audita el cierre.

    Devuelve los puntos ganados en esta llamada (0 si es replay, derrota o invitado repetido).
    """
    try:
        db = get_database()
        user_id = int(run_doc.get("user_id") or 0)
        guest_id = run_doc.get("guest_id")
        date_str = run_doc.get("date")
        if not date_str or (user_id <= 0 and not guest_id):
            return 0

        is_completed = run_doc.get("status") == "completed"
        rango = run_doc.get("finalizacion", {}).get("rango", "F")
        grade = rango if rango in DEFAULT_PUNTOS_POR_CALIFICACION else "F"

        if guest_id:
            if not is_completed:
                return 0
            puntos_config = await obtener_puntos_por_calificacion()
            puntos = int(puntos_config.get(grade, 0))
            idempotency_key = f"guest_narrative:{guest_id}:narrativo:{date_str}"
            if await db["economy_ledger"].find_one({"_id": idempotency_key}):
                return 0
            await get_points_ledger().record_event(
                user_id=0,
                motivo="guest_narrative",
                puntos=puntos,
                idempotency_key=idempotency_key,
                metadata={
                    "guest_id": guest_id,
                    "game_id": "narrativo",
                    "date": date_str,
                    "difficulty": "normal",
                    "grade": grade,
                    "rango": rango,
                    "mes_final": run_doc.get("mes_actual", 1),
                },
                status="recorded",
            )
            return puntos

        status_str = "completed" if is_completed else "failed"
        puntos_config = await obtener_puntos_por_calificacion()
        score, stars = calificar_intento(
            grade, puntos_config, completado=is_completed
        )

        await registrar_intento_narrativo(
            user_id,
            date_str,
            status_str=status_str,
            attempts=run_doc.get("mes_actual", 1),
            stars=stars,
            score=score,
            grade=grade,
            game_data={
                "rango": rango,
                "mes_final": run_doc.get("mes_actual", 1),
                "recursos_finales": run_doc.get("recursos", {}),
                "finalizacion": run_doc.get("finalizacion"),
            },
        )

        if not is_completed:
            return 0

        puntos = score
        if puntos <= 0:
            return 0

        resultado = await get_points_ledger().credit(
            LedgerKey(
                user_id=user_id,
                motivo="attempt",
                game_id="narrativo",
                date=date_str,
                difficulty="normal",
            ),
            puntos,
            metadata={"grade": grade, "rango": rango, "source": "narrativo"},
        )
        return puntos if resultado.applied else 0
    except Exception as e:
        logger.warning(f"Aviso al sincronizar partida narrativa con user_attempts: {e}")
        return 0
