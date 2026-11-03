"""Constantes y guardas compartidas por la generación diaria."""

import calendar

from fastapi import HTTPException

from app.core.database import get_database

MONTH_NAMES_ES = [
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
]

CRUCIGRAMA_DIFFICULTIES = ["facil", "dificil"]


async def assert_month_regenerable(game_id: str, year: int, month: int) -> None:
    """
    Bloquea la regeneración forzada de un mes que ya tiene intentos registrados:
    cambiar las soluciones invalidaría las partidas jugadas.
    """
    _, days_in_month = calendar.monthrange(year, month)
    start_date = f"{year:04d}-{month:02d}-01"
    end_date = f"{year:04d}-{month:02d}-{days_in_month:02d}"
    db = get_database()
    intento = await db["user_attempts"].find_one(
        {"game_id": game_id, "date": {"$gte": start_date, "$lte": end_date}},
        {"_id": 1},
    )
    if intento:
        raise HTTPException(
            status_code=409,
            detail=(
                f"No se puede regenerar {game_id} para {year}-{month:02d}: "
                "ya existen intentos de jugadores. Usá un mes futuro."
            ),
        )
