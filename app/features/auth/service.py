import httpx
from datetime import datetime, date, timezone
from fastapi import HTTPException, status
from app.core.database import get_database
from app.core.security import create_access_token
from app.core.config import settings
from app.features.auth.schemas import (
    LoginSistemasRequest, LoginCodigoRequest, VerificarTokenRequest,
    RegisterRequest
)

def format_user_response(user: dict) -> dict:
    """Formatea el documento de MongoDB al contrato JSON esperado por el frontend."""
    date_start = user.get("date_start")
    if isinstance(date_start, datetime):
        date_start_str = date_start.strftime("%Y-%m-%dT%H:%M:%S")
    elif isinstance(date_start, date):
        date_start_str = date_start.strftime("%Y-%m-%dT00:00:00")
    else:
        date_start_str = date_start

    date_end = user.get("date_end")
    if isinstance(date_end, (datetime, date)):
        date_end_str = date_end.strftime("%Y-%m-%d")
    else:
        date_end_str = date_end

    estado_id = user.get("estado_id", 2 if user.get("activo", True) else 3)
    estado_codigo = user.get("estado_codigo")
    if not estado_codigo:
        if estado_id == 1:
            estado_codigo = "PENDIENTE_VERIFICACION"
        elif estado_id == 2:
            estado_codigo = "ACTIVO"
        else:
            estado_codigo = "SUSPENDIDO"

    return {
        "id": user.get("id"),
        "name": user.get("name", ""),
        "email": user.get("email", ""),
        "codigoAcceso": user.get("codigo_acceso", ""),
        "tipoUsuario": user.get("tipo_usuario", 1),
        "black": bool(user.get("black", False)),
        "activo": bool(user.get("activo", True)),
        "estadoId": estado_id,
        "estadoCodigo": estado_codigo,
        "dateStart": date_start_str,
        "dateEnd": date_end_str
    }

async def sync_local_user_from_auth_service(remote_user: dict) -> dict:
    """
    Sincroniza o crea el usuario en la coleccion local 'usuarios' de MongoDB (mayores_actualizaciones).
    El microservicio central de Autenticacion es el UNICO dueno de la verdad del ID numerico y la identidad.
    Utiliza una operacion atomica de 'upsert' por 'id' que garantiza que nunca ocurran colisiones de clave duplicada.
    """
    if not remote_user:
        return {}

    db = get_database()
    user_id = int(remote_user["id"])
    email = remote_user.get("email", "").lower().strip()
    name = remote_user.get("name") or remote_user.get("nombre") or ""
    codigo_acceso = remote_user.get("codigoAcceso") or remote_user.get("codigo_acceso") or ""
    tipo_usuario = int(remote_user.get("tipoUsuario") or remote_user.get("tipo_usuario") or 1)
    black = bool(remote_user.get("black", False))
    activo = bool(remote_user.get("activo", True))
    estado_id = int(remote_user.get("estadoId") or remote_user.get("estado_id") or 2)
    estado_codigo = remote_user.get("estadoCodigo") or remote_user.get("estado_codigo") or "ACTIVO"

    update_fields = {
        "id": user_id,
        "name": name,
        "email": email,
        "codigo_acceso": codigo_acceso,
        "tipo_usuario": tipo_usuario,
        "black": black,
        "activo": activo,
        "estado_id": estado_id,
        "estado_codigo": estado_codigo,
    }

    if email:
        await db["usuarios"].delete_many({"email": email, "id": {"$ne": user_id}})

    await db["usuarios"].update_one(
        {"id": user_id},
        {
            "$set": update_fields,
            "$setOnInsert": {
                "date_start": datetime.now(timezone.utc),
                "date_end": None,
                "progresos": [],
                "puntos": 0
            }
        },
        upsert=True
    )

    local_user = await db["usuarios"].find_one({"id": user_id})
    return local_user or {}

async def login_sistemas(req: LoginSistemasRequest):
    """
    Autentica al operador de sistemas delegando la verificación de credenciales
    al microservicio central de Autenticación.
    """
    auth_url = f"{settings.AUTH_SERVICE_URL.rstrip('/')}/auth/login"
    payload = {
        "email": req.email.lower().strip(),
        "password": req.password,
        "servicio": "mayoresactualizaciones"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(auth_url, json=payload)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Servicio de autenticación central no disponible ({settings.AUTH_SERVICE_URL}): {str(exc)}"
        )

    if resp.status_code != 200:
        error_detail = "Credenciales incorrectas"
        try:
            err_data = resp.json()
            if "detail" in err_data:
                error_detail = err_data["detail"]
        except Exception:
            pass
        raise HTTPException(
            status_code=resp.status_code,
            detail=error_detail
        )

    data = resp.json()
    remote_user = data.get("user") or {}
    token = data.get("token")

    tipo_usuario = int(remote_user.get("tipoUsuario") or remote_user.get("tipo_usuario") or 1)
    if tipo_usuario != 2:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: Se requieren permisos de Operador de Sistemas"
        )

    local_user = await sync_local_user_from_auth_service(remote_user)

    return {
        "success": True,
        "message": "Inicio de sesión exitoso",
        "token": token,
        "user": format_user_response(local_user)
    }

