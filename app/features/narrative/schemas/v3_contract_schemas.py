from datetime import date
from enum import Enum
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.features.narrative.enums import CategoriaCartaEnum, TipoFinalizacionEnum, TipoResultadoEnum
from app.features.narrative.schemas.catalog_schemas import RecursoDefinicionSchema
from app.features.narrative.schemas.rules_schemas import EfectoSchema
from app.features.narrative.schemas.v2_graph_schemas import NodoClienteSchema

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
Revision = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]


class V3Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    GAME_OVER = "game_over"


class RunPhaseV3(str, Enum):
    DRAFT_MENSUAL = "DRAFT_MENSUAL"
    TOMA_DECISION_EVENTO = "TOMA_DECISION_EVENTO"
    RESOLVER_CONVERSACION = "RESOLVER_CONVERSACION"
    BALANCE_MES = "BALANCE_MES"
    FINALIZADA = "FINALIZADA"


class CommandType(str, Enum):
    INICIAR_PARTIDA = "INICIAR_PARTIDA"
    ELEGIR_CARTA_MENSUAL = "ELEGIR_CARTA_MENSUAL"
    AVANZAR_NODO = "AVANZAR_NODO"
    CONTINUAR_RESULTADO = "CONTINUAR_RESULTADO"
    AVANZAR_MES = "AVANZAR_MES"
    REINICIAR_PARTIDA = "REINICIAR_PARTIDA"


class RunCommandType(str, Enum):
    ELEGIR_CARTA_MENSUAL = "ELEGIR_CARTA_MENSUAL"
    AVANZAR_NODO = "AVANZAR_NODO"
    CONTINUAR_RESULTADO = "CONTINUAR_RESULTADO"
    AVANZAR_MES = "AVANZAR_MES"
    REINICIAR_PARTIDA = "REINICIAR_PARTIDA"


class ErrorCode(str, Enum):
    VALIDATION_ERROR = "validation_error"
    UNAUTHENTICATED = "unauthenticated"
    FORBIDDEN = "forbidden"
    RUN_NOT_FOUND = "run_not_found"
    RUN_ALREADY_EXISTS = "run_already_exists"
    RECEIPT_NOT_FOUND = "receipt_not_found"
    VERSION_CONFLICT = "version_conflict"
    GENERATION_CONFLICT = "generation_conflict"
    COMMAND_REUSED = "command_reused"
    PHASE_CONFLICT = "phase_conflict"
    CONTENT_UNAVAILABLE = "content_unavailable"
    COMMAND_OUTCOME_UNKNOWN = "command_outcome_unknown"


class ErrorDetails(V3Model):
    commandId: Optional[Identifier] = None
    currentVersion: Optional[int] = Field(default=None, ge=0)
    currentGeneration: Optional[int] = Field(default=None, ge=1)


class ErrorResponse(V3Model):
    code: ErrorCode
    message: str = Field(min_length=1)
    retryable: bool = False
    details: Optional[ErrorDetails] = None


class PersonajeJugador(V3Model):
    id: Identifier
    nombre: str
    titulo: str
    imagen: Optional[str] = None
    descripcion: str
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    efectos: list[EfectoSchema] = Field(default_factory=list)


class CartaJugador(V3Model):
    id: Identifier
    categoria: CategoriaCartaEnum
    nombre: str
    descripcion: str
    imagen: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    efectos: list[EfectoSchema] = Field(default_factory=list)


class CartaEnInventario(V3Model):
    instanceId: Identifier
    carta: CartaJugador


class RecursoJugador(V3Model):
    definicion: RecursoDefinicionSchema
    valor: int


class FinalizacionJugador(V3Model):
    id: Identifier
    tipo: TipoFinalizacionEnum
    titulo: str
    texto: str
    imagen: Optional[str] = None
    rango: Optional[str] = None
    recurso_clave: Optional[str] = None


class ContenidoDraft(V3Model):
    tipo: Literal["draft"] = "draft"
    cartasOfrecidas: list[CartaJugador]


class ContenidoNodoV2(V3Model):
    tipo: Literal["nodo_v2"] = "nodo_v2"
    grafoId: Identifier
    tipoGrafo: Literal["evento", "conversacion", "evento_especial"]
    titulo: str
    imagen: Optional[str] = None
    nodoActual: NodoClienteSchema


class ContenidoFinal(V3Model):
    tipo: Literal["final"] = "final"
    finalizacion: FinalizacionJugador


