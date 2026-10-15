import random
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import HTTPException

from app.core.database import get_database
from app.features.narrative.enums import (
    RunPhaseEnum,
    DisparadorEnum,
    TipoResultadoEnum
)
from app.features.narrative.schemas import (
    UniversoCreateRequest,
    UniversoResponse,
    PersonajeCreateRequest,
    PersonajeResponse,
    CartaCreateRequest,
    CartaResponse,
    ResultadoCreateRequest,
    ResultadoResponse,
    EventoCreateRequest,
    EventoResponse,
    ConversacionCreateRequest,
    ConversacionResponse,
    NarrativeRunSchema,
    TurnoSnapshot,
    HistorialMes,
    IniciarPartidaRequest,
    ElegirCartaMesRequest,
    DecidirEventoRequest,
    ResponderConversacionRequest,
    AvanzarMesRequest,
    ReiniciarPartidaRequest,
    SetupDesafioResponse,
    EstadoPartidaActivaResponse,
    EventoTurnoResponse,
    EfectoSchema,
    CondicionSchema
)
from app.features.narrative.rule_engine import despachar_efectos, evaluar_condiciones
from app.features.narrative.event_director import (
    seleccionar_evento_mes,
    calcular_opciones_evento,
    sortear_resultado_opcion
)

logger = logging.getLogger(__name__)

# ============================================================================
# COLECCIONES EN MONGODB
# ============================================================================
COLL_SETTINGS = "narrative_settings"
COLL_CHARACTERS = "narrative_characters"
COLL_CARDS = "narrative_cards"
COLL_RESULTS = "narrative_results"
COLL_EVENTS = "narrative_events"
COLL_CONVERSATIONS = "narrative_conversations"
COLL_RUNS = "narrative_runs"
COLL_CHALLENGES = "daily_challenges"

# ============================================================================
# 1. SERVICIOS DE ADMINISTRACIÓN Y CATÁLOGO (CRUDs)
# ============================================================================

async def crear_o_actualizar_universo(req: UniversoCreateRequest) -> UniversoResponse:
    db = get_database()
    doc = req.model_dump(by_alias=True)
    await db[COLL_SETTINGS].replace_one({"_id": req.id}, doc, upsert=True)
    return UniversoResponse(**doc)

async def obtener_universos() -> List[UniversoResponse]:
    db = get_database()
    cursor = db[COLL_SETTINGS].find({})
    items = []
    async for doc in cursor:
        items.append(UniversoResponse(**doc))
    return items

async def obtener_universo_por_id(universo_id: str) -> Optional[UniversoResponse]:
    db = get_database()
    doc = await db[COLL_SETTINGS].find_one({"_id": universo_id})
    if doc:
        return UniversoResponse(**doc)
    return None

async def eliminar_universo(universo_id: str) -> bool:
    db = get_database()
    res = await db[COLL_SETTINGS].delete_one({"_id": universo_id})
    return res.deleted_count > 0

# --- Personajes ---
async def crear_o_actualizar_personaje(req: PersonajeCreateRequest) -> PersonajeResponse:
    db = get_database()
    doc = req.model_dump(by_alias=True)
    await db[COLL_CHARACTERS].replace_one({"_id": req.id}, doc, upsert=True)
    return PersonajeResponse(**doc)

async def obtener_personajes(universo_id: Optional[str] = None) -> List[PersonajeResponse]:
    db = get_database()
    query = {"universo_id": universo_id} if universo_id else {}
    cursor = db[COLL_CHARACTERS].find(query)
    items = []
    async for doc in cursor:
        items.append(PersonajeResponse(**doc))
    return items

async def eliminar_personaje(personaje_id: str) -> bool:
    db = get_database()
    res = await db[COLL_CHARACTERS].delete_one({"_id": personaje_id})
    return res.deleted_count > 0

# --- Cartas ---
async def crear_o_actualizar_carta(req: CartaCreateRequest) -> CartaResponse:
    db = get_database()
    doc = req.model_dump(by_alias=True)
    await db[COLL_CARDS].replace_one({"_id": req.id}, doc, upsert=True)
    return CartaResponse(**doc)

