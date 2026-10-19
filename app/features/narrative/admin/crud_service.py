"""
crud_service.py
Capa CRUD genérica reutilizable y servicios de administración para las 7 colecciones
del catálogo narrativo (Universos, Personajes, Cartas, Resultados, Eventos, Conversaciones y Finalizaciones).
"""

from typing import TypeVar, Type, Optional, List
from pydantic import BaseModel

from app.core.database import get_database
from app.features.narrative.constants import (
    COLL_SETTINGS,
    COLL_CHARACTERS,
    COLL_CARDS,
    COLL_RESULTS,
    COLL_EVENTS,
    COLL_CONVERSATIONS,
    COLL_ENDINGS
)
from app.features.narrative.schemas.catalog_schemas import (
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
    FinalizacionResponse
)

T = TypeVar("T", bound=BaseModel)

# ============================================================================
# OPERACIONES GENÉRICAS
# ============================================================================

async def guardar_item_catalogo(
    collection_name: str,
    item_id: str,
    data: BaseModel,
    response_cls: Type[T]
) -> T:
    """Inserta o actualiza un documento en la colección especificada y lo retorna validado."""
    db = get_database()
    doc = data.model_dump(by_alias=True)
    await db[collection_name].replace_one({"_id": item_id}, doc, upsert=True)
    return response_cls(**doc)

async def listar_items_catalogo(
    collection_name: str,
    response_cls: Type[T],
    universo_id: Optional[str] = None,
    limit: Optional[int] = None,
    skip: int = 0
) -> List[T]:
    """Lista documentos de una colección aplicando filtro opcional de universo y paginación."""
    db = get_database()
    filtro = {}
    if universo_id:
        filtro["universo_id"] = universo_id

    cursor = db[collection_name].find(filtro).skip(skip)
    if limit is not None and limit > 0:
        cursor = cursor.limit(limit)

    docs = await cursor.to_list(length=limit or 500)
    return [response_cls(**d) for d in docs]

async def obtener_item_catalogo_por_id(
    collection_name: str,
    item_id: str,
    response_cls: Type[T]
) -> Optional[T]:
    """Recupera un documento específico de una colección por su ID."""
    db = get_database()
    doc = await db[collection_name].find_one({"_id": item_id})
    if not doc:
        return None
    return response_cls(**doc)

async def eliminar_item_catalogo_por_id(
    collection_name: str,
    item_id: str
) -> bool:
    """Elimina un documento de la colección dada por su identificador único."""
    db = get_database()
    res = await db[collection_name].delete_one({"_id": item_id})
    return res.deleted_count > 0

# ============================================================================
# CONVENIENCE WRAPPERS POR ENTIDAD
# ============================================================================

# Universos
async def crear_o_actualizar_universo(req: UniversoCreateRequest) -> UniversoResponse:
    return await guardar_item_catalogo(COLL_SETTINGS, req.id, req, UniversoResponse)

async def obtener_universos() -> List[UniversoResponse]:
    return await listar_items_catalogo(COLL_SETTINGS, UniversoResponse)

async def obtener_universo_por_id(universo_id: str) -> Optional[UniversoResponse]:
    return await obtener_item_catalogo_por_id(COLL_SETTINGS, universo_id, UniversoResponse)

async def eliminar_universo(universo_id: str) -> bool:
    return await eliminar_item_catalogo_por_id(COLL_SETTINGS, universo_id)

# Personajes
async def crear_o_actualizar_personaje(req: PersonajeCreateRequest) -> PersonajeResponse:
    return await guardar_item_catalogo(COLL_CHARACTERS, req.id, req, PersonajeResponse)

async def obtener_personajes(universo_id: Optional[str] = None, limit: Optional[int] = None, skip: int = 0) -> List[PersonajeResponse]:
    return await listar_items_catalogo(COLL_CHARACTERS, PersonajeResponse, universo_id, limit, skip)

async def obtener_personaje_por_id(personaje_id: str) -> Optional[PersonajeResponse]:
    return await obtener_item_catalogo_por_id(COLL_CHARACTERS, personaje_id, PersonajeResponse)

async def eliminar_personaje(personaje_id: str) -> bool:
    return await eliminar_item_catalogo_por_id(COLL_CHARACTERS, personaje_id)

# Cartas
async def crear_o_actualizar_carta(req: CartaCreateRequest) -> CartaResponse:
    return await guardar_item_catalogo(COLL_CARDS, req.id, req, CartaResponse)

async def obtener_cartas(universo_id: Optional[str] = None, limit: Optional[int] = None, skip: int = 0) -> List[CartaResponse]:
    return await listar_items_catalogo(COLL_CARDS, CartaResponse, universo_id, limit, skip)

