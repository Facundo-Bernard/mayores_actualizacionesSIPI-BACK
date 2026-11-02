"""
router.py
Controlador FastAPI de la Torre de Control y Administración (/api/narrative/admin).
Expone endpoints REST para catálogo de reglas, carga de multimedia WebP,
gestión de colecciones estáticas y generador procedural mensual.
"""

from fastapi import APIRouter, Query, Path, HTTPException, File, UploadFile
from typing import Optional, List, Dict, Any

from app.features.narrative.schemas import (
    UniversoCreateRequest,
    UniversoResponse,
    PersonajeCreateRequest,
    PersonajeResponse,
    CartaCreateRequest,
    CartaResponse,
    ResultadoCreateRequest,
    ResultadoResponse,
    EventoCreateRequest,
    EventoResponse,
    ConversacionCreateRequest,
    ConversacionResponse,
    FinalizacionCreateRequest,
    FinalizacionResponse
)
from app.features.narrative.schemas.v2_graph_schemas import (
    EventoV2GrafoSchema,
    ConversacionV2GrafoSchema,
    EventoEspecialV2GrafoSchema,
    ValidarGrafoV2Request,
    ValidarGrafoV2Response
)
from app.features.narrative.validation import (
    TIPOS_VALIDOS,
    validar_grafo,
    validar_grafos_almacenados
)
from app.features.narrative.admin.rules_catalog import obtener_catalogo_reglas_dict
from app.features.narrative.admin.image_service import procesar_y_guardar_imagen_narrativa
from app.features.narrative.admin.crud_service import (
    crear_o_actualizar_universo,
    obtener_universos,
    obtener_universo_por_id,
    eliminar_universo,
    crear_o_actualizar_personaje,
    obtener_personajes,
    obtener_personaje_por_id,
    eliminar_personaje,
    crear_o_actualizar_carta,
    obtener_cartas,
    obtener_carta_por_id,
    eliminar_carta,
    crear_o_actualizar_resultado,
    obtener_resultados,
    obtener_resultado_por_id,
    eliminar_resultado,
    crear_o_actualizar_evento,
    obtener_eventos,
    obtener_evento_por_id,
    eliminar_evento,
    crear_o_actualizar_conversacion,
    obtener_conversaciones,
    obtener_conversacion_por_id,
    eliminar_conversacion,
    crear_o_actualizar_finalizacion,
    obtener_finalizaciones,
    obtener_finalizacion_por_id,
    eliminar_finalizacion,
    crear_o_actualizar_evento_v2,
    obtener_eventos_v2,
    obtener_evento_v2_por_id,
    eliminar_evento_v2,
    crear_o_actualizar_conversacion_v2,
    obtener_conversaciones_v2,
    obtener_conversacion_v2_por_id,
    eliminar_conversacion_v2,
    crear_o_actualizar_evento_especial_v2,
    obtener_eventos_especiales_v2,
    obtener_evento_especial_v2_por_id,
    eliminar_evento_especial_v2
)
from app.features.narrative.admin.challenge_service import (
    sembrar_finalizaciones_para_universo,
    generar_mes_narrativo
)

from fastapi import Depends
from app.core.dependencies import get_current_admin

router = APIRouter(
    prefix="/api/narrative/admin",
    tags=["Juego Narrativo - Torre de Control"],
    dependencies=[Depends(get_current_admin)]
)

# ============================================================================
# 1. CATÁLOGO OFICIAL DE REGLAS (Para desplegables del Admin)
# ============================================================================

@router.get(
    "/catalogo-reglas",
    summary="Obtener el catálogo formal de disparadores, operadores y acciones"
)
async def endpoint_obtener_catalogo_reglas():
    """Retorna el catálogo canónico de disparadores, operadores y acciones para desplegables de UI."""
    return obtener_catalogo_reglas_dict()

# ============================================================================
# 2. SUBIDA Y OPTIMIZACIÓN DE IMÁGENES WEBP
# ============================================================================

@router.post(
    "/upload-imagen",
    summary="Subir y optimizar imagen a WebP para cualquier categoría del juego narrativo"
)
async def endpoint_subir_imagen_narrativa(
    file: UploadFile = File(...),
    categoria: str = Query(..., description="Categoría (universos, personajes, cartas, eventos, resultados, conversaciones, finalizaciones)")
):
    """Procesa una imagen JPG/PNG, la redimensiona proporcionalmente y la comprime a WebP."""
    return await procesar_y_guardar_imagen_narrativa(file=file, categoria=categoria)

