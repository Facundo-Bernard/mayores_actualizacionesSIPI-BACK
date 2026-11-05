"""
run_repository.py
Persistencia de `narrative_runs` con control optimista de versión.

Cada escritura incrementa `version` y exige que la copia en memoria siga siendo la vigente.
Las partidas antiguas sin `version` se tratan como versión 0.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.database import get_database
from app.features.narrative.constants import (
    COLL_RUNS,
    COLL_RUNS_ARCHIVE,
    PROTOCOLO_V3,
)

CONFLICTO_DETALLE = (
    "La partida fue modificada por otra petición. "
    "Recargá el estado actual antes de continuar."
)


class RunAlreadyExistsError(Exception):
    """Otra petición creó la misma generación de run antes de esta inserción."""

    def __init__(self, run_id: str):
        super().__init__(f"La partida '{run_id}' ya existe.")
        self.run_id = run_id


def asegurar_run_legacy(run: Dict[str, Any]) -> None:
    """Una run del protocolo v3 no admite mutaciones por las rutas legacy."""
    if run.get("protocolo") == PROTOCOLO_V3:
        raise HTTPException(
            status_code=409,
            detail=(
                "La partida usa el protocolo de comandos v3; "
                "no admite mutaciones legacy."
            ),
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
    """Inserta una generación nueva; nunca reemplaza a la ganadora de una carrera."""
    run["version"] = 0
    run.setdefault("generation", 1)
    db = get_database()
    try:
        await db[COLL_RUNS].insert_one(run)
    except DuplicateKeyError as exc:
        raise RunAlreadyExistsError(run["_id"]) from exc


async def archivar_run(run: Dict[str, Any], expected_version: Optional[int] = None) -> None:
    """Mueve una generación a archivo y solo entonces libera su slot activo."""
    asegurar_run_legacy(run)
    version = int(run.get("version") or 0)
    if expected_version is not None and version != expected_version:
        raise HTTPException(status_code=409, detail=CONFLICTO_DETALLE)

    db = get_database()
    archivado = dict(run)
    archivado.setdefault("generation", 1)
    archivado["archived_at"] = datetime.now(timezone.utc).isoformat()
    await db[COLL_RUNS_ARCHIVE].replace_one({"_id": run["_id"]}, archivado, upsert=True)

    resultado = await db[COLL_RUNS].delete_one(_filtro_version(run))
    if resultado.deleted_count == 0:
        raise HTTPException(status_code=409, detail=CONFLICTO_DETALLE)


async def persistir_run(
    run: Dict[str, Any],
    campos: Optional[Iterable[str]] = None
) -> None:
    """Guarda la partida y sube la versión; 409 si otra escritura se adelantó."""
    asegurar_run_legacy(run)
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


async def obtener_run_activo(run_id: str) -> Optional[Dict[str, Any]]:
    return await get_database()[COLL_RUNS].find_one({"_id": run_id})


async def obtener_run_por_id(run_id: str) -> Optional[Dict[str, Any]]:
    """Lectura de recuperación: activo primero, archivo después."""
    run = await obtener_run_activo(run_id)
    if run is not None:
        return run
    return await get_database()[COLL_RUNS_ARCHIVE].find_one({"_id": run_id})


async def confirmar_comando(
    run_id: str,
    *,
    generation: int,
    expected_version: int,
    cambios: Dict[str, Any],
    recibo: Dict[str, Any],
    liquidacion: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Confirma estado + recibo + obligación en una sola escritura atómica.

    Devuelve el documento posterior si esta petición ganó el CAS; ``None`` si
    otra escritura se adelantó (el llamador debe recuperar el recibo ganador).
    """
    db = get_database()
    campos = {
        clave: valor
        for clave, valor in cambios.items()
        if clave not in ("_id", "version", "generation", "recibos", "liquidacion")
    }
    update: Dict[str, Any] = {
        "$set": {**campos, "version": expected_version + 1},
        "$push": {"recibos": recibo},
    }
    if liquidacion is not None:
        update["$set"]["liquidacion"] = liquidacion

    return await db[COLL_RUNS].find_one_and_update(
        {
            "_id": run_id,
            "protocolo": PROTOCOLO_V3,
            "generation": generation,
            "version": expected_version,
        },
        update,
        return_document=ReturnDocument.AFTER,
    )
