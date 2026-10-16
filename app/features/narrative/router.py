from fastapi import APIRouter, Header, Query, HTTPException, Depends
from typing import Optional, List

from app.core.security import decode_access_token
from app.features.narrative.schemas import (
    IniciarPartidaRequest,
    ElegirCartaMesRequest,
    DecidirEventoRequest,
    ResponderConversacionRequest,
    AvanzarMesRequest,
    ReiniciarPartidaRequest,
    ConversacionesPosiblesRequest,
    ConversacionResponse,
    SetupDesafioResponse,
    EstadoPartidaActivaResponse,
    HistorialPartidaResponse,
    InventarioPartidaResponse,
    CortePartidaResponse,
    FinalizacionPartidaResponse,
    EstadoTurnoResponse,
    EventoTurnoResponse,
    ResultadoResponse,
    CartaResponse
)
from app.features.narrative.service import (
    obtener_setup_desafio,
    reiniciar_partida,
    obtener_partida_activa,
    iniciar_partida,
    elegir_carta_mes,
    decidir_evento,
    responder_conversacion,
    avanzar_mes,
    obtener_conversaciones_posibles_por_personajes,
    obtener_historial_partida,
    obtener_inventario_partida,
    obtener_corte_partida,
    obtener_finalizacion_partida,
    obtener_turno_actual,
    obtener_evento_actual_partida,
    obtener_conversacion_actual_partida,
    obtener_resultado_actual_partida,
    obtener_draft_actual_partida
)

router = APIRouter(prefix="/api/narrative/partida", tags=["Juego Narrativo - Partidas"])

def _get_current_user_id(authorization: Optional[str] = Header(None)) -> int:
    """
    Extrae el ID del usuario del JWT Bearer token o usa un ID de invitado (0) si no hay token.
    """
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

@router.get(
    "/setup",
    response_model=SetupDesafioResponse,
    summary="Fase 0: Obtener los 5 personajes y 5 cartas ofrecidas para iniciar el día"
)
async def endpoint_obtener_setup(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha YYYY-MM-DD"),
    user_id: int = Depends(_get_current_user_id)
):
    return await obtener_setup_desafio(user_id=user_id, date=date)

@router.post(
    "/reiniciar",
    summary="Reiniciar partida de hoy para volver a Fase 0 (Setup limpio)"
)
async def endpoint_reiniciar_partida(
    req: ReiniciarPartidaRequest,
    user_id: int = Depends(_get_current_user_id)
):
    return await reiniciar_partida(user_id=user_id, date=req.date)

@router.get(
    "/activa",
    response_model=EstadoPartidaActivaResponse,
    include_in_schema=False,
    summary="[Legacy V1] Obtener el estado vivo de la partida activa del alumno"
)
async def endpoint_obtener_partida_activa(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha YYYY-MM-DD"),
    user_id: int = Depends(_get_current_user_id)
):
    return await obtener_partida_activa(user_id=user_id, date=date)

@router.post(
    "/iniciar",
    response_model=EstadoPartidaActivaResponse,
    include_in_schema=False,
    summary="[Legacy V1] Fase 0: Iniciar partida eligiendo 3 miembros de corte y 3 cartas iniciales"
)
async def endpoint_iniciar_partida(
    req: IniciarPartidaRequest,
    user_id: int = Depends(_get_current_user_id)
):
    return await iniciar_partida(user_id=user_id, req=req)

@router.post(
    "/elegir-carta-mes",
    response_model=EstadoPartidaActivaResponse,
    include_in_schema=False,
    summary="[Legacy V1] Fase 1: Elegir 1 de las 3 cartas del mazo mensual y sortear evento"
)
async def endpoint_elegir_carta_mes(
    req: ElegirCartaMesRequest,
    user_id: int = Depends(_get_current_user_id)
):
    return await elegir_carta_mes(user_id=user_id, req=req)

@router.post(
    "/decidir-evento",
    response_model=EstadoPartidaActivaResponse,
    include_in_schema=False,
    summary="[Legacy V1] Fase 2: Elegir opción A, B o C en el evento del mes (tirada de probabilidad)"
)
async def endpoint_decidir_evento(
    req: DecidirEventoRequest,
    user_id: int = Depends(_get_current_user_id)
):
    return await decidir_evento(user_id=user_id, req=req)

@router.post(
    "/responder-conversacion",
    response_model=EstadoPartidaActivaResponse,
    include_in_schema=False,
    summary="[Legacy V1] Fase 3: Intervenir en el diálogo entre 2 miembros de la corte"
)
async def endpoint_responder_conversacion(
    req: ResponderConversacionRequest,
    user_id: int = Depends(_get_current_user_id)
):
    return await responder_conversacion(user_id=user_id, req=req)

