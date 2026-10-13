from pydantic import BaseModel
from typing import Optional, List, Generic, TypeVar
from datetime import datetime, date

T = TypeVar("T")

class EstadoUsuarioSchema(BaseModel):
    id: int
    codigo: str
    nombre: str
    descripcion: str
    permite_login: bool = False
    color: str = "slate"
    habilitado: bool = True

class CambiarEstadoUsuarioRequest(BaseModel):
    estado_id: int

class CrearEstadoRequest(BaseModel):
    nombre: str
    codigo: Optional[str] = None
    descripcion: Optional[str] = ""
    color: Optional[str] = "indigo"
    permite_login: Optional[bool] = False

class CambiarEstadoUsuarioResponse(BaseModel):
    success: bool
    message: str
    estado_id: int
    estado_codigo: str
    activo: bool


class UsuarioResponse(BaseModel):
    id: int
    name: str
    email: str
    codigoAcceso: Optional[str] = ""
    tipoUsuario: int = 1
    black: bool = False
    activo: bool = True
    estadoId: int = 2
    estadoCodigo: str = "ACTIVO"
    estado: Optional[EstadoUsuarioSchema] = None
    dateStart: Optional[str] = None
    dateEnd: Optional[str] = None

class ListEstadosResponse(BaseModel):
    success: bool
    estados: List[EstadoUsuarioSchema]

class PaginatedUsuariosResponse(BaseModel):
    total: int
    skip: int
    limit: int
    items: List[UsuarioResponse]

class EstadoActivoResponse(BaseModel):
    success: bool
    message: str
    activo: bool

class SuscripcionResponse(BaseModel):
    success: bool
    message: str
    black: bool
