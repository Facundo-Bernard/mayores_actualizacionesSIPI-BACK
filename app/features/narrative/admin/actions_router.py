from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Query, Path

from app.features.narrative.schemas.rules_schemas import (
    AccionCatalogoCreateRequest,
    AccionCatalogoUpdateRequest,
    AccionCatalogoResponse,
    FrecuenciasUniversoDocument,
    FrecuenciasUniversoUpdateRequest,
)
from app.features.narrative.admin.actions_crud_service import (
    CATALOGO_PRIMITIVAS,
    EVENTOS_MOTOR,
    crear_accion,
    listar_acciones,
    obtener_accion_por_id,
    actualizar_accion,
    eliminar_accion,
    obtener_usos_accion,
    obtener_frecuencias_universo,
    actualizar_frecuencias_universo,
    obtener_usos_frecuencia,
)

actions_admin_router = APIRouter(tags=["Narrativo - Administración"])


@actions_admin_router.get("/operaciones", response_model=List[Dict[str, Any]])
async def get_operaciones_motor():
    """Catálogo canónico de operaciones/primitivas ejecutables por el motor."""
    return CATALOGO_PRIMITIVAS


@actions_admin_router.get("/eventos-motor", response_model=List[Dict[str, Any]])
async def get_eventos_motor():
    """Eventos del ciclo de vida del motor donde se pueden despachar efectos."""
    return EVENTOS_MOTOR


@actions_admin_router.get("/acciones", response_model=List[AccionCatalogoResponse])
async def get_acciones(
    universo_id: Optional[str] = Query(None, description="Filtrar por universo")
):
    """Lista las acciones registradas en el catálogo."""
    return await listar_acciones(universo_id=universo_id)


@actions_admin_router.post("/acciones", response_model=AccionCatalogoResponse, status_code=201)
async def post_accion(payload: AccionCatalogoCreateRequest):
    """Crea una nueva acción en el catálogo de un universo."""
    return await crear_accion(payload)


@actions_admin_router.get("/acciones/{accion_id}", response_model=AccionCatalogoResponse)
async def get_accion(
    accion_id: str = Path(..., description="ID de la acción"),
    universo_id: Optional[str] = Query(None, description="Universo opcional"),
):
    """Obtiene el detalle de una acción de catálogo."""
    return await obtener_accion_por_id(accion_id, universo_id)


@actions_admin_router.put("/acciones/{accion_id}", response_model=AccionCatalogoResponse)
async def put_accion(
    payload: AccionCatalogoUpdateRequest,
    accion_id: str = Path(..., description="ID de la acción"),
    universo_id: Optional[str] = Query(None, description="Universo opcional"),
):
    """Actualiza una acción existente con control de concurrencia optimista."""
    return await actualizar_accion(accion_id, payload, universo_id)


@actions_admin_router.delete("/acciones/{accion_id}")
async def delete_accion(
    accion_id: str = Path(..., description="ID de la acción"),
    universo_id: Optional[str] = Query(None, description="Universo opcional"),
):
    """Elimina una acción si no está siendo utilizada por cartas o personajes."""
    return await eliminar_accion(accion_id, universo_id)


@actions_admin_router.get("/acciones/{accion_id}/usos")
async def get_usos_accion(accion_id: str = Path(..., description="ID de la acción")):
    """Reporta qué cartas y personajes hacen referencia a esta acción."""
    return await obtener_usos_accion(accion_id)


@actions_admin_router.get("/frecuencias", response_model=FrecuenciasUniversoDocument)
async def get_frecuencias(
    universo_id: str = Query("corte_medieval", description="ID del universo")
):
    """Obtiene el documento de frecuencias configurado para el universo."""
    return await obtener_frecuencias_universo(universo_id)


@actions_admin_router.put("/frecuencias/{universo_id}", response_model=FrecuenciasUniversoDocument)
async def put_frecuencias(
    payload: FrecuenciasUniversoUpdateRequest,
    universo_id: str = Path(..., description="ID del universo"),
):
    """Actualiza el catálogo de frecuencias del universo con OCC."""
    return await actualizar_frecuencias_universo(universo_id, payload)


@actions_admin_router.get("/frecuencias/{frecuencia_id}/usos")
async def get_usos_frecuencia(
    frecuencia_id: str = Path(..., description="ID de la frecuencia"),
    universo_id: Optional[str] = Query(None, description="Universo opcional"),
):
    """Reporta qué cartas y personajes hacen referencia a esta frecuencia."""
    return await obtener_usos_frecuencia(frecuencia_id, universo_id)
