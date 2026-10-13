from fastapi import APIRouter, Query, Path
from typing import Optional
from app.features.daily_challenges.schemas import (
    DailyChallengeCreateRequest,
    DailyChallengeResponse,
    MonthChallengesResponse,
    ChallengeRangeResponse
)
from app.features.daily_challenges.service import (
    get_today_challenge,
    get_month_challenges,
    get_challenge_by_date,
    upsert_challenge,
    get_challenge_date_range
)

router = APIRouter(prefix="/api/challenges", tags=["Desafíos Diarios"])

@router.get(
    "/today",
    response_model=DailyChallengeResponse,
    summary="Obtener el desafío de hoy"
)
async def endpoint_get_today_challenge(
    game_id: str = Query("wordle", description="Identificador del juego (ej: wordle, sudoku)"),
    difficulty: str = Query("standard", description="Dificultad del desafío")
):
    return await get_today_challenge(game_id=game_id, difficulty=difficulty)

@router.get(
    "/month",
    response_model=MonthChallengesResponse,
    summary="Obtener los desafíos del mes (con tope estricto de días del mes)"
)
async def endpoint_get_month_challenges(
    year: int = Query(..., ge=2020, le=2050, description="Año a consultar (ej: 2026)"),
    month: int = Query(..., ge=1, le=12, description="Mes a consultar (1-12)"),
    game_id: str = Query("wordle", description="Identificador del juego"),
    difficulty: str = Query("standard", description="Dificultad del desafío"),
    until_today: bool = Query(False, description="Si es True, devuelve hasta la fecha actual inclusive")
):
    return await get_month_challenges(
        year=year,
        month=month,
        game_id=game_id,
        difficulty=difficulty,
        until_today=until_today
    )

@router.get(
    "/range",
    response_model=ChallengeRangeResponse,
    summary="Obtener el rango de fechas disponibles para un juego"
)
async def endpoint_get_challenge_range(
    game_id: str = Query("wordle", description="Identificador del juego")
):
    return await get_challenge_date_range(game_id=game_id)

@router.get(
    "/date/{date}",
    response_model=DailyChallengeResponse,
    summary="Obtener el desafío de una fecha específica"
)
async def endpoint_get_challenge_by_date(
    date: str = Path(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha en formato YYYY-MM-DD"),
    game_id: str = Query("wordle", description="Identificador del juego"),
    difficulty: str = Query("standard", description="Dificultad del desafío")
):
    return await get_challenge_by_date(game_id=game_id, target_date=date, difficulty=difficulty)

@router.post(
    "",
    response_model=DailyChallengeResponse,
    summary="Crear o actualizar un desafío diario"
)
async def endpoint_upsert_challenge(req: DailyChallengeCreateRequest):
    return await upsert_challenge(req)
