"""Endpoints administrativos del diseñador de máscaras de crucigrama."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.concurrency import run_in_threadpool

from app.core.dependencies import get_current_admin
from app.features.daily_challenges.crucigrama.bans import get_global_banned_words
from app.features.daily_challenges.crucigrama_admin import service
from app.features.daily_challenges.crucigrama_admin.schemas import (
    CrucigramaApplyRequest,
    CrucigramaDictionaryRequest,
    CrucigramaGlobalBansRequest,
    CrucigramaMaskValidateRequest,
    CrucigramaPublishRequest,
    CrucigramaTemplateCreate,
    CrucigramaTemplateDetail,
    CrucigramaTemplateListResponse,
    CrucigramaTemplateUpdate,
)

router = APIRouter(
    prefix="/api/challenges/admin/crucigrama/templates",
    tags=["Desafíos Diarios - Administración de Crucigramas"],
    dependencies=[Depends(get_current_admin)],
)


@router.post("/validate", summary="Validar una máscara (estructura y solubilidad) sin guardarla")
async def endpoint_validate_mask(payload: CrucigramaMaskValidateRequest):
    global_bans = await get_global_banned_words()
    return await run_in_threadpool(service.validate_mask, payload, global_bans)


@router.get(
    "/global-bans",
    summary="Vetos globales de palabras (aplican a todos los tableros)",
)
async def endpoint_get_global_bans():
    return await service.get_global_bans()


@router.put(
    "/global-bans",
    summary="Reemplazar los vetos globales de palabras",
)
async def endpoint_update_global_bans(
    payload: CrucigramaGlobalBansRequest,
    current_admin=Depends(get_current_admin),
):
    return await service.update_global_bans(payload, current_admin)


@router.get(
    "/dictionary/{word}",
    summary="Consultar la definición RAE de una palabra (pista)",
)
async def endpoint_lookup_definition(word: str):
    return await run_in_threadpool(service.lookup_definition, word)


@router.post(
    "/dictionary",
    summary="Consultar definiciones RAE en lote para autocompletar pistas",
)
async def endpoint_lookup_definitions(payload: CrucigramaDictionaryRequest):
    return await run_in_threadpool(service.lookup_definitions, payload.words)


@router.get("", response_model=CrucigramaTemplateListResponse, summary="Listar plantillas")
async def endpoint_list_templates(
    status: Optional[str] = Query(None, pattern="^(draft|published|archived)$"),
    difficulty: Optional[str] = Query(None, pattern="^(facil|dificil)$"),
    size: Optional[int] = Query(None, ge=3, le=21),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    return await service.list_templates(
        status=status, difficulty=difficulty, size=size, limit=limit, skip=skip
    )


@router.post(
    "",
    response_model=CrucigramaTemplateDetail,
    summary="Crear una plantilla en borrador",
)
async def endpoint_create_template(
    payload: CrucigramaTemplateCreate,
    current_admin=Depends(get_current_admin),
):
    return await service.create_template(payload, current_admin)


@router.get(
    "/{template_id}",
    response_model=CrucigramaTemplateDetail,
    summary="Obtener una plantilla",
)
async def endpoint_get_template(template_id: str):
    return await service.get_template(template_id)


@router.put(
    "/{template_id}",
    response_model=CrucigramaTemplateDetail,
    summary="Editar una plantilla en borrador o archivada",
)
async def endpoint_update_template(
    template_id: str,
    payload: CrucigramaTemplateUpdate,
    current_admin=Depends(get_current_admin),
):
    return await service.update_template(template_id, payload, current_admin)


@router.delete("/{template_id}", summary="Eliminar una plantilla no publicada")
async def endpoint_delete_template(template_id: str):
    return await service.delete_template(template_id)


@router.post(
    "/{template_id}/publish",
    summary="Resolver, publicar y agendar una plantilla",
)
async def endpoint_publish_template(
    template_id: str,
    payload: CrucigramaPublishRequest,
    current_admin=Depends(get_current_admin),
):
    return await service.publish_template(template_id, payload, current_admin)


@router.post(
    "/{template_id}/archive",
    response_model=CrucigramaTemplateDetail,
    summary="Archivar una plantilla",
)
async def endpoint_archive_template(
    template_id: str,
    current_admin=Depends(get_current_admin),
):
    return await service.archive_template(template_id, current_admin)


@router.post(
    "/{template_id}/apply",
    summary="Aplicar una plantilla publicada a una fecha concreta",
)
async def endpoint_apply_template(
    template_id: str,
    payload: CrucigramaApplyRequest,
    current_admin=Depends(get_current_admin),
):
    return await service.apply_template(
        template_id, payload.date, payload.force, current_admin
    )
