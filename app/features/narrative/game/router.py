"""
router.py
Controladores FastAPI del módulo de Juego Narrativo:
- router (/api/narrative/partida): Setup diario, reinicio y modales de consulta bajo demanda.
- router_v2 (/api/narrative/v2/partida): Ciclo reactivo nativo V2 (iniciar, draft, evento, diálogo, avance, estado).
"""

from fastapi import APIRouter, Header, Query, HTTPException, Depends
from typing import Optional, List

from app.core.security import decode_access_token
from app.features.narrative.schemas.game_schemas import (
    IniciarPartidaRequest,
    ElegirCartaMesRequest,
    DecidirEventoRequest,
    ResponderConversacionRequest,
    AvanzarMesRequest,
    ReiniciarPartidaRequest,
    ConversacionesPosiblesRequest,
    IniciarPartidaV2Response,
    ElegirCartaMesV2Response,
    DecidirEventoV2Response,
    ResponderConversacionV2Response,
    AvanzarMesV2Response,
    EstadoTurnoResponse,
    SetupDesafioResponse,
    HistorialPartidaResponse,
    InventarioPartidaResponse,
    CortePartidaResponse,
    FinalizacionPartidaResponse,
    EventoTurnoResponse
)
from app.features.narrative.schemas.catalog_schemas import (
    ConversacionResponse,
    ResultadoResponse,
    CartaResponse
)
from app.features.narrative.schemas.v2_graph_schemas import (
    AvanzarNodoV2Request,
    EstadoGrafoV2Response
)
from app.features.narrative.game.motor_v2.v2_graph_service import (
    avanzar_nodo_v2,
    obtener_grafo_actual_v2,
    iniciar_evento_mes_v2,
    iniciar_conversacion_mes_v2
)
from app.features.narrative.game.setup_service import (
    obtener_setup_desafio,
    iniciar_partida,
    reiniciar_partida
)
from app.features.narrative.game.turn_service import elegir_carta_mes
from app.features.narrative.game.motor_v1.turn_service import (
    decidir_evento,
    responder_conversacion
)
from app.features.narrative.game.transition_service import avanzar_mes
from app.features.narrative.game.modals_service import (
    obtener_historial_partida,
    obtener_inventario_partida,
    obtener_corte_partida,
    obtener_finalizacion_partida
)
from app.features.narrative.game.motor_v1.modals import (
    obtener_evento_actual_partida,
    obtener_conversacion_actual_partida,
    obtener_resultado_actual_partida,
    obtener_draft_actual_partida
)
from app.features.narrative.game.turn_state import obtener_turno_actual
from app.features.narrative.game.identity import cargar_guest_id
from app.features.narrative.admin.crud_service import (
    obtener_conversaciones_posibles_por_personajes
)

def _get_current_user_id(authorization: Optional[str] = Header(None)) -> int:
    """Extrae el ID del usuario del JWT Bearer token o usa invitado (0) si no hay cabecera."""
    if not authorization:
        return 0
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        payload = decode_access_token(parts[1])
        if payload and "id" in payload:
            try:
                return int(payload["id"])
            except (ValueError, TypeError):
                return 0
    return 0

# ============================================================================
# ROUTER V2: CICLO MENSUAL NATIVO LIGERO (/api/narrative/v2/partida)
# ============================================================================

router_v2 = APIRouter(
    prefix="/api/narrative/v2/partida",
    tags=["Juego Narrativo - Partidas (V2 Ligero)"],
    dependencies=[Depends(cargar_guest_id)],
)

@router_v2.post(
    "/iniciar",
    response_model=IniciarPartidaV2Response,
    summary="[V2] Fase 0: Iniciar partida devolviendo solo recursos iniciales y las 3 cartas de draft del Mes 1"
)
async def endpoint_v2_iniciar_partida(
    req: IniciarPartidaRequest,
    user_id: int = Depends(_get_current_user_id)
):
    """Inicia la partida para la fecha actual devolviendo recursos y mazo de draft inicial."""
    return await iniciar_partida(user_id=user_id, req=req)

@router_v2.post(
    "/elegir-carta-mes",
    response_model=ElegirCartaMesV2Response,
    summary="[V2] Fase 1: Elegir carta de draft mensual devolviendo solo el evento sorteado"
)
async def endpoint_v2_elegir_carta_mes(
    req: ElegirCartaMesRequest,
    user_id: int = Depends(_get_current_user_id)
):
    """Aplica la carta seleccionada y retorna el evento sorteado del mes (o finalización si colapsó)."""
    return await elegir_carta_mes(user_id=user_id, req=req)

@router_v2.post(
    "/decidir-evento",
    response_model=DecidirEventoV2Response,
    summary="[V1 Plano, deprecado] Fase 2: Decidir opción en evento (usar /avanzar-nodo en motor V2)",
    deprecated=True
)
async def endpoint_v2_decidir_evento(
    req: DecidirEventoRequest,
    user_id: int = Depends(_get_current_user_id)
):
    """Resuelve la tirada plana V1. En partidas V2 responde 409 y se debe usar /avanzar-nodo."""
    return await decidir_evento(user_id=user_id, req=req)

