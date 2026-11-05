import asyncio
import os
import sys
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"))
sys.path.insert(0, BASE_DIR)

from app.core.config import settings
from app.features.narrative.constants import COLL_ACTIONS, COLL_FREQUENCIES

async def seed():
    mongo_uri = settings.MONGO_URI or "mongodb://localhost:27017"
    db_name = settings.MONGO_DB_NAME or "mayores_actualizaciones_dev"
    client = AsyncIOMotorClient(mongo_uri)
    db = client[db_name]
    print(f"Connected to MongoDB: {db_name}")

    universo_id = "corte_medieval"

    # 1. Sembrar acciones canónicas
    acciones = [
        {
            "_id": "modificar_recurso",
            "universo_id": universo_id,
            "nombre": "Modificar recurso",
            "descripcion": "Aumenta o disminuye el valor de un recurso (positivo suma, negativo resta).",
            "primitiva": "modificar_recurso",
            "permitido_en": ["carta", "personaje"],
            "activo": True,
            "version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "_id": "modificar_afinidad",
            "universo_id": universo_id,
            "nombre": "Modificar afinidad",
            "descripcion": "Modifica la afinidad (0 a 100) con el personaje de la corte o portador.",
            "primitiva": "modificar_afinidad",
            "permitido_en": ["carta", "personaje"],
            "activo": True,
            "version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "_id": "otorgar_tag",
            "universo_id": universo_id,
            "nombre": "Otorgar tag pasivo",
            "descripcion": "Otorga un tag o perk a la partida.",
            "primitiva": "otorgar_tag",
            "permitido_en": ["carta", "personaje"],
            "activo": True,
            "version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "_id": "remover_tag",
            "universo_id": universo_id,
            "nombre": "Remover tag",
            "descripcion": "Remueve un tag activo de la partida.",
            "primitiva": "remover_tag",
            "permitido_en": ["carta", "personaje"],
            "activo": True,
            "version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "_id": "amortiguar_danio",
            "universo_id": universo_id,
            "nombre": "Amortiguar daño",
            "descripcion": "Reduce porcentualmente las pérdidas de un recurso ante eventos y costos.",
            "primitiva": "amortiguar_danio",
            "permitido_en": ["carta", "personaje"],
            "activo": True,
            "version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    ]

    for acc in acciones:
        await db[COLL_ACTIONS].update_one(
            {"_id": acc["_id"], "universo_id": universo_id},
            {"$set": acc},
            upsert=True,
        )
        print(f"Acción upserted: {acc['_id']}")

    # 2. Sembrar frecuencias
    frec_doc = {
        "_id": f"frecuencias_{universo_id}",
        "universo_id": universo_id,
        "version": 1,
        "items": [
            {
                "id": "al_obtener",
                "nombre": "Al obtener",
                "evento_motor": "al_obtener",
                "cada": 1,
                "desfase": 0,
                "conteo_desde": "adquisicion",
                "activo": True,
            },
            {
                "id": "mensual",
                "nombre": "Cada mes",
                "evento_motor": "inicio_mes",
                "cada": 1,
                "desfase": 0,
                "conteo_desde": "inicio_partida",
                "activo": True,
            },
            {
                "id": "cada_2_meses",
                "nombre": "Cada 2 meses desde adquisición",
                "evento_motor": "inicio_mes",
                "cada": 2,
                "desfase": 0,
                "conteo_desde": "adquisicion",
                "activo": True,
            },
            {
                "id": "cada_3_meses",
                "nombre": "Cada 3 meses desde adquisición",
                "evento_motor": "inicio_mes",
                "cada": 3,
                "desfase": 0,
                "conteo_desde": "adquisicion",
                "activo": True,
            },
        ],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    await db[COLL_FREQUENCIES].update_one(
        {"_id": frec_doc["_id"]},
        {"$set": frec_doc},
        upsert=True,
    )
    print(f"Frecuencias upserted para: {universo_id}")

    client.close()

if __name__ == "__main__":
    asyncio.run(seed())
