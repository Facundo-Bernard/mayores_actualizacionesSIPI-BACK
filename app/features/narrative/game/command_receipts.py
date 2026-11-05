"""Lectura autorizada de recibos y snapshots confirmados.

La lectura no ejecuta negocio: devuelve lo que ya quedó confirmado. El
propietario y la generación se verifican siempre; un recibo ausente no prueba
que otro request en vuelo no vaya a confirmarlo, por eso el error es retryable.
"""

from copy import deepcopy
from typing import Any, Dict

from app.features.narrative.game.command_protocol import (
    CommandError,
    Principal,
    buscar_recibo,
    estado_confirmado,
    verificar_propiedad,
)
from app.features.narrative.game.run_repository import obtener_run_por_id
from app.features.narrative.schemas.v3_contract_schemas import ErrorCode


async def _run_autorizado(
    run_id: str, *, generation: int, principal: Principal
) -> Dict[str, Any]:
    run = await obtener_run_por_id(run_id)
    if run is None:
        raise CommandError(
            ErrorCode.RUN_NOT_FOUND, "Partida no encontrada.", http_status=404
        )
    verificar_propiedad(run, principal)
    actual = int(run.get("generation") or 1)
    if actual != int(generation):
        raise CommandError(
            ErrorCode.GENERATION_CONFLICT,
            "La generación solicitada no corresponde a la partida.",
            detail={"currentGeneration": actual},
        )
    return run


async def obtener_recibo_autorizado(
    run_id: str,
    command_id: str,
    *,
    generation: int,
    principal: Principal,
) -> Dict[str, Any]:
    run = await _run_autorizado(run_id, generation=generation, principal=principal)
    recibo = buscar_recibo(run, command_id)
    if recibo is None:
        raise CommandError(
            ErrorCode.RECEIPT_NOT_FOUND,
            "No hay un recibo confirmado para ese comando.",
            http_status=404,
            retryable=True,
        )
    respuesta = deepcopy(recibo)
    respuesta["runId"] = run["_id"]

    liquidacion = run.get("liquidacion") or {}
    recompensa = respuesta.get("recompensa")
    if (
        recompensa
        and recompensa.get("canal") == "ledger"
        and liquidacion.get("estado")
    ):
        recompensa["liquidacion"] = {"estado": liquidacion["estado"]}
    return respuesta


async def obtener_snapshot_autorizado(
    run_id: str, *, generation: int, principal: Principal
) -> Dict[str, Any]:
    run = await _run_autorizado(run_id, generation=generation, principal=principal)
    return {
        "runId": run["_id"],
        "generation": int(run.get("generation") or 1),
        "version": int(run.get("version") or 0),
        "estado": estado_confirmado(run),
    }