@router_v2.post(
    "/responder-conversacion",
    response_model=ResponderConversacionV2Response,
    summary="[V1 Plano, deprecado] Fase 3: Responder diálogo de corte (usar /avanzar-nodo en motor V2)",
    deprecated=True
)
async def endpoint_v2_responder_conversacion(
    req: ResponderConversacionRequest,
    user_id: int = Depends(_get_current_user_id)
):
    """Resuelve el diálogo plano V1. En partidas V2 responde 409 y se debe usar /avanzar-nodo."""
    return await responder_conversacion(user_id=user_id, req=req)

@router_v2.post(
    "/avanzar-mes",
    response_model=AvanzarMesV2Response,
    summary="[V2] Fase 4: Avanzar mes devolviendo recursos post-pasivos y las 3 nuevas cartas de draft"
)
async def endpoint_v2_avanzar_mes(
    req: AvanzarMesRequest,
    user_id: int = Depends(_get_current_user_id)
):
    """Aplica pasivos mensuales, guarda el historial y avanza al siguiente mes (o decreta fin de año)."""
    return await avanzar_mes(user_id=user_id, req=req)

@router_v2.get(
    "/estado",
    response_model=EstadoTurnoResponse,
    summary="[V2] Consultar estado reactivo del turno actual para sincronización / F5"
)
async def endpoint_v2_obtener_estado_turno(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha YYYY-MM-DD"),
    user_id: int = Depends(_get_current_user_id)
):
    """Permite al frontend restaurar el estado exacto del turno tras recargar la página."""
    return await obtener_turno_actual(user_id=user_id, date=date)

@router_v2.post(
    "/avanzar-nodo",
    response_model=EstadoGrafoV2Response,
    summary="[V2 Grafos] Avanzar un paso en el grafo activo (evento o conversación) sin spoilers"
)
async def endpoint_v2_avanzar_nodo(
    req: AvanzarNodoV2Request,
    user_id: int = Depends(_get_current_user_id)
):
    """
    Avanza un paso en el árbol narrativo activo.
    Si el siguiente nodo es intermedio, retorna el nuevo nodo a mostrar.
    Si es final, aplica impactos en recursos y afinidad y avanza la fase de la partida.
    """
    return await avanzar_nodo_v2(user_id=user_id, req=req)

@router_v2.get(
    "/grafo-actual",
    response_model=Optional[EstadoGrafoV2Response],
    summary="[V2 Grafos] Consultar el estado del grafo activo (evento o conversación) para recargas/F5"
)
async def endpoint_v2_obtener_grafo_actual(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha YYYY-MM-DD"),
    user_id: int = Depends(_get_current_user_id)
):
    """Permite restaurar el nodo activo tras recargar la página."""
    return await obtener_grafo_actual_v2(user_id=user_id, date=date)

@router_v2.post(
    "/iniciar-evento-grafo",
    response_model=EstadoGrafoV2Response,
    summary="[V2 Grafos] Iniciar un evento basado en grafos para el mes actual"
)
async def endpoint_v2_iniciar_evento_grafo(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha YYYY-MM-DD"),
    user_id: int = Depends(_get_current_user_id)
):
    """Inicia un evento V2 del pool respetando arcos narrativos y requisitos previos."""
    return await iniciar_evento_mes_v2(user_id=user_id, date=date)

@router_v2.post(
    "/iniciar-conversacion-grafo",
    response_model=Optional[EstadoGrafoV2Response],
    summary="[V2 Grafos] Iniciar una conversación basada en grafos para el mes actual"
)
async def endpoint_v2_iniciar_conversacion_grafo(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha YYYY-MM-DD"),
    user_id: int = Depends(_get_current_user_id)
):
    """Inicia una conversación V2 si los requisitos de consejeros activos se cumplen."""
    return await iniciar_conversacion_mes_v2(user_id=user_id, date=date)

# ============================================================================
# ROUTER CONSULTAS: MODALES Y SETUP (/api/narrative/partida)
# ============================================================================

router = APIRouter(
    prefix="/api/narrative/partida",
    tags=["Juego Narrativo - Consultas"],
    dependencies=[Depends(cargar_guest_id)],
)

@router.get(
    "/setup",
    response_model=SetupDesafioResponse,
    summary="Fase 0: Obtener los 5 personajes y 5 cartas ofrecidas para iniciar el día"
)
async def endpoint_obtener_setup(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha YYYY-MM-DD"),
    user_id: int = Depends(_get_current_user_id)
):
    """Consulta los 5 personajes y 5 cartas ofrecidas para la selección inicial del día."""
    return await obtener_setup_desafio(user_id=user_id, date=date)

@router.post(
    "/reiniciar",
    summary="Reiniciar partida de hoy para volver a Fase 0 (Setup limpio)"
)
async def endpoint_reiniciar_partida(
    req: ReiniciarPartidaRequest,
    user_id: int = Depends(_get_current_user_id)
):
    """Elimina la run en curso para permitir comenzar de nuevo desde el setup."""
    return await reiniciar_partida(user_id=user_id, date=req.date)

