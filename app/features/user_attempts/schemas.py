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
    difficulty: Optional[str] = Field(
        None,
        pattern=r"^[A-Za-z0-9_-]{1,32}$",
        description="Dificultad de la partida (ej: facil, dificil, standard)",
    )
    attempts: int = Field(1, ge=0, le=1000, description="Número de intentos utilizados")
    stars: Optional[int] = Field(None, ge=0, le=3, description="Estrellas obtenidas (1 a 3). Si se omite se calcula automáticamente")
    score: Optional[int] = Field(None, ge=0, le=100000, description="Puntaje obtenido. Si se omite se calcula según calificación")
    grade: Optional[str] = Field(None, description="Calificación obtenida por desempeño: 'S', 'A', 'B', 'C', 'F'")
    guesses: Optional[List[Any]] = Field(default_factory=list, description="Lista de intentos realizados (palabras, objetos o números)")
    game_data: Optional[Dict[str, Any]] = Field(None, description="Datos adicionales específicos del juego")
    remaining_attempts: Optional[int] = Field(0, ge=0, le=1000, description="Vidas/intentos restantes del juego")
    time_taken_seconds: Optional[int] = Field(None, ge=0, le=604800, description="Tiempo en segundos que tardó en completar la partida")

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
    grade: Optional[str] = None
    remaining_attempts: int = 0
    time_taken_seconds: Optional[int] = None
    puntos_ganados: int = 0
    puntos_totales_usuario: Optional[int] = None
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
