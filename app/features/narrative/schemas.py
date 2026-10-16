from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime

from app.features.narrative.enums import (
    DisparadorEnum,
    OperadorEnum,
    TipoCondicionEnum,
    TipoAccionEnum,
    TipoCalculoEnum,
    RunPhaseEnum,
    TipoResultadoEnum,
    CategoriaCartaEnum,
    TipoFinalizacionEnum
)

# ============================================================================
# 1. BLOQUES DEL PATRÓN ECA (Event - Condition - Action)
# ============================================================================

class CondicionSchema(BaseModel):
    tipo: TipoCondicionEnum
    clave: Optional[str] = None          # Nombre del recurso (ej: "oro", "pueblo")
    operador: Optional[OperadorEnum] = None # ">=", "<=", "==", etc.
    valor: Optional[Union[int, float, str]] = None
    personaje_id: Optional[str] = None
    carta_id: Optional[str] = None
    tag: Optional[str] = None

class AccionSchema(BaseModel):
    tipo: TipoAccionEnum
    clave: Optional[str] = None          # Recurso a modificar o proteger
    tipo_calculo: Optional[TipoCalculoEnum] = TipoCalculoEnum.FIJO
    valor: Optional[float] = 0.0
    personaje_id: Optional[str] = None   # Para modificar_afinidad
    tag: Optional[str] = None            # Para otorgar_tag

class EfectoSchema(BaseModel):
    disparador: DisparadorEnum
    condiciones: List[CondicionSchema] = []
    accion: AccionSchema

# ============================================================================
# 2. CATÁLOGO DE UNIVERSOS / TEMÁTICAS (narrative_settings)
# ============================================================================

class RecursoDefinicionSchema(BaseModel):
    clave: str
    nombre: str
    icono: str = "coins"
    min: int = 0
    max: int = 100
    inicial: int = 50

class UniversoCreateRequest(BaseModel):
    id: str = Field(..., alias="_id", description="Identificador único del universo (ej: corte_medieval)")
    nombre: str
    descripcion: str
    icono: str = "crown"
    imagen: str = "/assets/narrative/universos/default.webp"
    recursos: List[RecursoDefinicionSchema]

    model_config = {"populate_by_name": True}

class UniversoResponse(BaseModel):
    id: str = Field(..., alias="_id")
    nombre: str
    descripcion: str
    icono: str
    imagen: str = "/assets/narrative/universos/default.webp"
    recursos: List[RecursoDefinicionSchema]

    model_config = {"populate_by_name": True}

# ============================================================================
# 3. ENTIDADES DE CONTENIDO (Characters, Cards, Results, Events, Conversations)
# ============================================================================

class PersonajeConversacionProbabilidad(BaseModel):
    idConversacion: str
    probabilidad: float = 0.30

class PersonajeCreateRequest(BaseModel):
    id: str = Field(..., alias="_id")
    universo_id: str
    nombre: str
    titulo: str
    imagen: str = "/assets/narrative/personajes/default.webp"
    descripcion: str
    pros: List[str] = []
    cons: List[str] = []
    tags: List[str] = []
    afinidad_inicial: int = 50
    efectos: List[EfectoSchema] = []
    conversaciones: List[PersonajeConversacionProbabilidad] = []

    model_config = {"populate_by_name": True}

class PersonajeResponse(PersonajeCreateRequest):
    pass

class CartaCreateRequest(BaseModel):
    id: str = Field(..., alias="_id")
    universo_id: str
    categoria: CategoriaCartaEnum
    nombre: str
    descripcion: str
    imagen: str = "/assets/narrative/cartas/default.webp"
    tags: List[str] = []
    efectos: List[EfectoSchema] = []

    model_config = {"populate_by_name": True}

class CartaResponse(CartaCreateRequest):
    pass

class ImpactoAfinidadSchema(BaseModel):
    personaje_id: str
    delta: int

class ResultadoCreateRequest(BaseModel):
    id: str = Field(..., alias="_id")
    universo_id: str
    titulo: str
    texto: str
    imagen: str = "/assets/narrative/resultados/default.webp"
    tipo_resultado: TipoResultadoEnum = TipoResultadoEnum.NEUTRO
    efectos: List[EfectoSchema] = []
    impacto_afinidad: List[ImpactoAfinidadSchema] = []

    model_config = {"populate_by_name": True}

class ResultadoResponse(ResultadoCreateRequest):
    pass

class ModificadorProbabilidadSchema(BaseModel):
    condicion: CondicionSchema
    delta_peso: float
    explicacion: Optional[str] = None

