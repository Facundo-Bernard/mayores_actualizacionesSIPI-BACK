from fastapi import APIRouter, Header, Query, HTTPException, Depends
from typing import Optional

from app.core.security import decode_access_token
from app.features.narrative.schemas import (
    IniciarPartidaRequest,
    ElegirCartaMesRequest,
    DecidirEventoRequest,
    ResponderConversacionRequest,
    AvanzarMesRequest,
    ReiniciarPartidaRequest,
    SetupDesafioResponse,
    EstadoPartidaActivaResponse
)
from app.features.narrative.service import (
    obtener_setup_desafio,
    reiniciar_partida,
    obtener_partida_activa,
    iniciar_partida,
    elegir_carta_mes,
    decidir_evento,
    responder_conversacion,
    avanzar_mes
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
    summary="Obtener el estado vivo de la partida activa del alumno"
)
async def endpoint_obtener_partida_activa(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha YYYY-MM-DD"),
    user_id: int = Depends(_get_current_user_id)
):
    return await obtener_partida_activa(user_id=user_id, date=date)

@router.post(
    "/iniciar",
    response_model=EstadoPartidaActivaResponse,
    summary="Fase 0: Iniciar partida eligiendo 3 miembros de corte y 3 cartas iniciales"
)
async def endpoint_iniciar_partida(
    req: IniciarPartidaRequest,
    user_id: int = Depends(_get_current_user_id)
):
    return await iniciar_partida(user_id=user_id, req=req)

@router.post(
    "/elegir-carta-mes",
    response_model=EstadoPartidaActivaResponse,
    summary="Fase 1: Elegir 1 de las 3 cartas del mazo mensual y sortear evento"
)
async def endpoint_elegir_carta_mes(
    req: ElegirCartaMesRequest,
    user_id: int = Depends(_get_current_user_id)
):
    return await elegir_carta_mes(user_id=user_id, req=req)

@router.post(
    "/decidir-evento",
    response_model=EstadoPartidaActivaResponse,
    summary="Fase 2: Elegir opción A, B o C en el evento del mes (tirada de probabilidad)"
)
async def endpoint_decidir_evento(
    req: DecidirEventoRequest,
    user_id: int = Depends(_get_current_user_id)
):
    return await decidir_evento(user_id=user_id, req=req)

@router.post(
    "/responder-conversacion",
    response_model=EstadoPartidaActivaResponse,
    summary="Fase 3: Intervenir en el diálogo entre 2 miembros de la corte"
)
async def endpoint_responder_conversacion(
    req: ResponderConversacionRequest,
    user_id: int = Depends(_get_current_user_id)
):
    return await responder_conversacion(user_id=user_id, req=req)

@router.post(
    "/avanzar-mes",
    response_model=EstadoPartidaActivaResponse,
    summary="Fase 4: Guardar balance del mes y avanzar al siguiente (o epílogo Mes 12)"
)
async def endpoint_avanzar_mes(
    req: AvanzarMesRequest,
    user_id: int = Depends(_get_current_user_id)
):
    return await avanzar_mes(user_id=user_id, req=req)
