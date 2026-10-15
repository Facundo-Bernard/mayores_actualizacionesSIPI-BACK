import random
from datetime import datetime, date, timezone
from fastapi import HTTPException, status
from app.core.database import get_database, get_next_sequence_value
from app.core.security import verify_password, get_password_hash, create_access_token, decode_access_token
from app.core.config import settings
from app.features.auth.schemas import (
    LoginSistemasRequest, LoginCodigoRequest, VerificarTokenRequest,
    EnviarAccesoCorreoRequest, RegisterRequest,
    VerificarCodigoRegistroRequest, ReenviarCodigoRequest, ModificarEmailRegistroRequest
)
from app.features.auth.email_service import enviar_magic_link, enviar_codigo_activacion

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
        "success": True,
        "message": "Inicio de sesión exitoso",
        "token": token,
        "user": format_user_response(user)
    }

async def login_codigo(req: LoginCodigoRequest):
    db = get_database()
    code = req.get_codigo()
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El código es obligatorio"
        )
    user = await db["usuarios"].find_one({"codigo_acceso": code})

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Código de acceso incorrecto"
        )

    estado_id = user.get("estado_id")
    if estado_id == 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta aún no está confirmada. Por favor, ingresá el código de 6 dígitos que enviamos a tu correo para activarla."
        )

    if user.get("activo") is False or estado_id == 3:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta se encuentra inactiva. Contacta al administrador."
        )

    token = create_access_token(user)
    return {
        "success": True,
        "message": "Acceso concedido exitosamente.",
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
        "success": True,
        "valid": True,
        "message": "Token verificado con éxito",
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

async def register_usuario(req: RegisterRequest, is_admin_creation: bool = False):
    db = get_database()
    email_clean = req.email.lower().strip()
    name_clean = req.name.strip()

    existing = await db["usuarios"].find_one({"email": email_clean})
    if existing:
        # Si ya existe pero está pendiente de verificación, reenviar código sin dar error
        if existing.get("estado_id") == 1:
            await db["usuarios"].update_one(
                {"id": existing["id"]},
                {"$set": {"name": name_clean}}
            )
            codigo = existing.get("codigo_acceso")
            await enviar_codigo_activacion(email_clean, name_clean, codigo)
            return {
                "success": True,
                "status": "PENDIENTE_VERIFICACION",
                "message": "¡Ya tenías un registro iniciado! Te reenviamos tu código a tu correo.",
                "email": email_clean
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El correo electrónico ya está registrado. Podés ingresar directamente con tu código en 'Tengo mi código'."
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

    # Prevenir escalada de privilegios (Mass Assignment): solo administradores autenticados pueden definir roles elevados
    tipo_usuario = req.tipoUsuario if (is_admin_creation and req.tipoUsuario is not None) else 1
    black = bool(req.black) if (is_admin_creation and req.black is not None) else False

    # Si se crea explícitamente como activo desde admin, queda ACTIVO (id 2). Si es registro público, PENDIENTE_VERIFICACION (id 1)
    is_admin_preactive = (is_admin_creation and req.activo is True)
    estado_id = 2 if is_admin_preactive else 1
    estado_codigo = "ACTIVO" if is_admin_preactive else "PENDIENTE_VERIFICACION"
    activo = True if is_admin_preactive else False

    doc = {
        "id": user_id,
        "name": name_clean,
        "email": email_clean,
        "password": pwd_hash,
        "codigo_acceso": codigo,
        "tipo_usuario": tipo_usuario,
        "black": black,
        "activo": activo,
        "estado_id": estado_id,
        "estado_codigo": estado_codigo,
        "date_start": datetime.now(timezone.utc),
        "date_end": None,
        "progresos": []
    }

    await db["usuarios"].insert_one(doc)

    # Si requiere verificación de email
    if estado_id == 1:
        await enviar_codigo_activacion(email_clean, name_clean, codigo)
        return {
            "success": True,
            "status": "PENDIENTE_VERIFICACION",
            "message": "Te enviamos un código de activación a tu correo electrónico.",
            "email": email_clean
        }

    # Creación administrativa pre-activada
    token = create_access_token(doc)
    return {
        "success": True,
        "message": "Usuario registrado con éxito.",
        "token": token,
        "user": format_user_response(doc)
    }

async def verificar_codigo_registro(req: VerificarCodigoRegistroRequest):
    db = get_database()
    email_clean = req.email.lower().strip()
    code_clean = req.codigo.strip()

    user = await db["usuarios"].find_one({"email": email_clean})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No encontramos ninguna cuenta con ese correo electrónico."
        )

    if user.get("estado_id") == 3:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta se encuentra inactiva. Contacta al administrador."
        )

    if user.get("codigo_acceso") != code_clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El código ingresado no coincide con el enviado a tu correo. Revisalo e intentalo nuevamente."
        )

    # Activar la cuenta
    now = datetime.now(timezone.utc)
    await db["usuarios"].update_one(
        {"id": user["id"]},
        {"$set": {
            "estado_id": 2,
            "estado_codigo": "ACTIVO",
            "activo": True,
            "fecha_activacion": now
        }}
    )

    user["estado_id"] = 2
    user["estado_codigo"] = "ACTIVO"
    user["activo"] = True

    token = create_access_token(user)
    return {
        "success": True,
        "message": "¡Cuenta activada con éxito!",
        "token": token,
        "user": format_user_response(user)
    }

async def reenviar_codigo_registro(req: ReenviarCodigoRequest):
    db = get_database()
    email_clean = req.email.lower().strip()

    user = await db["usuarios"].find_one({"email": email_clean})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No encontramos ninguna cuenta con ese correo electrónico."
        )

    if user.get("estado_id") == 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tu cuenta ya está activada. Podés ingresar directamente con tu código en 'Tengo mi código'."
        )

    codigo = user.get("codigo_acceso")
    await enviar_codigo_activacion(email_clean, user.get("name", "Estimado alumno"), codigo)

    return {
        "success": True,
        "message": f"Código reenviado con éxito a {email_clean}."
    }

async def modificar_email_registro(req: ModificarEmailRegistroRequest):
    db = get_database()
    actual_clean = req.email_actual.lower().strip()
    nuevo_clean = req.email_nuevo.lower().strip()

    if actual_clean == nuevo_clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El nuevo correo electrónico debe ser diferente al anterior."
        )

    user = await db["usuarios"].find_one({"email": actual_clean})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No encontramos el registro anterior."
        )

    if user.get("estado_id") == 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No es posible modificar el correo de una cuenta ya activada mediante este proceso."
        )

    conflict = await db["usuarios"].find_one({"email": nuevo_clean, "id": {"$ne": user["id"]}})
    if conflict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El nuevo correo electrónico ya pertenece a otra cuenta registrada."
        )

    await db["usuarios"].update_one(
        {"id": user["id"]},
        {"$set": {"email": nuevo_clean}}
    )

    codigo = user.get("codigo_acceso")
    await enviar_codigo_activacion(nuevo_clean, user.get("name", "Estimado alumno"), codigo)

    return {
        "success": True,
        "message": f"Correo actualizado con éxito. Te enviamos el código a {nuevo_clean}.",
        "email": nuevo_clean
    }
