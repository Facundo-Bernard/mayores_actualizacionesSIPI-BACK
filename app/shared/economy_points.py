"""Lectura compartida de la configuración de puntos por calificación."""

from typing import Dict

COLL_ECONOMIA = "configuracion_economia"
ECONOMY_CONFIG_ID = "global_economy"

DEFAULT_PUNTOS_POR_CALIFICACION: Dict[str, int] = {
    "S": 100,
    "A": 90,
    "B": 75,
    "C": 50,
    "F": 0,
}


async def obtener_puntos_por_calificacion() -> Dict[str, int]:
    """Devuelve el mapa vigente S/A/B/C/F sin arrastrar dependencias entre features."""
    from app.core.database import get_database

    doc = await get_database()[COLL_ECONOMIA].find_one(
        {"_id": ECONOMY_CONFIG_ID},
        {"puntos_por_calificacion": 1},
    )
    configurado = (doc or {}).get("puntos_por_calificacion") or {}
    return {**DEFAULT_PUNTOS_POR_CALIFICACION, **configurado}
