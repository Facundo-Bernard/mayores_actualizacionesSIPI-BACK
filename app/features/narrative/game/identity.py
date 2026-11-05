"""
identity.py
Identidad efectiva de las partidas narrativas.

Dos transportes, ambos verificados por el backend:

- ``Authorization: Bearer`` con JWT válido: valida firma, expiración, permisos del
  servicio y estado de la cuenta.
- ``X-Guest-Credential`` emitido por ``POST /api/auth/guest-credential``: credencial
  firmada cuyo ``guest_id`` no puede elegir el cliente.

Un JWT inválido o una credencial ausente/inválida responde 401: nunca se degrada la
sesión a un usuario compartido. Los invitados siguen sin fila en ``usuarios``: sus
partidas se aíslan con una clave interna negativa derivada del ``guest_id`` firmado.
"""

import hashlib
from contextvars import ContextVar
from typing import Optional, Tuple

from fastapi import Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from app.core.dependencies import get_current_user
from app.core.security import GUEST_ID_PATTERN, decode_guest_credential

_guest_id_actual: ContextVar[Optional[str]] = ContextVar("narrative_guest_id", default=None)


def _no_autorizado(detalle: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detalle,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _guest_id_valido(valor: Optional[str]) -> Optional[str]:
    if not valor:
        return None
    limpio = valor.strip()
    if not limpio or not GUEST_ID_PATTERN.match(limpio):
        return None
    return limpio


async def obtener_identidad_narrativa(
    authorization: Optional[str] = Header(None),
    x_guest_credential: Optional[str] = Header(None),
) -> int:
    """
    Dependencia de request: autentica usuario o invitado y publica la identidad
    efectiva en ContextVars. Devuelve el id de usuario (0 para invitado).
    """
    if authorization is not None:
        partes = authorization.split()
        if len(partes) != 2 or partes[0].lower() != "bearer" or not partes[1]:
            raise _no_autorizado("Token de autenticación inválido o expirado.")

        user = await get_current_user(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=partes[1])
        )
        user_id = int(user["id"])
        token_guest = _guest_id_actual.set(None)
        try:
            yield user_id
        finally:
            _guest_id_actual.reset(token_guest)
        return

    if not x_guest_credential:
        raise _no_autorizado(
            "Se requiere autenticación: token Bearer o credencial de invitado."
        )

    payload = decode_guest_credential(x_guest_credential)
    guest_id = _guest_id_valido((payload or {}).get("sub"))
    if not guest_id:
        raise _no_autorizado("Credencial de invitado inválida o expirada.")

    token_guest = _guest_id_actual.set(guest_id)
    try:
        yield 0
    finally:
        _guest_id_actual.reset(token_guest)


def guest_id_actual() -> Optional[str]:
    return _guest_id_actual.get()


def resolver_identidad(user_id: int) -> Tuple[int, Optional[str]]:
    """Devuelve ``(id_interno, guest_id)``. Los invitados reciben un id negativo estable."""
    guest_id = guest_id_actual()
    if user_id or not guest_id:
        return int(user_id), None
    digest = hashlib.sha256(guest_id.encode("utf-8")).digest()
    interno = -(int.from_bytes(digest[:8], "big") % 2_000_000_000) - 1
    return interno, guest_id


def filtro_run(user_id: int, date: str) -> dict:
    """Filtro de partida que aísla invitados usando la credencial verificada."""
    interno, guest_id = resolver_identidad(user_id)
    filtro = {"user_id": interno, "date": date, "game_id": "narrativo"}
    if guest_id:
        filtro["guest_id"] = guest_id
    return filtro


def id_run(user_id: int, date: str, generation: int = 1) -> str:
    interno, guest_id = resolver_identidad(user_id)
    prefijo = f"run_guest_{guest_id}_{date}" if guest_id else f"run_{interno}_{date}"
    return prefijo if generation <= 1 else f"{prefijo}_g{generation}"
