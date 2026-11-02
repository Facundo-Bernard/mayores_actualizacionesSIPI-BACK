"""
identity.py
Identidad de las partidas narrativas: usuarios autenticados o invitados aislados por ``X-Guest-Id``.

Los invitados no tienen fila en ``usuarios``. Para que sus partidas no compartan el
documento de ``user_id = 0`` se derivan claves internas estables y negativas a partir
del ``guest_id``. El identificador original siempre queda guardado en ``guest_id``.
"""

import hashlib
import re
from contextvars import ContextVar
from typing import Optional, Tuple

from fastapi import Header, HTTPException

_GUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_guest_id_actual: ContextVar[Optional[str]] = ContextVar("narrative_guest_id", default=None)


def _normalizar_guest_id(valor: Optional[str]) -> Optional[str]:
    if not valor:
        return None
    limpio = valor.strip()
    if not limpio:
        return None
    if not _GUEST_ID_PATTERN.match(limpio):
        raise HTTPException(
            status_code=400,
            detail="El header 'X-Guest-Id' solo admite letras, números, guiones y guiones bajos (máx. 64).",
        )
    return limpio


async def cargar_guest_id(x_guest_id: Optional[str] = Header(None)) -> None:
    """Dependencia de request: publica el ``X-Guest-Id`` en un ContextVar."""
    token = _guest_id_actual.set(_normalizar_guest_id(x_guest_id))
    try:
        yield
    finally:
        _guest_id_actual.reset(token)


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
    """Filtro de partida que aísla invitados cuando envían ``X-Guest-Id``."""
    interno, guest_id = resolver_identidad(user_id)
    filtro = {"user_id": interno, "date": date, "game_id": "narrativo"}
    if guest_id:
        filtro["guest_id"] = guest_id
    return filtro


def id_run(user_id: int, date: str) -> str:
    interno, guest_id = resolver_identidad(user_id)
    if guest_id:
        return f"run_guest_{guest_id}_{date}"
    return f"run_{interno}_{date}"
