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
        db_instance.client = AsyncIOMotorClient(settings.MONGODB_URL)
        db_instance.db = db_instance.client[settings.MONGODB_DB_NAME]
    return db_instance.db

async def connect_to_mongo():
    logger.info(f"Conectando a MongoDB en: {settings.MONGODB_URL} (Base: {settings.MONGODB_DB_NAME})")
    db_instance.client = AsyncIOMotorClient(settings.MONGODB_URL)
    db_instance.db = db_instance.client[settings.MONGODB_DB_NAME]
    await init_indexes()
    logger.info("Conexión a MongoDB establecida exitosamente.")

async def close_mongo_connection():
    if db_instance.client:
        db_instance.client.close()
        logger.info("Conexión a MongoDB cerrada.")

async def get_next_sequence_value(sequence_name: str) -> int:
    """
    Genera un ID secuencial numérico atómico (1, 2, 3...)
    equivalente a AUTO_INCREMENT de MySQL usando la colección 'counters'.
    """
    db = get_database()
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

        logger.info("Índices de MongoDB inicializados correctamente.")
    except Exception as e:
        logger.warning(f"Aviso al inicializar índices: {e}")