async def obtener_cartas(universo_id: Optional[str] = None) -> List[CartaResponse]:
    db = get_database()
    query = {"universo_id": universo_id} if universo_id else {}
    cursor = db[COLL_CARDS].find(query)
    items = []
    async for doc in cursor:
        items.append(CartaResponse(**doc))
    return items

async def eliminar_carta(carta_id: str) -> bool:
    db = get_database()
    res = await db[COLL_CARDS].delete_one({"_id": carta_id})
    return res.deleted_count > 0

# --- Resultados ---
async def crear_o_actualizar_resultado(req: ResultadoCreateRequest) -> ResultadoResponse:
    db = get_database()
    doc = req.model_dump(by_alias=True)
    await db[COLL_RESULTS].replace_one({"_id": req.id}, doc, upsert=True)
    return ResultadoResponse(**doc)

async def obtener_resultados(universo_id: Optional[str] = None) -> List[ResultadoResponse]:
    db = get_database()
    query = {"universo_id": universo_id} if universo_id else {}
    cursor = db[COLL_RESULTS].find(query)
    items = []
    async for doc in cursor:
        items.append(ResultadoResponse(**doc))
    return items

async def eliminar_resultado(resultado_id: str) -> bool:
    db = get_database()
    res = await db[COLL_RESULTS].delete_one({"_id": resultado_id})
    return res.deleted_count > 0

# --- Eventos ---
async def crear_o_actualizar_evento(req: EventoCreateRequest) -> EventoResponse:
    db = get_database()
    doc = req.model_dump(by_alias=True)
    await db[COLL_EVENTS].replace_one({"_id": req.id}, doc, upsert=True)
    return EventoResponse(**doc)

async def obtener_eventos(universo_id: Optional[str] = None) -> List[EventoResponse]:
    db = get_database()
    query = {"universo_id": universo_id} if universo_id else {}
    cursor = db[COLL_EVENTS].find(query)
    items = []
    async for doc in cursor:
        items.append(EventoResponse(**doc))
    return items

async def eliminar_evento(evento_id: str) -> bool:
    db = get_database()
    res = await db[COLL_EVENTS].delete_one({"_id": evento_id})
    return res.deleted_count > 0

# --- Conversaciones ---
async def crear_o_actualizar_conversacion(req: ConversacionCreateRequest) -> ConversacionResponse:
    db = get_database()
    doc = req.model_dump(by_alias=True)
    await db[COLL_CONVERSATIONS].replace_one({"_id": req.id}, doc, upsert=True)
    return ConversacionResponse(**doc)

async def obtener_conversaciones(universo_id: Optional[str] = None) -> List[ConversacionResponse]:
    db = get_database()
    query = {"universo_id": universo_id} if universo_id else {}
    cursor = db[COLL_CONVERSATIONS].find(query)
    items = []
    async for doc in cursor:
        items.append(ConversacionResponse(**doc))
    return items

async def eliminar_conversacion(conversacion_id: str) -> bool:
    db = get_database()
    res = await db[COLL_CONVERSATIONS].delete_one({"_id": conversacion_id})
    return res.deleted_count > 0

# ============================================================================
# 2. GENERADOR MENSUAL DE DESAFÍOS (Torre de Control)
# ============================================================================

