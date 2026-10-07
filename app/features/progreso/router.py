from fastapi import APIRouter, status
from typing import List
from app.features.progreso.schemas import (
    ProgresoCreateRequest, ProgresoUpdateRequest, ProgresoResponse
)
from app.features.progreso.service import (
    crear_progreso, actualizar_progreso, obtener_progreso_por_usuario
)

router = APIRouter(prefix="/progreso", tags=["Progreso de Cursos"])

@router.post("/crear", response_model=ProgresoResponse, status_code=status.HTTP_201_CREATED, summary="Crear registro de progreso")
async def endpoint_crear_progreso(req: ProgresoCreateRequest):
    return await crear_progreso(req)

@router.put("/actualizar/{usuario_id}/{curso_id}", response_model=ProgresoResponse, summary="Actualizar progreso de un curso (con Upsert)")
async def endpoint_actualizar_progreso(usuario_id: int, curso_id: int, req: ProgresoUpdateRequest):
    return await actualizar_progreso(usuario_id, curso_id, req)

@router.get("/obtenerUsuario/{usuario_id}", response_model=List[ProgresoResponse], summary="Obtener todos los cursos y progresos de un usuario")
async def endpoint_obtener_progreso_usuario(usuario_id: int):
    return await obtener_progreso_por_usuario(usuario_id)
