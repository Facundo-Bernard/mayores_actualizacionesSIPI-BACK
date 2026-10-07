import random
from datetime import datetime, timezone
from fastapi import HTTPException, status
from app.core.database import get_database, get_next_sequence_value
from app.core.security import verify_password, get_password_hash, create_access_token, decode_access_token
from app.core.config import settings
from app.features.auth.schemas import (
    LoginSistemasRequest, LoginCodigoRequest, VerificarTokenRequest,
    EnviarAccesoCorreoRequest, RegisterRequest
)
from app.features.auth.email_service import enviar_magic_link

def format_user_response(user: dict) -> dict:
    """Formatea el documento de MongoDB al contrato JSON esperado por el frontend."""
    date_start = user.get("date_start")
    if isinstance(date_start, datetime):
        date_start_str = date_start.strftime("%Y-%m-%dT%H:%M:%S")
    else:
        date_start_str = date_start

    date_end = user.get("date_end")
    if isinstance(date_end, datetime):
        date_end_str = date_end.strftime("%Y-%m-%d")
    else:
        date_end_str = date_end

    return {
        "id": user.get("id"),
        "name": user.get("name", ""),
        "email": user.get("email", ""),
        "codigoAcceso": user.get("codigo_acceso", ""),
        "tipoUsuario": user.get("tipo_usuario", 1),
        "black": bool(user.get("black", False)),
        "activo": bool(user.get("activo", True)),
        "dateStart": date_start_str,
        "dateEnd": date_end_str
    }

async def login_sistemas(req: LoginSistemasRequest):
    db = get_database()
    user = await db["usuarios"].find_one({"email": req.email.lower().strip()})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas"
        )
    
    if user.get("activo") is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta se encuentra inactiva. Contacta al administrador del sistema."
        )
        
    if user.get("tipo_usuario") != 2:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: Se requieren permisos de Operador de Sistemas"
        )

    if not verify_password(req.password, user.get("password", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas"
        )

    token = create_access_token(user)
    return {
        "token": token,
        "user": format_user_response(user)
    }

async def login_codigo(req: LoginCodigoRequest):
    db = get_database()
    code = req.codigoAcceso.strip()
    user = await db["usuarios"].find_one({"codigo_acceso": code})

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Código de acceso incorrecto"
        )

    if user.get("activo") is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta se encuentra inactiva. Contacta al administrador."
        )

    token = create_access_token(user)
    return {
        "token": token,
        "user": format_user_response(user)
    }

async def verificar_token(req: VerificarTokenRequest):
    payload = decode_access_token(req.token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado"
        )

    user_id = payload.get("id")
    email = payload.get("email")
    
    db = get_database()
    query = {}
    if user_id:
        query["id"] = int(user_id)
    elif email:
        query["email"] = email

    user = await db["usuarios"].find_one(query)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    if user.get("activo") is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta se encuentra inactiva. Contacta al administrador."
        )

    return {
        "valid": True,
        "user": format_user_response(user)
    }

async def enviar_acceso_correo(req: EnviarAccesoCorreoRequest):
    db = get_database()
    user = await db["usuarios"].find_one({"email": req.email.lower().strip()})

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró ningún usuario con ese correo electrónico"
        )

    if user.get("activo") is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario se encuentra inactivo. Debe ser activado antes de enviar enlaces de acceso."
        )

    token = create_access_token(user)
    base_url = settings.FRONTEND_URL.rstrip("/")
    redirect = req.redirectPath.lstrip("/") if req.redirectPath else "mis-cursos"
    access_url = f"{base_url}/{redirect}?token={token}"

    ok = await enviar_magic_link(
        to_email=user["email"],
        user_name=user.get("name", "Estimado alumno"),
        access_url=access_url,
        codigo_acceso=user.get("codigo_acceso")
    )

    if not ok:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al enviar el correo electrónico"
        )

    return {
        "success": True,
        "message": f"Correo de acceso enviado con éxito a {user['email']}"
    }

async def register_usuario(req: RegisterRequest):
    db = get_database()
    email_clean = req.email.lower().strip()

    existing = await db["usuarios"].find_one({"email": email_clean})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado"
        )

    # Generar ID secuencial numérico atómico
    user_id = await get_next_sequence_value("usuario_id")

    # Generar código PIN de 6 dígitos único si no fue provisto
    codigo = req.codigoAcceso
    if not codigo:
        while True:
            codigo = str(random.randint(100000, 999999))
            code_exists = await db["usuarios"].find_one({"codigo_acceso": codigo})
            if not code_exists:
                break

    pwd_hash = get_password_hash(req.password) if req.password else None

    doc = {
        "id": user_id,
        "name": req.name.strip(),
        "email": email_clean,
        "password": pwd_hash,
        "codigo_acceso": codigo,
        "tipo_usuario": req.tipoUsuario if req.tipoUsuario is not None else 1,
        "black": bool(req.black) if req.black is not None else False,
        "activo": bool(req.activo) if req.activo is not None else True,
        "date_start": datetime.now(timezone.utc),
        "date_end": None,
        "progresos": []
    }

    await db["usuarios"].insert_one(doc)
    return format_user_response(doc)