@router.post(
    "/avanzar-mes",
    response_model=EstadoPartidaActivaResponse,
    include_in_schema=False,
    summary="[Legacy V1] Fase 4: Guardar balance del mes y avanzar al siguiente (o epílogo Mes 12)"
)
async def endpoint_avanzar_mes(
    req: AvanzarMesRequest,
    user_id: int = Depends(_get_current_user_id)
):
    return await avanzar_mes(user_id=user_id, req=req)

@router.post(
    "/conversaciones-posibles",
    response_model=List[ConversacionResponse],
    summary="Obtener conversaciones habilitadas según una mano de personajes (vía POST)"
)
async def endpoint_conversaciones_posibles_post(req: ConversacionesPosiblesRequest):
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
    ids = [x.strip() for x in personajes_ids.split(",") if x.strip()]
    return await obtener_conversaciones_posibles_por_personajes(
        personajes_ids=ids,
        universo_id=universo_id
    )

# ============================================================================
# ENDPOINTS DE CONSULTA ESPECIALIZADOS (BAJO DEMANDA)
# ============================================================================

@router.get(
    "/historial",
    response_model=HistorialPartidaResponse,
    summary="Consultar historial mensual acumulado de la partida (bajo demanda)"
)
async def endpoint_obtener_historial_partida(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha YYYY-MM-DD"),
    user_id: int = Depends(_get_current_user_id)
):
    return await obtener_historial_partida(user_id=user_id, date=date)

@router.get(
    "/inventario",
    response_model=InventarioPartidaResponse,
    summary="Consultar cartas en mano y tags activos del jugador (bajo demanda)"
)
async def endpoint_obtener_inventario_partida(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha YYYY-MM-DD"),
    user_id: int = Depends(_get_current_user_id)
):
    return await obtener_inventario_partida(user_id=user_id, date=date)

@router.get(
    "/corte",
    response_model=CortePartidaResponse,
    summary="Consultar integrantes de la corte y sus afinidades actuales (bajo demanda)"
)
async def endpoint_obtener_corte_partida(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha YYYY-MM-DD"),
    user_id: int = Depends(_get_current_user_id)
):
    return await obtener_corte_partida(user_id=user_id, date=date)

@router.get(
    "/finalizacion",
    response_model=FinalizacionPartidaResponse,
    summary="Consultar desenlace / finalización detallada de la partida (bajo demanda)"
)
async def endpoint_obtener_finalizacion_partida(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha YYYY-MM-DD"),
    user_id: int = Depends(_get_current_user_id)
):
    return await obtener_finalizacion_partida(user_id=user_id, date=date)

@router.get(
    "/turno",
    response_model=EstadoTurnoResponse,
    include_in_schema=False,
    summary="[Legacy] Consultar estado ultraligero del turno actual sin cargar historial ni inventario"
)
async def endpoint_obtener_turno_actual(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha YYYY-MM-DD"),
    user_id: int = Depends(_get_current_user_id)
):
    return await obtener_turno_actual(user_id=user_id, date=date)

@router.get(
    "/evento-actual",
    response_model=Optional[EventoTurnoResponse],
    summary="Consultar únicamente el evento activo del mes (con opciones y probabilidades)"
)
async def endpoint_obtener_evento_actual(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha YYYY-MM-DD"),
    user_id: int = Depends(_get_current_user_id)
):
    return await obtener_evento_actual_partida(user_id=user_id, date=date)

@router.get(
    "/conversacion-actual",
    response_model=Optional[ConversacionResponse],
    summary="Consultar únicamente la conversación activa del mes (o null si no hubo)"
)
async def endpoint_obtener_conversacion_actual(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha YYYY-MM-DD"),
    user_id: int = Depends(_get_current_user_id)
):
    return await obtener_conversacion_actual_partida(user_id=user_id, date=date)

@router.get(
    "/resultado-actual",
    response_model=Optional[ResultadoResponse],
    summary="Consultar únicamente el resultado del evento recién resuelto"
)
async def endpoint_obtener_resultado_actual(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha YYYY-MM-DD"),
    user_id: int = Depends(_get_current_user_id)
):
    return await obtener_resultado_actual_partida(user_id=user_id, date=date)

@router.get(
    "/draft-actual",
    response_model=List[CartaResponse],
    summary="Consultar únicamente las cartas ofrecidas en el draft del mes actual"
)
async def endpoint_obtener_draft_actual(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha YYYY-MM-DD"),
    user_id: int = Depends(_get_current_user_id)
):
    return await obtener_draft_actual_partida(user_id=user_id, date=date)


