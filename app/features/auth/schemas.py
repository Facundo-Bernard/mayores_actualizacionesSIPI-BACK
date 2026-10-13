from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Any, Dict

class LoginSistemasRequest(BaseModel):
    email: EmailStr
    password: str

class LoginCodigoRequest(BaseModel):
    codigo: Optional[str] = None
    codigoAcceso: Optional[str] = Field(None, alias="codigoAcceso")

    class Config:
        populate_by_name = True

    def get_codigo(self) -> str:
        return (self.codigo or self.codigoAcceso or "").strip()

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
    activo: Optional[bool] = None

class VerificarCodigoRegistroRequest(BaseModel):
    email: EmailStr
    codigo: str

class ReenviarCodigoRequest(BaseModel):
    email: EmailStr

class ModificarEmailRegistroRequest(BaseModel):
    email_actual: EmailStr
    email_nuevo: EmailStr

class LoginSistemasResponse(BaseModel):
    success: bool = True
    message: str = "Inicio de sesión exitoso"
    token: str
    user: Dict[str, Any]

class RegistroResponse(BaseModel):
    success: bool = True
    message: str = "Acceso concedido exitosamente."
    token: str
    user: Dict[str, Any]

class TokenVerifyResponse(BaseModel):
    success: bool = True
    valid: bool = True
    user: Optional[Dict[str, Any]] = None
    message: str = "Token verificado con éxito"

class GenericMessageResponse(BaseModel):
    message: str
    success: bool = True