class ResultadoPosibleSchema(BaseModel):
    resultado_id: str
    peso_base: float = 50.0
    modificadores_probabilidad: List[ModificadorProbabilidadSchema] = []

class OpcionEventoSchema(BaseModel):
    id: str
    texto: str
    es_secreta: bool = False
    condiciones: List[CondicionSchema] = []
    resultados_posibles: List[ResultadoPosibleSchema]

class EventoCreateRequest(BaseModel):
    id: str = Field(..., alias="_id")
    universo_id: str
    titulo: str
    descripcion: str
    imagen: str = "/assets/narrative/eventos/default.webp"
    tags_tematicos: List[str] = []
    peso_base: float = 100.0
    opciones: List[OpcionEventoSchema]

    model_config = {"populate_by_name": True}

class EventoResponse(EventoCreateRequest):
    pass

class ConversacionFraseSchema(BaseModel):
    personajeId: str
    texto: str

class ConversacionDecisionSchema(BaseModel):
    opcion: int
    texto: str
    condiciones: List[CondicionSchema] = []
    resultado_texto: str
    impacto_afinidad: List[ImpactoAfinidadSchema] = []

class ConversacionRequisitoSchema(BaseModel):
    personajeId: str

class ConversacionCreateRequest(BaseModel):
    id: str = Field(..., alias="_id")
    universo_id: str
    titulo: str
    requisitos: List[ConversacionRequisitoSchema]
    imagen: str = "/assets/narrative/conversaciones/default.webp"
    frases: List[ConversacionFraseSchema]
    decisiones: List[ConversacionDecisionSchema]

    model_config = {"populate_by_name": True}

class ConversacionResponse(ConversacionCreateRequest):
    pass

class FinalizacionCreateRequest(BaseModel):
    id: str = Field(..., alias="_id", description="Identificador único (ej: fin_corte_oro_cero)")
    universo_id: str
    recurso_clave: Optional[str] = None
    tipo: TipoFinalizacionEnum = TipoFinalizacionEnum.DERROTA_RECURSO
    titulo: str
    texto: str
    imagen: str = "/assets/narrative/finalizaciones/default.webp"
    rango: Optional[str] = "F"

    model_config = {"populate_by_name": True}

class FinalizacionResponse(FinalizacionCreateRequest):
    pass


# ============================================================================
# 4. CONFIGURACIÓN DEL DESAFÍO DIARIO (Extensión a daily_challenges)
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
# 5. ESTADO VIVO DE LA PARTIDA DEL ALUMNO (narrative_runs)
# ============================================================================

class TurnoSnapshot(BaseModel):
    cartas_ofrecidas_ids: List[str] = []
    carta_elegida_id: Optional[str] = None
    evento_actual_id: Optional[str] = None
    opcion_elegida_id: Optional[str] = None
    resultado_obtenido_id: Optional[str] = None
    conversacion_actual_id: Optional[str] = None

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
    status: str = "in_progress" # in_progress | completed
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
# 6. DTOs DE ENTRADA Y SALIDA PARA EL CLIENTE (Web / App)
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

class EstadoPartidaActivaResponse(BaseModel):
    run: NarrativeRunSchema
    universo: UniversoResponse
    personajes_corte: List[PersonajeResponse]
    cartas_inventario: List[CartaResponse]
    cartas_draft_actual: List[CartaResponse] = []
    evento_actual: Optional[EventoTurnoResponse] = None
    resultado_actual: Optional[ResultadoResponse] = None
    conversacion_actual: Optional[ConversacionResponse] = None
    epilogo_final: Optional[Dict[str, Any]] = None
    finalizacion: Optional[FinalizacionResponse] = None

# ============================================================================
# 7. DTOs PARA ENDPOINTS DE CONSULTA ESPECIALIZADOS (BAJO DEMANDA)
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
# 8. DTOs PARA ENDPOINTS HERMANOS V2 (LIGEROS / POR FASE)
# ============================================================================

class IniciarPartidaV2Response(BaseModel):
    mes_actual: int = 1
    fase_actual: str = "DRAFT_MENSUAL"
    recursos: Dict[str, int]
    afinidad: Dict[str, int]
    cartas_draft_actual: List[CartaResponse]

class ElegirCartaMesV2Response(BaseModel):
    fase_actual: str = "TOMA_DECISION_EVENTO"
    recursos: Dict[str, int]
    evento_actual: EventoTurnoResponse

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



