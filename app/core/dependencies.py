from typing import Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.security import decode_access_token
from app.core.database import get_database

security_bearer = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)
) -> Dict[str, Any]:
    """
    Extrae y valida el token JWT del encabezado Authorization Bearer.
    Verifica firma con JWT_SECRET compartido con el Autenticador Central,
    valida expiración y permisos de servicio para 'mayoresactualizaciones'.
    Garantiza que el perfil local exista en MongoDB para asegurar la persistencia
    de progresos y partidas de juegos.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación requerida. Token no proporcionado.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticación inválido o expirado.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Validar permisos específicos para el servicio mayoresactualizaciones
    tipo_usuario = int(payload.get("tipo_usuario") or payload.get("tipoUsuario") or 1)
    servicios = payload.get("servicios") or {}
    if tipo_usuario != 2 and not servicios.get("mayoresactualizaciones", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: El usuario no tiene permisos habilitados para el servicio 'mayoresactualizaciones'."
        )

    user_id = payload.get("id") or payload.get("sub")
    email = payload.get("email")

    db = get_database()
    query = {}
    if user_id:
        try:
            query["id"] = int(user_id)
        except (ValueError, TypeError):
            query["id"] = user_id
    elif email:
        query["email"] = email
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token no contiene una identidad de usuario válida.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user = await db["usuarios"].find_one(query)
    if not user:
        # Sincronización automática de perfil local para compatibilidad de juegos y progreso
        try:
            user_id_int = int(user_id)
        except (ValueError, TypeError):
            user_id_int = 0

        user = {
            "id": user_id_int,
            "name": payload.get("name") or payload.get("nombre") or "",
            "email": email or "",
            "codigo_acceso": payload.get("codigoAcceso") or "",
            "tipo_usuario": tipo_usuario,
            "black": bool(payload.get("black", False)),
            "activo": bool(payload.get("activo", True)),
            "estado_id": 2,
            "estado_codigo": "ACTIVO",
            "date_start": datetime.now(timezone.utc),
            "date_end": None,
            "progresos": []
        }
        await db["usuarios"].update_one(
            {"id": user_id_int},
            {"$setOnInsert": user},
            upsert=True
        )
        user = await db["usuarios"].find_one({"id": user_id_int})

    if user.get("activo") is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta de usuario se encuentra inactiva. Contacta al administrador."
        )

    return user

async def get_current_admin(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Valida que el usuario autenticado tenga rol de Operador de Sistemas / Administrador (tipo_usuario == 2).
    """
    if current_user.get("tipo_usuario") != 2:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido: Se requieren permisos de Operador de Sistemas / Administrador."
        )
    return current_user
