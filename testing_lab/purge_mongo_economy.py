import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def purge_mongo():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["mayores_actualizaciones_dev"]
    res = await db["configuracion_economia"].update_one(
        {"_id": "global_economy"},
        {"$unset": {"paquetes_tienda": "", "costo_vida_puntos": "", "vidas_maximas": ""}}
    )
    print(f"Configuracion economia updated: {res.modified_count}")
    doc = await db["configuracion_economia"].find_one({"_id": "global_economy"})
    print("Remaining keys in global_economy:", list(doc.keys()) if doc else None)

if __name__ == "__main__":
    asyncio.run(purge_mongo())
