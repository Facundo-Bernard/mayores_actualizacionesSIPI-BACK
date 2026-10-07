from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Any, Dict
from datetime import datetime, date

class LoginSistemasRequest(BaseModel):
    email: EmailStr
    password: str

class LoginCodigoRequest(BaseModel):
    codigoAcceso: str = Field(..., alias="codigoAcceso")

    class Config:
        populate_by_name = True

class VerificarTokenRequest(BaseModel):
    token: str

class EnviarAccesoCorreoRequest(BaseModel):
    email: EmailStr
    redirectPath: Optional[str] = "/mis-cursos"

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: Optional[str] = None
    codigoAcceso: Optional[str] = None
    tipoUsuario: Optional[int] = 1
    black: Optional[bool] = False
    activo: Optional[bool] = True

class GenericMessageResponse(BaseModel):
    message: str
    success: bool = True
