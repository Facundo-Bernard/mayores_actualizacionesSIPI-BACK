"""
turn_service.py (Motor V1)
Resolución plana del ciclo mensual:
- Fase 1 (rama V1): sorteo ponderado del evento del mes y cálculo de probabilidades.
- Fase 2: tirada de dados sobre la opción elegida y activación del diálogo incidental.
- Fase 3: respuesta al diálogo entre consejeros.

Estas dos últimas rutas quedan deprecadas: el motor de grafos V2 las reemplaza por
`avanzar-nodo`. Se retirarán cuando todos los universos migren a V2.
"""

import random
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import HTTPException

from app.core.database import get_database
from app.features.narrative.constants import (
    COLL_CHARACTERS,
    COLL_RESULTS,
    COLL_EVENTS,
    COLL_CONVERSATIONS,
    COLL_RUNS,
    COLL_CHALLENGES
)
from app.features.narrative.enums import (
    RunPhaseEnum,
    DisparadorEnum
)
from app.features.narrative.schemas.rules_schemas import (
    EfectoSchema,
    CondicionSchema
)
from app.features.narrative.schemas.catalog_schemas import (
    ResultadoResponse,
    ConversacionResponse,
    FinalizacionResponse
)
from app.features.narrative.schemas.game_schemas import (
    ElegirCartaMesRequest,
    DecidirEventoRequest,
    ResponderConversacionRequest,
    ElegirCartaMesV2Response,
    DecidirEventoV2Response,
    ResponderConversacionV2Response,
    EventoTurnoResponse
)
from app.features.narrative.engine.rule_engine import despachar_efectos, evaluar_condiciones
from app.features.narrative.engine.event_director import (
    seleccionar_evento_mes,
    sortear_resultado_opcion,
    calcular_opciones_evento
)
from app.features.narrative.game.endings_service import (
    verificar_colapso_recursos,
    sincronizar_intento_usuario
)
from app.features.narrative.game.universe_resources import obtener_mapa_recursos_universo
from app.features.narrative.game.run_repository import persistir_run
from app.features.narrative.game.identity import filtro_run

logger = logging.getLogger(__name__)

_AVISOS_EMITIDOS: set[str] = set()


def _avisar_deprecado(nombre: str) -> None:
    if nombre not in _AVISOS_EMITIDOS:
        _AVISOS_EMITIDOS.add(nombre)
        logger.warning(
            "Endpoint plano V1 '%s' en desuso; se retirará cuando los universos migren a V2.",
            nombre,
        )


async def sortear_evento_plano(
    run: Dict[str, Any],
    req: ElegirCartaMesRequest,
    turno: Dict[str, Any]
) -> ElegirCartaMesV2Response:
    """Rama V1 de la Fase 1: sortea el evento plano del desafío y calcula sus probabilidades."""
    db = get_database()
    challenge = await db[COLL_CHALLENGES].find_one({"game_id": "narrativo", "date": req.date})
    pool_eventos_ids = challenge.get("config", {}).get("pool_eventos_disponibles_ids", [])

    eventos_candidatos = await db[COLL_EVENTS].find({"_id": {"$in": pool_eventos_ids}}).to_list(None)
    corte_ids = list(run.get("afinidad", {}).keys()) or run.get("corte_activa", [])
    personajes_activos = await db[COLL_CHARACTERS].find(
        {"_id": {"$in": corte_ids}},
        {"_id": 1, "tags": 1}
    ).to_list(None)
    cartas_activas_mock = [{"tags": run.get("tags_activos", [])}]

    evento_seleccionado = seleccionar_evento_mes(
        eventos_candidatos=eventos_candidatos,
        run_data=run,
        personajes_activos=personajes_activos,
        cartas_activas=cartas_activas_mock,
        eventos_jugados=run.get("eventos_jugados", [])
    )

    if not evento_seleccionado:
        raise HTTPException(status_code=500, detail="No hay eventos disponibles en el pool del desafío.")

    turno["evento_actual_id"] = evento_seleccionado["_id"]
    run["fase_actual"] = RunPhaseEnum.TOMA_DECISION_EVENTO.value
    run["updated_at"] = datetime.now(timezone.utc).isoformat()

    await persistir_run(run)

    res_ids = set()
    for op in evento_seleccionado.get("opciones", []):
        for rp in op.get("resultados_posibles", []):
            res_ids.add(rp.get("resultado_id"))
    resultados_docs = await db[COLL_RESULTS].find({"_id": {"$in": list(res_ids)}}).to_list(None) if res_ids else []
    res_dict = {r["_id"]: r for r in resultados_docs}

    opciones_calc = calcular_opciones_evento(evento_seleccionado, run, res_dict)
    evento_dto = EventoTurnoResponse(
        id=evento_seleccionado["_id"],
        titulo=evento_seleccionado.get("titulo", ""),
        descripcion=evento_seleccionado.get("descripcion", ""),
        imagen=evento_seleccionado.get("imagen", ""),
        opciones=opciones_calc
    )

    return ElegirCartaMesV2Response(
        fase_actual=run["fase_actual"],
        recursos=run["recursos"],
        evento_actual=evento_dto,
        finalizacion=None,
        motor=run.get("motor", "v1"),
    )


