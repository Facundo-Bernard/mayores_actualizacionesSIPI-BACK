from fastapi import APIRouter, Query, Depends, HTTPException, status
from typing import Optional, Dict, Any
from datetime import date
from app.core.dependencies import get_current_admin, get_current_user
from app.features.usuario.schemas import (
    UsuarioResponse, PaginatedUsuariosResponse,
    EstadoActivoResponse, SuscripcionResponse,
    ListEstadosResponse, EstadoUsuarioSchema,
    CambiarEstadoUsuarioRequest, CambiarEstadoUsuarioResponse,
    CrearEstadoRequest
)
from app.features.usuario.service import (
    get_usuarios_paginados, get_usuario_by_id,
    toggle_activo, toggle_black, get_estados_usuario,
    cambiar_estado_usuario, crear_estado_usuario,
    toggle_habilitado_estado
)
from app.features.auth.schemas import RegisterRequest
from app.features.auth.service import register_usuario

router = APIRouter(prefix="/usuario", tags=["Usuarios y Torre de Control"])

@router.get("", response_model=PaginatedUsuariosResponse, summary="Listar usuarios paginados con filtros dinámicos (Solo Admin)")
async def endpoint_listar_usuarios(
    limit: int = Query(10, ge=1, le=100, description="Cantidad de registros por página"),
    skip: int = Query(0, ge=0, description="Cantidad de registros a saltear (offset)"),
    nombre: Optional[str] = Query(None, description="Búsqueda parcial en nombre o email"),
    fechaDesde: Optional[date] = Query(None, description="Fecha de inicio (YYYY-MM-DD)"),
    fechaHasta: Optional[date] = Query(None, description="Fecha fin (YYYY-MM-DD)"),
    tipoUsuario: Optional[int] = Query(None, description="1: Alumno, 2: Administrador"),
    black: Optional[bool] = Query(None, description="Filtro por suscripción Black"),
    activo: Optional[bool] = Query(None, description="Filtro por cuenta activa/inactiva"),
    orden: str = Query("desc", pattern="^(asc|desc)$", description="Orden por fecha de alta"),
    admin: Dict[str, Any] = Depends(get_current_admin)
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

@router.get("/estados", response_model=ListEstadosResponse, summary="Listar catálogo de estados de usuario")
async def endpoint_listar_estados(soloHabilitados: bool = Query(False, description="Filtrar solo los estados habilitados")):
    return await get_estados_usuario(solo_habilitados=soloHabilitados)

@router.post("/estados", summary="Crear un nuevo estado en el catálogo (Solo Admin)")
async def endpoint_crear_estado(
    req: CrearEstadoRequest,
    admin: Dict[str, Any] = Depends(get_current_admin)
):
    return await crear_estado_usuario(
        nombre=req.nombre,
        codigo=req.codigo,
        descripcion=req.descripcion,
        color=req.color,
        permite_login=req.permite_login or False
    )

@router.put("/estados/{estado_id}/toggle-habilitado", summary="Habilitar o inhabilitar un estado del catálogo (Solo Admin)")
async def endpoint_toggle_habilitado_estado(
    estado_id: int,
    admin: Dict[str, Any] = Depends(get_current_admin)
):
    return await toggle_habilitado_estado(estado_id)

@router.put("/{user_id}/cambiar-estado", response_model=CambiarEstadoUsuarioResponse, summary="Cambiar estado del usuario en el catálogo (Solo Admin)")
async def endpoint_cambiar_estado_usuario(
    user_id: int,
    req: CambiarEstadoUsuarioRequest,
    admin: Dict[str, Any] = Depends(get_current_admin)
):
    return await cambiar_estado_usuario(user_id, req.estado_id)

@router.get("/{user_id}", response_model=UsuarioResponse, summary="Obtener usuario por ID")
async def endpoint_obtener_usuario(
    user_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    # Solo el propio usuario o un administrador puede ver el perfil
    if current_user.get("tipo_usuario") != 2 and current_user.get("id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para consultar la información de este usuario."
        )
    return await get_usuario_by_id(user_id)

@router.put("/{user_id}/toggle-activo", response_model=EstadoActivoResponse, summary="Activar o desactivar cuenta de usuario (Solo Admin)")
async def endpoint_toggle_activo(
    user_id: int,
    admin: Dict[str, Any] = Depends(get_current_admin)
):
    return await toggle_activo(user_id)

@router.put("/{user_id}/toggle-black", response_model=SuscripcionResponse, summary="Activar o desactivar suscripción Black (Solo Admin)")
@router.put("/{user_id}/suscribirse", response_model=SuscripcionResponse, summary="Alias para alternar suscripción Black (Solo Admin)")
async def endpoint_toggle_black(
    user_id: int,
    admin: Dict[str, Any] = Depends(get_current_admin)
):
    return await toggle_black(user_id)

@router.post("", response_model=UsuarioResponse, summary="Crear un nuevo usuario desde la torre de control (Solo Admin)")
async def endpoint_crear_usuario(
    req: RegisterRequest,
    admin: Dict[str, Any] = Depends(get_current_admin)
):
    res = await register_usuario(req, is_admin_creation=True)
    if isinstance(res, dict) and "user" in res:
        return res["user"]
    return res

from app.core.database import get_database
from app.core.security import create_access_token
from app.core.config import settings

@router.post("/{user_id}/magic-link", summary="Generar enlace de acceso directo para un alumno (Solo Admin)")
async def endpoint_generar_magic_link(
    user_id: int,
    admin: Dict[str, Any] = Depends(get_current_admin)
):
    db = get_database()
    user = await db["usuarios"].find_one({"id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con ID {user_id} no encontrado"
        )

    token = create_access_token(user)
    base_url = settings.FRONTEND_URL.rstrip("/")
    access_url = f"{base_url}/acceso?token={token}"

    return {
        "success": True,
        "token": token,
        "accessUrl": access_url,
        "codigoAcceso": user.get("codigo_acceso"),
        "activo": bool(user.get("activo", True)),
        "message": "Enlace de acceso generado exitosamente."
    }
