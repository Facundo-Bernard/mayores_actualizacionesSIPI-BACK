"""Metadatos de recursos por universo (caché en memoria) compartidos por ambos motores."""

from typing import Dict, Any, Optional

from app.core.database import get_database
from app.features.narrative.constants import COLL_SETTINGS

_RECURSOS_MAPA_CACHE: Dict[str, Dict[str, Dict[str, Any]]] = {}


def invalidar_cache_recursos_universo(universo_id: Optional[str] = None) -> None:
    """Invalida la caché de metadatos de recursos para un universo o todos."""
    if universo_id and universo_id in _RECURSOS_MAPA_CACHE:
        _RECURSOS_MAPA_CACHE.pop(universo_id, None)
    else:
        _RECURSOS_MAPA_CACHE.clear()


async def obtener_mapa_recursos_universo(universo_id: str) -> Dict[str, Dict[str, Any]]:
    """Carga los límites (min, max) y metadatos de recursos configurados para el universo."""
    if universo_id in _RECURSOS_MAPA_CACHE:
        return _RECURSOS_MAPA_CACHE[universo_id]

    db = get_database()
    u = await db[COLL_SETTINGS].find_one({"_id": universo_id})
    if not u or "recursos" not in u:
        return {}
    mapa = {r["clave"]: r for r in u["recursos"]}
    _RECURSOS_MAPA_CACHE[universo_id] = mapa
    return mapa
