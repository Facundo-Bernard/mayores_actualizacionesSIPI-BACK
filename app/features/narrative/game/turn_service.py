"""
turn_service.py
Fase 1 común a ambos motores: valida el draft, aplica la carta elegida y deriva
al motor de la partida para abrir el evento del mes.
- Motor V1: sorteo plano del evento con probabilidades (motor_v1.turn_service).
- Motor V2: inicio de un grafo de evento (motor_v2.turn_service).
"""

import logging
from datetime import datetime, timezone

from fastapi import HTTPException

from app.core.database import get_database
from app.features.narrative.constants import (
    COLL_CARDS,
    COLL_RUNS,
)
from app.features.narrative.enums import (
    RunPhaseEnum,
    DisparadorEnum
)
from app.features.narrative.schemas.rules_schemas import EfectoSchema
from app.features.narrative.schemas.catalog_schemas import FinalizacionResponse
from app.features.narrative.schemas.game_schemas import (
    ElegirCartaMesRequest,
    ElegirCartaMesV2Response,
)
from app.features.narrative.engine.rule_engine import despachar_efectos
from app.features.narrative.game.endings_service import (
    verificar_colapso_recursos,
    sincronizar_intento_usuario
)
from app.features.narrative.game.universe_resources import obtener_mapa_recursos_universo
from app.features.narrative.game.run_repository import persistir_run
from app.features.narrative.game.identity import filtro_run
from app.features.narrative.game.motor_v1.turn_service import sortear_evento_plano
from app.features.narrative.game.motor_v2.turn_service import iniciar_evento_grafo_mes

logger = logging.getLogger(__name__)


async def elegir_carta_mes(user_id: int, req: ElegirCartaMesRequest) -> ElegirCartaMesV2Response:
    """
    Fase 1: aplica la carta elegida del draft, descuenta sus efectos y abre el evento del mes
    con el motor de la partida. Retorna el evento plano (V1) o el grafo inicial (V2).
    """
    db = get_database()
    run = await db[COLL_RUNS].find_one(filtro_run(user_id, req.date))
    if not run:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")

    if run.get("fase_actual") != RunPhaseEnum.DRAFT_MENSUAL.value:
        raise HTTPException(status_code=400, detail="La partida no se encuentra en fase de robo de cartas.")

    turno = run.get("turno_actual", {})
    if req.carta_id not in turno.get("cartas_ofrecidas_ids", []):
        raise HTTPException(status_code=400, detail="La carta seleccionada no fue ofrecida en este mes.")

    # 1. Agregar carta al inventario y registrar nuevos tags
    run["cartas_en_mano"].append(req.carta_id)
    carta_doc = await db[COLL_CARDS].find_one({"_id": req.carta_id})
    if carta_doc:
        for t in carta_doc.get("tags", []):
            if t not in run["tags_activos"]:
                run["tags_activos"].append(t)

        recursos_mapa = await obtener_mapa_recursos_universo(run["universo_id"])
        efectos_carta = [EfectoSchema(**e) for e in carta_doc.get("efectos", [])]
        despachar_efectos(DisparadorEnum.AL_OBTENER, run, efectos_carta, recursos_mapa)

    turno["carta_elegida_id"] = req.carta_id

    # Si la carta elegida causa el colapso inmediato de un recurso:
    derrota = await verificar_colapso_recursos(run)
    if derrota:
        run["updated_at"] = datetime.now(timezone.utc).isoformat()
        await persistir_run(run)
        puntos_ganados = await sincronizar_intento_usuario(run)
        fin_resp = FinalizacionResponse(**run["finalizacion"]) if run.get("finalizacion") else None
        return ElegirCartaMesV2Response(
            fase_actual=run["fase_actual"],
            recursos=run["recursos"],
            evento_actual=None,
            finalizacion=fin_resp,
            puntos_ganados=puntos_ganados,
            motor=run.get("motor", "v1"),
        )

    if run.get("motor") == "v2":
        return await iniciar_evento_grafo_mes(run, turno)

    return await sortear_evento_plano(run, req, turno)
