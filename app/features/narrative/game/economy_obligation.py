"""Obligación económica durable del cierre narrativo.

El cierre confirma la run y embebe ``liquidacion`` en la misma escritura. La
aplicación (intento + acreditación) ocurre después y es idempotente: si el
proceso cae, el reconciliador descubre la obligación pendiente. Un crédito que
alcanzó a aplicarse antes de la caída no se vuelve a acreditar porque la clave
del ledger es la misma y ``ledger_applied`` bloquea el segundo ``$inc``.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from app.core.database import get_database
from app.features.narrative.constants import COLL_RUNS
from app.features.narrative.game.command_protocol import Principal
from app.features.narrative.game.endings_service import (
    estrellas_por_rango,
    registrar_intento_narrativo,
)
from app.shared.clock import now_utc
from app.shared.economy_points import (
    DEFAULT_PUNTOS_POR_CALIFICACION,
    obtener_puntos_por_calificacion,
)
from app.shared.ledger import LedgerKey, get_points_ledger

logger = logging.getLogger(__name__)

ESTADO_PENDIENTE = "pendiente"
ESTADO_LIQUIDADA = "liquidada"
ESTADO_LOCAL = "local"


def reward_id(principal: Principal, date_str: str) -> str:
    return f"reward:narrativo:{principal.key}:{date_str}"


async def construir_obligacion(
    run_final: Dict[str, Any], *, creada_en: datetime
) -> Optional[Dict[str, Any]]:
    """Obligación a persistir junto al cierre; ``None`` si no hay nada que liquidar."""
    status = run_final.get("status")
    if status not in ("completed", "game_over"):
        return None
    date_str = run_final.get("date")
    if not date_str:
        return None

    guest_id = run_final.get("guest_id")
    if guest_id and status != "completed":
        # El invitado derrotado no genera intento ni auditoría de recompensa.
        return None

    rango = (run_final.get("finalizacion") or {}).get("rango", "F")
    grade = rango if rango in DEFAULT_PUNTOS_POR_CALIFICACION else "F"
    puntos = 0
    if status == "completed":
        puntos = int((await obtener_puntos_por_calificacion()).get(grade, 0))

    principal = Principal(int(run_final.get("user_id") or 0), guest_id or None)
    return {
        "rewardId": reward_id(principal, date_str),
        "estado": ESTADO_PENDIENTE,
        "puntos": puntos,
        "canal": "local" if guest_id else "ledger",
        "grade": grade,
        "rango": rango,
        "creada_en": creada_en,
    }


async def aplicar_liquidacion(run_doc: Dict[str, Any]) -> Tuple[int, str]:
    """Aplica la obligación embebida. Devuelve ``(puntos aplicados, estado final)``."""
    liquidacion = run_doc.get("liquidacion") or {}
    estado = liquidacion.get("estado")
    if estado != ESTADO_PENDIENTE:
        return 0, estado or "ausente"

    user_id = int(run_doc.get("user_id") or 0)
    guest_id = run_doc.get("guest_id")
    date_str = run_doc.get("date")
    if not date_str:
        return 0, ESTADO_PENDIENTE

    is_completed = run_doc.get("status") == "completed"
    grade = liquidacion.get("grade") or "F"
    rango = liquidacion.get("rango") or grade
    puntos = int(liquidacion.get("puntos") or 0)
    aplicado = 0

    if guest_id:
        if is_completed and puntos > 0:
            clave = f"guest_narrative:{guest_id}:narrativo:{date_str}"
            insertado = await get_points_ledger().record_event(
                user_id=0,
                motivo="guest_narrative",
                puntos=puntos,
                idempotency_key=clave,
                metadata={
                    "guest_id": guest_id,
                    "game_id": "narrativo",
                    "date": date_str,
                    "difficulty": "normal",
                    "grade": grade,
                    "rango": rango,
                    "mes_final": run_doc.get("mes_actual", 1),
                    "reward_id": liquidacion.get("rewardId"),
                },
                status="recorded",
            )
            if insertado:
                aplicado = puntos
        estado_final = ESTADO_LOCAL
    else:
        # El puntaje del intento es el snapshot del catálogo tomado al confirmar.
        score, stars = (
            (int(puntos), estrellas_por_rango(grade)) if is_completed else (0, 0)
        )
        await registrar_intento_narrativo(
            user_id,
            date_str,
            status_str="completed" if is_completed else "failed",
            attempts=run_doc.get("mes_actual", 1),
            stars=stars,
            score=score,
            grade=grade,
            game_data={
                "rango": rango,
                "mes_final": run_doc.get("mes_actual", 1),
                "recursos_finales": run_doc.get("recursos", {}),
                "finalizacion": run_doc.get("finalizacion"),
                "reward_id": liquidacion.get("rewardId"),
            },
        )
        if is_completed and puntos > 0:
            resultado = await get_points_ledger().credit(
                LedgerKey(
                    user_id=user_id,
                    motivo="attempt",
                    game_id="narrativo",
                    date=date_str,
                    difficulty="normal",
                ),
                puntos,
                metadata={
                    "grade": grade,
                    "rango": rango,
                    "source": "narrativo",
                    "reward_id": liquidacion.get("rewardId"),
                },
            )
            aplicado = puntos if resultado.applied else 0
        estado_final = ESTADO_LIQUIDADA

    await get_database()[COLL_RUNS].update_one(
        {"_id": run_doc["_id"], "liquidacion.estado": ESTADO_PENDIENTE},
        {
            "$set": {
                "liquidacion.estado": estado_final,
                "liquidacion.liquidada_en": now_utc(),
            }
        },
    )
    return aplicado, estado_final


async def reconciliar_liquidaciones_pendientes(older_than_seconds: int = 60) -> int:
    """Descubre cierres sin asiento y los liquida con las claves idempotentes."""
    cutoff = now_utc() - timedelta(seconds=older_than_seconds)
    cursor = get_database()[COLL_RUNS].find(
        {
            "liquidacion.estado": ESTADO_PENDIENTE,
            "liquidacion.creada_en": {"$lt": cutoff},
        }
    )
    procesadas = 0
    async for run_doc in cursor:
        try:
            await aplicar_liquidacion(run_doc)
            procesadas += 1
        except Exception:
            logger.exception(
                "No se pudo liquidar la partida narrativa %s", run_doc.get("_id")
            )
    return procesadas
