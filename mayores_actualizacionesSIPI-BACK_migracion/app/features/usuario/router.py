from fastapi import APIRouter, Query
from typing import Optional
from datetime import date
from app.features.usuario.schemas import (
    UsuarioResponse, PaginatedUsuariosResponse,
    EstadoActivoResponse, SuscripcionResponse
)
from app.features.usuario.service import (
    get_usuarios_paginados, get_usuario_by_id,
    toggle_activo, toggle_black
)
from app.features.auth.schemas import RegisterRequest
from app.features.auth.service import register_usuario

router = APIRouter(prefix="/usuario", tags=["Usuarios y Torre de Control"])

@router.get("", response_model=PaginatedUsuariosResponse, summary="Listar usuarios paginados con filtros dinámicos")
async def endpoint_listar_usuarios(
    limit: int = Query(10, ge=1, le=100, description="Cantidad de registros por página"),
    skip: int = Query(0, ge=0, description="Cantidad de registros a saltear (offset)"),
    nombre: Optional[str] = Query(None, description="Búsqueda parcial en nombre o email"),
    fechaDesde: Optional[date] = Query(None, description="Fecha de inicio (YYYY-MM-DD)"),
    fechaHasta: Optional[date] = Query(None, description="Fecha fin (YYYY-MM-DD)"),
    tipoUsuario: Optional[int] = Query(None, description="1: Alumno, 2: Administrador"),
    black: Optional[bool] = Query(None, description="Filtro por suscripción Black"),
    activo: Optional[bool] = Query(None, description="Filtro por cuenta activa/inactiva"),
    orden: str = Query("desc", pattern="^(asc|desc)$", description="Orden por fecha de alta")
):
    return await get_usuarios_paginados(
        limit=limit,
        skip=skip,
        nombre=nombre,
        fecha_desde=fechaDesde,
        fecha_hasta=fechaHasta,
        tipo_usuario=tipoUsuario,
        black=black,
        activo=activo,
        orden=orden
    )

@router.get("/{user_id}", response_model=UsuarioResponse, summary="Obtener usuario por ID")
async def endpoint_obtener_usuario(user_id: int):
    return await get_usuario_by_id(user_id)

@router.put("/{user_id}/toggle-activo", response_model=EstadoActivoResponse, summary="Activar o desactivar cuenta de usuario")
async def endpoint_toggle_activo(user_id: int):
    return await toggle_activo(user_id)

@router.put("/{user_id}/toggle-black", response_model=SuscripcionResponse, summary="Activar o desactivar suscripción Black")
async def endpoint_toggle_black(user_id: int):
    return await toggle_black(user_id)

@router.post("", response_model=UsuarioResponse, summary="Crear un nuevo usuario")
async def endpoint_crear_usuario(req: RegisterRequest):
    return await register_usuario(req)
