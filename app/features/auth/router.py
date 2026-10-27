from fastapi import APIRouter, Depends
from app.core.rate_limit import rate_limit
from app.features.auth.schemas import (
    LoginCodigoRequest, VerificarTokenRequest
)
from app.features.auth.service import (
    login_codigo, verificar_token
)

router = APIRouter(tags=["Autenticación"])


@router.post(
    "/api/auth/ingresar-codigo",
    dependencies=[Depends(rate_limit(max_requests=5, window_seconds=60))],
    summary="Ingreso de alumnos mediante PIN de 6 dígitos (Con Rate Limiting anti-fuerza bruta)"
)
async def endpoint_login_codigo(req: LoginCodigoRequest):
    return await login_codigo(req)


@router.post("/api/auth/verificar-token", summary="Verificar validez de token JWT y estado activo")
async def endpoint_verificar_token(req: VerificarTokenRequest):
    return await verificar_token(req)

