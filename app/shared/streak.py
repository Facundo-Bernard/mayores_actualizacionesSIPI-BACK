"""Racha de días consecutivos con al menos un desafío diario completado.

La racha se deriva de ``user_attempts`` y no se guarda como contador: así no se
desincroniza por replays, partidas de varios juegos el mismo día ni correcciones
posteriores.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from app.core.database import get_database
from app.shared.clock import today_art


@dataclass(frozen=True)
class Racha:
    actual: int
    ultima_fecha: Optional[str]
    hoy_jugada: bool


async def calcular_racha(user_id: int) -> Racha:
    """Cuenta los días consecutivos hacia atrás desde hoy o ayer (zona ART)."""
    hoy = today_art()
    ayer = hoy - timedelta(days=1)

    cursor = get_database()["user_attempts"].find(
        {
            "user_id": int(user_id),
            "mode": "daily",
            "status": "completed",
            "validation_status": {"$ne": "rejected"},
            "date": {"$lte": hoy.isoformat()},
        },
        {"_id": 0, "date": 1},
    ).sort("date", -1)

    ultima_fecha: Optional[str] = None
    ultima_contada: Optional[str] = None
    esperada: Optional[date] = None
    actual = 0

    async for doc in cursor:
        fecha_str = doc.get("date")
        if not isinstance(fecha_str, str):
            continue
        # Varios juegos el mismo día generan un documento por juego: el día cuenta una vez.
        if fecha_str == ultima_contada:
            continue
        ultima_contada = fecha_str

        if esperada is None:
            ultima_fecha = fecha_str
            try:
                esperada = date.fromisoformat(fecha_str)
            except ValueError:
                break
            # Si el último día jugado es anterior a ayer, la racha ya se cortó.
            if esperada < ayer:
                break

        if fecha_str != esperada.isoformat():
            break

        actual += 1
        esperada -= timedelta(days=1)

    return Racha(
        actual=actual,
        ultima_fecha=ultima_fecha,
        hoy_jugada=ultima_fecha == hoy.isoformat(),
    )
