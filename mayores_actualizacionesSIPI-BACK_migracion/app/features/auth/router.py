from fastapi import APIRouter
from app.features.auth.schemas import (
    LoginSistemasRequest, LoginCodigoRequest, VerificarTokenRequest,
    EnviarAccesoCorreoRequest, RegisterRequest
)
from app.features.auth.service import (
    login_sistemas, login_codigo, verificar_token,
    enviar_acceso_correo, register_usuario
)

router = APIRouter(tags=["Autenticación"])

@router.post("/api/auth/login-sistemas", summary="Iniciar sesión como Operador de Sistemas")
async def endpoint_login_sistemas(req: LoginSistemasRequest):
    return await login_sistemas(req)

@router.post("/api/auth/ingresar-codigo", summary="Ingreso de alumnos mediante PIN de 6 dígitos")
async def endpoint_login_codigo(req: LoginCodigoRequest):
    return await login_codigo(req)

@router.post("/api/auth/verificar-token", summary="Verificar validez de token JWT y estado activo")
async def endpoint_verificar_token(req: VerificarTokenRequest):
    return await verificar_token(req)

@router.post("/api/admin/enviar-acceso-correo", summary="Despachar Magic Link de acceso por email")
async def endpoint_enviar_acceso_correo(req: EnviarAccesoCorreoRequest):
    return await enviar_acceso_correo(req)

@router.post("/api/auth/register", summary="Registrar nuevo usuario")
async def endpoint_register(req: RegisterRequest):
    return await register_usuario(req)
