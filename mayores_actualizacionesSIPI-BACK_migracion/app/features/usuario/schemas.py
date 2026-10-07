from pydantic import BaseModel
from typing import Optional, List, Generic, TypeVar
from datetime import datetime, date

T = TypeVar("T")

class UsuarioResponse(BaseModel):
    id: int
    name: str
    email: str
    codigoAcceso: Optional[str] = ""
    tipoUsuario: int = 1
    black: bool = False
    activo: bool = True
    dateStart: Optional[str] = None
    dateEnd: Optional[str] = None

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
