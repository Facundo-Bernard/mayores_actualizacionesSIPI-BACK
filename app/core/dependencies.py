from typing import Optional, Dict, Any
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
    Verifica firma, expiración y que la cuenta del usuario esté activa.
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

    user_id = payload.get("id")
    email = payload.get("email")

    db = get_database()
    query = {}
    if user_id:
        query["id"] = int(user_id)
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario asociado a este token no existe."
        )

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
