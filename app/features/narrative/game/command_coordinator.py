"""Coordinador de comandos narrativos.

Un comando confirmado equivale a una sola versión de dominio. El orden es:

1. autorizar al principal y validar generación;
2. buscar el recibo **antes** de validar ``expectedVersion``;
3. resolver en memoria con el RNG que inyecte el llamador;
4. confirmar estado + recibo + obligación con un único CAS de documento;
5. aplicar la economía si el cierre la dejó pendiente.

Un CAS perdedor nunca publica su resolución: recupera el recibo ganador o
devuelve conflicto. Un error de red se informa como resultado incierto y el
cliente reintenta con la misma clave.
"""

import inspect
import logging
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

from bson import BSON
from pymongo.errors import (
    AutoReconnect,
    ConnectionFailure,
    ExecutionTimeout,
    NetworkTimeout,
)

from app.features.narrative.constants import PROTOCOLO_V3
from app.features.narrative.game.command_protocol import (
    CommandError,
    CommandOutcomeUnknown,
    Principal,
    buscar_recibo,
    estado_confirmado,
    hash_comando,
    verificar_propiedad,
)
from app.features.narrative.game.economy_obligation import (
    ESTADO_LIQUIDADA,
    ESTADO_PENDIENTE,
    aplicar_liquidacion,
    construir_obligacion,
)
from app.features.narrative.game.run_repository import (
    confirmar_comando,
    obtener_run_activo,
)
from app.features.narrative.schemas.v3_contract_schemas import ErrorCode, RunCommand
from app.shared.clock import now_utc

logger = logging.getLogger(__name__)

ERRORES_DE_RED = (AutoReconnect, ConnectionFailure, ExecutionTimeout, NetworkTimeout)

# Los recibos se retienen completos; este tope evita acercarse al límite BSON de 16 MB.
TAMANO_MAXIMO_RUN = 2_000_000


@dataclass
class CommandResolution:
    """Cambios de dominio calculados en memoria; no se publican si el CAS pierde."""

    cambios: Dict[str, Any]
    consecuencias: List[Dict[str, Any]] = field(default_factory=list)
    resultado: Optional[Dict[str, Any]] = None


Resolver = Callable[
    [Dict[str, Any], RunCommand],
    Union[CommandResolution, Awaitable[CommandResolution]],
]


async def ejecutar_comando(
    run_id: str,
    comando: RunCommand,
    resolver: Resolver,
    *,
    principal: Principal,
    clock: Callable[[], datetime] = now_utc,
    aplicar_economia: bool = True,
) -> Dict[str, Any]:
    ahora = clock()
    run = await obtener_run_activo(run_id)
    if run is None:
        raise CommandError(
            ErrorCode.RUN_NOT_FOUND, "Partida no encontrada.", http_status=404
        )
    verificar_propiedad(run, principal)
    _verificar_protocolo(run)
    generation = _verificar_generacion(run, comando)

    command_hash = hash_comando(comando)
    recibo_existente = buscar_recibo(run, comando.commandId)
    if recibo_existente is not None:
        _verificar_hash(recibo_existente, command_hash)
        return await _recuperar(run_id, run, recibo_existente, aplicar_economia)

    version_actual = int(run.get("version") or 0)
    if version_actual != int(comando.expectedVersion):
        raise CommandError(
            ErrorCode.VERSION_CONFLICT,
            "La partida fue modificada por otra petición. "
            "Recargá el estado actual antes de continuar.",
            detail={"currentVersion": version_actual},
        )
    if run.get("status") in ("completed", "game_over"):
        raise CommandError(
            ErrorCode.PHASE_CONFLICT, "La partida ya está finalizada."
        )

    resolucion = resolver(deepcopy(run), comando)
    if inspect.isawaitable(resolucion):
        resolucion = await resolucion
    if not isinstance(resolucion, CommandResolution):
        raise TypeError("El resolver debe devolver CommandResolution.")

    nuevo = deepcopy(run)
    nuevo.update(resolucion.cambios)
    nuevo["version"] = version_actual + 1

    liquidacion = None
    if (
        run.get("status") != nuevo.get("status")
        and nuevo.get("status") in ("completed", "game_over")
    ):
        liquidacion = await construir_obligacion(nuevo, creada_en=ahora)

    recibo = {
        "commandId": comando.commandId,
        "type": comando.type.value,
        "commandHash": command_hash,
        "previousVersion": version_actual,
        "version": version_actual + 1,
        "generation": generation,
        "estado": estado_confirmado(nuevo),
        "consecuencias": deepcopy(resolucion.consecuencias),
        "resultado": deepcopy(resolucion.resultado),
        "recompensa": _recompensa_publica(liquidacion),
        "created_at": ahora,
    }
    _verificar_tamano(nuevo, recibo, liquidacion)

    try:
        confirmado = await confirmar_comando(
            run_id,
            generation=generation,
            expected_version=version_actual,
            cambios=resolucion.cambios,
            recibo=recibo,
            liquidacion=liquidacion,
        )
    except ERRORES_DE_RED as exc:
        raise CommandOutcomeUnknown() from exc

    if confirmado is None:
        return await _resolver_cas_perdido(
            run_id, comando.commandId, command_hash, aplicar_economia
        )

    puntos = 0
    estado_liquidacion = ESTADO_PENDIENTE
    if liquidacion is not None and aplicar_economia:
        puntos, estado_liquidacion = await _liquidar_seguro(confirmado)

    respuesta = _respuesta(run_id, recibo, puntos)
    _actualizar_liquidacion(respuesta, estado_liquidacion)
    return respuesta


