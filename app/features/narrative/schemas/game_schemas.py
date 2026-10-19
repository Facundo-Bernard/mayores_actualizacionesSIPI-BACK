from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Dict, Any, Union

from app.features.narrative.enums import RunPhaseEnum
from app.features.narrative.schemas.rules_schemas import CondicionSchema
from app.features.narrative.schemas.catalog_schemas import (
    UniversoResponse,
    PersonajeResponse,
    CartaResponse,
    ResultadoResponse,
    ConversacionResponse,
    FinalizacionResponse
)

# ============================================================================
# 1. CONFIGURACIÓN DEL DESAFÍO DIARIO (Extensión a daily_challenges)
# ============================================================================

class NarrativeDailyChallengeConfig(BaseModel):
    universo_id: str
    titulo: str
    descripcion: Optional[str] = None
    duracion_meses: int = 12
    atributos_iniciales: Dict[str, int]
    setup_corte_ofrecidos_ids: List[str]
    setup_cartas_ofrecidas_ids: List[str]
    pool_eventos_disponibles_ids: List[str]
    pool_cartas_mensuales_ids: List[str]
    pool_conversaciones_ids: List[str]

# ============================================================================
# 2. ESTADO VIVO DE LA PARTIDA DEL ALUMNO (narrative_runs)
# ============================================================================

class TurnoSnapshot(BaseModel):
    cartas_ofrecidas_ids: List[str] = []
    carta_elegida_id: Optional[str] = None
    evento_actual_id: Optional[str] = None
    opcion_elegida_id: Optional[str] = None
    resultado_obtenido_id: Optional[str] = None
    conversacion_actual_id: Optional[str] = None
    decision_conversacion_opcion: Optional[int] = None

class HistorialMes(BaseModel):
    mes: int
    carta_elegida_id: Optional[str] = None
    evento_id: Optional[str] = None
    opcion_elegida_id: Optional[str] = None
    resultado_id: Optional[str] = None
    conversacion_id: Optional[str] = None
    decision_conversacion_opcion: Optional[int] = None
    recursos_fin_mes: Dict[str, int]

class NarrativeRunSchema(BaseModel):
    id: str = Field(..., alias="_id")
    user_id: int
    date: str
    game_id: str = "narrativo"
    universo_id: str
    mes_actual: int = 1
    fase_actual: RunPhaseEnum = RunPhaseEnum.DRAFT_MENSUAL
    status: str = "in_progress" # in_progress | completed | game_over
    recursos: Dict[str, int]
    afinidad: Dict[str, int]
    corte_activa: Optional[List[str]] = None
    cartas_en_mano: List[str]
    tags_activos: List[str]
    turno_actual: TurnoSnapshot
    eventos_jugados: List[str] = []
    conversaciones_jugadas: List[str] = []
    historial_mensual: List[Union[HistorialMes, str, Dict[str, Any]]] = []
    finalizacion: Optional[Dict[str, Any]] = None
    epilogo_final: Optional[Dict[str, Any]] = None
    updated_at: Optional[str] = None

    @model_validator(mode="after")
    def populate_corte_activa(self):
        if not self.corte_activa and self.afinidad:
            self.corte_activa = list(self.afinidad.keys())
        return self

    model_config = {"populate_by_name": True}

# ============================================================================
# 3. DTOs DE ENTRADA (REQUESTS DEL JUGADOR)
# ============================================================================

class IniciarPartidaRequest(BaseModel):
    date: str
    corte_elegida_ids: List[str]
    cartas_iniciales_ids: List[str]

class ElegirCartaMesRequest(BaseModel):
    date: str
    carta_id: str

class DecidirEventoRequest(BaseModel):
    date: str
    opcion_id: str

class ResponderConversacionRequest(BaseModel):
    date: str
    opcion_numero: int

class AvanzarMesRequest(BaseModel):
    date: str

class ReiniciarPartidaRequest(BaseModel):
    date: str

class ConversacionesPosiblesRequest(BaseModel):
    personajes_ids: List[str] = Field(..., description="Lista de IDs de personajes en mano o corte")
    universo_id: Optional[str] = Field(None, description="Filtro opcional por universo")