async def obtener_carta_por_id(carta_id: str) -> Optional[CartaResponse]:
    return await obtener_item_catalogo_por_id(COLL_CARDS, carta_id, CartaResponse)

async def eliminar_carta(carta_id: str) -> bool:
    return await eliminar_item_catalogo_por_id(COLL_CARDS, carta_id)

# Resultados
async def crear_o_actualizar_resultado(req: ResultadoCreateRequest) -> ResultadoResponse:
    return await guardar_item_catalogo(COLL_RESULTS, req.id, req, ResultadoResponse)

async def obtener_resultados(universo_id: Optional[str] = None, limit: Optional[int] = None, skip: int = 0) -> List[ResultadoResponse]:
    return await listar_items_catalogo(COLL_RESULTS, ResultadoResponse, universo_id, limit, skip)

async def obtener_resultado_por_id(resultado_id: str) -> Optional[ResultadoResponse]:
    return await obtener_item_catalogo_por_id(COLL_RESULTS, resultado_id, ResultadoResponse)

async def eliminar_resultado(resultado_id: str) -> bool:
    return await eliminar_item_catalogo_por_id(COLL_RESULTS, resultado_id)

# Eventos
async def crear_o_actualizar_evento(req: EventoCreateRequest) -> EventoResponse:
    return await guardar_item_catalogo(COLL_EVENTS, req.id, req, EventoResponse)

async def obtener_eventos(universo_id: Optional[str] = None, limit: Optional[int] = None, skip: int = 0) -> List[EventoResponse]:
    return await listar_items_catalogo(COLL_EVENTS, EventoResponse, universo_id, limit, skip)

async def obtener_evento_por_id(evento_id: str) -> Optional[EventoResponse]:
    return await obtener_item_catalogo_por_id(COLL_EVENTS, evento_id, EventoResponse)

async def eliminar_evento(evento_id: str) -> bool:
    return await eliminar_item_catalogo_por_id(COLL_EVENTS, evento_id)

# Conversaciones
async def crear_o_actualizar_conversacion(req: ConversacionCreateRequest) -> ConversacionResponse:
    return await guardar_item_catalogo(COLL_CONVERSATIONS, req.id, req, ConversacionResponse)

async def obtener_conversaciones(universo_id: Optional[str] = None, limit: Optional[int] = None, skip: int = 0) -> List[ConversacionResponse]:
    return await listar_items_catalogo(COLL_CONVERSATIONS, ConversacionResponse, universo_id, limit, skip)

async def obtener_conversacion_por_id(conversacion_id: str) -> Optional[ConversacionResponse]:
    return await obtener_item_catalogo_por_id(COLL_CONVERSATIONS, conversacion_id, ConversacionResponse)

async def eliminar_conversacion(conversacion_id: str) -> bool:
    return await eliminar_item_catalogo_por_id(COLL_CONVERSATIONS, conversacion_id)

async def obtener_conversaciones_posibles_por_personajes(
    personajes_ids: List[str],
    universo_id: Optional[str] = None
) -> List[ConversacionResponse]:
    """Retorna las conversaciones cuyos requisitos de personajes están contenidos en la mano provista."""
    db = get_database()
    filtro = {}
    if universo_id:
        filtro["universo_id"] = universo_id

    cursor = db[COLL_CONVERSATIONS].find(filtro)
    docs = await cursor.to_list(length=200)

    disponibles_set = set(personajes_ids)
    validas = []
    for d in docs:
        reqs = [r.get("personajeId") for r in d.get("requisitos", [])]
        if reqs and all(r in disponibles_set for r in reqs):
            validas.append(ConversacionResponse(**d))

    return validas

# Finalizaciones
async def crear_o_actualizar_finalizacion(req: FinalizacionCreateRequest) -> FinalizacionResponse:
    return await guardar_item_catalogo(COLL_ENDINGS, req.id, req, FinalizacionResponse)

async def obtener_finalizaciones(universo_id: Optional[str] = None, limit: Optional[int] = None, skip: int = 0) -> List[FinalizacionResponse]:
    return await listar_items_catalogo(COLL_ENDINGS, FinalizacionResponse, universo_id, limit, skip)

async def obtener_finalizacion_por_id(finalizacion_id: str) -> Optional[FinalizacionResponse]:
    return await obtener_item_catalogo_por_id(COLL_ENDINGS, finalizacion_id, FinalizacionResponse)

async def eliminar_finalizacion(finalizacion_id: str) -> bool:
    return await eliminar_item_catalogo_por_id(COLL_ENDINGS, finalizacion_id)
