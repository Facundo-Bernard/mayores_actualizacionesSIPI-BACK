from fastapi import APIRouter, Depends
from typing import Dict, Any
from app.core.dependencies import get_current_admin
from app.core.rate_limit import rate_limit
from app.features.auth.schemas import (
    LoginSistemasRequest, LoginCodigoRequest, VerificarTokenRequest,
    EnviarAccesoCorreoRequest, RegisterRequest,
    VerificarCodigoRegistroRequest, ReenviarCodigoRequest, ModificarEmailRegistroRequest
)
from app.features.auth.service import (
    login_sistemas, login_codigo, verificar_token,
    enviar_acceso_correo, register_usuario,
    verificar_codigo_registro, reenviar_codigo_registro, modificar_email_registro
)

router = APIRouter(tags=["Autenticación"])

@router.post(
    "/api/auth/login-sistemas",
    dependencies=[Depends(rate_limit(max_requests=5, window_seconds=60))],
    summary="Iniciar sesión como Operador de Sistemas (Con Rate Limiting)"
)
async def endpoint_login_sistemas(req: LoginSistemasRequest):
    return await login_sistemas(req)

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

@router.post(
    "/api/admin/enviar-acceso-correo",
    summary="Despachar Magic Link de acceso por email (Solo Admin)"
)
async def endpoint_enviar_acceso_correo(
    req: EnviarAccesoCorreoRequest,
    admin: Dict[str, Any] = Depends(get_current_admin)
):
    return await enviar_acceso_correo(req)

@router.post(
    "/api/auth/register",
    dependencies=[Depends(rate_limit(max_requests=5, window_seconds=60))],
    summary="Registrar nuevo usuario alumno (Con Rate Limiting)"
)
async def endpoint_register(req: RegisterRequest):
    # Registro público siempre crea cuentas de alumno (is_admin_creation=False)
    return await register_usuario(req, is_admin_creation=False)