# ============================================================================
# 3. CRUD DE UNIVERSOS / TEMÁTICAS
# ============================================================================

@router.get("/universos", response_model=List[UniversoResponse], summary="Listar todos los universos")
async def endpoint_listar_universos():
    return await obtener_universos()

@router.get("/universos/{universo_id}", response_model=UniversoResponse, summary="Obtener universo por ID")
async def endpoint_obtener_universo(universo_id: str = Path(...)):
    u = await obtener_universo_por_id(universo_id)
    if not u:
        raise HTTPException(status_code=404, detail="Universo no encontrado.")
    return u

@router.post("/universos", response_model=UniversoResponse, summary="Crear o actualizar un universo")
async def endpoint_guardar_universo(req: UniversoCreateRequest):
    return await crear_o_actualizar_universo(req)

@router.delete("/universos/{universo_id}", summary="Eliminar un universo")
async def endpoint_eliminar_universo(universo_id: str = Path(...)):
    exito = await eliminar_universo(universo_id)
    if not exito:
        raise HTTPException(status_code=404, detail="Universo no encontrado.")
    return {"message": "Universo eliminado correctamente."}

# ============================================================================
# 4. CRUD DE PERSONAJES
# ============================================================================

@router.get("/personajes", response_model=List[PersonajeResponse], summary="Listar personajes")
async def endpoint_listar_personajes(
    universo_id: Optional[str] = Query(None, description="Filtrar por universo"),
    limit: Optional[int] = Query(None, description="Límite de resultados"),
    skip: int = Query(0, description="Paginación offset")
):
    return await obtener_personajes(universo_id=universo_id, limit=limit, skip=skip)

@router.get("/personajes/{personaje_id}", response_model=PersonajeResponse, summary="Obtener personaje por ID")
async def endpoint_obtener_personaje(personaje_id: str = Path(...)):
    p = await obtener_personaje_por_id(personaje_id)
    if not p:
        raise HTTPException(status_code=404, detail="Personaje no encontrado.")
    return p

@router.post("/personajes", response_model=PersonajeResponse, summary="Crear o actualizar personaje")
async def endpoint_guardar_personaje(req: PersonajeCreateRequest):
    return await crear_o_actualizar_personaje(req)

@router.delete("/personajes/{personaje_id}", summary="Eliminar personaje")
async def endpoint_eliminar_personaje(personaje_id: str = Path(...)):
    exito = await eliminar_personaje(personaje_id)
    if not exito:
        raise HTTPException(status_code=404, detail="Personaje no encontrado.")
    return {"message": "Personaje eliminado correctamente."}

# ============================================================================
# 5. CRUD DE CARTAS
# ============================================================================

@router.get("/cartas", response_model=List[CartaResponse], summary="Listar cartas")
async def endpoint_listar_cartas(
    universo_id: Optional[str] = Query(None, description="Filtrar por universo"),
    limit: Optional[int] = Query(None, description="Límite de resultados"),
    skip: int = Query(0, description="Paginación offset")
):
    return await obtener_cartas(universo_id=universo_id, limit=limit, skip=skip)

@router.get("/cartas/{carta_id}", response_model=CartaResponse, summary="Obtener carta por ID")
async def endpoint_obtener_carta(carta_id: str = Path(...)):
    c = await obtener_carta_por_id(carta_id)
    if not c:
        raise HTTPException(status_code=404, detail="Carta no encontrada.")
    return c

@router.post("/cartas", response_model=CartaResponse, summary="Crear o actualizar carta")
async def endpoint_guardar_carta(req: CartaCreateRequest):
    return await crear_o_actualizar_carta(req)

@router.delete("/cartas/{carta_id}", summary="Eliminar carta")
async def endpoint_eliminar_carta(carta_id: str = Path(...)):
    exito = await eliminar_carta(carta_id)
    if not exito:
        raise HTTPException(status_code=404, detail="Carta no encontrada.")
    return {"message": "Carta eliminada correctamente."}

# ============================================================================
# 6. CRUD DE RESULTADOS
# ============================================================================

