from fastapi import APIRouter, status, Depends, HTTPException
from typing import List, Dict, Any
from app.core.dependencies import get_current_user
from app.features.progreso.schemas import (
    ProgresoCreateRequest, ProgresoUpdateRequest, ProgresoResponse
)
from app.features.progreso.service import (
    crear_progreso, actualizar_progreso, obtener_progreso_por_usuario
)

router = APIRouter(prefix="/progreso", tags=["Progreso de Cursos"])

@router.post("/crear", response_model=ProgresoResponse, status_code=status.HTTP_201_CREATED, summary="Crear registro de progreso")
async def endpoint_crear_progreso(
    req: ProgresoCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    # RLS / IDOR: Solo el propio alumno o un admin puede registrar progreso
    if current_user.get("tipo_usuario") != 2 and current_user.get("id") != req.usuarioId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes autorización para registrar progreso para otro usuario."
        )
    return await crear_progreso(req)

@router.put("/actualizar/{usuario_id}/{curso_id}", response_model=ProgresoResponse, summary="Actualizar progreso de un curso (con Upsert)")
async def endpoint_actualizar_progreso(
    usuario_id: int,
    curso_id: int,
    req: ProgresoUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    # RLS / IDOR: Solo el propio alumno o un admin puede modificar el progreso
    if current_user.get("tipo_usuario") != 2 and current_user.get("id") != usuario_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes autorización para actualizar el progreso de otro usuario."
        )
    return await actualizar_progreso(usuario_id, curso_id, req)

@router.get("/obtenerUsuario/{usuario_id}", response_model=List[ProgresoResponse], summary="Obtener todos los cursos y progresos de un usuario")
async def endpoint_obtener_progreso_usuario(
    usuario_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    # RLS / IDOR: Solo el propio alumno o un admin puede consultar el progreso
    if current_user.get("tipo_usuario") != 2 and current_user.get("id") != usuario_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes autorización para consultar el progreso de otro usuario."
        )
    return await obtener_progreso_por_usuario(usuario_id)
