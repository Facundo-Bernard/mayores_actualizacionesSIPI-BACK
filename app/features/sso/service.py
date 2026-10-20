import httpx
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from app.core.config import settings
from app.features.auth.service import sync_local_user_from_auth_service, format_user_response


async def canjear_ticket_en_autenticador(ticket: str) -> Dict[str, Any]:
    """
    Canjea el ticket efímero de acceso contra el microservicio central de Autenticación.
    Al validarse, el Autenticador quema el ticket en el mismo instante y emite el JWT oficial.
    SIPI-BACK sincroniza de inmediato el perfil local del administrador.
    """
    if not ticket or not ticket.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El ticket es obligatorio para realizar el canje.",
        )

    auth_url = f"{settings.AUTH_SERVICE_URL.rstrip('/')}/auth/sso/consume-ticket"
    payload = {
        "ticket": ticket.strip(),
        "servicio": "mayoresactualizaciones",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(auth_url, json=payload)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Servicio de autenticación central no disponible ({settings.AUTH_SERVICE_URL}): {str(exc)}",
        )

    if resp.status_code != 200:
        error_detail = "Ticket inválido, expirado o ya utilizado."
        try:
            err_data = resp.json()
            if "detail" in err_data:
                error_detail = err_data["detail"]
        except Exception:
            pass
        raise HTTPException(status_code=resp.status_code, detail=error_detail)

    data = resp.json()
    remote_user = data.get("user") or {}
    token = data.get("token")

    # Sincronización atómica por ID
    local_user = await sync_local_user_from_auth_service(remote_user)

    return {
        "success": True,
        "message": "Acceso SSO concedido exitosamente.",
        "token": token,
        "user": format_user_response(local_user),
    }


async def crear_ticket_retorno(token_actual: str, servicio_destino: str = "autenticador") -> Dict[str, Any]:
    """
    Solicita al Autenticador Central un ticket efímero de retorno
    para que el administrador pueda saltar de regreso al panel central de usuarios.
    """
    auth_url = f"{settings.AUTH_SERVICE_URL.rstrip('/')}/auth/sso/create-ticket"
    payload = {
        "servicio": servicio_destino.strip().lower(),
    }
    headers = {
        "Authorization": f"Bearer {token_actual}",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(auth_url, json=payload, headers=headers)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Servicio de autenticación central no disponible ({settings.AUTH_SERVICE_URL}): {str(exc)}",
        )

    if resp.status_code != 200:
        error_detail = "No se pudo generar el ticket de retorno SSO."
        try:
            err_data = resp.json()
            if "detail" in err_data:
                error_detail = err_data["detail"]
        except Exception:
            pass
        raise HTTPException(status_code=resp.status_code, detail=error_detail)

    return resp.json()