async def _resolver_cas_perdido(
    run_id: str, command_id: str, command_hash: str, aplicar_economia: bool
) -> Dict[str, Any]:
    actual = await obtener_run_activo(run_id)
    if actual is not None:
        ganador = buscar_recibo(actual, command_id)
        if ganador is not None:
            _verificar_hash(ganador, command_hash)
            return await _recuperar(run_id, actual, ganador, aplicar_economia)
    raise CommandError(
        ErrorCode.VERSION_CONFLICT,
        "La partida fue modificada por otra petición. "
        "Recargá el estado actual antes de continuar.",
        detail={
            "currentVersion": int((actual or {}).get("version") or 0)
        } if actual else None,
    )


async def _recuperar(
    run_id: str,
    run: Dict[str, Any],
    recibo: Dict[str, Any],
    aplicar_economia: bool,
) -> Dict[str, Any]:
    """Devuelve el recibo confirmado sin repetir azar ni efectos.

    Si el cierre alcanzó a confirmar pero no a liquidar, se termina la
    obligación acá; así el reintento no pierde puntos locales ni deja el
    asiento sin crear.
    """
    puntos = 0
    estado_liquidacion = (run.get("liquidacion") or {}).get("estado")
    if aplicar_economia and estado_liquidacion == ESTADO_PENDIENTE:
        puntos, estado_liquidacion = await _liquidar_seguro(run)
    respuesta = _respuesta(run_id, recibo, puntos)
    _actualizar_liquidacion(respuesta, estado_liquidacion)
    return respuesta


async def _liquidar_seguro(run: Dict[str, Any]) -> tuple[int, str]:
    try:
        return await aplicar_liquidacion(run)
    except Exception:
        logger.exception(
            "La obligación económica de la partida %s quedó pendiente",
            run.get("_id"),
        )
        return 0, ESTADO_PENDIENTE


def _respuesta(
    run_id: str, recibo: Dict[str, Any], puntos: int
) -> Dict[str, Any]:
    respuesta = deepcopy(recibo)
    respuesta["runId"] = run_id
    respuesta["puntos_ganados"] = puntos
    return respuesta


def _actualizar_liquidacion(respuesta: Dict[str, Any], estado: Optional[str]) -> None:
    recompensa = respuesta.get("recompensa")
    if recompensa and recompensa.get("canal") == "ledger" and estado:
        recompensa["liquidacion"] = {"estado": estado}


def _recompensa_publica(
    liquidacion: Optional[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    if not liquidacion:
        return None
    publica = {
        "rewardId": liquidacion["rewardId"],
        "puntos": liquidacion["puntos"],
        "canal": liquidacion["canal"],
    }
    if liquidacion["canal"] == "ledger":
        publica["liquidacion"] = {"estado": liquidacion["estado"]}
    return publica


def _verificar_tamano(
    nuevo: Dict[str, Any],
    recibo: Dict[str, Any],
    liquidacion: Optional[Dict[str, Any]],
) -> None:
    """Rechaza el comando antes del CAS si el documento superaría el tope de 2 MB."""
    proyectado = {
        **nuevo,
        "recibos": [*(nuevo.get("recibos") or []), recibo],
    }
    if liquidacion is not None:
        proyectado["liquidacion"] = liquidacion
    if len(BSON.encode(proyectado)) > TAMANO_MAXIMO_RUN:
        raise CommandError(
            ErrorCode.PHASE_CONFLICT,
            "La partida alcanzó el tamaño máximo de recibos y no admite más comandos.",
        )


def _verificar_protocolo(run: Dict[str, Any]) -> None:
    if run.get("protocolo") != PROTOCOLO_V3:
        raise CommandError(
            ErrorCode.PHASE_CONFLICT,
            "La partida no usa el protocolo de comandos v3.",
        )


def _verificar_generacion(run: Dict[str, Any], comando: RunCommand) -> int:
    generation = getattr(comando, "generation", None)
    if generation is None:
        raise CommandError(
            ErrorCode.VALIDATION_ERROR,
            "El comando no aplica a una partida existente.",
            http_status=422,
        )
    actual = int(run.get("generation") or 1)
    if actual != int(generation):
        raise CommandError(
            ErrorCode.GENERATION_CONFLICT,
            "La generación de la partida no coincide con la del comando.",
            detail={"currentGeneration": actual},
        )
    return actual


def _verificar_hash(recibo: Dict[str, Any], command_hash: str) -> None:
    if recibo.get("commandHash") != command_hash:
        raise CommandError(
            ErrorCode.COMMAND_REUSED,
            "El commandId ya se usó con otro contenido.",
            detail={"commandId": recibo.get("commandId")},
        )
