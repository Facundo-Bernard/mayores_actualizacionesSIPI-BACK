from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from typing import Dict, Any
from app.core.dependencies import get_current_admin, security_bearer
from app.features.sso.schemas import (
    CanjearTicketRequest,
    CanjearTicketResponse,
    CrearTicketRetornoRequest,
    CrearTicketRetornoResponse,
)
from app.features.sso.service import canjear_ticket_en_autenticador, crear_ticket_retorno

router = APIRouter(prefix="/api/auth/sso", tags=["Single Sign-On (SSO)"])


@router.post(
    "/canjear-ticket",
    response_model=CanjearTicketResponse,
    summary="Canjear un ticket descartable de entrada emitido por el Autenticador para iniciar sesión en la Torre de Control",
)
async def endpoint_canjear_ticket(req: CanjearTicketRequest):
    return await canjear_ticket_en_autenticador(req.ticket)


@router.post(
    "/crear-ticket-retorno",
    response_model=CrearTicketRetornoResponse,
    summary="Generar un ticket descartable de retorno para saltar de regreso a otro panel (Solo Admin autenticado)",
)
async def endpoint_crear_ticket_retorno(
    req: CrearTicketRetornoRequest,
    admin: Dict[str, Any] = Depends(get_current_admin),
    credentials: HTTPAuthorizationCredentials = Depends(security_bearer),
):
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere token para emitir ticket de retorno.",
        )
    return await crear_ticket_retorno(
        token_actual=credentials.credentials,
        servicio_destino=req.servicioDestino or "autenticador",
    )