@router.get("/resultados", response_model=List[ResultadoResponse], summary="Listar resultados")
async def endpoint_listar_resultados(
    universo_id: Optional[str] = Query(None, description="Filtrar por universo"),
    limit: Optional[int] = Query(None, description="Límite de resultados"),
    skip: int = Query(0, description="Paginación offset")
):
    return await obtener_resultados(universo_id=universo_id, limit=limit, skip=skip)

@router.get("/resultados/{resultado_id}", response_model=ResultadoResponse, summary="Obtener resultado por ID")
async def endpoint_obtener_resultado(resultado_id: str = Path(...)):
    r = await obtener_resultado_por_id(resultado_id)
    if not r:
        raise HTTPException(status_code=404, detail="Resultado no encontrado.")
    return r

@router.post("/resultados", response_model=ResultadoResponse, summary="Crear o actualizar resultado")
async def endpoint_guardar_resultado(req: ResultadoCreateRequest):
    return await crear_o_actualizar_resultado(req)

@router.delete("/resultados/{resultado_id}", summary="Eliminar resultado")
async def endpoint_eliminar_resultado(resultado_id: str = Path(...)):
    exito = await eliminar_resultado(resultado_id)
    if not exito:
        raise HTTPException(status_code=404, detail="Resultado no encontrado.")
    return {"message": "Resultado eliminado correctamente."}

# ============================================================================
# 7. CRUD DE EVENTOS
# ============================================================================

@router.get("/eventos", response_model=List[EventoResponse], summary="Listar eventos")
async def endpoint_listar_eventos(
    universo_id: Optional[str] = Query(None, description="Filtrar por universo"),
    limit: Optional[int] = Query(None, description="Límite de resultados"),
    skip: int = Query(0, description="Paginación offset")
):
    return await obtener_eventos(universo_id=universo_id, limit=limit, skip=skip)

@router.get("/eventos/{evento_id}", response_model=EventoResponse, summary="Obtener evento por ID")
async def endpoint_obtener_evento(evento_id: str = Path(...)):
    e = await obtener_evento_por_id(evento_id)
    if not e:
        raise HTTPException(status_code=404, detail="Evento no encontrado.")
    return e

@router.post("/eventos", response_model=EventoResponse, summary="Crear o actualizar evento")
async def endpoint_guardar_evento(req: EventoCreateRequest):
    return await crear_o_actualizar_evento(req)

@router.delete("/eventos/{evento_id}", summary="Eliminar evento")
async def endpoint_eliminar_evento(evento_id: str = Path(...)):
    exito = await eliminar_evento(evento_id)
    if not exito:
        raise HTTPException(status_code=404, detail="Evento no encontrado.")
    return {"message": "Evento eliminado correctamente."}

# ============================================================================
# 8. CRUD DE CONVERSACIONES
# ============================================================================

@router.get("/conversaciones", response_model=List[ConversacionResponse], summary="Listar conversaciones")
async def endpoint_listar_conversaciones(
    universo_id: Optional[str] = Query(None, description="Filtrar por universo"),
    limit: Optional[int] = Query(None, description="Límite de resultados"),
    skip: int = Query(0, description="Paginación offset")
):
    return await obtener_conversaciones(universo_id=universo_id, limit=limit, skip=skip)

@router.get("/conversaciones/{conversacion_id}", response_model=ConversacionResponse, summary="Obtener conversación por ID")
async def endpoint_obtener_conversacion(conversacion_id: str = Path(...)):
    c = await obtener_conversacion_por_id(conversacion_id)
    if not c:
        raise HTTPException(status_code=404, detail="Conversación no encontrada.")
    return c

@router.post("/conversaciones", response_model=ConversacionResponse, summary="Crear o actualizar conversación")
async def endpoint_guardar_conversacion(req: ConversacionCreateRequest):
    return await crear_o_actualizar_conversacion(req)

@router.delete("/conversaciones/{conversacion_id}", summary="Eliminar conversación")
async def endpoint_eliminar_conversacion(conversacion_id: str = Path(...)):
    exito = await eliminar_conversacion(conversacion_id)
    if not exito:
        raise HTTPException(status_code=404, detail="Conversación no encontrada.")
    return {"message": "Conversación eliminada correctamente."}

# ============================================================================
# 9. CRUD DE FINALIZACIONES / DERROTAS
# ============================================================================