# ============================================================================
# 4. DTOs DE CÁLCULO DE PROBABILIDADES Y TURNO
# ============================================================================

class SetupDesafioResponse(BaseModel):
    date: str
    universo_id: str
    universo_nombre: str
    universo_descripcion: str = ""
    atributos_iniciales: Dict[str, int]
    personajes_ofrecidos: List[PersonajeResponse]
    cartas_ofrecidas: List[CartaResponse]
    tiene_partida_activa: bool = False
    fase_partida_activa: Optional[str] = None

class ProbabilidadDesenlaceCalculada(BaseModel):
    resultado_id: str
    titulo: str
    porcentaje: float
    explicaciones: List[str] = []

class OpcionEventoCalculadaResponse(BaseModel):
    id: str
    texto: str
    es_secreta: bool
    bloqueada: bool
    probabilidades: List[ProbabilidadDesenlaceCalculada]

class EventoTurnoResponse(BaseModel):
    id: str
    titulo: str
    descripcion: str
    imagen: str
    opciones: List[OpcionEventoCalculadaResponse]

# ============================================================================
# 5. DTOs PARA ENDPOINTS DE CONSULTA ESPECIALIZADOS (BAJO DEMANDA)
# ============================================================================

class HistorialPartidaResponse(BaseModel):
    date: str
    mes_actual: int
    status: str
    fase_actual: str
    historial_mensual: List[Union[HistorialMes, Dict[str, Any], str]]

class InventarioPartidaResponse(BaseModel):
    date: str
    cartas: List[CartaResponse]
    tags_activos: List[str]

class PersonajeCorteDetalle(BaseModel):
    personaje: PersonajeResponse
    afinidad: int

class CortePartidaResponse(BaseModel):
    date: str
    corte: List[PersonajeCorteDetalle]
    afinidad: Dict[str, int]

class FinalizacionPartidaResponse(BaseModel):
    date: str
    status: str
    mes_actual: int
    finalizacion: Optional[FinalizacionResponse] = None
    epilogo_final: Optional[Dict[str, Any]] = None

class EstadoTurnoResponse(BaseModel):
    date: str
    mes_actual: int
    fase_actual: str
    status: str
    recursos: Dict[str, int]
    afinidad: Dict[str, int]
    cartas_draft_actual: List[CartaResponse] = []
    evento_actual: Optional[EventoTurnoResponse] = None
    resultado_actual: Optional[ResultadoResponse] = None
    conversacion_actual: Optional[ConversacionResponse] = None
    finalizacion: Optional[FinalizacionResponse] = None

# ============================================================================
# 7. DTOs DEL MOTOR V2 LIGERO (DELTAS POR FASE)
# ============================================================================

class IniciarPartidaV2Response(BaseModel):
    mes_actual: int = 1
    fase_actual: str = "DRAFT_MENSUAL"
    recursos: Dict[str, int]
    afinidad: Dict[str, int]
    cartas_draft_actual: List[CartaResponse]
    finalizacion: Optional[FinalizacionResponse] = None

class ElegirCartaMesV2Response(BaseModel):
    fase_actual: str = "TOMA_DECISION_EVENTO"
    recursos: Dict[str, int]
    evento_actual: Optional[EventoTurnoResponse] = None
    finalizacion: Optional[FinalizacionResponse] = None

class DecidirEventoV2Response(BaseModel):
    fase_actual: str
    recursos: Dict[str, int]
    resultado_actual: ResultadoResponse
    conversacion_actual: Optional[ConversacionResponse] = None
    finalizacion: Optional[FinalizacionResponse] = None

class ResponderConversacionV2Response(BaseModel):
    fase_actual: str = "BALANCE_MES"
    afinidad: Dict[str, int]
    resultado_texto: str
    impacto_afinidad: List[Dict[str, Any]]

class AvanzarMesV2Response(BaseModel):
    mes_actual: int
    fase_actual: str
    status: str
    recursos: Dict[str, int]
    cartas_draft_actual: List[CartaResponse] = []
    finalizacion: Optional[FinalizacionResponse] = None