async def decidir_evento(user_id: int, req: DecidirEventoRequest) -> DecidirEventoV2Response:
    """[V1 Plano] Fase 2: tirada ponderada de la opción elegida, consecuencias y diálogo incidental."""
    _avisar_deprecado("decidir-evento")
    db = get_database()
    run = await db[COLL_RUNS].find_one(filtro_run(user_id, req.date))
    if not run:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")

    if run.get("motor", "v1") == "v2":
        raise HTTPException(
            status_code=409,
            detail="La partida usa el motor V2 de grafos; resolvé el evento con '/api/narrative/v2/partida/avanzar-nodo'."
        )

    if run.get("fase_actual") != RunPhaseEnum.TOMA_DECISION_EVENTO.value:
        raise HTTPException(status_code=400, detail="La partida no se encuentra en fase de decisión de evento.")

    turno = run.get("turno_actual", {})
    evento_id = turno.get("evento_actual_id")
    evento_doc = await db[COLL_EVENTS].find_one({"_id": evento_id})
    if not evento_doc:
        raise HTTPException(status_code=404, detail="Evento actual no encontrado.")

    opcion_elegida = next((op for op in evento_doc.get("opciones", []) if op["id"] == req.opcion_id), None)
    if not opcion_elegida:
        raise HTTPException(status_code=400, detail=f"Opción '{req.opcion_id}' no válida para este evento.")

    if opcion_elegida.get("es_secreta", False):
        condiciones = [CondicionSchema(**c) for c in opcion_elegida.get("condiciones", [])]
        if not evaluar_condiciones(condiciones, run):
            raise HTTPException(status_code=403, detail="No cumples los requisitos para esta opción secreta.")

    # 1. Tirada ponderada para determinar el desenlace ganador
    resultado_ganador_id = sortear_resultado_opcion(opcion_elegida, run)
    turno["opcion_elegida_id"] = req.opcion_id
    turno["resultado_obtenido_id"] = resultado_ganador_id

    # 2. Aplicar los efectos del resultado
    res_doc = await db[COLL_RESULTS].find_one({"_id": resultado_ganador_id})
    if not res_doc:
        raise HTTPException(status_code=500, detail="No se encontró el desenlace obtenido en la base de datos.")

    recursos_mapa = await obtener_mapa_recursos_universo(run["universo_id"])
    efectos_res = [EfectoSchema(**e) for e in res_doc.get("efectos", [])]
    despachar_efectos(DisparadorEnum.AL_OBTENER, run, efectos_res, recursos_mapa)

    for imp in res_doc.get("impacto_afinidad", []):
        pid = imp.get("personaje_id")
        delta = int(imp.get("delta", 0))
        if pid in run["afinidad"]:
            run["afinidad"][pid] = max(0, min(100, run["afinidad"][pid] + delta))

    derrota = await verificar_colapso_recursos(run)
    if derrota:
        run["updated_at"] = datetime.now(timezone.utc).isoformat()
        await persistir_run(run)
        puntos_ganados = await sincronizar_intento_usuario(run)
        fin_resp = FinalizacionResponse(**run["finalizacion"]) if run.get("finalizacion") else None
        res_dto = ResultadoResponse(**res_doc)
        return DecidirEventoV2Response(
            fase_actual=run["fase_actual"],
            recursos=run["recursos"],
            resultado_actual=res_dto,
            conversacion_actual=None,
            finalizacion=fin_resp,
            puntos_ganados=puntos_ganados,
        )

    # 3. Evaluar si ocurre conversación incidental de corte (40% de probabilidad)
    challenge = await db[COLL_CHALLENGES].find_one({"game_id": "narrativo", "date": req.date})
    conv_pool_ids = challenge.get("config", {}).get("pool_conversaciones_ids", [])

    conversaciones_jugadas = set(run.get("conversaciones_jugadas", []))
    conversacion_sorteada = None
    if conv_pool_ids and random.random() < 0.40:
        candidatas = await db[COLL_CONVERSATIONS].find({"_id": {"$in": conv_pool_ids}}).to_list(None)
        corte_set = set(run.get("afinidad", {}).keys()) or set(run.get("corte_activa", []))
        validas = []
        for conv in candidatas:
            if conv["_id"] in conversaciones_jugadas:
                continue
            reqs = [r.get("personajeId") for r in conv.get("requisitos", [])]
            if all(r in corte_set for r in reqs):
                validas.append(conv)

        if validas:
            conversacion_sorteada = random.choice(validas)

    conversacion_dto = None
    if conversacion_sorteada:
        turno["conversacion_actual_id"] = conversacion_sorteada["_id"]
        run["fase_actual"] = RunPhaseEnum.RESOLVER_CONVERSACION.value
        if "conversaciones_jugadas" not in run:
            run["conversaciones_jugadas"] = []
        if conversacion_sorteada["_id"] not in run["conversaciones_jugadas"]:
            run["conversaciones_jugadas"].append(conversacion_sorteada["_id"])
        conversacion_dto = ConversacionResponse(**conversacion_sorteada)
    else:
        turno["conversacion_actual_id"] = None
        run["fase_actual"] = RunPhaseEnum.BALANCE_MES.value

    run["updated_at"] = datetime.now(timezone.utc).isoformat()
    await persistir_run(run)

    res_dto = ResultadoResponse(**res_doc)
    return DecidirEventoV2Response(
        fase_actual=run["fase_actual"],
        recursos=run["recursos"],
        resultado_actual=res_dto,
        conversacion_actual=conversacion_dto,
        finalizacion=None
    )


