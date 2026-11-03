"""Rate limiting en memoria para las rutas sensibles de la plataforma.

Dos usos sobre el mismo almacén de ventana deslizante:
- ``RateLimitMiddleware``: cupo por identidad (token o IP) en economía,
  intentos y narrativo.
- ``rate_limit(...)``: dependencia por IP y endpoint para el login anti-fuerza
  bruta, con bypass para administradores autenticados.
"""

import asyncio
import hashlib
import logging
import time
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.security import decode_access_token

logger = logging.getLogger("RateLimit")


class RateLimiter:
    """Ventana deslizante con reloj inyectable para pruebas deterministas."""

    def __init__(self) -> None:
        self._hits: Dict[str, List[float]] = {}
        self._lock = asyncio.Lock()

    async def allow(self, key: str, limit: int, window: int, now: Optional[float] = None) -> Tuple[bool, int]:
        """Devuelve (permitido, segundos_para_reintentar)."""
        momento = time.monotonic() if now is None else now
        async with self._lock:
            inicio = momento - window
            hits = [t for t in self._hits.get(key, []) if t > inicio]
            if len(hits) >= limit:
                retry = max(1, int(hits[0] + window - momento) + 1)
                self._hits[key] = hits
                return False, retry
            hits.append(momento)
            self._hits[key] = hits
            if len(self._hits) > 10_000:
                self._purgar(inicio)
            return True, 0

    def reset(self) -> None:
        self._hits.clear()

    def _purgar(self, inicio: float) -> None:
        vacios = [k for k, v in self._hits.items() if not v or v[-1] <= inicio]
        for k in vacios:
            self._hits.pop(k, None)


rate_limiter = RateLimiter()


def _ip_cliente(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "desconocido"


def _es_admin(request: Request) -> bool:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return False
    payload = decode_access_token(auth_header.split(" ", 1)[1])
    if not payload:
        return False
    return payload.get("tipoUsuario") == 2 or payload.get("rol") == 2


def rate_limit(max_requests: int = 5, window_seconds: int = 60):
    """Dependencia de FastAPI para limitar por IP y endpoint (login anti-fuerza bruta)."""

    async def dependency(request: Request):
        if _es_admin(request):
            return
        clave = f"{request.url.path}:{_ip_cliente(request)}"
        permitido, reintento = await rate_limiter.allow(clave, max_requests, window_seconds)
        if not permitido:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Demasiados intentos. Por favor espera {reintento} segundos "
                    "antes de reintentar."
                ),
                headers={"Retry-After": str(reintento)},
            )

    return dependency


def _scope_para(path: str) -> Optional[Tuple[str, int]]:
    if path.startswith("/api/economy"):
        return "/api/economy", settings.RATE_LIMIT_ECONOMY_PER_MINUTE
    if path.startswith("/api/games/attempts"):
        return "/api/games/attempts", settings.RATE_LIMIT_ATTEMPTS_PER_MINUTE
    if path.startswith("/api/narrative"):
        return "/api/narrative", settings.RATE_LIMIT_NARRATIVE_PER_MINUTE
    return None


def _clave(request: Request, scope: str) -> str:
    token = request.headers.get("authorization") or ""
    if token:
        identidad = hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]
    else:
        identidad = _ip_cliente(request)
    return f"{scope}:{identidad}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.RATE_LIMIT_ENABLED or request.method == "OPTIONS":
            return await call_next(request)

        scope = _scope_para(request.url.path)
        if scope is None:
            return await call_next(request)
        scope_path, limite = scope

        permitido, reintento = await rate_limiter.allow(
            _clave(request, scope_path),
            limit=limite,
            window=settings.RATE_LIMIT_WINDOW_SECONDS,
        )
        if not permitido:
            logger.warning(
                f"[RATE LIMIT] {request.method} {request.url.path} excedió {limite} solicitudes."
            )
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(reintento)},
                content={
                    "success": False,
                    "detail": "Demasiadas solicitudes. Esperá unos segundos y reintentá.",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limite)
        return response
