"""Cobertura mensual de desafíos para la Torre de Control."""

import calendar

from app.core.database import get_database
from app.features.daily_challenges.games.common import MONTH_NAMES_ES


async def get_challenges_monthly_status(year: int, game_id: str = "sudoku") -> dict:
    """
    Calcula el estado de cobertura de desafíos para cada uno de los 12 meses de un año.
    Permite a la Torre de Control auditar y generar meses faltantes.
    """
    db = get_database()
    months_status = []

    for m in range(1, 13):
        _, days_in_month = calendar.monthrange(year, m)
        start_date = f"{year:04d}-{m:02d}-01"
        end_date = f"{year:04d}-{m:02d}-{days_in_month:02d}"

        count = await db["daily_challenges"].count_documents({
            "game_id": game_id,
            "date": {"$gte": start_date, "$lte": end_date}
        })

        if count >= days_in_month:
            status = "completed"
        elif count > 0:
            status = "partial"
        else:
            status = "pending"

        months_status.append({
            "month": m,
            "name": MONTH_NAMES_ES[m - 1],
            "days_in_month": days_in_month,
            "generated_count": count,
            "status": status,
            "is_complete": count >= days_in_month
        })

    return {
        "game_id": game_id,
        "year": year,
        "months": months_status
    }