@router.post(
    "/conversaciones-posibles",
    response_model=List[ConversacionResponse],
    summary="Obtener conversaciones habilitadas según una mano de personajes (vía POST)"
)
async def endpoint_conversaciones_posibles_post(req: ConversacionesPosiblesRequest):
    """Retorna los diálogos de corte disponibles según los personajes provistos vía payload JSON."""
    return await obtener_conversaciones_posibles_por_personajes(
        personajes_ids=req.personajes_ids,
        universo_id=req.universo_id
    )

@router.get(
    "/conversaciones-posibles",
    response_model=List[ConversacionResponse],
    summary="Obtener conversaciones habilitadas según una mano de personajes (vía GET)"
)
async def endpoint_conversaciones_posibles_get(
    personajes_ids: str = Query(..., description="IDs de personajes separados por coma (ej: pj_elena,pj_marcus)"),
    universo_id: Optional[str] = Query(None, description="Filtro opcional por universo")
):
    """Retorna los diálogos de corte disponibles según los personajes provistos en Query String."""
    ids = [x.strip() for x in personajes_ids.split(",") if x.strip()]
    return await obtener_conversaciones_posibles_por_personajes(
        personajes_ids=ids,
        universo_id=universo_id
    )

@router.get(
    "/historial",
    response_model=HistorialPartidaResponse,
    summary="Consultar historial mensual acumulado de la partida (modal historial)"
)
async def endpoint_obtener_historial_partida(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha YYYY-MM-DD"),
    user_id: int = Depends(_get_current_user_id)
):
    """Retorna la bitácora histórica mes a mes con todas las elecciones y balances."""
    return await obtener_historial_partida(user_id=user_id, date=date)

@router.get(
    "/inventario",
    response_model=InventarioPartidaResponse,
    summary="Consultar cartas en mano y tags activos del jugador (modal inventario)"
)
async def endpoint_obtener_inventario_partida(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha YYYY-MM-DD"),
    user_id: int = Depends(_get_current_user_id)
):
    """Retorna el mazo de cartas acumuladas y los tags activos del jugador."""
    return await obtener_inventario_partida(user_id=user_id, date=date)

@router.get(
    "/corte",
    response_model=CortePartidaResponse,
    summary="Consultar integrantes de la corte y sus afinidades actuales (modal corte)"
)
async def endpoint_obtener_corte_partida(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha YYYY-MM-DD"),
    user_id: int = Depends(_get_current_user_id)
):
    """Retorna los 3 consejeros de la corte y su nivel de afinidad actual (0 a 100)."""
    return await obtener_corte_partida(user_id=user_id, date=date)

@router.get(
    "/finalizacion",
    response_model=FinalizacionPartidaResponse,
    summary="Consultar desenlace / finalización detallada de la partida (modal fin de juego)"
)
async def endpoint_obtener_finalizacion_partida(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha YYYY-MM-DD"),
    user_id: int = Depends(_get_current_user_id)
):
    """Retorna los datos del epílogo final (derrota o victoria anual)."""
    return await obtener_finalizacion_partida(user_id=user_id, date=date)

@router.get(
    "/evento-actual",
    response_model=Optional[EventoTurnoResponse],
    summary="[V1 Plano, deprecado] Consultar únicamente el evento activo del mes (usar /estado)",
    deprecated=True
)
async def endpoint_obtener_evento_actual(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha YYYY-MM-DD"),
    user_id: int = Depends(_get_current_user_id)
):
    """Retorna únicamente el evento del mes activo con sus opciones y probabilidades."""
    return await obtener_evento_actual_partida(user_id=user_id, date=date)

@router.get(
    "/conversacion-actual",
    response_model=Optional[ConversacionResponse],
    summary="[V1 Plano, deprecado] Consultar únicamente la conversación activa del mes (usar /estado)",
    deprecated=True
)
async def endpoint_obtener_conversacion_actual(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha YYYY-MM-DD"),
    user_id: int = Depends(_get_current_user_id)
):
    """Retorna únicamente el diálogo activo del mes o null si no se activó diálogo."""
    return await obtener_conversacion_actual_partida(user_id=user_id, date=date)

@router.get(
    "/resultado-actual",
    response_model=Optional[ResultadoResponse],
    summary="[V1 Plano, deprecado] Consultar únicamente el resultado del evento recién resuelto (usar /estado)",
    deprecated=True
)
async def endpoint_obtener_resultado_actual(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha YYYY-MM-DD"),
    user_id: int = Depends(_get_current_user_id)
):
    """Retorna únicamente el resultado obtenido tras resolver el evento."""
    return await obtener_resultado_actual_partida(user_id=user_id, date=date)

@router.get(
    "/draft-actual",
    response_model=List[CartaResponse],
    summary="[V1 Plano, deprecado] Consultar únicamente las cartas ofrecidas en el draft del mes actual (usar /estado)",
    deprecated=True
)
async def endpoint_obtener_draft_actual(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha YYYY-MM-DD"),
    user_id: int = Depends(_get_current_user_id)
):
    """Retorna únicamente las 3 cartas ofrecidas en el draft mensual activo."""
    return await obtener_draft_actual_partida(user_id=user_id, date=date)
