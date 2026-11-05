"""Protocolo de comandos narrativos: identidad, hash canónico y recibos.

El hash identifica la intención, no la recompensa: mismo ``commandId`` con el
mismo contenido es un reintento recuperable; con contenido distinto es un
reuso inválido. La identidad efectiva siempre viene de la credencial
(``Principal``), nunca de un campo del body.
"""

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.features.narrative.schemas.v3_contract_schemas import ErrorCode, RunCommand
from app.shared.errors import DomainError


@dataclass(frozen=True)
class Principal:
    """Identidad efectiva derivada de la credencial verificada."""

    user_id: int
    guest_id: Optional[str] = None

    @property
    def key(self) -> str:
        return f"guest_{self.guest_id}" if self.guest_id else f"user_{self.user_id}"


class CommandError(DomainError):
    def __init__(
        self,
        code: ErrorCode | str,
        message: str,
        *,
        http_status: int = 409,
        detail: Optional[dict] = None,
        retryable: bool = False,
    ):
        super().__init__(
            message,
            code=code.value if isinstance(code, ErrorCode) else code,
            http_status=http_status,
            detail=detail,
        )
        self.retryable = retryable


class CommandOutcomeUnknown(CommandError):
    """El commit pudo aplicarse; el cliente debe reintentar con la misma clave."""

    def __init__(self, message: Optional[str] = None):
        super().__init__(
            ErrorCode.COMMAND_OUTCOME_UNKNOWN,
            message
            or "No se pudo confirmar el resultado del comando. "
            "Reintentá con el mismo commandId y payload.",
            http_status=503,
            retryable=True,
        )


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def hash_comando(comando: RunCommand, *, date: Optional[str] = None) -> str:
    """SHA-256 sobre tipo, payload y versión esperada; la creación incluye la fecha."""
    payload = {
        "type": comando.type.value,
        "payload": comando.payload.model_dump(mode="json"),
        "expectedVersion": getattr(comando, "expectedVersion", None),
    }
    if date is not None:
        payload["date"] = str(date)
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


CAMPOS_INTERNOS_RUN = ("_id", "recibos", "liquidacion")


def estado_confirmado(run: Dict[str, Any]) -> Dict[str, Any]:
    """Estado publicable de una versión, sin la colección de recibos ni la liquidación."""
    return {
        clave: deepcopy(valor)
        for clave, valor in run.items()
        if clave not in CAMPOS_INTERNOS_RUN
    }


def buscar_recibo(run: Dict[str, Any], command_id: str) -> Optional[Dict[str, Any]]:
    for recibo in run.get("recibos") or []:
        if recibo.get("commandId") == command_id:
            return recibo
    return None


def principal_de_run(run: Dict[str, Any]) -> Principal:
    return Principal(
        user_id=int(run.get("user_id") or 0),
        guest_id=run.get("guest_id") or None,
    )


def verificar_propiedad(run: Dict[str, Any], principal: Principal) -> None:
    if principal_de_run(run) != principal:
        raise CommandError(
            ErrorCode.FORBIDDEN,
            "La partida no pertenece al principal autenticado.",
            http_status=403,
        )
