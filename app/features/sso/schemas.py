from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class CanjearTicketRequest(BaseModel):
    ticket: str = Field(..., description="Ticket SSO efímero descartable entregado por el Autenticador")


class CanjearTicketResponse(BaseModel):
    success: bool
    message: str
    token: str
    user: Dict[str, Any]


class CrearTicketRetornoRequest(BaseModel):
    servicioDestino: Optional[str] = Field("autenticador", description="Servicio o panel al que desea retornar el administrador")


class CrearTicketRetornoResponse(BaseModel):
    success: bool
    ticket: str
    expiresInSeconds: int = 30
    servicio: str
