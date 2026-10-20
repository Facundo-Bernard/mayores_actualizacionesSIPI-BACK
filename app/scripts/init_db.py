import logging
from datetime import datetime, timezone
from app.core.database import get_database, get_next_sequence_value
from app.core.config import settings
from pymongo.errors import DuplicateKeyError

logger = logging.getLogger("InitDB")

ESTADOS_DEFAULT = [
    {
        "id": 1,
        "codigo": "PENDIENTE_VERIFICACION",
        "nombre": "Pendiente de verificación",
        "descripcion": "El usuario se registró pero aún no verificó su cuenta mediante correo",
        "permite_login": False,
        "color": "amber",
        "habilitado": True
    },
    {
        "id": 2,
        "codigo": "ACTIVO",
        "nombre": "Activo",
        "descripcion": "Usuario habilitado con acceso completo a los cursos y contenidos",
        "permite_login": True,
        "color": "emerald",
        "habilitado": True
    },
    {
        "id": 3,
        "codigo": "SUSPENDIDO",
        "nombre": "Suspendido",
        "descripcion": "Cuenta suspendida temporalmente por administración",
        "permite_login": False,
        "color": "rose",
        "habilitado": True
    },
    {
        "id": 4,
        "codigo": "INACTIVO_TEMPORAL",
        "nombre": "Inactivo temporal",
        "descripcion": "El usuario solicitó una pausa temporal en su suscripción",
        "permite_login": False,
        "color": "slate",
        "habilitado": True
    }
]

async def seed_estados_usuario():
    """Inicializa la colección de estados de usuario si está vacía o faltan estados base."""
    db = get_database()
    estados = db["estados_usuario"]
    for estado in ESTADOS_DEFAULT:
        await estados.update_one(
            {"id": estado["id"]},
            {"$setOnInsert": estado},
            upsert=True
        )
    logger.info("[ESTADOS] Catálogo de estados de usuario verificado/sembrado correctamente.")

    # Migración retroactiva: asegurar que usuarios existentes tengan estado_id y estado_codigo
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
    
    # Buscar si ya existe por email o por el código único 999999
    admin = await db["usuarios"].find_one({
        "$or": [
            {"email": admin_email},
            {"codigo_acceso": "999999"}
        ]
    })
    if not admin:
        logger.info(f"[SISTEMAS] Inicializando superadmin inicial ({admin_email})...")
        user_id = await get_next_sequence_value("usuario_id")

        admin_doc = {
            "id": user_id,
            "name": settings.ADMIN_DEFAULT_NAME,
            "email": admin_email,
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
        try:
            await db["usuarios"].insert_one(admin_doc)
            logger.info(f"[SISTEMAS] Superadmin creado con éxito. ID: {user_id}, Email: {admin_email}")
        except DuplicateKeyError as e:
            logger.warning(f"[SISTEMAS] El administrador ya existía en la colección: {e}")
    else:
        logger.info(f"[SISTEMAS] Usuario administrador ya existente (ID: {admin.get('id')}, Email: {admin.get('email')}, PIN: {admin.get('codigo_acceso')})")
