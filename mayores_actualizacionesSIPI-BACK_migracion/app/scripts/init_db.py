import logging
from datetime import datetime, timezone
from app.core.database import get_database, get_next_sequence_value, init_indexes
from app.core.security import get_password_hash
from app.core.config import settings

logger = logging.getLogger(__name__)

async def seed_default_admin():
    """Crea el operador de sistemas inicial si no existe en la base de datos."""
    db = get_database()
    admin_email = settings.ADMIN_DEFAULT_EMAIL.lower().strip()
    
    admin = await db["usuarios"].find_one({"email": admin_email})
    if not admin:
        logger.info(f"[SISTEMAS] Inicializando superadmin inicial ({admin_email})...")
        user_id = await get_next_sequence_value("usuario_id")
        hashed_password = get_password_hash(settings.ADMIN_DEFAULT_PASSWORD)

        admin_doc = {
            "id": user_id,
            "name": settings.ADMIN_DEFAULT_NAME,
            "email": admin_email,
            "password": hashed_password,
            "codigo_acceso": "999999",
            "tipo_usuario": 2, # ROL_ADMIN
            "black": True,
            "activo": True,
            "date_start": datetime.now(timezone.utc),
            "date_end": None,
            "progresos": []
        }
        await db["usuarios"].insert_one(admin_doc)
        logger.info(f"[SISTEMAS] Superadmin creado con éxito. ID: {user_id}, Email: {admin_email}")
    else:
        logger.info(f"[SISTEMAS] Usuario administrador ya existente ({admin_email})")
