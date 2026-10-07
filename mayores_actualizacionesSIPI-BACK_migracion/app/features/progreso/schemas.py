from pydantic import BaseModel, Field
from typing import Optional

class ProgresoCreateRequest(BaseModel):
    usuarioId: int = Field(..., alias="usuarioId")
    cursoId: int = Field(..., alias="cursoId")
    progreso: int = 0
    completado: bool = False
    examenPuntos: int = Field(0, alias="examenPuntos")

    class Config:
        populate_by_name = True

class ProgresoUpdateRequest(BaseModel):
    progreso: int = 0
    completado: bool = False
    examenPuntos: int = Field(0, alias="examenPuntos")

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
