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
    get_challenge_date_range,
    generate_and_save_sudoku_month,
    generate_and_save_wordle_month,
    generate_and_save_sopa_month,
    generate_and_save_crucigrama_month,
    get_challenges_monthly_status
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

@router.get(
    "/admin/status",
    summary="Obtener el estado de cobertura de desafíos por mes para administración"
)
async def endpoint_admin_challenges_status(
    year: int = Query(2026, description="Año a auditar"),
    game_id: str = Query("sudoku", description="Juego a consultar (sudoku, wordle, sopa_letras, crucigrama)")
):
    return await get_challenges_monthly_status(year=year, game_id=game_id)

@router.post(
    "/admin/generate-month",
    summary="Generar o regenerar los desafíos de un mes completo desde la Torre de Control"
)
async def endpoint_admin_generate_month(
    year: int = Query(..., ge=2020, le=2050, description="Año a generar"),
    month: int = Query(..., ge=1, le=12, description="Mes a generar (1-12)"),
    game_id: str = Query("sudoku", description="Juego a generar (sudoku, wordle, sopa_letras, crucigrama)"),
    force: bool = Query(True, description="Forzar regeneración si ya existe")
):
    if game_id == "sudoku":
        return await generate_and_save_sudoku_month(year=year, month=month, force=force)
    elif game_id == "wordle":
        return await generate_and_save_wordle_month(year=year, month=month, force=force)
    elif game_id == "sopa_letras":
        return await generate_and_save_sopa_month(year=year, month=month, force=force)
    elif game_id == "crucigrama":
        return await generate_and_save_crucigrama_month(year=year, month=month, force=force)
    return {"success": False, "message": f"Generación automática no disponible para el juego '{game_id}'."}

