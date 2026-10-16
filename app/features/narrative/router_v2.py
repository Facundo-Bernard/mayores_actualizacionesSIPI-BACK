from fastapi import APIRouter, Header, Query, HTTPException, Depends
from typing import Optional, List

from app.core.security import decode_access_token
from app.features.narrative.schemas import (
    IniciarPartidaRequest,
    ElegirCartaMesRequest,
    DecidirEventoRequest,
    ResponderConversacionRequest,
    AvanzarMesRequest,
    IniciarPartidaV2Response,
    ElegirCartaMesV2Response,
    DecidirEventoV2Response,
    ResponderConversacionV2Response,
    AvanzarMesV2Response,
    EstadoTurnoResponse
)
from app.features.narrative.service import (
    iniciar_partida_v2,
    elegir_carta_mes_v2,
    decidir_evento_v2,
    responder_conversacion_v2,
    avanzar_mes_v2,
    obtener_turno_actual
)

router_v2 = APIRouter(prefix="/api/narrative/v2/partida", tags=["Juego Narrativo - Partidas (V2 Ligero)"])

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

@router_v2.post(
    "/iniciar",
    response_model=IniciarPartidaV2Response,
    summary="[V2] Fase 0: Iniciar partida devolviendo solo recursos iniciales y las 3 cartas de draft del Mes 1"
)
async def endpoint_v2_iniciar_partida(
    req: IniciarPartidaRequest,
    user_id: int = Depends(_get_current_user_id)
):
    return await iniciar_partida_v2(user_id=user_id, req=req)

@router_v2.post(
    "/elegir-carta-mes",
    response_model=ElegirCartaMesV2Response,
    summary="[V2] Fase 1: Elegir carta de draft mensual devolviendo solo el evento sorteado"
)
async def endpoint_v2_elegir_carta_mes(
    req: ElegirCartaMesRequest,
    user_id: int = Depends(_get_current_user_id)
):
    return await elegir_carta_mes_v2(user_id=user_id, req=req)

@router_v2.post(
    "/decidir-evento",
    response_model=DecidirEventoV2Response,
    summary="[V2] Fase 2: Decidir opción en evento devolviendo solo el resultado y el diálogo si hubo"
)
async def endpoint_v2_decidir_evento(
    req: DecidirEventoRequest,
    user_id: int = Depends(_get_current_user_id)
):
    return await decidir_evento_v2(user_id=user_id, req=req)

@router_v2.post(
    "/responder-conversacion",
    response_model=ResponderConversacionV2Response,
    summary="[V2] Fase 3: Responder diálogo de corte devolviendo afinidad actualizada y consecuencia"
)
async def endpoint_v2_responder_conversacion(
    req: ResponderConversacionRequest,
    user_id: int = Depends(_get_current_user_id)
):
    return await responder_conversacion_v2(user_id=user_id, req=req)

@router_v2.post(
    "/avanzar-mes",
    response_model=AvanzarMesV2Response,
    summary="[V2] Fase 4: Avanzar mes devolviendo recursos post-pasivos y las 3 nuevas cartas de draft"
)
async def endpoint_v2_avanzar_mes(
    req: AvanzarMesRequest,
    user_id: int = Depends(_get_current_user_id)
):
    return await avanzar_mes_v2(user_id=user_id, req=req)

@router_v2.get(
    "/estado",
    response_model=EstadoTurnoResponse,
    summary="[V2] Consultar estado reactivo del turno actual para sincronización / F5"
)
async def endpoint_v2_obtener_estado_turno(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha YYYY-MM-DD"),
    user_id: int = Depends(_get_current_user_id)
):
    return await obtener_turno_actual(user_id=user_id, date=date)
