"""
turn_service.py
Gestión de las Fases 1, 2 y 3 del ciclo mensual:
- Fase 1: Selección de carta del draft mensual y sorteo ponderado del evento del mes.
- Fase 2: Toma de decisión ante el evento, tirada de dados y activación de diálogos de corte.
- Fase 3: Respuesta al diálogo incidental entre consejeros.
"""

import random
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import HTTPException

from app.core.database import get_database
from app.features.narrative.constants import (
    COLL_CHARACTERS,
    COLL_CARDS,
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
from app.features.narrative.game.setup_service import _obtener_mapa_recursos_universo

logger = logging.getLogger(__name__)

# ============================================================================
# FASE 1: ELECCIÓN DE CARTA DEL MES Y APERTURA DEL EVENTO
# ============================================================================

async def elegir_carta_mes_v2(user_id: int, req: ElegirCartaMesRequest) -> ElegirCartaMesV2Response:
    """
    [V2 Nativo] Fase 1: Aplica la carta elegida del draft, sortea el evento del mes y calcula
    las probabilidades de sus opciones. Retorna únicamente el evento y los recursos vivos.
    """
    db = get_database()
    run = await db[COLL_RUNS].find_one({"user_id": user_id, "date": req.date, "game_id": "narrativo"})
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

        recursos_mapa = await _obtener_mapa_recursos_universo(run["universo_id"])
        efectos_carta = [EfectoSchema(**e) for e in carta_doc.get("efectos", [])]
        despachar_efectos(DisparadorEnum.AL_OBTENER, run, efectos_carta, recursos_mapa)

    turno["carta_elegida_id"] = req.carta_id

    # Si la carta elegida causa el colapso inmediato de un recurso:
    derrota = await verificar_colapso_recursos(run)
    if derrota:
        run["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db[COLL_RUNS].replace_one({"_id": run["_id"]}, run)
        await sincronizar_intento_usuario(run)
        fin_resp = FinalizacionResponse(**run["finalizacion"]) if run.get("finalizacion") else None
        return ElegirCartaMesV2Response(
            fase_actual=run["fase_actual"],
            recursos=run["recursos"],
            evento_actual=None,
            finalizacion=fin_resp
        )

    # 2. Sortear el Evento del Mes con el Director Narrativo
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

    await db[COLL_RUNS].replace_one({"_id": run["_id"]}, run)

    # Cargar y calcular probabilidades únicamente para el evento sorteado
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
        finalizacion=None
    )

# ============================================================================
# FASE 2: RESOLUCIÓN DE EVENTO Y TIRADA PONDERADA
# ============================================================================

async def decidir_evento_v2(user_id: int, req: DecidirEventoRequest) -> DecidirEventoV2Response:
    """
    [V2 Nativo] Fase 2: Ejecuta la tirada ponderada de la opción elegida, aplica consecuencias,
    y sortea diálogo incidental si aplica. Retorna únicamente el resultado obtenido y el diálogo.
    """
    db = get_database()
    run = await db[COLL_RUNS].find_one({"user_id": user_id, "date": req.date, "game_id": "narrativo"})
    if not run:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")

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

    recursos_mapa = await _obtener_mapa_recursos_universo(run["universo_id"])
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
        await db[COLL_RUNS].replace_one({"_id": run["_id"]}, run)
        await sincronizar_intento_usuario(run)
        fin_resp = FinalizacionResponse(**run["finalizacion"]) if run.get("finalizacion") else None
        res_dto = ResultadoResponse(**res_doc)
        return DecidirEventoV2Response(
            fase_actual=run["fase_actual"],
            recursos=run["recursos"],
            resultado_actual=res_dto,
            conversacion_actual=None,
            finalizacion=fin_resp
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
    await db[COLL_RUNS].replace_one({"_id": run["_id"]}, run)

    res_dto = ResultadoResponse(**res_doc)
    return DecidirEventoV2Response(
        fase_actual=run["fase_actual"],
        recursos=run["recursos"],
        resultado_actual=res_dto,
        conversacion_actual=conversacion_dto,
        finalizacion=None
    )

# ============================================================================
# FASE 3: RESPUESTA AL DIÁLOGO INCIDENTAL DE CORTE
# ============================================================================

async def responder_conversacion_v2(user_id: int, req: ResponderConversacionRequest) -> ResponderConversacionV2Response:
    """
    [V2 Nativo] Fase 3: Aplica la respuesta del diálogo con el consejero.
    Retorna afinidades actualizadas y texto de consecuencia en 1 única lectura y guardado.
    """
    db = get_database()
    run = await db[COLL_RUNS].find_one({"user_id": user_id, "date": req.date, "game_id": "narrativo"})
    if not run:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")

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

    # Modificar afinidades según la respuesta
    for imp in decision.get("impacto_afinidad", []):
        pid = imp.get("personaje_id")
        delta = int(imp.get("delta", 0))
        if pid in run["afinidad"]:
            run["afinidad"][pid] = max(0, min(100, run["afinidad"][pid] + delta))

    turno["decision_conversacion_opcion"] = req.opcion_numero
    run["fase_actual"] = RunPhaseEnum.BALANCE_MES.value
    run["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db[COLL_RUNS].replace_one({"_id": run["_id"]}, run)

    return ResponderConversacionV2Response(
        fase_actual=run["fase_actual"],
        afinidad=run["afinidad"],
        resultado_texto=decision.get("resultado_texto", ""),
        impacto_afinidad=decision.get("impacto_afinidad", [])
    )
