"""
turn_service.py (Motor V2)
Rama V2 de la Fase 1: sortea un grafo de evento y arranca su nodo raíz.
La resolución paso a paso ocurre en `graph_engine` vía `/v2/partida/avanzar-nodo`.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import HTTPException

from app.features.narrative.enums import RunPhaseEnum
from app.features.narrative.schemas.game_schemas import ElegirCartaMesV2Response
from app.features.narrative.game.motor_v2.graph_engine import graph_engine
from app.features.narrative.game.run_repository import persistir_run

logger = logging.getLogger(__name__)


async def iniciar_evento_grafo_mes(
    run: Dict[str, Any],
    turno: Dict[str, Any]
) -> ElegirCartaMesV2Response:
    """Rama V2 de la Fase 1: inicia un grafo de evento para el universo de la partida."""
    evento_v2 = await graph_engine.sortear_evento_v2(
        run=run,
        pool_ids=None,
        universo_id=run.get("universo_id", "corte_medieval")
    )
    if not evento_v2:
        raise HTTPException(status_code=500, detail="No hay eventos V2 disponibles o elegibles en el universo.")

    turno["evento_actual_id"] = evento_v2["_id"]
    run["fase_actual"] = RunPhaseEnum.TOMA_DECISION_EVENTO.value
    estado = await graph_engine.iniciar_grafo_en_partida(
        run=run,
        grafo=evento_v2,
        tipo="evento",
        fase=RunPhaseEnum.TOMA_DECISION_EVENTO.value
    )
    run["updated_at"] = datetime.now(timezone.utc).isoformat()
    await persistir_run(run)

    return ElegirCartaMesV2Response(
        fase_actual=run["fase_actual"],
        recursos=run["recursos"],
        evento_actual=None,
        grafo_actual=estado,
        finalizacion=None,
        motor=run.get("motor", "v1"),
    )