async def responder_conversacion(user_id: int, req: ResponderConversacionRequest) -> ResponderConversacionV2Response:
    """[V1 Plano] Fase 3: aplica la respuesta del diálogo con el consejero."""
    _avisar_deprecado("responder-conversacion")
    db = get_database()
    run = await db[COLL_RUNS].find_one(filtro_run(user_id, req.date))
    if not run:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")

    if run.get("motor", "v1") == "v2":
        raise HTTPException(
            status_code=409,
            detail="La partida usa el motor V2 de grafos; resolvé el diálogo con '/api/narrative/v2/partida/avanzar-nodo'."
        )

    if run.get("fase_actual") != RunPhaseEnum.RESOLVER_CONVERSACION.value:
        raise HTTPException(status_code=400, detail="La partida no se encuentra en fase de diálogo.")

    turno = run.get("turno_actual", {})
    conv_id = turno.get("conversacion_actual_id")
    conv_doc = await db[COLL_CONVERSATIONS].find_one({"_id": conv_id})
    if not conv_doc:
        raise HTTPException(status_code=404, detail="Conversación no encontrada.")

    decision = next((d for d in conv_doc.get("decisiones", []) if d.get("opcion") == req.opcion_numero), None)
    if not decision:
        raise HTTPException(status_code=400, detail=f"Opción {req.opcion_numero} no válida para esta conversación.")

    for imp in decision.get("impacto_afinidad", []):
        pid = imp.get("personaje_id")
        delta = int(imp.get("delta", 0))
        if pid in run["afinidad"]:
            run["afinidad"][pid] = max(0, min(100, run["afinidad"][pid] + delta))

    turno["decision_conversacion_opcion"] = req.opcion_numero
    run["fase_actual"] = RunPhaseEnum.BALANCE_MES.value
    run["updated_at"] = datetime.now(timezone.utc).isoformat()

    await persistir_run(run)

    return ResponderConversacionV2Response(
        fase_actual=run["fase_actual"],
        afinidad=run["afinidad"],
        resultado_texto=decision.get("resultado_texto", ""),
        impacto_afinidad=decision.get("impacto_afinidad", [])
    )
