from fastapi import APIRouter, Header, Query, HTTPException
from typing import Optional
from app.core.security import decode_access_token
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

def _extract_user_id_from_header(authorization: Optional[str]) -> Optional[int]:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        payload = decode_access_token(parts[1])
        if payload and "id" in payload:
            try:
                return int(payload["id"])
            except (ValueError, TypeError):
                return None
    return None

@router.post(
    "",
    response_model=UserAttemptResponse,
    summary="Guardar o actualizar el progreso de una partida"
)
async def endpoint_save_attempt(
    req: UserAttemptCreateRequest,
    authorization: Optional[str] = Header(None)
):
    user_id_from_token = _extract_user_id_from_header(authorization)
    effective_user_id = user_id_from_token or req.user_id
    if not effective_user_id:
        raise HTTPException(
            status_code=401,
            detail="Se requiere iniciar sesión para guardar progreso en la nube."
        )
    return await save_user_attempt(req, authenticated_user_id=effective_user_id)

@router.get(
    "/date/{date}",
    response_model=Optional[UserAttemptResponse],
    summary="Obtener intento de un usuario para una fecha específica"
)
async def endpoint_get_user_attempt_by_date(
    date: str,
    game_id: str = Query("wordle", description="Identificador del juego"),
    user_id: Optional[int] = Query(None, description="ID del usuario (opcional si se envía Bearer token)"),
    authorization: Optional[str] = Header(None)
):
    token_user_id = _extract_user_id_from_header(authorization)
    effective_user_id = user_id or token_user_id
    if not effective_user_id:
        return None

    return await get_user_attempt_by_date(
        user_id=effective_user_id,
        game_id=game_id,
        date=date
    )

@router.get(
    "",
    response_model=UserAttemptsListResponse,
    summary="Obtener intentos del usuario en un mes específico"
)
async def endpoint_get_user_attempts(
    user_id: Optional[int] = Query(None, description="ID del usuario (opcional si se envía Bearer token)"),
    game_id: str = Query("wordle", description="Identificador del juego"),
    year: int = Query(2026, description="Año a consultar"),
    month: int = Query(10, ge=1, le=12, description="Mes a consultar"),
    authorization: Optional[str] = Header(None)
):
    token_user_id = _extract_user_id_from_header(authorization)
    effective_user_id = user_id or token_user_id
    if not effective_user_id:
        return UserAttemptsListResponse(
            user_id=None,
            game_id=game_id,
            year=year,
            month=month,
            total=0,
            attempts=[]
        )

    return await get_user_attempts_by_month(
        user_id=effective_user_id,
        game_id=game_id,
        year=year,
        month=month
    )
