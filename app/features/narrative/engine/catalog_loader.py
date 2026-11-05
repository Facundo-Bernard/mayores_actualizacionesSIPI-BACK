from typing import Dict, Any, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.features.narrative.constants import COLL_ACTIONS, COLL_FREQUENCIES


async def obtener_catalogos_universo(
    universo_id: str,
    db: AsyncIOMotorDatabase,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Carga en memoria los catálogos de acciones activas y frecuencias configuradas
    para un universo dado, retornando (acciones_map, frecuencias_map).
    """
    acciones_docs = await db[COLL_ACTIONS].find(
        {"universo_id": universo_id, "activo": True}
    ).to_list(None)
    acciones_map = {str(a["_id"]): a for a in acciones_docs}

    frec_doc = await db[COLL_FREQUENCIES].find_one({"universo_id": universo_id})
    frecuencias_map: Dict[str, Any] = {}
    if frec_doc and "items" in frec_doc:
        frecuencias_map = {
            item["id"]: item for item in frec_doc["items"] if item.get("activo", True)
        }

    return acciones_map, frecuencias_map