@router.get("/finalizaciones", response_model=List[FinalizacionResponse], summary="Listar finalizaciones")
async def endpoint_listar_finalizaciones(
    universo_id: Optional[str] = Query(None, description="Filtrar por universo"),
    limit: Optional[int] = Query(None, description="Límite de resultados"),
    skip: int = Query(0, description="Paginación offset")
):
    return await obtener_finalizaciones(universo_id=universo_id, limit=limit, skip=skip)

@router.get("/finalizaciones/{finalizacion_id}", response_model=FinalizacionResponse, summary="Obtener finalización por ID")
async def endpoint_obtener_finalizacion(finalizacion_id: str = Path(...)):
    f = await obtener_finalizacion_por_id(finalizacion_id)
    if not f:
        raise HTTPException(status_code=404, detail="Finalización no encontrada.")
    return f

@router.post("/finalizaciones", response_model=FinalizacionResponse, summary="Crear o actualizar finalización")
async def endpoint_guardar_finalizacion(req: FinalizacionCreateRequest):
    return await crear_o_actualizar_finalizacion(req)

@router.delete("/finalizaciones/{finalizacion_id}", summary="Eliminar finalización")
async def endpoint_eliminar_finalizacion(finalizacion_id: str = Path(...)):
    exito = await eliminar_finalizacion(finalizacion_id)
    if not exito:
        raise HTTPException(status_code=404, detail="Finalización no encontrada.")
    return {"message": "Finalización eliminada correctamente."}

@router.post(
    "/universos/{universo_id}/sembrar-finalizaciones",
    response_model=List[FinalizacionResponse],
    summary="Sembrar automáticamente las finalizaciones de derrota base (<= 0) para cada recurso del universo"
)
async def endpoint_sembrar_finalizaciones_universo(universo_id: str = Path(...)):
    return await sembrar_finalizaciones_para_universo(universo_id)

# ============================================================================
# 10. GENERADOR MENSUAL DE DESAFÍOS
# ============================================================================

@router.post(
    "/generar-mes",
    summary="Generar masivamente los 28-31 desafíos diarios del mes para el juego narrativo"
)
async def endpoint_generar_mes_narrativo(
    year: int = Query(..., description="Año (ej: 2026)"),
    month: int = Query(..., ge=1, le=12, description="Mes (1 a 12)"),
    universo_id: str = Query(..., description="ID del universo (ej: corte_medieval)")
):
    return await generar_mes_narrativo(year=year, month=month, universo_id=universo_id)

# ============================================================================
# 11. MOTOR NARRATIVO V2: CRUD DE GRAFOS (EVENTOS Y CONVERSACIONES)
# ============================================================================

@router.get("/v2/eventos", response_model=List[EventoV2GrafoSchema], summary="Listar eventos de grafos V2")
async def endpoint_listar_eventos_v2(
    universo_id: Optional[str] = Query(None, description="Filtrar por universo"),
    limit: Optional[int] = Query(None, description="Límite de resultados"),
    skip: int = Query(0, description="Offset de paginación")
):
    return await obtener_eventos_v2(universo_id=universo_id, limit=limit, skip=skip)

@router.get("/v2/eventos/{evento_id}", response_model=EventoV2GrafoSchema, summary="Obtener evento V2 por ID")
async def endpoint_obtener_evento_v2(evento_id: str = Path(...)):
    e = await obtener_evento_v2_por_id(evento_id)
    if not e:
        raise HTTPException(status_code=404, detail="Evento V2 no encontrado.")
    return e

@router.post("/v2/eventos", response_model=EventoV2GrafoSchema, summary="Crear o actualizar evento V2")
async def endpoint_guardar_evento_v2(req: EventoV2GrafoSchema):
    return await crear_o_actualizar_evento_v2(req)

@router.delete("/v2/eventos/{evento_id}", summary="Eliminar evento V2")
async def endpoint_eliminar_evento_v2(evento_id: str = Path(...)):
    exito = await eliminar_evento_v2(evento_id)
    if not exito:
        raise HTTPException(status_code=404, detail="Evento V2 no encontrado.")
    return {"message": "Evento V2 eliminado correctamente."}

@router.get("/v2/conversaciones", response_model=List[ConversacionV2GrafoSchema], summary="Listar conversaciones de grafos V2")
async def endpoint_listar_conversaciones_v2(
    universo_id: Optional[str] = Query(None, description="Filtrar por universo"),
    limit: Optional[int] = Query(None, description="Límite de resultados"),
    skip: int = Query(0, description="Offset de paginación")
):
    return await obtener_conversaciones_v2(universo_id=universo_id, limit=limit, skip=skip)

