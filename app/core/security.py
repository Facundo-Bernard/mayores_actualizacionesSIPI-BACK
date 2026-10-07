import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from app.core.config import settings

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica una contraseña en texto plano contra un hash BCrypt.
    Totalmente compatible con los hashes generados por Spring Security ($2a$10$...).
    """
    if not plain_password or not hashed_password:
        return False
    try:
        # En caso de hash con prefijo $2a$, bcrypt de python lo acepta perfectamente
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    """Genera un hash BCrypt con salt."""
    salt = bcrypt.gensalt(rounds=10)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def create_access_token(user: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Genera un token JWT HMAC-SHA256 con los mismos claims
    que producía JwtService.java en Spring Boot.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.JWT_EXPIRATION_DAYS)

    claims = {
        "sub": str(user.get("id")),
        "id": user.get("id"),
        "name": user.get("name", ""),
        "email": user.get("email", ""),
        "black": bool(user.get("black", False)),
        "tipoUsuario": int(user.get("tipo_usuario", 1)),
        "rol": int(user.get("tipo_usuario", 1)),
        "activo": bool(user.get("activo", True)),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp())
    }

    token = jwt.encode(claims, settings.JWT_SECRET, algorithm="HS256")
    return token

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodifica y valida la firma y expiración de un token JWT."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None
