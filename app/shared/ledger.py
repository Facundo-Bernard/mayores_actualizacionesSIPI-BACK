"""Interfaz del ledger de puntos. La implementación (economy_ledger) llega en Fase 1."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LedgerKey:
    """Clave de negocio: una acreditación como máximo por combinación."""

    user_id: int
    motivo: str
    game_id: str
    date: str
    difficulty: str | None = None

    @property
    def business_key(self) -> tuple:
        return (self.user_id, self.motivo, self.game_id, self.date, self.difficulty or "")


@dataclass(frozen=True)
class LedgerResult:
    applied: bool
    puntos: int
    saldo: int | None = None


class PointsLedger(Protocol):
    async def credit(
        self, key: LedgerKey, puntos: int, *, metadata: dict | None = None
    ) -> LedgerResult: ...

    async def saldo(self, user_id: int) -> int: ...