ContenidoActual = Annotated[
    Union[ContenidoDraft, ContenidoNodoV2, ContenidoFinal],
    Field(discriminator="tipo"),
]


class OrigenConsecuencia(V3Model):
    tipo: Literal["carta", "personaje", "nodo", "sistema"]
    origenId: Identifier
    instanceId: Optional[Identifier] = None
    grafoId: Optional[Identifier] = None
    nodoId: Optional[Identifier] = None


class ConsecuenciaBase(V3Model):
    consecuenciaId: Identifier
    origen: OrigenConsecuencia


class ConsecuenciaNumerica(ConsecuenciaBase):
    tipo: Literal["recurso", "afinidad"]
    atributo: Identifier
    antes: int
    deltaSolicitado: int
    deltaAplicado: int
    despues: int

    @model_validator(mode="after")
    def validar_aritmetica(self):
        if self.antes + self.deltaAplicado != self.despues:
            raise ValueError("despues debe ser antes + deltaAplicado")
        return self


class ConsecuenciaTag(ConsecuenciaBase):
    tipo: Literal["tag"]
    tag: str = Field(min_length=1)
    operacion: Literal["otorgar"] = "otorgar"
    presenteAntes: bool
    presenteDespues: bool


class ConsecuenciaInventario(ConsecuenciaBase):
    tipo: Literal["inventario"]
    cartaId: Identifier
    instanceId: Identifier
    operacion: Literal["adquirir"] = "adquirir"
    cantidadAntes: int = Field(ge=0)
    cantidadDespues: int = Field(ge=0)


Consecuencia = Annotated[
    Union[ConsecuenciaNumerica, ConsecuenciaTag, ConsecuenciaInventario],
    Field(discriminator="tipo"),
]


class LiquidacionEconomica(V3Model):
    estado: Literal["pendiente", "liquidada", "fallida"]


class RecompensaRecuperable(V3Model):
    rewardId: Identifier
    puntos: int = Field(ge=0)
    canal: Literal["ledger", "local"]
    liquidacion: Optional[LiquidacionEconomica] = Field(
        default=None,
        description="Estado del ledger para cuentas; null para economía local de invitados.",
    )

    @model_validator(mode="after")
    def validar_canal(self):
        if self.canal == "ledger" and self.liquidacion is None:
            raise ValueError("Una recompensa por ledger exige estado de liquidación")
        if self.canal == "local" and self.liquidacion is not None:
            raise ValueError("La economía local no tiene liquidación de servidor")
        return self


class ResultadoNarrativo(V3Model):
    resultadoId: Identifier
    alcance: Literal["escena", "final"]
    titulo: Optional[str] = None
    texto: str = Field(min_length=1)
    imagen: Optional[str] = None
    tipoResultado: TipoResultadoEnum = TipoResultadoEnum.NEUTRO
    grafoId: Optional[Identifier] = None
    nodoId: Optional[Identifier] = None
    finalizacionId: Optional[Identifier] = None


class ResultadoPendiente(ResultadoNarrativo):
    consecuencias: list[Consecuencia] = Field(default_factory=list)
    recompensa: Optional[RecompensaRecuperable] = None


class ContinuacionPendiente(V3Model):
    resultadoId: Identifier


class EscenaHistorial(V3Model):
    tipo: Literal["evento", "conversacion", "evento_especial"]
    grafoId: Identifier
    opcionesElegidasIds: list[Identifier] = Field(default_factory=list)
    resultadoId: Optional[Identifier] = None


class HistorialMensualV3(V3Model):
    mes: int = Field(ge=1, le=12)
    cartaElegidaId: Optional[Identifier] = None
    recursosFinMes: dict[str, int]
    escenas: list[EscenaHistorial] = Field(default_factory=list)


