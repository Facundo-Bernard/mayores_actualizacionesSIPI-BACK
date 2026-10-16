import random
import logging
import asyncio
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple, Union
from fastapi import HTTPException

from app.core.database import get_database
from app.features.narrative.enums import (
    RunPhaseEnum,
    DisparadorEnum,
    TipoResultadoEnum,
    TipoFinalizacionEnum
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
    FinalizacionCreateRequest,
    FinalizacionResponse,
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
    HistorialPartidaResponse,
    InventarioPartidaResponse,
    PersonajeCorteDetalle,
    CortePartidaResponse,
    FinalizacionPartidaResponse,
    EstadoTurnoResponse,
    IniciarPartidaV2Response,
    ElegirCartaMesV2Response,
    DecidirEventoV2Response,
    ResponderConversacionV2Response,
    AvanzarMesV2Response,
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
COLL_ENDINGS = "narrative_endings"
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

async def obtener_personajes(
    universo_id: Optional[str] = None,
    skip: int = 0,
    limit: Optional[int] = None,
    busqueda: Optional[str] = None,
    with_total: bool = False
) -> Union[List[PersonajeResponse], Tuple[List[PersonajeResponse], int]]:
    db = get_database()
    query: Dict[str, Any] = {}
    if universo_id:
        query["universo_id"] = universo_id
    if busqueda:
        query["$or"] = [
            {"nombre": {"$regex": re.escape(busqueda), "$options": "i"}},
            {"arquetipo": {"$regex": re.escape(busqueda), "$options": "i"}},
            {"descripcion": {"$regex": re.escape(busqueda), "$options": "i"}},
            {"_id": {"$regex": re.escape(busqueda), "$options": "i"}}
        ]
    total = await db[COLL_CHARACTERS].count_documents(query)
    cursor = db[COLL_CHARACTERS].find(query).skip(skip)
    if limit is not None and limit > 0:
        cursor = cursor.limit(limit)
    items = []
    async for doc in cursor:
        items.append(PersonajeResponse(**doc))
    if with_total:
        return items, total
    return items

async def obtener_personaje_por_id(personaje_id: str) -> Optional[PersonajeResponse]:
    db = get_database()
    doc = await db[COLL_CHARACTERS].find_one({"_id": personaje_id})
    return PersonajeResponse(**doc) if doc else None

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

async def obtener_cartas(
    universo_id: Optional[str] = None,
    categoria: Optional[str] = None,
    skip: int = 0,
    limit: Optional[int] = None,
    busqueda: Optional[str] = None,
    with_total: bool = False
) -> Union[List[CartaResponse], Tuple[List[CartaResponse], int]]:
    db = get_database()
    query: Dict[str, Any] = {}
    if universo_id:
        query["universo_id"] = universo_id
    if categoria:
        query["categoria"] = categoria
    if busqueda:
        query["$or"] = [
            {"nombre": {"$regex": re.escape(busqueda), "$options": "i"}},
            {"descripcion": {"$regex": re.escape(busqueda), "$options": "i"}},
            {"tags": {"$in": [busqueda.lower()]}},
            {"_id": {"$regex": re.escape(busqueda), "$options": "i"}}
        ]
    total = await db[COLL_CARDS].count_documents(query)
    cursor = db[COLL_CARDS].find(query).skip(skip)
    if limit is not None and limit > 0:
        cursor = cursor.limit(limit)
    items = []
    async for doc in cursor:
        items.append(CartaResponse(**doc))
    if with_total:
        return items, total
    return items

async def obtener_carta_por_id(carta_id: str) -> Optional[CartaResponse]:
    db = get_database()
    doc = await db[COLL_CARDS].find_one({"_id": carta_id})
    return CartaResponse(**doc) if doc else None

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

async def obtener_resultados(
    universo_id: Optional[str] = None,
    tipo: Optional[str] = None,
    skip: int = 0,
    limit: Optional[int] = None,
    busqueda: Optional[str] = None,
    with_total: bool = False
) -> Union[List[ResultadoResponse], Tuple[List[ResultadoResponse], int]]:
    db = get_database()
    query: Dict[str, Any] = {}
    if universo_id:
        query["universo_id"] = universo_id
    if tipo:
        query["tipo_resultado"] = tipo
    if busqueda:
        query["$or"] = [
            {"titulo": {"$regex": re.escape(busqueda), "$options": "i"}},
            {"texto": {"$regex": re.escape(busqueda), "$options": "i"}},
            {"_id": {"$regex": re.escape(busqueda), "$options": "i"}}
        ]
    total = await db[COLL_RESULTS].count_documents(query)
    cursor = db[COLL_RESULTS].find(query).skip(skip)
    if limit is not None and limit > 0:
        cursor = cursor.limit(limit)
    items = []
    async for doc in cursor:
        items.append(ResultadoResponse(**doc))
    if with_total:
        return items, total
    return items

async def obtener_resultado_por_id(resultado_id: str) -> Optional[ResultadoResponse]:
    db = get_database()
    doc = await db[COLL_RESULTS].find_one({"_id": resultado_id})
    return ResultadoResponse(**doc) if doc else None

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

async def obtener_eventos(
    universo_id: Optional[str] = None,
    skip: int = 0,
    limit: Optional[int] = None,
    busqueda: Optional[str] = None,
    with_total: bool = False
) -> Union[List[EventoResponse], Tuple[List[EventoResponse], int]]:
    db = get_database()
    query: Dict[str, Any] = {}
    if universo_id:
        query["universo_id"] = universo_id
    if busqueda:
        query["$or"] = [
            {"titulo": {"$regex": re.escape(busqueda), "$options": "i"}},
            {"descripcion": {"$regex": re.escape(busqueda), "$options": "i"}},
            {"_id": {"$regex": re.escape(busqueda), "$options": "i"}}
        ]
    total = await db[COLL_EVENTS].count_documents(query)
    cursor = db[COLL_EVENTS].find(query).skip(skip)
    if limit is not None and limit > 0:
        cursor = cursor.limit(limit)
    items = []
    async for doc in cursor:
        items.append(EventoResponse(**doc))
    if with_total:
        return items, total
    return items

async def obtener_evento_por_id(evento_id: str) -> Optional[EventoResponse]:
    db = get_database()
    doc = await db[COLL_EVENTS].find_one({"_id": evento_id})
    return EventoResponse(**doc) if doc else None

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

async def obtener_conversaciones(
    universo_id: Optional[str] = None,
    skip: int = 0,
    limit: Optional[int] = None,
    busqueda: Optional[str] = None,
    with_total: bool = False
) -> Union[List[ConversacionResponse], Tuple[List[ConversacionResponse], int]]:
    db = get_database()
    query: Dict[str, Any] = {}
    if universo_id:
        query["universo_id"] = universo_id
    if busqueda:
        query["$or"] = [
            {"titulo": {"$regex": re.escape(busqueda), "$options": "i"}},
            {"contexto": {"$regex": re.escape(busqueda), "$options": "i"}},
            {"_id": {"$regex": re.escape(busqueda), "$options": "i"}}
        ]
    total = await db[COLL_CONVERSATIONS].count_documents(query)
    cursor = db[COLL_CONVERSATIONS].find(query).skip(skip)
    if limit is not None and limit > 0:
        cursor = cursor.limit(limit)
    items = []
    async for doc in cursor:
        items.append(ConversacionResponse(**doc))
    if with_total:
        return items, total
    return items

async def obtener_conversacion_por_id(conversacion_id: str) -> Optional[ConversacionResponse]:
    db = get_database()
    doc = await db[COLL_CONVERSATIONS].find_one({"_id": conversacion_id})
    return ConversacionResponse(**doc) if doc else None

async def eliminar_conversacion(conversacion_id: str) -> bool:
    db = get_database()
    res = await db[COLL_CONVERSATIONS].delete_one({"_id": conversacion_id})
    return res.deleted_count > 0

async def obtener_conversaciones_posibles_por_personajes(
    personajes_ids: List[str],
    universo_id: Optional[str] = None
) -> List[ConversacionResponse]:
    """
    Dada una lista de IDs de personajes (mano o corte activa),
    retorna todas las conversaciones del catálogo cuyos requisitos
    están completamente satisfechos por ese conjunto de personajes.
    """
    if not personajes_ids:
        return []

    db = get_database()
    query: Dict[str, Any] = {}
    if universo_id:
        query["universo_id"] = universo_id

    cursor = db[COLL_CONVERSATIONS].find(query)
    corte_set = set(personajes_ids)
    posibles = []

    async for doc in cursor:
        reqs = [r.get("personajeId") for r in doc.get("requisitos", [])]
        if reqs and all(r in corte_set for r in reqs):
            posibles.append(ConversacionResponse(**doc))

    return posibles

# --- Finalizaciones / Desenlaces de Reino ---
async def crear_o_actualizar_finalizacion(req: FinalizacionCreateRequest) -> FinalizacionResponse:
    db = get_database()
    # 1. Validar que el universo exista
    universo = await db[COLL_SETTINGS].find_one({"_id": req.universo_id})
    if not universo:
        raise HTTPException(
            status_code=400,
            detail=f"El universo '{req.universo_id}' no existe en el catálogo."
        )

    # 2. Si especifica un recurso_clave, validar que pertenezca a los recursos de ese universo
    if req.recurso_clave:
        claves_validas = [r["clave"] for r in universo.get("recursos", [])]
        if req.recurso_clave not in claves_validas:
            raise HTTPException(
                status_code=400,
                detail=f"El recurso '{req.recurso_clave}' no pertenece al universo '{universo.get('nombre', req.universo_id)}'. Recursos válidos: {claves_validas}"
            )

    doc = req.model_dump(by_alias=True)
    await db[COLL_ENDINGS].replace_one({"_id": req.id}, doc, upsert=True)
    return FinalizacionResponse(**doc)

async def obtener_finalizaciones(
    universo_id: Optional[str] = None,
    recurso_clave: Optional[str] = None,
    skip: int = 0,
    limit: Optional[int] = None,
    busqueda: Optional[str] = None,
    with_total: bool = False
) -> Union[List[FinalizacionResponse], Tuple[List[FinalizacionResponse], int]]:
    db = get_database()
    query: Dict[str, Any] = {}
    if universo_id:
        query["universo_id"] = universo_id
    if recurso_clave:
        query["recurso_clave"] = recurso_clave
    if busqueda:
        query["$or"] = [
            {"titulo": {"$regex": re.escape(busqueda), "$options": "i"}},
            {"texto": {"$regex": re.escape(busqueda), "$options": "i"}},
            {"_id": {"$regex": re.escape(busqueda), "$options": "i"}}
        ]
    total = await db[COLL_ENDINGS].count_documents(query)
    cursor = db[COLL_ENDINGS].find(query).skip(skip)
    if limit is not None and limit > 0:
        cursor = cursor.limit(limit)
    items = []
    async for doc in cursor:
        items.append(FinalizacionResponse(**doc))
    if with_total:
        return items, total
    return items

async def obtener_finalizacion_por_id(finalizacion_id: str) -> Optional[FinalizacionResponse]:
    db = get_database()
    doc = await db[COLL_ENDINGS].find_one({"_id": finalizacion_id})
    if doc:
        return FinalizacionResponse(**doc)
    return None

async def eliminar_finalizacion(finalizacion_id: str) -> bool:
    db = get_database()
    res = await db[COLL_ENDINGS].delete_one({"_id": finalizacion_id})
    return res.deleted_count > 0

async def sembrar_finalizaciones_para_universo(universo_id: str) -> List[FinalizacionResponse]:
    """
    Genera automáticamente las finalizaciones de derrota base (<= 0)
    para cada recurso definido en el universo indicado, si todavía no existen.
    Garantiza que cada universo tenga sus propios textos e imágenes sin compartir finales.
    """
    db = get_database()
    universo = await db[COLL_SETTINGS].find_one({"_id": universo_id})
    if not universo:
        raise HTTPException(status_code=404, detail=f"Universo '{universo_id}' no encontrado.")

    # Si es corte_medieval, aplicar las canónicas ya redactadas
    if universo_id == "corte_medieval":
        default_endings = [
            {
                "_id": "fin_corte_oro_cero",
                "universo_id": "corte_medieval",
                "recurso_clave": "oro",
                "tipo": TipoFinalizacionEnum.DERROTA_RECURSO.value,
                "titulo": "Bancarrota de la Corona",
                "texto": "Las arcas del reino quedaron completamente vacías. La guardia real desertó por falta de paga y los acreedores extranjeros confiscaron los castillos.",
                "imagen": "/assets/narrative/finalizaciones/default.webp",
                "rango": "F"
            },
            {
                "_id": "fin_corte_pueblo_cero",
                "universo_id": "corte_medieval",
                "recurso_clave": "pueblo",
                "tipo": TipoFinalizacionEnum.DERROTA_RECURSO.value,
                "titulo": "Revolución Popular",
                "texto": "El pueblo hambriento y descontento derribó los portones del palacio. La muchedumbre desconoció las leyes de la corona y la corte debió huir al exilio.",
                "imagen": "/assets/narrative/finalizaciones/default.webp",
                "rango": "F"
            },
            {
                "_id": "fin_corte_ejercito_cero",
                "universo_id": "corte_medieval",
                "recurso_clave": "ejercito",
                "tipo": TipoFinalizacionEnum.DERROTA_RECURSO.value,
                "titulo": "Invasión y Conquista",
                "texto": "Sin tropas para vigilar los pasos fronterizos ni defender las guarniciones, los reinos rivales avanzaron sin resistencia y subyugaron la corona.",
                "imagen": "/assets/narrative/finalizaciones/default.webp",
                "rango": "F"
            },
            {
                "_id": "fin_corte_fe_cero",
                "universo_id": "corte_medieval",
                "recurso_clave": "fe",
                "tipo": TipoFinalizacionEnum.DERROTA_RECURSO.value,
                "titulo": "Herejía y Anarquía",
                "texto": "Los monasterios cerraron sus puertas y el clero declaró maldito el linaje real. La desesperanza y el caos se apoderaron de cada aldea.",
                "imagen": "/assets/narrative/finalizaciones/default.webp",
                "rango": "F"
            }
        ]
        for e in default_endings:
            await db[COLL_ENDINGS].replace_one(
                {"universo_id": universo_id, "recurso_clave": e["recurso_clave"]},
                e,
                upsert=True
            )
        items = await obtener_finalizaciones(universo_id=universo_id)
        return items

    # Para cualquier otro universo (ej. granjero, ciencia ficción, etc.)
    recursos = universo.get("recursos", [])
    creadas = []
    universo_nombre = universo.get("nombre", universo_id)
    for r in recursos:
        clave = r.get("clave")
        nombre_rec = r.get("nombre", clave.capitalize())
        existente = await db[COLL_ENDINGS].find_one({
            "universo_id": universo_id,
            "recurso_clave": clave
        })
        if not existente:
            doc = {
                "_id": f"fin_{universo_id}_{clave}_cero",
                "universo_id": universo_id,
                "recurso_clave": clave,
                "tipo": TipoFinalizacionEnum.DERROTA_RECURSO.value,
                "titulo": f"Colapso por {nombre_rec} ({universo_nombre})",
                "texto": f"El recurso '{nombre_rec}' se ha agotado por completo en {universo_nombre}, provocando el fracaso irrevocable de tu historia.",
                "imagen": "/assets/narrative/finalizaciones/default.webp",
                "rango": "F"
            }
            await db[COLL_ENDINGS].insert_one(doc)
            creadas.append(FinalizacionResponse(**doc))

    return creadas

async def sembrar_finalizaciones_default():
    """
    Siembra las finalizaciones para 'corte_medieval' si no existen.
    """
    await sembrar_finalizaciones_para_universo("corte_medieval")

async def verificar_colapso_recursos(run_doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Verifica si algún recurso del reino llegó a <= 0.
    En tal caso, busca en narrative_endings la finalización asociada al recurso agotado,
    marca la partida como game_over y FINALIZADA, y guarda el epílogo de la derrota.
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

    # Verificar si algún recurso colapsó tras efectos iniciales
    derrota = await verificar_colapso_recursos(run_doc)
    if derrota:
        await db[COLL_RUNS].replace_one({"_id": run_doc["_id"]}, run_doc, upsert=True)
        return await _construir_estado_respuesta(run_doc)

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

    # Si la carta elegida causa el colapso inmediato de un recurso:
    derrota = await verificar_colapso_recursos(run)
    if derrota:
        run["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db[COLL_RUNS].replace_one({"_id": run["_id"]}, run)
        return await _construir_estado_respuesta(run)

    # 2. Sortear el Evento del Mes con el Director Narrativo
    challenge = await db[COLL_CHALLENGES].find_one({"game_id": "narrativo", "date": req.date})
    pool_eventos_ids = challenge.get("config", {}).get("pool_eventos_disponibles_ids", [])

    eventos_candidatos = await db[COLL_EVENTS].find({"_id": {"$in": pool_eventos_ids}}).to_list(None)
    corte_ids = list(run.get("afinidad", {}).keys()) or run.get("corte_activa", [])
    personajes_activos = await db[COLL_CHARACTERS].find({"_id": {"$in": corte_ids}}).to_list(None)
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

    # Si algún recurso colapsó tras el resultado del evento:
    derrota = await verificar_colapso_recursos(run)
    if derrota:
        run["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db[COLL_RUNS].replace_one({"_id": run["_id"]}, run)
        return await _construir_estado_respuesta(run)

    # 3. Evaluar si ocurre conversación de corte (evitando repetidas en la misma partida)
    challenge = await db[COLL_CHALLENGES].find_one({"game_id": "narrativo", "date": req.date})
    conv_pool_ids = challenge.get("config", {}).get("pool_conversaciones_ids", [])

    conversaciones_jugadas = set(run.get("conversaciones_jugadas", []))
    conversacion_sorteada = None
    if conv_pool_ids and random.random() < 0.40: # 40% de probabilidad base mensual
        candidatas = await db[COLL_CONVERSATIONS].find({"_id": {"$in": conv_pool_ids}}).to_list(None)
        # Filtrar solo las que cumplen los personajes de la corte actual Y no se jugaron ya
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

    # 1. Guardar resumen completo del mes en historial_mensual
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
        universo_doc = await db[COLL_SETTINGS].find_one({"_id": run.get("universo_id")})
        run["finalizacion"] = _calcular_finalizacion_victoria(run, universo_doc)
    else:
        # Avanzar al siguiente mes
        run["mes_actual"] = mes_actual + 1
        run["fase_actual"] = RunPhaseEnum.DRAFT_MENSUAL.value

        # Aplicar efectos "cada_mes" de personajes y cartas
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
            return await _construir_estado_respuesta(run)

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

def _calcular_finalizacion_victoria(run_data: Dict[str, Any], universo_doc: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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

# ============================================================================
# 4. CONSTRUCTOR DE ESTADO COMPLETO PARA EL CLIENTE (Optimizado con asyncio.gather)
# ============================================================================

async def _sincronizar_intento_usuario(run_doc: Dict[str, Any]):
    """
    Sincroniza el resultado final del día con la colección 'user_attempts'
    para que impacte en el progreso, racha y calendario mensual del alumno.
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

        await db["user_attempts"].find_one_and_update(
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

async def _construir_estado_respuesta(run_doc: Dict[str, Any]) -> EstadoPartidaActivaResponse:
    db = get_database()
    universo_id = run_doc.get("universo_id")
    turno = run_doc.get("turno_actual", {})
    draft_ids = turno.get("cartas_ofrecidas_ids", [])
    corte_ids = list(run_doc.get("afinidad", {}).keys()) or run_doc.get("corte_activa", [])
    cartas_ids = run_doc.get("cartas_en_mano", [])
    evento_id = turno.get("evento_actual_id")
    resultado_id = turno.get("resultado_obtenido_id")
    conversacion_id = turno.get("conversacion_actual_id")

    # Ejecución paralela concurrente de todas las consultas independientes
    async def _get_empty_list():
        return []

    async def _get_none():
        return None

    universo_task = db[COLL_SETTINGS].find_one({"_id": universo_id})
    personajes_task = db[COLL_CHARACTERS].find({"_id": {"$in": corte_ids}}).to_list(None) if corte_ids else _get_empty_list()
    cartas_task = db[COLL_CARDS].find({"_id": {"$in": cartas_ids}}).to_list(None) if cartas_ids else _get_empty_list()
    draft_task = db[COLL_CARDS].find({"_id": {"$in": draft_ids}}).to_list(None) if draft_ids else _get_empty_list()
    evento_task = db[COLL_EVENTS].find_one({"_id": evento_id}) if evento_id else _get_none()
    resultado_task = db[COLL_RESULTS].find_one({"_id": resultado_id}) if resultado_id else _get_none()
    conversacion_task = db[COLL_CONVERSATIONS].find_one({"_id": conversacion_id}) if conversacion_id else _get_none()

    (
        universo_doc,
        personajes_docs,
        cartas_docs,
        cartas_draft_docs,
        evento_doc,
        res_doc,
        conv_doc
    ) = await asyncio.gather(
        universo_task,
        personajes_task,
        cartas_task,
        draft_task,
        evento_task,
        resultado_task,
        conversacion_task
    )

    universo_resp = UniversoResponse(**universo_doc) if universo_doc else UniversoResponse(
        _id=universo_id, nombre="Universo", descripcion="", icono="crown", recursos=[]
    )
    personajes_resp = [PersonajeResponse(**p) for p in personajes_docs]
    cartas_resp = [CartaResponse(**c) for c in cartas_docs]
    cartas_draft_resp = [CartaResponse(**c) for c in cartas_draft_docs]

    # Evento actual con opciones calculadas
    evento_resp = None
    if evento_doc:
        res_ids = set()
        for op in evento_doc.get("opciones", []):
            for rp in op.get("resultados_posibles", []):
                res_ids.add(rp.get("resultado_id"))
        resultados_docs = await db[COLL_RESULTS].find({"_id": {"$in": list(res_ids)}}).to_list(None) if res_ids else []
        res_dict = {r["_id"]: r for r in resultados_docs}

        opciones_calc = calcular_opciones_evento(evento_doc, run_doc, res_dict)
        evento_resp = EventoTurnoResponse(
            id=evento_doc["_id"],
            titulo=evento_doc.get("titulo", ""),
            descripcion=evento_doc.get("descripcion", ""),
            imagen=evento_doc.get("imagen", ""),
            opciones=opciones_calc
        )

    resultado_resp = ResultadoResponse(**res_doc) if res_doc else None
    conversacion_resp = ConversacionResponse(**conv_doc) if conv_doc else None
    finalizacion_resp = FinalizacionResponse(**run_doc["finalizacion"]) if run_doc.get("finalizacion") else None

    # Si la partida llegó a su término (derrota o victoria), sincronizar con user_attempts
    if run_doc.get("status") in ("game_over", "completed"):
        await _sincronizar_intento_usuario(run_doc)

    return EstadoPartidaActivaResponse(
        run=NarrativeRunSchema(**run_doc),
        universo=universo_resp,
        personajes_corte=personajes_resp,
        cartas_inventario=cartas_resp,
        cartas_draft_actual=cartas_draft_resp,
        evento_actual=evento_resp,
        resultado_actual=resultado_resp,
        conversacion_actual=conversacion_resp,
        epilogo_final=None,
        finalizacion=finalizacion_resp
    )

# ============================================================================
# ENDPOINTS DE CONSULTA ESPECIALIZADOS (BAJO DEMANDA)
# ============================================================================

async def obtener_historial_partida(user_id: int, date: str) -> HistorialPartidaResponse:
    db = get_database()
    run = await db[COLL_RUNS].find_one({"user_id": user_id, "date": date})
    if not run:
        raise HTTPException(status_code=404, detail="No se encontró una partida activa para esa fecha.")
    return HistorialPartidaResponse(
        date=run.get("date", date),
        mes_actual=run.get("mes_actual", 1),
        status=run.get("status", "in_progress"),
        fase_actual=run.get("fase_actual", ""),
        historial_mensual=run.get("historial_mensual", [])
    )

async def obtener_inventario_partida(user_id: int, date: str) -> InventarioPartidaResponse:
    db = get_database()
    run = await db[COLL_RUNS].find_one({"user_id": user_id, "date": date})
    if not run:
        raise HTTPException(status_code=404, detail="No se encontró una partida activa para esa fecha.")
    cartas_ids = run.get("cartas_en_mano", [])
    cartas_docs = await db[COLL_CARDS].find({"_id": {"$in": cartas_ids}}).to_list(None) if cartas_ids else []
    return InventarioPartidaResponse(
        date=run.get("date", date),
        cartas=[CartaResponse(**c) for c in cartas_docs],
        tags_activos=run.get("tags_activos", [])
    )

async def obtener_corte_partida(user_id: int, date: str) -> CortePartidaResponse:
    db = get_database()
    run = await db[COLL_RUNS].find_one({"user_id": user_id, "date": date})
    if not run:
        raise HTTPException(status_code=404, detail="No se encontró una partida activa para esa fecha.")
    afinidades = run.get("afinidad", {})
    corte_ids = list(afinidades.keys()) or run.get("corte_activa", [])
    personajes_docs = await db[COLL_CHARACTERS].find({"_id": {"$in": corte_ids}}).to_list(None) if corte_ids else []
    corte_detalles = [
        PersonajeCorteDetalle(
            personaje=PersonajeResponse(**p),
            afinidad=afinidades.get(p["_id"], 50)
        )
        for p in personajes_docs
    ]
    return CortePartidaResponse(
        date=run.get("date", date),
        corte=corte_detalles,
        afinidad=afinidades
    )

async def obtener_finalizacion_partida(user_id: int, date: str) -> FinalizacionPartidaResponse:
    db = get_database()
    run = await db[COLL_RUNS].find_one({"user_id": user_id, "date": date})
    if not run:
        raise HTTPException(status_code=404, detail="No se encontró una partida activa para esa fecha.")
    fin_raw = run.get("finalizacion")
    fin_resp = FinalizacionResponse(**fin_raw) if fin_raw else None
    return FinalizacionPartidaResponse(
        date=run.get("date", date),
        status=run.get("status", "in_progress"),
        mes_actual=run.get("mes_actual", 1),
        finalizacion=fin_resp,
        epilogo_final=run.get("epilogo_final")
    )

async def obtener_turno_actual(user_id: int, date: str) -> EstadoTurnoResponse:
    db = get_database()
    run_doc = await db[COLL_RUNS].find_one({"user_id": user_id, "date": date})
    if not run_doc:
        raise HTTPException(status_code=404, detail="No se encontró una partida activa para esa fecha.")

    turno = run_doc.get("turno_actual", {})
    draft_ids = turno.get("cartas_ofrecidas_ids", [])
    evento_id = turno.get("evento_actual_id")
    resultado_id = turno.get("resultado_obtenido_id")
    conversacion_id = turno.get("conversacion_actual_id")

    async def _get_empty_list():
        return []

    async def _get_none():
        return None

    draft_task = db[COLL_CARDS].find({"_id": {"$in": draft_ids}}).to_list(None) if draft_ids else _get_empty_list()
    evento_task = db[COLL_EVENTS].find_one({"_id": evento_id}) if evento_id else _get_none()
    resultado_task = db[COLL_RESULTS].find_one({"_id": resultado_id}) if resultado_id else _get_none()
    conversacion_task = db[COLL_CONVERSATIONS].find_one({"_id": conversacion_id}) if conversacion_id else _get_none()

    cartas_draft_docs, evento_doc, res_doc, conv_doc = await asyncio.gather(
        draft_task, evento_task, resultado_task, conversacion_task
    )

    evento_resp = None
    if evento_doc:
        res_ids = set()
        for op in evento_doc.get("opciones", []):
            for rp in op.get("resultados_posibles", []):
                res_ids.add(rp.get("resultado_id"))
        resultados_docs = await db[COLL_RESULTS].find({"_id": {"$in": list(res_ids)}}).to_list(None) if res_ids else []
        res_dict = {r["_id"]: r for r in resultados_docs}

        opciones_calc = calcular_opciones_evento(evento_doc, run_doc, res_dict)
        evento_resp = EventoTurnoResponse(
            id=evento_doc["_id"],
            titulo=evento_doc.get("titulo", ""),
            descripcion=evento_doc.get("descripcion", ""),
            imagen=evento_doc.get("imagen", ""),
            opciones=opciones_calc
        )

    resultado_resp = ResultadoResponse(**res_doc) if res_doc else None
    conversacion_resp = ConversacionResponse(**conv_doc) if conv_doc else None
    finalizacion_resp = FinalizacionResponse(**run_doc["finalizacion"]) if run_doc.get("finalizacion") else None

    return EstadoTurnoResponse(
        date=run_doc.get("date", date),
        mes_actual=run_doc.get("mes_actual", 1),
        fase_actual=run_doc.get("fase_actual", ""),
        status=run_doc.get("status", "in_progress"),
        recursos=run_doc.get("recursos", {}),
        afinidad=run_doc.get("afinidad", {}),
        cartas_draft_actual=[CartaResponse(**c) for c in cartas_draft_docs],
        evento_actual=evento_resp,
        resultado_actual=resultado_resp,
        conversacion_actual=conversacion_resp,
        finalizacion=finalizacion_resp
    )

async def obtener_evento_actual_partida(user_id: int, date: str) -> Optional[EventoTurnoResponse]:
    db = get_database()
    run_doc = await db[COLL_RUNS].find_one({"user_id": user_id, "date": date})
    if not run_doc:
        raise HTTPException(status_code=404, detail="No se encontró una partida activa para esa fecha.")

    turno = run_doc.get("turno_actual", {})
    evento_id = turno.get("evento_actual_id")
    if not evento_id:
        return None

    evento_doc = await db[COLL_EVENTS].find_one({"_id": evento_id})
    if not evento_doc:
        return None

    res_ids = set()
    for op in evento_doc.get("opciones", []):
        for rp in op.get("resultados_posibles", []):
            res_ids.add(rp.get("resultado_id"))
    resultados_docs = await db[COLL_RESULTS].find({"_id": {"$in": list(res_ids)}}).to_list(None) if res_ids else []
    res_dict = {r["_id"]: r for r in resultados_docs}

    opciones_calc = calcular_opciones_evento(evento_doc, run_doc, res_dict)
    return EventoTurnoResponse(
        id=evento_doc["_id"],
        titulo=evento_doc.get("titulo", ""),
        descripcion=evento_doc.get("descripcion", ""),
        imagen=evento_doc.get("imagen", ""),
        opciones=opciones_calc
    )

async def obtener_conversacion_actual_partida(user_id: int, date: str) -> Optional[ConversacionResponse]:
    db = get_database()
    run_doc = await db[COLL_RUNS].find_one({"user_id": user_id, "date": date})
    if not run_doc:
        raise HTTPException(status_code=404, detail="No se encontró una partida activa para esa fecha.")

    turno = run_doc.get("turno_actual", {})
    conversacion_id = turno.get("conversacion_actual_id")
    if not conversacion_id:
        return None

    conv_doc = await db[COLL_CONVERSATIONS].find_one({"_id": conversacion_id})
    return ConversacionResponse(**conv_doc) if conv_doc else None

async def obtener_resultado_actual_partida(user_id: int, date: str) -> Optional[ResultadoResponse]:
    db = get_database()
    run_doc = await db[COLL_RUNS].find_one({"user_id": user_id, "date": date})
    if not run_doc:
        raise HTTPException(status_code=404, detail="No se encontró una partida activa para esa fecha.")

    turno = run_doc.get("turno_actual", {})
    resultado_id = turno.get("resultado_obtenido_id")
    if not resultado_id:
        return None

    res_doc = await db[COLL_RESULTS].find_one({"_id": resultado_id})
    return ResultadoResponse(**res_doc) if res_doc else None

async def obtener_draft_actual_partida(user_id: int, date: str) -> List[CartaResponse]:
    db = get_database()
    run_doc = await db[COLL_RUNS].find_one({"user_id": user_id, "date": date})
    if not run_doc:
        raise HTTPException(status_code=404, detail="No se encontró una partida activa para esa fecha.")

    turno = run_doc.get("turno_actual", {})
    draft_ids = turno.get("cartas_ofrecidas_ids", [])
    if not draft_ids:
        return []

    cartas_draft_docs = await db[COLL_CARDS].find({"_id": {"$in": draft_ids}}).to_list(None)
    return [CartaResponse(**c) for c in cartas_draft_docs]

# ============================================================================
# FUNCIONES DEL MOTOR V2 (RESPUESTAS LIGERAS POR FASE)
# ============================================================================

async def iniciar_partida_v2(user_id: int, req: IniciarPartidaRequest) -> IniciarPartidaV2Response:
    full = await iniciar_partida(user_id, req)
    fase_str = full.run.fase_actual.value if hasattr(full.run.fase_actual, "value") else str(full.run.fase_actual)
    return IniciarPartidaV2Response(
        mes_actual=full.run.mes_actual,
        fase_actual=fase_str,
        recursos=full.run.recursos,
        afinidad=full.run.afinidad,
        cartas_draft_actual=full.cartas_draft_actual
    )

async def elegir_carta_mes_v2(user_id: int, req: ElegirCartaMesRequest) -> ElegirCartaMesV2Response:
    full = await elegir_carta_mes(user_id, req)
    fase_str = full.run.fase_actual.value if hasattr(full.run.fase_actual, "value") else str(full.run.fase_actual)
    if not full.evento_actual:
        raise HTTPException(status_code=500, detail="No se pudo sortear el evento del mes.")
    return ElegirCartaMesV2Response(
        fase_actual=fase_str,
        recursos=full.run.recursos,
        evento_actual=full.evento_actual
    )

async def decidir_evento_v2(user_id: int, req: DecidirEventoRequest) -> DecidirEventoV2Response:
    full = await decidir_evento(user_id, req)
    fase_str = full.run.fase_actual.value if hasattr(full.run.fase_actual, "value") else str(full.run.fase_actual)
    if not full.resultado_actual:
        raise HTTPException(status_code=500, detail="No se pudo resolver el resultado del evento.")
    return DecidirEventoV2Response(
        fase_actual=fase_str,
        recursos=full.run.recursos,
        resultado_actual=full.resultado_actual,
        conversacion_actual=full.conversacion_actual,
        finalizacion=full.finalizacion
    )

async def responder_conversacion_v2(user_id: int, req: ResponderConversacionRequest) -> ResponderConversacionV2Response:
    db = get_database()
    run_before = await db[COLL_RUNS].find_one({"user_id": user_id, "date": req.date, "game_id": "narrativo"})
    conv_id = run_before.get("turno_actual", {}).get("conversacion_actual_id") if run_before else None
    conv_doc = await db[COLL_CONVERSATIONS].find_one({"_id": conv_id}) if conv_id else None
    decision = next((d for d in conv_doc.get("decisiones", []) if d.get("opcion") == req.opcion_numero), None) if conv_doc else None

    full = await responder_conversacion(user_id, req)
    fase_str = full.run.fase_actual.value if hasattr(full.run.fase_actual, "value") else str(full.run.fase_actual)
    return ResponderConversacionV2Response(
        fase_actual=fase_str,
        afinidad=full.run.afinidad,
        resultado_texto=decision.get("resultado_texto", "") if decision else "",
        impacto_afinidad=decision.get("impacto_afinidad", []) if decision else []
    )

async def avanzar_mes_v2(user_id: int, req: AvanzarMesRequest) -> AvanzarMesV2Response:
    full = await avanzar_mes(user_id, req)
    fase_str = full.run.fase_actual.value if hasattr(full.run.fase_actual, "value") else str(full.run.fase_actual)
    return AvanzarMesV2Response(
        mes_actual=full.run.mes_actual,
        fase_actual=fase_str,
        status=full.run.status,
        recursos=full.run.recursos,
        cartas_draft_actual=full.cartas_draft_actual,
        finalizacion=full.finalizacion
    )



