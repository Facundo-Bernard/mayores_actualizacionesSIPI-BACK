from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any


class EscalaCalificacionTiempo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    grade: str = Field(..., description="Letra o código de la calificación (ej: 'S', 'A', 'B', 'C', 'D')")
    tiempo_max_segundos: int = Field(..., ge=1, description="Tiempo máximo en segundos para obtener esta calificación")
    puntos: int = Field(..., ge=0, description="Puntos otorgados al completar en este rango")
    estrellas: int = Field(3, ge=0, le=3, description="Estrellas visuales otorgadas (0 a 3)")
    titulo: Optional[str] = Field(None, description="Título amigable ej: '¡Impecable!', '¡Excelente!'")
    descripcion: Optional[str] = Field(None, description="Descripción del rango ej: 'Menos de 03:00'")


DEFAULT_ESCALAS_TIEMPO: Dict[str, List[Dict[str, Any]]] = {
    "sudoku": [
        {"grade": "S", "tiempo_max_segundos": 180, "puntos": 100, "estrellas": 3, "titulo": "¡Impecable!", "descripcion": "Menos de 03:00"},
        {"grade": "A", "tiempo_max_segundos": 300, "puntos": 90, "estrellas": 3, "titulo": "¡Excelente!", "descripcion": "03:01 a 05:00"},
        {"grade": "B", "tiempo_max_segundos": 480, "puntos": 75, "estrellas": 2, "titulo": "¡Muy Bueno!", "descripcion": "05:01 a 08:00"},
        {"grade": "C", "tiempo_max_segundos": 720, "puntos": 50, "estrellas": 1, "titulo": "¡Buen Trabajo!", "descripcion": "08:01 a 12:00"},
        {"grade": "D", "tiempo_max_segundos": 999999, "puntos": 25, "estrellas": 1, "titulo": "¡Completado!", "descripcion": "Más de 12:00"},
    ],
    "crucigrama": [
        {"grade": "S", "tiempo_max_segundos": 240, "puntos": 100, "estrellas": 3, "titulo": "¡Impecable!", "descripcion": "Menos de 04:00"},
        {"grade": "A", "tiempo_max_segundos": 420, "puntos": 90, "estrellas": 3, "titulo": "¡Excelente!", "descripcion": "04:01 a 07:00"},
        {"grade": "B", "tiempo_max_segundos": 600, "puntos": 75, "estrellas": 2, "titulo": "¡Muy Bueno!", "descripcion": "07:01 a 10:00"},
        {"grade": "C", "tiempo_max_segundos": 900, "puntos": 50, "estrellas": 1, "titulo": "¡Buen Trabajo!", "descripcion": "10:01 a 15:00"},
        {"grade": "D", "tiempo_max_segundos": 999999, "puntos": 25, "estrellas": 1, "titulo": "¡Completado!", "descripcion": "Más de 15:00"},
    ],
    "sopa_letras": [
        {"grade": "S", "tiempo_max_segundos": 120, "puntos": 100, "estrellas": 3, "titulo": "¡Impecable!", "descripcion": "Menos de 02:00"},
        {"grade": "A", "tiempo_max_segundos": 240, "puntos": 90, "estrellas": 3, "titulo": "¡Excelente!", "descripcion": "02:01 a 04:00"},
        {"grade": "B", "tiempo_max_segundos": 360, "puntos": 75, "estrellas": 2, "titulo": "¡Muy Bueno!", "descripcion": "04:01 a 06:00"},
        {"grade": "C", "tiempo_max_segundos": 600, "puntos": 50, "estrellas": 1, "titulo": "¡Buen Trabajo!", "descripcion": "06:01 a 10:00"},
        {"grade": "D", "tiempo_max_segundos": 999999, "puntos": 25, "estrellas": 1, "titulo": "¡Completado!", "descripcion": "Más de 10:00"},
    ],
}


class EconomyConfigResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    vidas_iniciales: int = Field(5, ge=1, description="Vidas con las que arranca cada cuenta nueva (deprecado/local)")
    costo_desbloqueo_dia_puntos: int = Field(100, ge=0, description="Costo en puntos para desbloquear un día histórico")
    costo_pista_puntos: int = Field(20, ge=0, description="Costo en puntos para solicitar una pista")
    puntos_por_calificacion: Dict[str, int] = Field(
        default_factory=lambda: {
            "S": 100,
            "A": 90,
            "B": 75,
            "C": 50,
            "F": 0,
        },
        description="Puntos otorgados según calificación S, A, B, C, F",
    )
    escalas_tiempo_por_juego: Dict[str, List[EscalaCalificacionTiempo]] = Field(
        default_factory=lambda: {
            k: [EscalaCalificacionTiempo(**item) for item in v]
            for k, v in DEFAULT_ESCALAS_TIEMPO.items()
        },
        description="Escalas de calificación por tiempo configuradas por juego",
    )
    puntos_por_juego: Dict[str, int] = Field(
        default_factory=lambda: {
            "wordle": 50,
            "sopa_letras": 50,
            "sudoku": 60,
            "crucigrama": 70,
            "narrativo": 80,
        },
        description="Puntos que otorga cada juego al completar un desafío",
    )
    guest_migration_max_points: int = Field(
        1000, ge=0, description="Tope de puntos de invitado que una cuenta puede reclamar al registrarse"
    )
    updated_at: Optional[str] = None


class EconomyConfigUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    vidas_iniciales: Optional[int] = Field(None, ge=1, description="Vidas iniciales para cuentas nuevas")
    costo_desbloqueo_dia_puntos: Optional[int] = Field(None, ge=0, description="Costo en puntos para desbloquear un día histórico")
    costo_pista_puntos: Optional[int] = Field(None, ge=0, description="Costo en puntos para solicitar una pista")
    puntos_por_calificacion: Optional[Dict[str, int]] = Field(None, description="Puntos otorgados según calificación S, A, B, C, F")
    escalas_tiempo_por_juego: Optional[Dict[str, List[EscalaCalificacionTiempo]]] = Field(
        None, description="Escalas de calificación por tiempo por juego (sudoku, crucigrama, sopa_letras)"
    )
    puntos_por_juego: Optional[Dict[str, int]] = None
    guest_migration_max_points: Optional[int] = Field(
        None, ge=0, description="Tope de puntos de invitado reclamables por cuenta"
    )


class UserEconomyResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: int
    vidas: Optional[int] = Field(5, description="Deprecado: vidas globales informativas")
    puntos: int
    racha: int = Field(0, description="Días consecutivos con al menos un desafío diario completado")
    racha_ultima_fecha: Optional[str] = Field(None, description="Último día jugado en formato YYYY-MM-DD")
    racha_hoy_jugada: bool = Field(False, description="Indica si ya completó un desafío diario hoy (ART)")
    suscripcion: str = Field("basica", description="'basica' | 'premium'")
    dias_desbloqueados: List[str] = Field(default_factory=list, description="Días históricos desbloqueados ej: ['crucigrama:2026-10-15']")
    costo_pista_puntos: int = Field(20, description="Costo en puntos para solicitar una pista")
    updated_at: Optional[str] = None


class ConsumeLifeRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    game_id: Optional[str] = Field(None, description="Juego en el que se consumió la vida")
    motivo: Optional[str] = Field("error", description="error | reintento | inicio")


class ConsumeLifeResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    success: bool
    vidas_restantes: int
    consumidas: int = 1
    message: Optional[str] = None


class RefillLivesResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    success: bool
    puntos: int = Field(..., description="Saldo de puntos restante tras la recarga")
    message: str


class UnlockDayRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    game_id: str = Field(..., description="ID del juego: wordle, crucigrama, sopa_letras, sudoku")
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha YYYY-MM-DD del día a desbloquear")


class UnlockDayResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    success: bool
    unlocked: bool
    puntos: int
    costo: int
    date: str
    game_id: str
    message: str


class CambiarSuscripcionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    suscripcion: str = Field("basica", pattern=r"^(basica|premium)$", description="'basica' o 'premium'")


class SearchUserEconomyResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    email: Optional[str] = None
    codigoAcceso: Optional[str] = None
    vidas: int
    puntos: int
    suscripcion: str = "basica"
    dias_desbloqueados: List[str] = []


class AdjustUserEconomyRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    identificador: str = Field(..., description="Email, código de acceso PIN o ID del usuario")
    vidas_sumar: Optional[int] = Field(None, description="Cantidad de vidas a sumar (positivo) o restar (negativo)")
    puntos_sumar: Optional[int] = Field(None, description="Cantidad de puntos a sumar (positivo) o restar (negativo)")
    vidas_set: Optional[int] = Field(None, ge=0, description="Fijar vidas a un valor exacto")
    puntos_set: Optional[int] = Field(None, ge=0, description="Fijar puntos a un valor exacto")
    suscripcion_set: Optional[str] = Field(None, pattern=r"^(basica|premium)$", description="Cambiar suscripción a 'basica' o 'premium'")


class AdjustUserEconomyResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    success: bool
    user_id: int
    name: str
    email: Optional[str] = None
    codigoAcceso: Optional[str] = None
    vidas: int
    puntos: int
    suscripcion: str
    message: str


class UseHintRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    game_id: str = Field(..., description="ID del juego: wordle, sudoku, sopa_letras, crucigrama")
    date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha YYYY-MM-DD del desafío")
    difficulty: Optional[str] = Field(
        None,
        pattern=r"^[A-Za-z0-9_-]{1,32}$",
        description="Dificultad de la partida; si falta se infiere del intento del usuario",
    )
    hint_index: Optional[int] = Field(0, ge=0, le=1000, description="Índice de la pista a consultar (para Wordle o Sopa de Letras)")
    row: Optional[int] = Field(None, description="Fila de la casilla a revelar (Sudoku / Crucigrama)")
    col: Optional[int] = Field(None, description="Columna de la casilla a revelar (Sudoku / Crucigrama)")


class UseHintResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    success: bool
    puntos_restantes: int = Field(..., description="Saldo actualizado de puntos del usuario")
    puntos_descontados: int = Field(20, description="Puntos descontados por solicitar la pista")
    vidas_restantes: Optional[int] = Field(None, description="Deprecado / informativo")
    vidas_descontadas: Optional[int] = Field(0, description="Deprecado / informativo")
    pista: Optional[str] = Field(None, description="Texto de la pista generada o definición RAE")
    valor_revelado: Optional[Any] = Field(None, description="Número o letra revelada si aplica (ej: celda de Sudoku o letra de Crucigrama)")
    message: str


class GuestMigrationRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    guest_id: str = Field(
        ...,
        pattern=r"^[A-Za-z0-9_-]{1,64}$",
        description="Identificador anónimo (X-Guest-Id) con el que se acumularon puntos sin cuenta",
    )
    puntos: int = Field(..., ge=0, description="Puntos informados por el cliente; el servidor aplica el tope configurado")


class GuestMigrationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    success: bool
    ya_migrado: bool = Field(..., description="True si la cuenta ya había reclamado puntos de invitado")
    puntos_solicitados: int
    puntos_migrados: int
    tope: int
    puntos_totales: int = Field(..., description="Saldo total de puntos de la cuenta tras la migración")
    message: str
