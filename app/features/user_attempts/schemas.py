from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class GuessEvaluationItem(BaseModel):
    word: str
    statuses: Optional[List[str]] = None

class UserAttemptCreateRequest(BaseModel):
    user_id: Optional[int] = Field(None, description="ID del usuario (opcional si se envía Bearer token)")
    game_id: str = Field("wordle", description="Identificador del juego")
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha de la partida (YYYY-MM-DD)")
    mode: str = Field("daily", description="Modo: 'daily' o 'campaign'")
    status: str = Field("completed", description="'in_progress', 'completed' o 'failed'")
    word: Optional[str] = Field(None, description="Palabra de la partida")
    attempts: int = Field(1, description="Número de intentos utilizados")
    stars: int = Field(1, description="Estrellas obtenidas (1 a 3)")
    score: int = Field(100, description="Puntaje obtenido")
    guesses: Optional[List[Any]] = Field(default_factory=list, description="Lista de intentos realizados (palabras, objetos o números)")
    game_data: Optional[Dict[str, Any]] = Field(None, description="Datos adicionales específicos del juego")
    remaining_attempts: Optional[int] = Field(0, description="Intentos restantes")

class UserAttemptResponse(BaseModel):
    id: str
    user_id: Optional[int] = None
    game_id: str
    date: str
    mode: str
    status: str
    word: Optional[str] = None
    attempts: int
    stars: int
    score: int
    guesses: List[Any] = []
    game_data: Optional[Dict[str, Any]] = None
    updated_at: Optional[str] = None

class UserAttemptsListResponse(BaseModel):
    user_id: Optional[int] = None
    game_id: str
    year: int
    month: int
    total: int
    attempts: List[UserAttemptResponse]
