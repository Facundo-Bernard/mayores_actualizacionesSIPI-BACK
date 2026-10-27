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

AUTENTICADOR_CENTRAL_SECRET = "K8v_3mNp92WzX5qL7rT4yB1cV6jH0gF2sA9dE4uI"

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodifica y valida la firma de un token JWT.
    Soporta la clave configurada en settings y la clave del Autenticador Central (SSOT).
    Utiliza verify_exp=False para soportar los tokens permanentes generados para los alumnos.
    """
    secrets_to_try = []
    if settings.JWT_SECRET:
        secrets_to_try.append(settings.JWT_SECRET)
    if AUTENTICADOR_CENTRAL_SECRET not in secrets_to_try:
        secrets_to_try.append(AUTENTICADOR_CENTRAL_SECRET)
    if "super_secret_autenticador_key_2026" not in secrets_to_try:
        secrets_to_try.append("super_secret_autenticador_key_2026")

    for secret in secrets_to_try:
        if not secret:
            continue
        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                options={"verify_exp": False}
            )
            return payload
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            continue
    return None
