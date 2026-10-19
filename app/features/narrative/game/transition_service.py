"""
transition_service.py
Gestión de la Fase 4 (Balance y Transición Mensual):
- Registro del resumen del mes en la bitácora acumulada (historial).
- Evaluación de fin de año (Mes 12: Victoria y cálculo de rango S/A/B/C).
- Avance al siguiente mes (Mes + 1).
- Despacho de efectos pasivos recurrentes (CADA_MES) de corte y cartas.
- Verificación de colapso de recursos post-pasivos.
- Sorteo de las 3 cartas para el nuevo draft.
"""

import random
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import HTTPException

from app.core.database import get_database
from app.features.narrative.constants import (
    COLL_SETTINGS,
    COLL_CHARACTERS,
    COLL_CARDS,
    COLL_RUNS,
    COLL_CHALLENGES
)
from app.features.narrative.enums import (
    RunPhaseEnum,
    DisparadorEnum
)
from app.features.narrative.schemas.catalog_schemas import (
    CartaResponse,
    FinalizacionResponse
)
from app.features.narrative.schemas.game_schemas import (
    AvanzarMesRequest,
    AvanzarMesV2Response
)
from app.features.narrative.schemas.rules_schemas import EfectoSchema
from app.features.narrative.engine.rule_engine import despachar_efectos
from app.features.narrative.game.endings_service import (
    verificar_colapso_recursos,
    calcular_finalizacion_victoria,
    sincronizar_intento_usuario
)
from app.features.narrative.game.setup_service import _obtener_mapa_recursos_universo

logger = logging.getLogger(__name__)

async def avanzar_mes_v2(user_id: int, req: AvanzarMesRequest) -> AvanzarMesV2Response:
    """
    [V2 Nativo] Fase 4: Aplica efectos pasivos 'cada_mes' y avanza al siguiente mes.
    Retorna los recursos post-pasivos y únicamente las 3 nuevas cartas de draft (o epílogo si terminó).
    """
    db = get_database()
    run = await db[COLL_RUNS].find_one({"user_id": user_id, "date": req.date, "game_id": "narrativo"})
    if not run:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")

    if run.get("fase_actual") != RunPhaseEnum.BALANCE_MES.value:
        raise HTTPException(status_code=400, detail="La partida no se encuentra en fase de balance mensual.")

    turno = run.get("turno_actual", {})
    mes_actual = run.get("mes_actual", 1)

    # 1. Guardar resumen del mes en historial acumulado
    historial_item = {
        "mes": mes_actual,
        "carta_elegida_id": turno.get("carta_elegida_id"),
        "evento_id": turno.get("evento_actual_id"),
        "opcion_elegida_id": turno.get("opcion_elegida_id"),
        "resultado_id": turno.get("resultado_obtenido_id"),
        "conversacion_id": turno.get("conversacion_actual_id"),
        "decision_conversacion_opcion": turno.get("decision_conversacion_opcion"),
        "recursos_fin_mes": dict(run.get("recursos", {}))
    }
    run["historial_mensual"].append(historial_item)

    if turno.get("evento_actual_id"):
        run["eventos_jugados"].append(turno.get("evento_actual_id"))

    # 2. ¿Llegó al Mes 12? Fin de Partida (Victoria Anual)
    if mes_actual >= 12:
        run["fase_actual"] = RunPhaseEnum.FINALIZADA.value
        run["status"] = "completed"
        universo_doc = await db[COLL_SETTINGS].find_one({"_id": run.get("universo_id")})
        run["finalizacion"] = calcular_finalizacion_victoria(run, universo_doc)
        run["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db[COLL_RUNS].replace_one({"_id": run["_id"]}, run)
        await sincronizar_intento_usuario(run)
        fin_resp = FinalizacionResponse(**run["finalizacion"]) if run.get("finalizacion") else None
        return AvanzarMesV2Response(
            mes_actual=run["mes_actual"],
            fase_actual=run["fase_actual"],
            status=run["status"],
            recursos=run["recursos"],
            cartas_draft_actual=[],
            finalizacion=fin_resp
        )

    # Avanzar al siguiente mes
    run["mes_actual"] = mes_actual + 1
    run["fase_actual"] = RunPhaseEnum.DRAFT_MENSUAL.value

    # Aplicar efectos pasivos "cada_mes"
    recursos_mapa = await _obtener_mapa_recursos_universo(run["universo_id"])
    corte_ids = list(run.get("afinidad", {}).keys()) or run.get("corte_activa", [])
    personajes_docs = await db[COLL_CHARACTERS].find({"_id": {"$in": corte_ids}}).to_list(None)
    cartas_docs = await db[COLL_CARDS].find({"_id": {"$in": run["cartas_en_mano"]}}).to_list(None)

    for p in personajes_docs:
        efectos_p = [EfectoSchema(**e) for e in p.get("efectos", [])]
        despachar_efectos(DisparadorEnum.CADA_MES, run, efectos_p, recursos_mapa)

    for c in cartas_docs:
        efectos_c = [EfectoSchema(**e) for e in c.get("efectos", [])]
        despachar_efectos(DisparadorEnum.CADA_MES, run, efectos_c, recursos_mapa)

    # Si algún recurso colapsó por costos mensuales pasivos:
    derrota = await verificar_colapso_recursos(run)
    if derrota:
        run["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db[COLL_RUNS].replace_one({"_id": run["_id"]}, run)
        await sincronizar_intento_usuario(run)
        fin_resp = FinalizacionResponse(**run["finalizacion"]) if run.get("finalizacion") else None
        return AvanzarMesV2Response(
            mes_actual=run["mes_actual"],
            fase_actual=run["fase_actual"],
            status=run["status"],
            recursos=run["recursos"],
            cartas_draft_actual=[],
            finalizacion=fin_resp
        )

    # Sortear 3 cartas para el nuevo mes
    challenge = await db[COLL_CHALLENGES].find_one({"game_id": "narrativo", "date": req.date})
    pool_mensuales = challenge.get("config", {}).get("pool_cartas_mensuales_ids", [])
    disponibles = [cid for cid in pool_mensuales if cid not in run["cartas_en_mano"]]
    if len(disponibles) < 3:
        disponibles = pool_mensuales

    cartas_sorteadas = random.sample(disponibles, min(3, len(disponibles)))
    run["turno_actual"] = {
        "cartas_ofrecidas_ids": cartas_sorteadas,
        "carta_elegida_id": None,
        "evento_actual_id": None,
        "opcion_elegida_id": None,
        "resultado_obtenido_id": None,
        "conversacion_actual_id": None
    }

    run["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db[COLL_RUNS].replace_one({"_id": run["_id"]}, run)

    # Cargar ÚNICAMENTE las 3 cartas sorteadas para la respuesta
    draft_docs = await db[COLL_CARDS].find({"_id": {"$in": cartas_sorteadas}}).to_list(None)
    cartas_draft_resp = [CartaResponse(**c) for c in draft_docs]

    return AvanzarMesV2Response(
        mes_actual=run["mes_actual"],
        fase_actual=run["fase_actual"],
        status=run["status"],
        recursos=run["recursos"],
        cartas_draft_actual=cartas_draft_resp,
        finalizacion=None
    )
