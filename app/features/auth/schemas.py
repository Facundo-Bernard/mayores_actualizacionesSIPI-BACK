from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Optional, Any, Dict


class LoginSistemasRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class LoginCodigoRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    codigo: Optional[str] = Field(None, min_length=4, max_length=10)
    codigoAcceso: Optional[str] = Field(None, alias="codigoAcceso", min_length=4, max_length=10)

    def get_codigo(self) -> str:
        return (self.codigo or self.codigoAcceso or "").strip()


class VerificarTokenRequest(BaseModel):
    token: str = Field(..., min_length=10)


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: Optional[str] = Field(None, max_length=128)
    codigoAcceso: Optional[str] = None
    tipoUsuario: Optional[int] = 1
    black: Optional[bool] = False
    activo: Optional[bool] = None


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
