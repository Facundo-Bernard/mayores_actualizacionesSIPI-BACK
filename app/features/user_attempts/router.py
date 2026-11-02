from fastapi import APIRouter, Depends, Query
from typing import Optional, Dict, Any

from app.core.dependencies import get_current_user
from app.features.user_attempts.schemas import (
    UserAttemptCreateRequest,
    UserAttemptResponse,
    UserAttemptsListResponse
)
from app.features.user_attempts.service import (
    save_user_attempt,
    get_user_attempts_by_month,
    get_user_attempt_by_date
)

router = APIRouter(prefix="/api/games/attempts", tags=["Partidas e Intentos de Usuarios"])


@router.post(
    "",
    response_model=UserAttemptResponse,
    summary="Guardar o actualizar el progreso de una partida"
)
async def endpoint_save_attempt(
    req: UserAttemptCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return await save_user_attempt(
        req, authenticated_user_id=int(current_user["id"])
    )


@router.get(
    "/date/{date}",
    response_model=Optional[UserAttemptResponse],
    summary="Obtener intento de un usuario para una fecha específica"
)
async def endpoint_get_user_attempt_by_date(
    date: str,
    game_id: str = Query("wordle", description="Identificador del juego"),
    user_id: Optional[int] = Query(None, description="Deprecado: se ignora, gana el usuario del token"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return await get_user_attempt_by_date(
        user_id=int(current_user["id"]),
        game_id=game_id,
        date=date
    )


@router.get(
    "",
    response_model=UserAttemptsListResponse,
    summary="Obtener intentos del usuario en un mes específico"
)
async def endpoint_get_user_attempts(
    user_id: Optional[int] = Query(None, description="Deprecado: se ignora, gana el usuario del token"),
    game_id: str = Query("wordle", description="Identificador del juego"),
    year: int = Query(2026, description="Año a consultar"),
    month: int = Query(10, ge=1, le=12, description="Mes a consultar"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return await get_user_attempts_by_month(
        user_id=int(current_user["id"]),
        game_id=game_id,
        year=year,
        month=month
    )