class SnapshotRunV3(V3Model):
    runId: Identifier
    generation: int = Field(ge=1)
    schemaVersion: int = Field(ge=1)
    rulesVersion: Revision
    contentVersion: Revision
    version: int = Field(ge=0)
    motor: Literal["v2"] = "v2"
    date: date
    mesActual: int = Field(ge=1, le=12)
    faseActual: RunPhaseV3
    status: RunStatus
    gamePolicyVersion: Revision
    ageAdaptation: Literal["none"] = "none"
    corte: list[PersonajeJugador]
    afinidad: dict[str, int]
    inventario: list[CartaEnInventario]
    tagsActivos: list[str]
    recursos: list[RecursoJugador]
    contenidoActual: Optional[ContenidoActual] = None
    comandosPermitidos: list[RunCommandType] = Field(default_factory=list)
    resultadoPendiente: Optional[ResultadoPendiente] = None
    continuacionPendiente: Optional[ContinuacionPendiente] = None
    historialMensual: list[HistorialMensualV3] = Field(default_factory=list)

    @field_validator("inventario")
    @classmethod
    def validar_instancias_unicas(cls, value: list[CartaEnInventario]) -> list[CartaEnInventario]:
        instance_ids = [item.instanceId for item in value]
        if len(set(instance_ids)) != len(instance_ids):
            raise ValueError("instanceId debe ser único dentro del inventario")
        return value

    @model_validator(mode="after")
    def validar_continuacion(self):
        if (self.resultadoPendiente is None) != (self.continuacionPendiente is None):
            raise ValueError("resultadoPendiente y continuacionPendiente deben coexistir")
        if self.resultadoPendiente is not None:
            if self.continuacionPendiente.resultadoId != self.resultadoPendiente.resultadoId:
                raise ValueError("La continuación debe referenciar el resultado pendiente")
            if RunCommandType.CONTINUAR_RESULTADO not in self.comandosPermitidos:
                raise ValueError("Un resultado pendiente exige CONTINUAR_RESULTADO")
        elif RunCommandType.CONTINUAR_RESULTADO in self.comandosPermitidos:
            raise ValueError("CONTINUAR_RESULTADO requiere un resultado pendiente")
        return self


class IniciarPartidaPayload(V3Model):
    corteElegidaIds: list[Identifier] = Field(min_length=3, max_length=3)
    cartasInicialesIds: list[Identifier] = Field(min_length=3, max_length=3)

    @field_validator("corteElegidaIds", "cartasInicialesIds")
    @classmethod
    def rechazar_duplicados_iniciales(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("Las selecciones iniciales no admiten duplicados")
        return value


class IniciarPartidaCommand(V3Model):
    commandId: Identifier
    date: date
    type: Literal[CommandType.INICIAR_PARTIDA]
    payload: IniciarPartidaPayload


class ElegirCartaMensualPayload(V3Model):
    cartaId: Identifier


class AvanzarNodoPayload(V3Model):
    opcionId: Identifier


class ContinuarResultadoPayload(V3Model):
    resultadoId: Identifier


class PayloadVacio(V3Model):
    pass


class RunCommandBase(V3Model):
    commandId: Identifier
    generation: int = Field(ge=1)
    expectedVersion: int = Field(ge=0)


class ElegirCartaMensualCommand(RunCommandBase):
    type: Literal[CommandType.ELEGIR_CARTA_MENSUAL]
    payload: ElegirCartaMensualPayload


class AvanzarNodoCommand(RunCommandBase):
    type: Literal[CommandType.AVANZAR_NODO]
    payload: AvanzarNodoPayload


class ContinuarResultadoCommand(RunCommandBase):
    type: Literal[CommandType.CONTINUAR_RESULTADO]
    payload: ContinuarResultadoPayload


class AvanzarMesCommand(RunCommandBase):
    type: Literal[CommandType.AVANZAR_MES]
    payload: PayloadVacio


class ReiniciarPartidaCommand(RunCommandBase):
    type: Literal[CommandType.REINICIAR_PARTIDA]
    payload: PayloadVacio


RunCommand = Annotated[
    Union[
        ElegirCartaMensualCommand,
        AvanzarNodoCommand,
        ContinuarResultadoCommand,
        AvanzarMesCommand,
        ReiniciarPartidaCommand,
    ],
    Field(discriminator="type"),
]


class ReciboComandoV3(V3Model):
    runId: Identifier = Field(description="Run destino del comando; en reinicio es la generación anterior.")
    generation: int = Field(ge=1, description="Generación destino del comando.")
    commandId: Identifier
    type: CommandType
    commandHash: str = Field(
        min_length=1,
        description="Hash del servidor sobre tipo, payload y expectedVersion; en creación incluye date.",
    )
    previousVersion: Optional[int] = Field(default=None, ge=0)
    version: int = Field(ge=0)
    snapshot: SnapshotRunV3
    consecuencias: list[Consecuencia] = Field(default_factory=list)
    resultado: Optional[ResultadoNarrativo] = None
    recompensa: Optional[RecompensaRecuperable] = None
