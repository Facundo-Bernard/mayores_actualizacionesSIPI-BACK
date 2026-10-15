import time
from collections import defaultdict, deque
from threading import Lock
from fastapi import Request, HTTPException, status
from app.core.security import decode_access_token

class InMemoryRateLimiter:
    def __init__(self):
        # Mapea clave (ip + endpoint) -> deque de timestamps
        self._history = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, max_requests: int, window_seconds: int):
        now = time.time()
        with self._lock:
            timestamps = self._history[key]
            # Limpiar marcas de tiempo fuera de la ventana
            while timestamps and timestamps[0] <= now - window_seconds:
                timestamps.popleft()

            if len(timestamps) >= max_requests:
                earliest = timestamps[0]
                retry_after = int(window_seconds - (now - earliest)) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Demasiados intentos. Por favor espera {max(1, retry_after)} segundos antes de reintentar.",
                    headers={"Retry-After": str(max(1, retry_after))}
                )

            timestamps.append(now)

rate_limiter = InMemoryRateLimiter()

def rate_limit(max_requests: int = 5, window_seconds: int = 60):
    """
    Dependencia de FastAPI para limitar la tasa de peticiones por IP en endpoints sensibles.
    Permite bypass automático si la petición proviene de un Administrador autenticado.
    """
    async def dependency(request: Request):
        # Si la petición incluye un token de administrador válido, omitir límite
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
          token = auth_header.split(" ")[1]
          payload = decode_access_token(token)
          if payload and (payload.get("tipoUsuario") == 2 or payload.get("rol") == 2):
              return

        # Obtener IP real considerando proxy inverso (Caddy/Nginx)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        route_key = f"{client_ip}:{request.url.path}"
        rate_limiter.check(route_key, max_requests, window_seconds)

    return dependency
