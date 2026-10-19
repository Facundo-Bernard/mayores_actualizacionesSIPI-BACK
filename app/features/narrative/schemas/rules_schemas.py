from pydantic import BaseModel
from typing import Optional, List, Union

from app.features.narrative.enums import (
    DisparadorEnum,
    OperadorEnum,
    TipoCondicionEnum,
    TipoAccionEnum,
    TipoCalculoEnum
)

# ============================================================================
# BLOQUES DEL PATRÓN ECA (Event - Condition - Action)
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
