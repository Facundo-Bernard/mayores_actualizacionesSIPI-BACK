import logging
from datetime import datetime, timezone
from app.core.database import get_database, get_next_sequence_value, init_indexes
from app.core.security import get_password_hash
from app.core.config import settings

logger = logging.getLogger(__name__)

ESTADOS_INICIALES = [
    {
        "id": 1,
        "codigo": "PENDIENTE_VERIFICACION",
        "nombre": "Pendiente de verificación",
        "descripcion": "El usuario se registró pero aún no confirmó el código enviado a su correo",
        "permite_login": False,
        "color": "amber"
    },
    {
        "id": 2,
        "codigo": "ACTIVO",
        "nombre": "Cuenta activa",
        "descripcion": "Cuenta confirmada y habilitada para acceder a la plataforma",
        "permite_login": True,
        "color": "emerald"
    },
    {
        "id": 3,
        "codigo": "SUSPENDIDO",
        "nombre": "Cuenta suspendida",
        "descripcion": "Cuenta inhabilitada temporal o permanentemente por administración",
        "permite_login": False,
        "color": "rose"
    }
]

async def seed_estados_usuario():
    """Siembra los estados de cuenta en la colección 'estados_usuario' y migra usuarios existentes."""
    db = get_database()
    col = db["estados_usuario"]

    for est in ESTADOS_INICIALES:
        await col.update_one(
            {"id": est["id"]},
            {"$set": est},
            upsert=True
        )
    logger.info("[ESTADOS] Catálogo de estados de usuario inicializado en MongoDB.")

    # Migrar usuarios existentes que no tengan estado_id
    usuarios = db["usuarios"]
    res_activos = await usuarios.update_many(
        {"estado_id": {"$exists": False}, "activo": {"$ne": False}},
        {"$set": {"estado_id": 2, "estado_codigo": "ACTIVO"}}
    )
    res_inactivos = await usuarios.update_many(
        {"estado_id": {"$exists": False}, "activo": False},
        {"$set": {"estado_id": 3, "estado_codigo": "SUSPENDIDO"}}
    )
    if res_activos.modified_count > 0 or res_inactivos.modified_count > 0:
        logger.info(
            f"[ESTADOS] Usuarios previos migrados: {res_activos.modified_count} activos, {res_inactivos.modified_count} suspendidos."
        )

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
            "estado_id": 2,
            "estado_codigo": "ACTIVO",
            "date_start": datetime.now(timezone.utc),
            "date_end": None,
            "progresos": []
        }
        await db["usuarios"].insert_one(admin_doc)
        logger.info(f"[SISTEMAS] Superadmin creado con éxito. ID: {user_id}, Email: {admin_email}")
    else:
        logger.info(f"[SISTEMAS] Usuario administrador ya existente ({admin_email})")
