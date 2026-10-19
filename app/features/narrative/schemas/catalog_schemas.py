from pydantic import BaseModel, Field
from typing import Optional, List

from app.features.narrative.enums import (
    CategoriaCartaEnum,
    TipoResultadoEnum,
    TipoFinalizacionEnum
)
from app.features.narrative.schemas.rules_schemas import (
    CondicionSchema,
    EfectoSchema
)

# ============================================================================
# 1. UNIVERSOS Y RECURSOS (narrative_settings)
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
# 2. PERSONAJES DE LA CORTE (narrative_characters)
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

# ============================================================================
# 3. CARTAS DE APOYO E INVENTARIO (narrative_cards)
# ============================================================================

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

# ============================================================================
# 4. RESULTADOS Y DESENLACES (narrative_results)
# ============================================================================

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

# ============================================================================
# 5. EVENTOS MENSUALES (narrative_events)
# ============================================================================

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

# ============================================================================
# 6. CONVERSACIONES DE CORTE (narrative_conversations)
# ============================================================================

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

# ============================================================================
# 7. FINALIZACIONES Y DERROTAS (narrative_endings)
# ============================================================================

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