async def login_codigo(req: LoginCodigoRequest):
    """
    Autentica a los alumnos mediante su PIN/Código de acceso delegando
    la validación al microservicio central de Autenticación.
    """
    code = req.get_codigo()
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El código es obligatorio"
        )

    auth_url = f"{settings.AUTH_SERVICE_URL.rstrip('/')}/auth/validar-acceso"
    payload = {
        "codigoAcceso": code,
        "servicio": "mayoresactualizaciones"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(auth_url, json=payload)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Servicio de autenticación central no disponible ({settings.AUTH_SERVICE_URL}): {str(exc)}"
        )

    if resp.status_code != 200:
        error_detail = "Código de acceso incorrecto"
        try:
            err_data = resp.json()
            if "detail" in err_data:
                error_detail = err_data["detail"]
        except Exception:
            pass
        raise HTTPException(
            status_code=resp.status_code,
            detail=error_detail
        )

    data = resp.json()
    if not data.get("allowed"):
        message = data.get("message") or "Acceso denegado al servicio."
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN if data.get("success") else status.HTTP_401_UNAUTHORIZED,
            detail=message
        )

    remote_user = data.get("user") or {}
    token = data.get("token")

    local_user = await sync_local_user_from_auth_service(remote_user)

    return {
        "success": True,
        "message": "Acceso concedido exitosamente.",
        "token": token,
        "user": format_user_response(local_user)
    }

async def verificar_token(req: VerificarTokenRequest):
    """
    Verifica la validez de un token JWT contra el microservicio central de Autenticación.
    """
    auth_url = f"{settings.AUTH_SERVICE_URL.rstrip('/')}/auth/validar-acceso"
    payload = {
        "token": req.token,
        "servicio": "mayoresactualizaciones"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(auth_url, json=payload)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Servicio de autenticación central no disponible ({settings.AUTH_SERVICE_URL}): {str(exc)}"
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado"
        )

    data = resp.json()
    if not data.get("allowed"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=data.get("message") or "Token inválido o no autorizado para el servicio."
        )

    remote_user = data.get("user") or {}
    local_user = await sync_local_user_from_auth_service(remote_user)

    return {
        "success": True,
        "valid": True,
        "message": "Token verificado con éxito",
        "user": format_user_response(local_user)
    }

async def register_usuario(req: RegisterRequest, is_admin_creation: bool = False):
    """
    Registra un nuevo usuario delegando la creación y generación de PIN
    al microservicio central de Autenticación.
    """
    auth_url = f"{settings.AUTH_SERVICE_URL.rstrip('/')}/auth/register"
    tipo_usuario = req.tipoUsuario if (is_admin_creation and req.tipoUsuario is not None) else 1
    black = bool(req.black) if (is_admin_creation and req.black is not None) else False
    activo = bool(req.activo) if (is_admin_creation and req.activo is not None) else True

    payload = {
        "name": req.name.strip(),
        "email": req.email.lower().strip(),
        "password": req.password,
        "codigoAcceso": req.codigoAcceso,
        "servicioOrigen": "mayoresactualizaciones",
        "tipoUsuario": tipo_usuario,
        "black": black,
        "activo": activo,
        "servicios": {"mayoresactualizaciones": True}
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(auth_url, json=payload)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Servicio de autenticación central no disponible ({settings.AUTH_SERVICE_URL}): {str(exc)}"
        )

    if resp.status_code != 200:
        error_detail = "Error al registrar el usuario en el Autenticador Central"
        try:
            err_data = resp.json()
            if "detail" in err_data:
                error_detail = err_data["detail"]
        except Exception:
            pass
        raise HTTPException(
            status_code=resp.status_code,
            detail=error_detail
        )

    data = resp.json()
    remote_user = data.get("user") or {}
    token = data.get("token")

    local_user = await sync_local_user_from_auth_service(remote_user)

    return {
        "success": True,
        "message": data.get("message") or "Usuario registrado con éxito.",
        "token": token,
        "user": format_user_response(local_user)
    }