@router.get("/v2/conversaciones/{conversacion_id}", response_model=ConversacionV2GrafoSchema, summary="Obtener conversación V2 por ID")
async def endpoint_obtener_conversacion_v2(conversacion_id: str = Path(...)):
    c = await obtener_conversacion_v2_por_id(conversacion_id)
    if not c:
        raise HTTPException(status_code=404, detail="Conversación V2 no encontrada.")
    return c

@router.post("/v2/conversaciones", response_model=ConversacionV2GrafoSchema, summary="Crear o actualizar conversación V2")
async def endpoint_guardar_conversacion_v2(req: ConversacionV2GrafoSchema):
    return await crear_o_actualizar_conversacion_v2(req)

@router.delete("/v2/conversaciones/{conversacion_id}", summary="Eliminar conversación V2")
async def endpoint_eliminar_conversacion_v2(conversacion_id: str = Path(...)):
    exito = await eliminar_conversacion_v2(conversacion_id)
    if not exito:
        raise HTTPException(status_code=404, detail="Conversación V2 no encontrada.")
    return {"message": "Conversación V2 eliminada correctamente."}

@router.get("/v2/eventos-especiales", response_model=List[EventoEspecialV2GrafoSchema], summary="Listar eventos especiales de afinidad (lealtad/traición)")
async def endpoint_listar_eventos_especiales_v2(
    universo_id: Optional[str] = Query(None, description="Filtrar por universo"),
    limit: Optional[int] = Query(None, description="Límite de resultados"),
    skip: int = Query(0, description="Offset de paginación")
):
    return await obtener_eventos_especiales_v2(universo_id=universo_id, limit=limit, skip=skip)

@router.get("/v2/eventos-especiales/{evento_id}", response_model=EventoEspecialV2GrafoSchema, summary="Obtener evento especial V2 por ID")
async def endpoint_obtener_evento_especial_v2(evento_id: str = Path(...)):
    e = await obtener_evento_especial_v2_por_id(evento_id)
    if not e:
        raise HTTPException(status_code=404, detail="Evento especial V2 no encontrado.")
    return e

@router.post("/v2/eventos-especiales", response_model=EventoEspecialV2GrafoSchema, summary="Crear o actualizar evento especial V2")
async def endpoint_guardar_evento_especial_v2(req: EventoEspecialV2GrafoSchema):
    return await crear_o_actualizar_evento_especial_v2(req)

@router.delete("/v2/eventos-especiales/{evento_id}", summary="Eliminar evento especial V2")
async def endpoint_eliminar_evento_especial_v2(evento_id: str = Path(...)):
    exito = await eliminar_evento_especial_v2(evento_id)
    if not exito:
        raise HTTPException(status_code=404, detail="Evento especial V2 no encontrado.")
    return {"message": "Evento especial V2 eliminado correctamente."}

@router.post(
    "/v2/validar",
    response_model=ValidarGrafoV2Response,
    summary="Validar grafos V2 (referencias, hojas, pesos y ciclos)"
)
async def endpoint_validar_grafos_v2(req: ValidarGrafoV2Request):
    """Valida un grafo inline, uno almacenado o todos los grafos de un universo."""
    if req.tipo is not None and req.tipo not in TIPOS_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo inválido: '{req.tipo}'. Válidos: {list(TIPOS_VALIDOS)}."
        )

    if req.grafo is not None:
        if not req.tipo:
            raise HTTPException(
                status_code=400,
                detail="Para validar un grafo inline se requiere indicar 'tipo'."
            )
        resultados = [validar_grafo(req.grafo, req.tipo)]
    else:
        tipos = [req.tipo] if req.tipo else None
        resultados = await validar_grafos_almacenados(
            tipos=tipos,
            grafo_id=req.grafo_id,
            universo_id=req.universo_id
        )
        if req.grafo_id and not resultados:
            raise HTTPException(status_code=404, detail=f"Grafo '{req.grafo_id}' no encontrado.")

    return {
        "resultados": [r.as_dict() for r in resultados],
        "total": len(resultados),
        "invalidos": sum(1 for r in resultados if not r.valido)
    }

