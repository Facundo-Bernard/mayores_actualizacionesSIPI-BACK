"""Ledger de puntos sobre MongoDB.

La acreditación es idempotente por ``idempotency_key`` y, además, cada usuario
guarda en ``ledger_applied`` las claves ya aplicadas. Esa segunda guarda permite
que el reconciliador reintente un asiento ``pending`` sin duplicar el ``$inc``
cuando la request original alcanzó a acreditar pero no a marcar el asiento.
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Protocol

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.database import get_database
from app.shared.clock import now_utc

COLLECTION = "economy_ledger"


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

    @property
    def idempotency_key(self) -> str:
        difficulty = self.difficulty or "standard"
        return f"{self.motivo}:{self.user_id}:{self.game_id}:{self.date}:{difficulty}"


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


class MongoPointsLedger:
    async def credit(
        self, key: LedgerKey, puntos: int, *, metadata: dict | None = None
    ) -> LedgerResult:
        db = get_database()
        now = now_utc()
        asiento = {
            "_id": key.idempotency_key,
            "idempotency_key": key.idempotency_key,
            "user_id": int(key.user_id),
            "motivo": key.motivo,
            "game_id": key.game_id,
            "date": key.date,
            "difficulty": key.difficulty or "standard",
            "puntos": int(puntos),
            "status": "pending",
            "metadata": metadata or {},
            "created_at": now,
            "updated_at": now,
        }
        try:
            await db[COLLECTION].insert_one(asiento)
        except DuplicateKeyError:
            existing = await db[COLLECTION].find_one({"_id": key.idempotency_key})
            if existing and existing.get("status") == "applied":
                return LedgerResult(
                    applied=False,
                    puntos=0,
                    saldo=existing.get("saldo_despues"),
                )
            # Un asiento pendiente ya existe (otra request en vuelo o un crash).
            # No se acredita acá: el dueño original o el reconciliador lo resuelve.
            return LedgerResult(
                applied=False,
                puntos=0,
                saldo=await self.saldo(key.user_id),
            )
        return await self._apply(asiento)

    async def _apply(self, asiento: dict[str, Any]) -> LedgerResult:
        db = get_database()
        clave = asiento["idempotency_key"]
        user_id = int(asiento["user_id"])
        puntos = int(asiento["puntos"])

        user = await db["usuarios"].find_one_and_update(
            {"id": user_id, "ledger_applied": {"$ne": clave}},
            {
                "$inc": {"puntos": puntos},
                "$addToSet": {"ledger_applied": clave},
                "$set": {"updated_at": now_utc()},
            },
            return_document=ReturnDocument.AFTER,
        )

        if not user:
            actual = await db["usuarios"].find_one({"id": user_id})
            if not actual:
                await self._mark(asiento, status="failed", saldo=None)
                return LedgerResult(applied=False, puntos=0, saldo=None)
            # La clave ya estaba aplicada: se cierra el asiento sin volver a sumar.
            saldo = int(actual.get("puntos", 0))
            await self._mark(asiento, status="applied", saldo=saldo)
            return LedgerResult(applied=False, puntos=0, saldo=saldo)

        saldo = int(user.get("puntos", 0))
        await self._mark(asiento, status="applied", saldo=saldo)
        return LedgerResult(applied=True, puntos=puntos, saldo=saldo)

    async def _mark(self, asiento: dict[str, Any], *, status: str, saldo: int | None) -> None:
        db = get_database()
        await db[COLLECTION].update_one(
            {"_id": asiento["idempotency_key"]},
            {
                "$set": {
                    "status": status,
                    "saldo_despues": saldo,
                    "updated_at": now_utc(),
                    "applied_at": now_utc() if status == "applied" else None,
                }
            },
        )

    async def saldo(self, user_id: int) -> int:
        user = await get_database()["usuarios"].find_one(
            {"id": int(user_id)}, {"puntos": 1}
        )
        return int(user.get("puntos", 0)) if user else 0

    async def record_event(
        self,
        *,
        user_id: int,
        motivo: str,
        puntos: int = 0,
        idempotency_key: str | None = None,
        metadata: dict | None = None,
        status: str = "recorded",
    ) -> None:
        """Registra un evento de auditoría (replay, ajuste admin) sin tocar el saldo."""
        db = get_database()
        clave = idempotency_key or f"{motivo}:{user_id}:{now_utc().isoformat()}"
        now = now_utc()
        await db[COLLECTION].update_one(
            {"_id": clave},
            {
                "$setOnInsert": {
                    "idempotency_key": clave,
                    "user_id": int(user_id),
                    "motivo": motivo,
                    "game_id": (metadata or {}).get("game_id", ""),
                    "date": (metadata or {}).get("date", ""),
                    "difficulty": (metadata or {}).get("difficulty", "standard"),
                    "puntos": int(puntos),
                    "status": status,
                    "metadata": metadata or {},
                    "created_at": now,
                    "updated_at": now,
                }
            },
            upsert=True,
        )


_ledger = MongoPointsLedger()


def get_points_ledger() -> MongoPointsLedger:
    return _ledger


async def reconcile_pending_ledger(older_than_seconds: int = 60) -> int:
    """Cierra asientos pendientes antiguos. Devuelve la cantidad procesada."""
    db = get_database()
    cutoff = now_utc() - timedelta(seconds=older_than_seconds)
    cursor = db[COLLECTION].find(
        {"status": "pending", "created_at": {"$lte": cutoff}}
    ).limit(100)
    procesados = 0
    async for asiento in cursor:
        await _ledger._apply(asiento)
        procesados += 1
    if procesados:
        import logging

        logging.getLogger("PointsLedger").info(
            f"[LEDGER] Reconciliados {procesados} asientos pendientes."
        )
    return procesados
