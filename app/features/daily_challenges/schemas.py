from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class DailyChallengeCreateRequest(BaseModel):
    game_id: str = Field(..., description="Identificador del juego (ej: wordle, sudoku)")
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha en formato YYYY-MM-DD")
    difficulty: str = Field("standard", description="Nivel de dificultad")
    title: Optional[str] = None
    config: Dict[str, Any] = Field(..., description="Configuración específica del juego")

class DailyChallengeResponse(BaseModel):
    id: str
    game_id: str
    date: str
    difficulty: str
    title: Optional[str] = None
    config: Dict[str, Any]
    is_today: bool = False
    is_past: bool = False
    is_future: bool = False
    created_at: Optional[str] = None

class MonthChallengesResponse(BaseModel):
    year: int
    month: int
    days_in_month: int
    total_challenges: int
    challenges: List[DailyChallengeResponse]

class ChallengeRangeResponse(BaseModel):
    game_id: str
    min_date: Optional[str] = None
    max_date: Optional[str] = None

