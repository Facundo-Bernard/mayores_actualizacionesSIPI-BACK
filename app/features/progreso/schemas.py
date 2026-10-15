from pydantic import BaseModel, Field
from typing import Optional

class ProgresoCreateRequest(BaseModel):
    usuarioId: int = Field(..., alias="usuarioId", ge=1)
    cursoId: int = Field(..., alias="cursoId", ge=1)
    progreso: int = Field(0, ge=0, le=100)
    completado: bool = False
    examenPuntos: int = Field(0, alias="examenPuntos", ge=0, le=1000)

    class Config:
        populate_by_name = True

class ProgresoUpdateRequest(BaseModel):
    progreso: int = Field(0, ge=0, le=100)
    completado: bool = False
    examenPuntos: int = Field(0, alias="examenPuntos", ge=0, le=1000)

    class Config:
        populate_by_name = True

class ProgresoResponse(BaseModel):
    id: Optional[int] = None
    progreso: int
    completado: bool
    examenPuntos: int
    cursoId: int
    usuarioId: int

    class Config:
        populate_by_name = True
