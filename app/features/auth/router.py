from fastapi import APIRouter
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

@router.post("/api/auth/register", summary="Registrar nuevo usuario o iniciar verificación de email")
async def endpoint_register(req: RegisterRequest):
    return await register_usuario(req)

@router.post("/api/auth/verificar-codigo-registro", summary="Confirmar código de email y activar cuenta")
async def endpoint_verificar_codigo_registro(req: VerificarCodigoRegistroRequest):
    return await verificar_codigo_registro(req)

@router.post("/api/auth/reenviar-codigo-registro", summary="Reenviar código de activación al correo")
async def endpoint_reenviar_codigo_registro(req: ReenviarCodigoRequest):
    return await reenviar_codigo_registro(req)

@router.post("/api/auth/modificar-email-registro", summary="Corregir correo electrónico del registro pendiente")
async def endpoint_modificar_email_registro(req: ModificarEmailRegistroRequest):
    return await modificar_email_registro(req)
