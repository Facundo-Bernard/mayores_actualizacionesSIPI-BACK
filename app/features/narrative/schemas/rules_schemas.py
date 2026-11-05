from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Union, Dict, Any
from enum import Enum

from app.features.narrative.enums import (
    DisparadorEnum,
    OperadorEnum,
    TipoCondicionEnum,
    TipoAccionEnum,
    TipoCalculoEnum,
    OperacionMatematicaEnum
)

# ============================================================================
# BLOQUES DEL PATRÓN ECA (Event - Condition - Action) Y DESACOPLE V2
# ============================================================================

class PrimitivaOperacionEnum(str, Enum):
    MODIFICAR_RECURSO = "modificar_recurso"
    MODIFICAR_AFINIDAD = "modificar_afinidad"
    OTORGAR_TAG = "otorgar_tag"
    REMOVER_TAG = "remover_tag"
    AMORTIGUAR_DANIO = "amortiguar_danio"
    MUTAR_ESTADO = "mutar_estado"

class DestinoAfinidadEnum(str, Enum):
    PORTADOR = "portador"
    PERSONAJE = "personaje"

class PermitidoEnEnum(str, Enum):
    CARTA = "carta"
    PERSONAJE = "personaje"
    AMBOS = "ambos"

class CondicionSchema(BaseModel):
    tipo: TipoCondicionEnum
    clave: Optional[str] = None          # Nombre del recurso (ej: "oro", "pueblo")
    operador: Optional[OperadorEnum] = None # ">=", "<=", "==", etc.
    valor: Optional[Union[int, float, str]] = None
    personaje_id: Optional[str] = None
    carta_id: Optional[str] = None
    tag: Optional[str] = None

class AccionSchema(BaseModel):
    """Schema legacy de acción embebida directa."""
    tipo: TipoAccionEnum
    clave: Optional[str] = None          # Recurso a modificar o proteger
    tipo_calculo: Optional[TipoCalculoEnum] = TipoCalculoEnum.FIJO
    valor: Optional[float] = 0.0
    personaje_id: Optional[str] = None   # Para modificar_afinidad
    tag: Optional[str] = None            # Para otorgar_tag

class ParametrosAccionSchema(BaseModel):
    clave: Optional[str] = None
    ruta: Optional[str] = None
    operacion_matematica: Optional[OperacionMatematicaEnum] = OperacionMatematicaEnum.SUMAR
    valor: Optional[float] = 0.0
    tipo_calculo: Optional[TipoCalculoEnum] = TipoCalculoEnum.FIJO
    destino: Optional[str] = "portador"   # "portador" | "personaje"
    personaje_id: Optional[str] = None
    tag: Optional[str] = None
    porcentaje: Optional[float] = None

class AccionReferenciadaSchema(BaseModel):
    accion_id: str
    parametros: ParametrosAccionSchema = Field(default_factory=ParametrosAccionSchema)

class AccionCatalogoCreateRequest(BaseModel):
    id: str = Field(..., alias="_id", description="Identificador único de la acción en el universo")
    universo_id: str = Field(..., description="ID del universo al que pertenece")
    nombre: str = Field(..., description="Nombre amigable para el catálogo")
    descripcion: Optional[str] = Field("", description="Descripción detallada")
    primitiva: PrimitivaOperacionEnum = Field(..., description="Primitiva del motor que ejecuta la mutación")
    permitido_en: List[str] = Field(default_factory=lambda: ["carta", "personaje"], description="['carta', 'personaje']")
    activo: bool = Field(True, description="Si está disponible para seleccionar")
    version: int = Field(1, description="Versión para control de concurrencia OCC")

    model_config = {"populate_by_name": True}

class AccionCatalogoUpdateRequest(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    primitiva: Optional[PrimitivaOperacionEnum] = None
    permitido_en: Optional[List[str]] = None
    activo: Optional[bool] = None
    expected_version: Optional[int] = None

class AccionCatalogoResponse(BaseModel):
    id: str = Field(..., alias="_id")
    universo_id: str
    nombre: str
    descripcion: str = ""
    primitiva: PrimitivaOperacionEnum
    permitido_en: List[str] = ["carta", "personaje"]
    activo: bool = True
    version: int = 1
    updated_at: Optional[str] = None

    model_config = {"populate_by_name": True}

class ItemFrecuenciaSchema(BaseModel):
    id: str = Field(..., description="Identificador de la frecuencia ej: 'al_obtener', 'cada_2_meses'")
    nombre: str = Field(..., description="Nombre legible ej: 'Cada 2 meses'")
    evento_motor: str = Field(..., description="'al_obtener' | 'inicio_mes'")
    cada: int = Field(1, ge=1, le=12, description="Intervalo de meses (solo si evento_motor='inicio_mes')")
    desfase: int = Field(0, ge=0, description="Desfase de meses antes del primer disparo")
    conteo_desde: str = Field("adquisicion", description="'adquisicion' | 'inicio_partida'")
    activo: bool = Field(True, description="Si está activa")

class FrecuenciasUniversoDocument(BaseModel):
    id: str = Field(..., alias="_id")
    universo_id: str
    version: int = 1
    items: List[ItemFrecuenciaSchema] = Field(default_factory=list)
    updated_at: Optional[str] = None

    model_config = {"populate_by_name": True}

class FrecuenciasUniversoUpdateRequest(BaseModel):
    items: List[ItemFrecuenciaSchema]
    expected_version: Optional[int] = None

class EfectoSchema(BaseModel):
    id: Optional[str] = None
    frecuencia_id: Optional[str] = None
    disparador: Optional[DisparadorEnum] = None  # Compatibilidad legacy
    condiciones: List[CondicionSchema] = []
    acciones: List[AccionReferenciadaSchema] = []
    accion: Optional[AccionSchema] = None        # Compatibilidad legacy

    @model_validator(mode="after")
    def normalizar_compatibilidad(self) -> "EfectoSchema":
        if self.frecuencia_id is None and self.disparador is not None:
            self.frecuencia_id = self.disparador.value
        elif self.disparador is None and self.frecuencia_id is not None:
            try:
                self.disparador = DisparadorEnum(self.frecuencia_id)
            except ValueError:
                pass
        
        if not self.acciones and self.accion is not None:
            self.acciones = [
                AccionReferenciadaSchema(
                    accion_id=self.accion.tipo.value,
                    parametros=ParametrosAccionSchema(
                        clave=self.accion.clave,
                        valor=self.accion.valor,
                        tipo_calculo=self.accion.tipo_calculo,
                        personaje_id=self.accion.personaje_id,
                        tag=self.accion.tag,
                    )
                )
            ]
        return self
