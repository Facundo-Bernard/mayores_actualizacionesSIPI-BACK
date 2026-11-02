"""
run_repository.py
Persistencia de `narrative_runs` con control optimista de versión.

Cada escritura incrementa `version` y exige que la copia en memoria siga siendo la vigente.
Las partidas antiguas sin `version` se tratan como versión 0.
"""

from typing import Any, Dict, Iterable, Optional

from fastapi import HTTPException

from app.core.database import get_database
from app.features.narrative.constants import COLL_RUNS

CONFLICTO_DETALLE = (
    "La partida fue modificada por otra petición. "
    "Recargá el estado actual antes de continuar."
)


def _filtro_version(run: Dict[str, Any]) -> Dict[str, Any]:
    version = int(run.get("version") or 0)
    filtro: Dict[str, Any] = {"_id": run["_id"]}
    if version:
        filtro["version"] = version
    else:
        filtro["$or"] = [{"version": 0}, {"version": {"$exists": False}}]
    return filtro


def _proyectar(run: Dict[str, Any], campos: Optional[Iterable[str]]) -> Dict[str, Any]:
    if campos is None:
        return {k: v for k, v in run.items() if k not in ("_id", "version")}
    return {k: run[k] for k in campos if k in run}


async def crear_run(run: Dict[str, Any]) -> None:
    """Inserta la partida en estado inicial (versión 0)."""
    run["version"] = 0
    db = get_database()
    await db[COLL_RUNS].replace_one({"_id": run["_id"]}, run, upsert=True)


async def persistir_run(
    run: Dict[str, Any],
    campos: Optional[Iterable[str]] = None
) -> None:
    """Guarda la partida y sube la versión; 409 si otra escritura se adelantó."""
    db = get_database()
    version_actual = int(run.get("version") or 0)
    cambios = _proyectar(run, campos)
    if "version" in cambios:
        cambios.pop("version")

    resultado = await db[COLL_RUNS].update_one(
        _filtro_version(run),
        {"$set": cambios, "$inc": {"version": 1}},
    )
    if resultado.matched_count == 0:
        raise HTTPException(status_code=409, detail=CONFLICTO_DETALLE)

    run["version"] = version_actual + 1