async def generar_mes_narrativo(year: int, month: int, universo_id: str) -> Dict[str, Any]:
    """
    Genera y guarda en daily_challenges los 28-31 días del mes para el juego narrativo,
    asegurando que todo el contenido pertenezca estrictamente al universo indicado.
    """
    import calendar
    db = get_database()

    universo = await db[COLL_SETTINGS].find_one({"_id": universo_id})
    if not universo:
        raise HTTPException(status_code=404, detail=f"El universo '{universo_id}' no existe.")

    # Cargar pools de contenido del universo
    personajes = await db[COLL_CHARACTERS].find({"universo_id": universo_id}).to_list(length=100)
    cartas = await db[COLL_CARDS].find({"universo_id": universo_id}).to_list(length=200)
    eventos = await db[COLL_EVENTS].find({"universo_id": universo_id}).to_list(length=200)
    conversaciones = await db[COLL_CONVERSATIONS].find({"universo_id": universo_id}).to_list(length=100)

    if len(personajes) < 5:
        raise HTTPException(
            status_code=400,
            detail=f"Se requieren al menos 5 personajes en el universo '{universo_id}' (actuales: {len(personajes)})."
        )
    if len(cartas) < 8:
        raise HTTPException(
            status_code=400,
            detail=f"Se requieren al menos 8 cartas en el universo '{universo_id}' (actuales: {len(cartas)})."
        )
    if len(eventos) < 12:
        raise HTTPException(
            status_code=400,
            detail=f"Se requieren al menos 12 eventos en el universo '{universo_id}' (actuales: {len(eventos)})."
        )

    p_ids = [p["_id"] for p in personajes]
    c_ids = [c["_id"] for c in cartas]
    e_ids = [e["_id"] for e in eventos]
    conv_ids = [conv["_id"] for conv in conversaciones]

    recursos_iniciales = {r["clave"]: r.get("inicial", 50) for r in universo.get("recursos", [])}

    num_dias = calendar.monthrange(year, month)[1]
    desafios_creados = 0

    for dia in range(1, num_dias + 1):
        fecha_str = f"{year:04d}-{month:02d}-{dia:02d}"

        # Sorteo aleatorio reproducible o dinámico de setup inicial (5 PJ y 5 Cartas)
        corte_ofrecidos = random.sample(p_ids, 5)
        cartas_ofrecidas = random.sample(c_ids, min(5, len(c_ids)))
        cartas_mensuales = [cid for cid in c_ids if cid not in cartas_ofrecidas]
        if not cartas_mensuales:
            cartas_mensuales = c_ids

        challenge_doc = {
            "game_id": "narrativo",
            "date": fecha_str,
            "difficulty": "standard",
            "title": f"{universo.get('nombre', 'Crónicas')} - {fecha_str}",
            "config": {
                "universo_id": universo_id,
                "titulo": universo.get("nombre", "Aventura Narrativa"),
                "descripcion": universo.get("descripcion", ""),
                "duracion_meses": 12,
                "atributos_iniciales": recursos_iniciales,
                "setup_corte_ofrecidos_ids": corte_ofrecidos,
                "setup_cartas_ofrecidas_ids": cartas_ofrecidas,
                "pool_eventos_disponibles_ids": e_ids,
                "pool_cartas_mensuales_ids": cartas_mensuales,
                "pool_conversaciones_ids": conv_ids
            },
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        await db[COLL_CHALLENGES].replace_one(
            {"game_id": "narrativo", "date": fecha_str},
            challenge_doc,
            upsert=True
        )
        desafios_creados += 1

    return {
        "year": year,
        "month": month,
        "universo_id": universo_id,
        "desafios_creados": desafios_creados
    }

# ============================================================================
# 3. LÓGICA DE PARTIDA VIVA DEL ALUMNO (Save & Resume / Máquina de Estados)
# ============================================================================

async def _obtener_mapa_recursos_universo(universo_id: str) -> Dict[str, Dict[str, Any]]:
    db = get_database()
    universo = await db[COLL_SETTINGS].find_one({"_id": universo_id})
    if not universo:
        return {}
    return {r["clave"]: r for r in universo.get("recursos", [])}

async def obtener_setup_desafio(user_id: int, date: str) -> SetupDesafioResponse:
    """
    Devuelve la configuración de Fase 0 (Setup) para la fecha dada:
    Los 5 personajes ofrecidos y las 5 cartas ofrecidas con todos sus detalles para que el jugador elija 3 y 3.
    """
    db = get_database()
    challenge = await db[COLL_CHALLENGES].find_one({"game_id": "narrativo", "date": date})
    if not challenge:
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            await generar_mes_narrativo(year=dt.year, month=dt.month, universo_id="corte_medieval")
            challenge = await db[COLL_CHALLENGES].find_one({"game_id": "narrativo", "date": date})
        except Exception as e:
            logger.error(f"Error autogenerando desafío para {date}: {e}")

    if not challenge:
        raise HTTPException(status_code=404, detail=f"No existe desafío narrativo para la fecha {date}.")

    cfg = challenge.get("config", {})
    universo_id = cfg.get("universo_id", "corte_medieval")
    universo = await db[COLL_SETTINGS].find_one({"_id": universo_id})

    p_ids = cfg.get("setup_corte_ofrecidos_ids", [])
    c_ids = cfg.get("setup_cartas_ofrecidas_ids", [])

    personajes = await db[COLL_CHARACTERS].find({"_id": {"$in": p_ids}}).to_list(None)
    cartas = await db[COLL_CARDS].find({"_id": {"$in": c_ids}}).to_list(None)

    run = await db[COLL_RUNS].find_one({"user_id": user_id, "date": date, "game_id": "narrativo"})

    return SetupDesafioResponse(
        date=date,
        universo_id=universo_id,
        universo_nombre=(universo or {}).get("nombre", "Crónicas de la Corte Real"),
        universo_descripcion=(universo or {}).get("descripcion", ""),
        atributos_iniciales=cfg.get("atributos_iniciales", {"oro": 50, "pueblo": 50, "ejercito": 50, "fe": 50}),
        personajes_ofrecidos=[PersonajeResponse(**p) for p in personajes],
        cartas_ofrecidas=[CartaResponse(**c) for c in cartas],
        tiene_partida_activa=run is not None,
        fase_partida_activa=run.get("fase_actual") if run else None
    )

async def reiniciar_partida(user_id: int, date: str) -> Dict[str, Any]:
    """
    Elimina la partida activa del usuario en esa fecha para permitir arrancar de cero.
    """
    db = get_database()
    res = await db[COLL_RUNS].delete_one({"user_id": user_id, "date": date, "game_id": "narrativo"})
    return {
        "status": "ok",
        "deleted_count": res.deleted_count,
        "message": f"Partida del {date} reiniciada exitosamente."
    }

async def obtener_partida_activa(user_id: int, date: str) -> EstadoPartidaActivaResponse:
    """
    Recupera el estado exacto donde el alumno dejó la partida en esa fecha.
    """
    db = get_database()
    run = await db[COLL_RUNS].find_one({"user_id": user_id, "date": date, "game_id": "narrativo"})
    
    if not run:
        raise HTTPException(
            status_code=404,
            detail=f"No hay una partida activa para el usuario {user_id} en la fecha {date}."
        )

    return await _construir_estado_respuesta(run)

async def iniciar_partida(user_id: int, req: IniciarPartidaRequest) -> EstadoPartidaActivaResponse:
    """
    Fase 0: Elige 3 de 5 personajes y 3 de 5 cartas. Inicializa la partida en Mes 1, Fase DRAFT_MENSUAL.
    """
    db = get_database()
    
    # 1. Verificar si ya existe run activa
    run_existente = await db[COLL_RUNS].find_one({"user_id": user_id, "date": req.date, "game_id": "narrativo"})
    if run_existente:
        return await _construir_estado_respuesta(run_existente)

    # 2. Obtener desafío del día
    challenge = await db[COLL_CHALLENGES].find_one({"game_id": "narrativo", "date": req.date})
    if not challenge:
        raise HTTPException(status_code=404, detail=f"No existe desafío narrativo para la fecha {req.date}.")

    cfg = challenge.get("config", {})
    universo_id = cfg.get("universo_id")

    # 3. Validar selecciones
    if len(req.corte_elegida_ids) != 3:
        raise HTTPException(status_code=400, detail="Debes seleccionar exactamente 3 personajes para la corte.")
    if len(req.cartas_iniciales_ids) != 3:
        raise HTTPException(status_code=400, detail="Debes seleccionar exactamente 3 cartas de apoyo iniciales.")

    for pid in req.corte_elegida_ids:
        if pid not in cfg.get("setup_corte_ofrecidos_ids", []):
            raise HTTPException(status_code=400, detail=f"El personaje '{pid}' no estaba en la oferta inicial.")

    for cid in req.cartas_iniciales_ids:
        if cid not in cfg.get("setup_cartas_ofrecidas_ids", []):
            raise HTTPException(status_code=400, detail=f"La carta '{cid}' no estaba en la oferta inicial.")

    # 4. Cargar universo y recursos iniciales
    recursos_mapa = await _obtener_mapa_recursos_universo(universo_id)
    recursos_actuales = dict(cfg.get("atributos_iniciales", {}))

    # Cargar personajes y cartas elegidas
    personajes_docs = await db[COLL_CHARACTERS].find({"_id": {"$in": req.corte_elegida_ids}}).to_list(None)
    cartas_docs = await db[COLL_CARDS].find({"_id": {"$in": req.cartas_iniciales_ids}}).to_list(None)

    afinidades = {p["_id"]: p.get("afinidad_inicial", 50) for p in personajes_docs}

    tags_activos = set()
    for c in cartas_docs:
        for t in c.get("tags", []):
            tags_activos.add(t)

    run_doc = {
        "_id": f"run_{user_id}_{req.date}",
        "user_id": user_id,
        "date": req.date,
        "game_id": "narrativo",
        "universo_id": universo_id,
        "mes_actual": 1,
        "fase_actual": RunPhaseEnum.DRAFT_MENSUAL.value,
        "status": "in_progress",
        "recursos": recursos_actuales,
        "corte_activa": req.corte_elegida_ids,
        "afinidad": afinidades,
        "cartas_en_mano": req.cartas_iniciales_ids,
        "tags_activos": list(tags_activos),
        "turno_actual": {
            "cartas_ofrecidas_ids": [],
            "carta_elegida_id": None,
            "evento_actual_id": None,
            "opcion_elegida_id": None,
            "resultado_obtenido_id": None,
            "conversacion_actual_id": None
        },
        "eventos_jugados": [],
        "conversaciones_jugadas": [],
        "historial_mensual": [],
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    # Aplicar efectos "al_obtener" de la corte y cartas iniciales
    for p in personajes_docs:
        efectos_p = [EfectoSchema(**e) for e in p.get("efectos", [])]
        despachar_efectos(DisparadorEnum.AL_OBTENER, run_doc, efectos_p, recursos_mapa)

    for c in cartas_docs:
        efectos_c = [EfectoSchema(**e) for e in c.get("efectos", [])]
        despachar_efectos(DisparadorEnum.AL_OBTENER, run_doc, efectos_c, recursos_mapa)

    # Sortear las 3 cartas para el Draft del Mes 1
    pool_mensuales = cfg.get("pool_cartas_mensuales_ids", [])
    cartas_ofrecidas_mes = random.sample(pool_mensuales, min(3, len(pool_mensuales)))
    run_doc["turno_actual"]["cartas_ofrecidas_ids"] = cartas_ofrecidas_mes

    await db[COLL_RUNS].replace_one({"_id": run_doc["_id"]}, run_doc, upsert=True)
    return await _construir_estado_respuesta(run_doc)

async def elegir_carta_mes(user_id: int, req: ElegirCartaMesRequest) -> EstadoPartidaActivaResponse:
    """
    Fase 1: El jugador elige 1 de las 3 cartas ofrecidas.
    El backend aplica sus efectos, sortea el evento del mes y pasa a TOMA_DECISION_EVENTO.
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

    # 1. Agregar carta al inventario y tags
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

    # 2. Sortear el Evento del Mes con el Director Narrativo
    challenge = await db[COLL_CHALLENGES].find_one({"game_id": "narrativo", "date": req.date})
    pool_eventos_ids = challenge.get("config", {}).get("pool_eventos_disponibles_ids", [])

    eventos_candidatos = await db[COLL_EVENTS].find({"_id": {"$in": pool_eventos_ids}}).to_list(None)
    personajes_activos = await db[COLL_CHARACTERS].find({"_id": {"$in": run["corte_activa"]}}).to_list(None)
    cartas_activas = await db[COLL_CARDS].find({"_id": {"$in": run["cartas_en_mano"]}}).to_list(None)

    evento_seleccionado = seleccionar_evento_mes(
        eventos_candidatos=eventos_candidatos,
        run_data=run,
        personajes_activos=personajes_activos,
        cartas_activas=cartas_activas,
        eventos_jugados=run.get("eventos_jugados", [])
    )

    if not evento_seleccionado:
        raise HTTPException(status_code=500, detail="No hay eventos disponibles en el pool del desafío.")

    turno["evento_actual_id"] = evento_seleccionado["_id"]
    run["fase_actual"] = RunPhaseEnum.TOMA_DECISION_EVENTO.value
    run["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db[COLL_RUNS].replace_one({"_id": run["_id"]}, run)
    return await _construir_estado_respuesta(run)

async def decidir_evento(user_id: int, req: DecidirEventoRequest) -> EstadoPartidaActivaResponse:
    """
    Fase 2: El jugador envía la opción elegida (A, B o C).
    El backend ejecuta la tirada ponderada de resultados_posibles, persiste el resultado
    y evalúa si se detona una conversación de corte.
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

    # Buscar la opción seleccionada
    opcion_elegida = next((op for op in evento_doc.get("opciones", []) if op["id"] == req.opcion_id), None)
    if not opcion_elegida:
        raise HTTPException(status_code=400, detail=f"Opción '{req.opcion_id}' no válida para este evento.")

    # Si es secreta, verificar si cumple las condiciones
    if opcion_elegida.get("es_secreta", False):
        condiciones = [CondicionSchema(**c) for c in opcion_elegida.get("condiciones", [])]
        if not evaluar_condiciones(condiciones, run):
            raise HTTPException(status_code=403, detail="No cumples los requisitos para esta opción secreta.")

    # 1. Tirada ponderada para determinar el resultado
    resultado_ganador_id = sortear_resultado_opcion(opcion_elegida, run)
    turno["opcion_elegida_id"] = req.opcion_id
    turno["resultado_obtenido_id"] = resultado_ganador_id

    # 2. Aplicar los efectos del resultado
    res_doc = await db[COLL_RESULTS].find_one({"_id": resultado_ganador_id})
    recursos_mapa = await _obtener_mapa_recursos_universo(run["universo_id"])

    if res_doc:
        efectos_res = [EfectoSchema(**e) for e in res_doc.get("efectos", [])]
        despachar_efectos(DisparadorEnum.AL_OBTENER, run, efectos_res, recursos_mapa)

        # Aplicar afinidades del resultado si las tiene
        for imp in res_doc.get("impacto_afinidad", []):
            pid = imp.get("personaje_id")
            delta = int(imp.get("delta", 0))
            if pid in run["afinidad"]:
                run["afinidad"][pid] = max(0, min(100, run["afinidad"][pid] + delta))

    # 3. Evaluar si ocurre conversación de corte (evitando repetidas en la misma partida)
    challenge = await db[COLL_CHALLENGES].find_one({"game_id": "narrativo", "date": req.date})
    conv_pool_ids = challenge.get("config", {}).get("pool_conversaciones_ids", [])

    conversaciones_jugadas = set(run.get("conversaciones_jugadas", []))
    conversacion_sorteada = None
    if conv_pool_ids and random.random() < 0.40: # 40% de probabilidad base mensual
        candidatas = await db[COLL_CONVERSATIONS].find({"_id": {"$in": conv_pool_ids}}).to_list(None)
        # Filtrar solo las que cumplen los personajes de la corte actual Y no se jugaron ya
        corte_set = set(run["corte_activa"])
        validas = []
        for conv in candidatas:
            if conv["_id"] in conversaciones_jugadas:
                continue
            reqs = [r.get("personajeId") for r in conv.get("requisitos", [])]
            if all(r in corte_set for r in reqs):
                validas.append(conv)

        if validas:
            conversacion_sorteada = random.choice(validas)

    if conversacion_sorteada:
        turno["conversacion_actual_id"] = conversacion_sorteada["_id"]
        run["fase_actual"] = RunPhaseEnum.RESOLVER_CONVERSACION.value
        if "conversaciones_jugadas" not in run:
            run["conversaciones_jugadas"] = []
        if conversacion_sorteada["_id"] not in run["conversaciones_jugadas"]:
            run["conversaciones_jugadas"].append(conversacion_sorteada["_id"])
    else:
        turno["conversacion_actual_id"] = None
        run["fase_actual"] = RunPhaseEnum.BALANCE_MES.value

    run["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db[COLL_RUNS].replace_one({"_id": run["_id"]}, run)
    return await _construir_estado_respuesta(run)

async def responder_conversacion(user_id: int, req: ResponderConversacionRequest) -> EstadoPartidaActivaResponse:
    """
    Fase 3: El jugador interviene en el diálogo de personajes eligiendo opción 1 o 2.
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
    return await _construir_estado_respuesta(run)

async def avanzar_mes(user_id: int, req: AvanzarMesRequest) -> EstadoPartidaActivaResponse:
    """
    Fase 4: Cierra el mes actual, guarda en historial y avanza al mes siguiente (o epílogo si Mes == 12).
    """
    db = get_database()
    run = await db[COLL_RUNS].find_one({"user_id": user_id, "date": req.date, "game_id": "narrativo"})
    if not run:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")

    if run.get("fase_actual") != RunPhaseEnum.BALANCE_MES.value:
        raise HTTPException(status_code=400, detail="La partida no se encuentra en fase de balance mensual.")

    turno = run.get("turno_actual", {})
    mes_actual = run.get("mes_actual", 1)

    # 1. Guardar resumen del mes en historial
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

    # 2. ¿Llegó al Mes 12? Fin de Partida
    if mes_actual >= 12:
        run["fase_actual"] = RunPhaseEnum.FINALIZADA.value
        run["status"] = "completed"
        run["epilogo_final"] = _calcular_epilogo_final(run)
    else:
        # Avanzar al siguiente mes
        run["mes_actual"] = mes_actual + 1
        run["fase_actual"] = RunPhaseEnum.DRAFT_MENSUAL.value

        # Aplicar efectos "cada_mes" de personajes y cartas
        recursos_mapa = await _obtener_mapa_recursos_universo(run["universo_id"])
        personajes_docs = await db[COLL_CHARACTERS].find({"_id": {"$in": run["corte_activa"]}}).to_list(None)
        cartas_docs = await db[COLL_CARDS].find({"_id": {"$in": run["cartas_en_mano"]}}).to_list(None)

        for p in personajes_docs:
            efectos_p = [EfectoSchema(**e) for e in p.get("efectos", [])]
            despachar_efectos(DisparadorEnum.CADA_MES, run, efectos_p, recursos_mapa)

        for c in cartas_docs:
            efectos_c = [EfectoSchema(**e) for e in c.get("efectos", [])]
            despachar_efectos(DisparadorEnum.CADA_MES, run, efectos_c, recursos_mapa)

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
    return await _construir_estado_respuesta(run)

def _calcular_epilogo_final(run_data: Dict[str, Any]) -> Dict[str, Any]:
    recursos = run_data.get("recursos", {})
    promedio = sum(recursos.values()) / max(1, len(recursos))

    if promedio >= 75:
        rango = "S"
        titulo = "Era de Oro y Prosperidad Eterna"
        texto = "Tus sabias decisiones y el balance de tu corte llevaron al reino a su máximo esplendor histórico."
    elif promedio >= 55:
        rango = "A"
        titulo = "Paz Sólida y Buen Gobierno"
        texto = "Superaste las crisis y aseguraste la estabilidad de las tierras por muchas generaciones."
    elif promedio >= 35:
        rango = "B"
        titulo = "Tiempos Difíciles pero Superados"
        texto = "El año fue duro y las pérdidas se sintieron, pero la corona sigue firme en tu cabeza."
    else:
        rango = "C"
        titulo = "Reino en Ruinas"
        texto = "Apenas lograste sostener el poder. Las tensiones internas amenazan con derrumbar lo poco que queda."

    return {
        "rango": rango,
        "titulo": titulo,
        "descripcion": texto,
        "promedio_recursos": round(promedio, 1),
        "recursos_finales": recursos
    }

# ============================================================================
# 4. CONSTRUCTOR DE ESTADO COMPLETO PARA EL CLIENTE
# ============================================================================

async def _construir_estado_respuesta(run_doc: Dict[str, Any]) -> EstadoPartidaActivaResponse:
    db = get_database()
    universo_id = run_doc.get("universo_id")

    universo_doc = await db[COLL_SETTINGS].find_one({"_id": universo_id})
    universo_resp = UniversoResponse(**universo_doc) if universo_doc else UniversoResponse(
        _id=universo_id, nombre="Universo", descripcion="", icono="crown", recursos=[]
    )

    # Personajes de la corte
    personajes_docs = await db[COLL_CHARACTERS].find({"_id": {"$in": run_doc.get("corte_activa", [])}}).to_list(None)
    personajes_resp = [PersonajeResponse(**p) for p in personajes_docs]

    # Cartas en mano
    cartas_docs = await db[COLL_CARDS].find({"_id": {"$in": run_doc.get("cartas_en_mano", [])}}).to_list(None)
    cartas_resp = [CartaResponse(**c) for c in cartas_docs]

    turno = run_doc.get("turno_actual", {})

    # Cartas ofrecidas en draft
    draft_ids = turno.get("cartas_ofrecidas_ids", [])
    cartas_draft_docs = await db[COLL_CARDS].find({"_id": {"$in": draft_ids}}).to_list(None) if draft_ids else []
    cartas_draft_resp = [CartaResponse(**c) for c in cartas_draft_docs]

    # Evento actual con opciones calculadas
    evento_resp = None
    if turno.get("evento_actual_id"):
        evento_doc = await db[COLL_EVENTS].find_one({"_id": turno.get("evento_actual_id")})
        if evento_doc:
            # Precargar todos los resultados posibles del evento
            res_ids = set()
            for op in evento_doc.get("opciones", []):
                for rp in op.get("resultados_posibles", []):
                    res_ids.add(rp.get("resultado_id"))
            resultados_docs = await db[COLL_RESULTS].find({"_id": {"$in": list(res_ids)}}).to_list(None)
            res_dict = {r["_id"]: r for r in resultados_docs}

            opciones_calc = calcular_opciones_evento(evento_doc, run_doc, res_dict)
            evento_resp = EventoTurnoResponse(
                id=evento_doc["_id"],
                titulo=evento_doc.get("titulo", ""),
                descripcion=evento_doc.get("descripcion", ""),
                imagen=evento_doc.get("imagen", ""),
                opciones=opciones_calc
            )

    # Resultado actual obtenido
    resultado_resp = None
    if turno.get("resultado_obtenido_id"):
        res_doc = await db[COLL_RESULTS].find_one({"_id": turno.get("resultado_obtenido_id")})
        if res_doc:
            resultado_resp = ResultadoResponse(**res_doc)

    # Conversación actual
    conversacion_resp = None
    if turno.get("conversacion_actual_id"):
        conv_doc = await db[COLL_CONVERSATIONS].find_one({"_id": turno.get("conversacion_actual_id")})
        if conv_doc:
            conversacion_resp = ConversacionResponse(**conv_doc)

    return EstadoPartidaActivaResponse(
        run=NarrativeRunSchema(**run_doc),
        universo=universo_resp,
        personajes_corte=personajes_resp,
        cartas_inventario=cartas_resp,
        cartas_draft_actual=cartas_draft_resp,
        evento_actual=evento_resp,
        resultado_actual=resultado_resp,
        conversacion_actual=conversacion_resp,
        epilogo_final=run_doc.get("epilogo_final")
    )
