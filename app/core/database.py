from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ReturnDocument, ASCENDING
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class Database:
    client: AsyncIOMotorClient = None
    db: AsyncIOMotorDatabase = None

db_instance = Database()

def get_database() -> AsyncIOMotorDatabase:
    if db_instance.db is None:
        url = settings.mongodb_connection_url
        db_name = settings.effective_db_name
        db_instance.client = AsyncIOMotorClient(url)
        try:
            db_instance.db = db_instance.client.get_default_database()
        except Exception:
            db_instance.db = db_instance.client[db_name]
    return db_instance.db

async def connect_to_mongo():
    url = settings.mongodb_connection_url
    db_name = settings.effective_db_name
    # Log seguro: ocultar contraseñas para evitar fugas en logs
    safe_log_url = url
    if "@" in url:
        pre, post = url.split("@", 1)
        protocol = pre.split("://")[0]
        safe_log_url = f"{protocol}://****:****@{post}"
    logger.info(f"Conectando a MongoDB en: {safe_log_url} (Base: {db_name})")
    db_instance.client = AsyncIOMotorClient(url, serverSelectionTimeoutMS=5000)
    try:
        db_instance.db = db_instance.client.get_default_database()
    except Exception:
        db_instance.db = db_instance.client[db_name]

    # Verificación activa e inmediata de credenciales y conectividad
    try:
        await db_instance.client.admin.command('ping')
        logger.info("Conexión y autenticación con MongoDB verificadas exitosamente.")
    except Exception as e:
        logger.warning(f"No se pudo verificar la conexión inicial con MongoDB ({e}). La app continuará e intentará reconectar.")

    try:
        await init_indexes()
    except Exception as e:
        logger.warning(f"Aviso al inicializar índices en el arranque: {e}")

async def close_mongo_connection():
    if db_instance.client:
        db_instance.client.close()
        logger.info("Conexión a MongoDB cerrada.")

async def get_next_sequence_value(sequence_name: str) -> int:
    """
    Genera un ID secuencial numérico atómico (1, 2, 3...)
    equivalente a AUTO_INCREMENT de MySQL usando la colección 'counters'.
    Auto-sincroniza preventivamente contra el ID máximo existente para evitar DuplicateKeyError.
    """
    db = get_database()
    if sequence_name == "usuario_id":
        max_user = await db["usuarios"].find_one(sort=[("id", -1)])
        max_id = max_user["id"] if (max_user and isinstance(max_user.get("id"), int)) else 0
        counter_doc = await db["counters"].find_one({"_id": sequence_name})
        current_seq = counter_doc.get("seq", 0) if counter_doc else 0
        if max_id >= current_seq:
            await db["counters"].update_one(
                {"_id": sequence_name},
                {"$set": {"seq": max_id}},
                upsert=True
            )

    counter = await db["counters"].find_one_and_update(
        {"_id": sequence_name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    return counter["seq"]

async def set_sequence_value(sequence_name: str, value: int):
    """Establece el contador a un valor específico (útil tras migración)."""
    db = get_database()
    await db["counters"].update_one(
        {"_id": sequence_name},
        {"$set": {"seq": value}},
        upsert=True
    )

async def init_indexes():
    """Crea los índices únicos y de búsqueda para las colecciones."""
    db = get_database()
    try:
        # Índices de Usuarios
        usuarios = db["usuarios"]
        await usuarios.create_index([("email", ASCENDING)], unique=True)
        await usuarios.create_index([("codigo_acceso", ASCENDING)])
        await usuarios.create_index([("id", ASCENDING)], unique=True)
        await usuarios.create_index([("name", ASCENDING)])
        await usuarios.create_index([("date_start", ASCENDING)])

        # Índices de Desafíos Diarios (daily_challenges)
        daily_challenges = db["daily_challenges"]
        await daily_challenges.create_index(
            [("game_id", ASCENDING), ("date", ASCENDING), ("difficulty", ASCENDING)],
            unique=True
        )
        await daily_challenges.create_index([("date", ASCENDING)])

        # Índices de Intentos / Partidas (user_attempts)
        user_attempts = db["user_attempts"]
        await user_attempts.create_index(
            [("user_id", ASCENDING), ("game_id", ASCENDING), ("date", ASCENDING)],
            unique=True
        )
        await user_attempts.create_index([("user_id", ASCENDING), ("date", -1)])

        # Ledger de puntos: una acreditación por clave de negocio
        await db["economy_ledger"].create_index(
            [("idempotency_key", ASCENDING)], unique=True
        )
        await db["economy_ledger"].create_index(
            [("status", ASCENDING), ("created_at", ASCENDING)]
        )

        # Pistas entregadas: una sola entrega/cobro por usuario, juego, fecha, dificultad y pista
        await db["user_hints"].create_index(
            [("user_id", ASCENDING), ("game_id", ASCENDING), ("date", ASCENDING),
             ("difficulty", ASCENDING), ("hint_key", ASCENDING)],
            unique=True
        )

        # Índices de Estados de Usuario (estados_usuario)
        estados_usuario = db["estados_usuario"]
        await estados_usuario.create_index([("id", ASCENDING)], unique=True)
        await estados_usuario.create_index([("codigo", ASCENDING)], unique=True)

        # Índices de Juego Narrativo
        narrative_runs = db["narrative_runs"]
        await narrative_runs.create_index(
            [("user_id", ASCENDING), ("date", ASCENDING), ("game_id", ASCENDING)],
            unique=True
        )
        await narrative_runs.create_index([("user_id", ASCENDING), ("date", -1)])

        narrative_endings = db["narrative_endings"]
        await narrative_endings.create_index([("universo_id", ASCENDING), ("recurso_clave", ASCENDING)])

        for col_name in ["narrative_characters", "narrative_cards", "narrative_events", "narrative_results", "narrative_conversations"]:
            await db[col_name].create_index([("universo_id", ASCENDING)])

        # Motor V2 de grafos: búsquedas por universo y eventos especiales por personaje/dirección
        for col_name in ["narrative_v2_events", "narrative_v2_conversations", "narrative_v2_eventos_especiales"]:
            await db[col_name].create_index([("universo_id", ASCENDING)])
        await db["narrative_v2_eventos_especiales"].create_index(
            [("universo_id", ASCENDING), ("personaje_id", ASCENDING), ("direccion", ASCENDING)]
        )

        # Índices de Plantillas de Crucigrama (diseñador administrativo)
        crucigrama_templates = db["crucigrama_templates"]
        await crucigrama_templates.create_index([("id", ASCENDING)], unique=True)
        await crucigrama_templates.create_index(
            [("status", ASCENDING), ("scheduled_date", ASCENDING), ("difficulty", ASCENDING)]
        )
        await crucigrama_templates.create_index(
            [("scheduled_date", ASCENDING), ("difficulty", ASCENDING)],
            unique=True,
            partialFilterExpression={
                "status": "published",
                "scheduled_date": {"$type": "string"},
            },
            name="uniq_published_schedule",
        )
        await crucigrama_templates.create_index(
            [("monthly_day", ASCENDING), ("difficulty", ASCENDING)],
            unique=True,
            partialFilterExpression={
                "status": "published",
                "monthly_day": {"$type": "number"},
            },
            name="uniq_published_monthly_day",
        )

        logger.info("Índices de MongoDB inicializados correctamente.")
    except Exception as e:
        logger.warning(f"Aviso al inicializar índices: {e}")
