import os
import re
import uuid
import io
from PIL import Image
from fastapi import APIRouter, Query, Path, HTTPException, File, UploadFile, Response
from typing import Optional, List, Dict, Any

from app.features.narrative.enums import (
    DisparadorEnum,
    OperadorEnum,
    TipoCondicionEnum,
    TipoAccionEnum,
    TipoCalculoEnum,
    CategoriaCartaEnum,
    TipoResultadoEnum
)
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
from app.features.narrative.service import (
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
    sembrar_finalizaciones_para_universo,
    generar_mes_narrativo
)

admin_router = APIRouter(prefix="/api/narrative/admin", tags=["Juego Narrativo - Torre de Control"])

# ============================================================================
# 1. CATÁLOGO OFICIAL DE REGLAS Y CONDICIONES (Para selects del Admin)
# ============================================================================

@admin_router.get(
    "/catalogo-reglas",
    summary="Obtener el catálogo formal de disparadores, operadores y acciones"
)
async def endpoint_obtener_catalogo_reglas():
    return {
        "disparadores": [
            {"clave": DisparadorEnum.AL_OBTENER.value, "label": "Al obtener la carta o reclutar personaje"},
            {"clave": DisparadorEnum.CADA_MES.value, "label": "Al comenzar cada mes"},
            {"clave": DisparadorEnum.EN_EVENTO_POSITIVO.value, "label": "Tras un desenlace positivo en el evento"},
            {"clave": DisparadorEnum.EN_EVENTO_NEGATIVO.value, "label": "Tras un desenlace negativo en el evento"},
            {"clave": DisparadorEnum.AL_FINAL_PARTIDA.value, "label": "Al completar los 12 meses"}
        ],
        "operadores": [
            {"clave": OperadorEnum.MAYOR_IGUAL.value, "label": "Mayor o igual (>=)"},
            {"clave": OperadorEnum.MENOR_IGUAL.value, "label": "Menor o igual (<=)"},
            {"clave": OperadorEnum.MAYOR.value, "label": "Mayor estricto (>)"},
            {"clave": OperadorEnum.MENOR.value, "label": "Menor estricto (<)"},
            {"clave": OperadorEnum.IGUAL.value, "label": "Igual (==)"},
            {"clave": OperadorEnum.DISTINTO.value, "label": "Distinto (!=)"}
        ],
        "tipos_condicion": [
            {"clave": TipoCondicionEnum.COMPARAR_RECURSO.value, "label": "Comparar valor de un recurso"},
            {"clave": TipoCondicionEnum.TIENE_PERSONAJE.value, "label": "Tiene a un personaje específico en la corte"},
            {"clave": TipoCondicionEnum.AFINIDAD_PERSONAJE.value, "label": "Nivel de afinidad con un personaje"},
            {"clave": TipoCondicionEnum.TIENE_TAG.value, "label": "Posee un tag pasivo activo"},
            {"clave": TipoCondicionEnum.TIENE_CARTA.value, "label": "Posee una carta en el inventario"}
        ],
        "tipos_accion": [
            {"clave": TipoAccionEnum.MODIFICAR_RECURSO.value, "label": "Modificar cantidad de un recurso"},
            {"clave": TipoAccionEnum.MODIFICAR_AFINIDAD.value, "label": "Modificar afinidad con personaje"},
            {"clave": TipoAccionEnum.OTORGAR_TAG.value, "label": "Otorgar un tag pasivo permanente"},
            {"clave": TipoAccionEnum.AMORTIGUAR_DANIO.value, "label": "Amortiguar pérdida de un recurso"}
        ],
        "tipos_calculo": [
            {"clave": TipoCalculoEnum.FIJO.value, "label": "Cantidad Fija (+10, -5)"},
            {"clave": TipoCalculoEnum.PORCENTUAL.value, "label": "Porcentual (+15%, -20%)"}
        ],
        "categorias_carta": [
            {"clave": CategoriaCartaEnum.ITEM.value, "label": "Ítem"},
            {"clave": CategoriaCartaEnum.BONUS.value, "label": "Bonus"},
            {"clave": CategoriaCartaEnum.PERSONAJE.value, "label": "Personaje / Recluta"}
        ],
        "tipos_resultado": [
            {"clave": TipoResultadoEnum.POSITIVO.value, "label": "Positivo (Verde / Victoria)"},
            {"clave": TipoResultadoEnum.NEGATIVO.value, "label": "Negativo (Rojo / Pérdida)"},
            {"clave": TipoResultadoEnum.NEUTRO.value, "label": "Neutro (Gris / Balance)"}
        ]
    }

# ============================================================================
# 2. CRUD DE UNIVERSOS / TEMÁTICAS
# ============================================================================

@admin_router.get("/universos", response_model=List[UniversoResponse], summary="Listar todos los universos")
async def endpoint_listar_universos():
    return await obtener_universos()

@admin_router.get("/universos/{universo_id}", response_model=UniversoResponse, summary="Obtener universo por ID")
async def endpoint_obtener_universo(universo_id: str = Path(...)):
    u = await obtener_universo_por_id(universo_id)
    if not u:
        raise HTTPException(status_code=404, detail="Universo no encontrado.")
    return u

@admin_router.post("/universos", response_model=UniversoResponse, summary="Crear o actualizar un universo")
async def endpoint_guardar_universo(req: UniversoCreateRequest):
    return await crear_o_actualizar_universo(req)

@admin_router.delete("/universos/{universo_id}", summary="Eliminar un universo")
async def endpoint_eliminar_universo(universo_id: str = Path(...)):
    exito = await eliminar_universo(universo_id)
    if not exito:
        raise HTTPException(status_code=404, detail="Universo no encontrado.")
    return {"message": "Universo eliminado correctamente."}

# ============================================================================
# 3. CRUD DE PERSONAJES
# ============================================================================

@admin_router.get(
    "/personajes",
    response_model=List[PersonajeResponse],
    summary="Listar personajes (con filtro universo, paginación y búsqueda)"
)
async def endpoint_listar_personajes(
    response: Response,
    universo_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0, description="Registros a omitir"),
    limit: Optional[int] = Query(None, ge=1, le=500, description="Límite de registros a retornar"),
    busqueda: Optional[str] = Query(None, description="Búsqueda por texto en nombre, rol o descripción")
):
    items, total = await obtener_personajes(
        universo_id=universo_id,
        skip=skip,
        limit=limit,
        busqueda=busqueda,
        with_total=True
    )
    response.headers["X-Total-Count"] = str(total)
    return items

@admin_router.get(
    "/personajes/{personaje_id}",
    response_model=PersonajeResponse,
    summary="Obtener un personaje por ID"
)
async def endpoint_obtener_personaje(personaje_id: str = Path(...)):
    p = await obtener_personaje_por_id(personaje_id)
    if not p:
        raise HTTPException(status_code=404, detail="Personaje no encontrado.")
    return p

@admin_router.post("/personajes", response_model=PersonajeResponse, summary="Crear o actualizar personaje")
async def endpoint_guardar_personaje(req: PersonajeCreateRequest):
    return await crear_o_actualizar_personaje(req)

@admin_router.delete("/personajes/{personaje_id}", summary="Eliminar personaje")
async def endpoint_eliminar_personaje(personaje_id: str = Path(...)):
    exito = await eliminar_personaje(personaje_id)
    if not exito:
        raise HTTPException(status_code=404, detail="Personaje no encontrado.")
    return {"message": "Personaje eliminado correctamente."}

# ============================================================================
# 4. CRUD DE CARTAS
# ============================================================================

@admin_router.get(
    "/cartas",
    response_model=List[CartaResponse],
    summary="Listar cartas (con filtro universo, paginación y búsqueda)"
)
async def endpoint_listar_cartas(
    response: Response,
    universo_id: Optional[str] = Query(None),
    categoria: Optional[str] = Query(None),
    skip: int = Query(0, ge=0, description="Registros a omitir"),
    limit: Optional[int] = Query(None, ge=1, le=500, description="Límite de registros a retornar"),
    busqueda: Optional[str] = Query(None, description="Búsqueda por texto en nombre o descripción")
):
    items, total = await obtener_cartas(
        universo_id=universo_id,
        categoria=categoria,
        skip=skip,
        limit=limit,
        busqueda=busqueda,
        with_total=True
    )
    response.headers["X-Total-Count"] = str(total)
    return items

@admin_router.get(
    "/cartas/{carta_id}",
    response_model=CartaResponse,
    summary="Obtener una carta por ID"
)
async def endpoint_obtener_carta(carta_id: str = Path(...)):
    c = await obtener_carta_por_id(carta_id)
    if not c:
        raise HTTPException(status_code=404, detail="Carta no encontrada.")
    return c

@admin_router.post("/cartas", response_model=CartaResponse, summary="Crear o actualizar carta")
async def endpoint_guardar_carta(req: CartaCreateRequest):
    return await crear_o_actualizar_carta(req)

@admin_router.delete("/cartas/{carta_id}", summary="Eliminar carta")
async def endpoint_eliminar_carta(carta_id: str = Path(...)):
    exito = await eliminar_carta(carta_id)
    if not exito:
        raise HTTPException(status_code=404, detail="Carta no encontrada.")
    return {"message": "Carta eliminada correctamente."}

# ============================================================================
# 5. CRUD DE RESULTADOS
# ============================================================================

@admin_router.get(
    "/resultados",
    response_model=List[ResultadoResponse],
    summary="Listar resultados (con filtro universo, paginación y búsqueda)"
)
async def endpoint_listar_resultados(
    response: Response,
    universo_id: Optional[str] = Query(None),
    tipo: Optional[str] = Query(None),
    skip: int = Query(0, ge=0, description="Registros a omitir"),
    limit: Optional[int] = Query(None, ge=1, le=500, description="Límite de registros a retornar"),
    busqueda: Optional[str] = Query(None, description="Búsqueda por texto en título o texto descriptivo")
):
    items, total = await obtener_resultados(
        universo_id=universo_id,
        tipo=tipo,
        skip=skip,
        limit=limit,
        busqueda=busqueda,
        with_total=True
    )
    response.headers["X-Total-Count"] = str(total)
    return items

@admin_router.get(
    "/resultados/{resultado_id}",
    response_model=ResultadoResponse,
    summary="Obtener un resultado por ID"
)
async def endpoint_obtener_resultado(resultado_id: str = Path(...)):
    r = await obtener_resultado_por_id(resultado_id)
    if not r:
        raise HTTPException(status_code=404, detail="Resultado no encontrado.")
    return r

@admin_router.post("/resultados", response_model=ResultadoResponse, summary="Crear o actualizar resultado")
async def endpoint_guardar_resultado(req: ResultadoCreateRequest):
    return await crear_o_actualizar_resultado(req)

@admin_router.delete("/resultados/{resultado_id}", summary="Eliminar resultado")
async def endpoint_eliminar_resultado(resultado_id: str = Path(...)):
    exito = await eliminar_resultado(resultado_id)
    if not exito:
        raise HTTPException(status_code=404, detail="Resultado no encontrado.")
    return {"message": "Resultado eliminado correctamente."}

# ============================================================================
# 6. CRUD DE EVENTOS
# ============================================================================

@admin_router.get(
    "/eventos",
    response_model=List[EventoResponse],
    summary="Listar eventos (con filtro universo, paginación y búsqueda)"
)
async def endpoint_listar_eventos(
    response: Response,
    universo_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0, description="Registros a omitir"),
    limit: Optional[int] = Query(None, ge=1, le=500, description="Límite de registros a retornar"),
    busqueda: Optional[str] = Query(None, description="Búsqueda por texto en título o descripción")
):
    items, total = await obtener_eventos(
        universo_id=universo_id,
        skip=skip,
        limit=limit,
        busqueda=busqueda,
        with_total=True
    )
    response.headers["X-Total-Count"] = str(total)
    return items

@admin_router.get(
    "/eventos/{evento_id}",
    response_model=EventoResponse,
    summary="Obtener un evento por ID"
)
async def endpoint_obtener_evento(evento_id: str = Path(...)):
    e = await obtener_evento_por_id(evento_id)
    if not e:
        raise HTTPException(status_code=404, detail="Evento no encontrado.")
    return e

@admin_router.post("/eventos", response_model=EventoResponse, summary="Crear o actualizar evento")
async def endpoint_guardar_evento(req: EventoCreateRequest):
    return await crear_o_actualizar_evento(req)

@admin_router.delete("/eventos/{evento_id}", summary="Eliminar evento")
async def endpoint_eliminar_evento(evento_id: str = Path(...)):
    exito = await eliminar_evento(evento_id)
    if not exito:
        raise HTTPException(status_code=404, detail="Evento no encontrado.")
    return {"message": "Evento eliminado correctamente."}

# ============================================================================
# 7. CRUD DE CONVERSACIONES
# ============================================================================

@admin_router.get(
    "/conversaciones",
    response_model=List[ConversacionResponse],
    summary="Listar conversaciones (con filtro universo, paginación y búsqueda)"
)
async def endpoint_listar_conversaciones(
    response: Response,
    universo_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0, description="Registros a omitir"),
    limit: Optional[int] = Query(None, ge=1, le=500, description="Límite de registros a retornar"),
    busqueda: Optional[str] = Query(None, description="Búsqueda por texto en título o contexto")
):
    items, total = await obtener_conversaciones(
        universo_id=universo_id,
        skip=skip,
        limit=limit,
        busqueda=busqueda,
        with_total=True
    )
    response.headers["X-Total-Count"] = str(total)
    return items

@admin_router.get(
    "/conversaciones/{conversacion_id}",
    response_model=ConversacionResponse,
    summary="Obtener una conversación por ID"
)
async def endpoint_obtener_conversacion(conversacion_id: str = Path(...)):
    c = await obtener_conversacion_por_id(conversacion_id)
    if not c:
        raise HTTPException(status_code=404, detail="Conversación no encontrada.")
    return c

@admin_router.post("/conversaciones", response_model=ConversacionResponse, summary="Crear o actualizar conversación")
async def endpoint_guardar_conversacion(req: ConversacionCreateRequest):
    return await crear_o_actualizar_conversacion(req)

@admin_router.delete("/conversaciones/{conversacion_id}", summary="Eliminar conversación")
async def endpoint_eliminar_conversacion(conversacion_id: str = Path(...)):
    exito = await eliminar_conversacion(conversacion_id)
    if not exito:
        raise HTTPException(status_code=404, detail="Conversación no encontrada.")
    return {"message": "Conversación eliminada correctamente."}

# ============================================================================
# 8. CRUD DE FINALIZACIONES / DESENLACES DE REINO
# ============================================================================

@admin_router.get(
    "/finalizaciones",
    response_model=List[FinalizacionResponse],
    summary="Listar finalizaciones (con filtro universo, recurso, paginación y búsqueda)"
)
async def endpoint_listar_finalizaciones(
    response: Response,
    universo_id: Optional[str] = Query(None),
    recurso_clave: Optional[str] = Query(None),
    skip: int = Query(0, ge=0, description="Registros a omitir"),
    limit: Optional[int] = Query(None, ge=1, le=500, description="Límite de registros a retornar"),
    busqueda: Optional[str] = Query(None, description="Búsqueda por texto en título o epílogo")
):
    items, total = await obtener_finalizaciones(
        universo_id=universo_id,
        recurso_clave=recurso_clave,
        skip=skip,
        limit=limit,
        busqueda=busqueda,
        with_total=True
    )
    response.headers["X-Total-Count"] = str(total)
    return items

@admin_router.get("/finalizaciones/{finalizacion_id}", response_model=FinalizacionResponse, summary="Obtener una finalización por ID")
async def endpoint_obtener_finalizacion(finalizacion_id: str = Path(...)):
    fin = await obtener_finalizacion_por_id(finalizacion_id)
    if not fin:
        raise HTTPException(status_code=404, detail="Finalización no encontrada.")
    return fin

@admin_router.post("/finalizaciones", response_model=FinalizacionResponse, summary="Crear o actualizar finalización")
async def endpoint_guardar_finalizacion(req: FinalizacionCreateRequest):
    return await crear_o_actualizar_finalizacion(req)

@admin_router.delete("/finalizaciones/{finalizacion_id}", summary="Eliminar finalización")
async def endpoint_eliminar_finalizacion(finalizacion_id: str = Path(...)):
    exito = await eliminar_finalizacion(finalizacion_id)
    if not exito:
        raise HTTPException(status_code=404, detail="Finalización no encontrada.")
    return {"message": "Finalización eliminada correctamente."}

@admin_router.post(
    "/universos/{universo_id}/sembrar-finalizaciones",
    response_model=List[FinalizacionResponse],
    summary="Generar o sembrar las finalizaciones base por agotamiento de recursos para un universo"
)
async def endpoint_sembrar_finalizaciones_universo(universo_id: str = Path(...)):
    return await sembrar_finalizaciones_para_universo(universo_id=universo_id)

# ============================================================================
# 9. GENERADOR MENSUAL DE DESAFÍOS
# ============================================================================

@admin_router.post(
    "/generar-mes",
    summary="Generar automáticamente los desafíos diarios del mes para un universo temático"
)
async def endpoint_generar_mes(
    year: int = Query(..., ge=2020, le=2050, description="Año"),
    month: int = Query(..., ge=1, le=12, description="Mes (1-12)"),
    universo_id: str = Query("corte_medieval", description="ID del universo temático")
):
    return await generar_mes_narrativo(year=year, month=month, universo_id=universo_id)

# ============================================================================
# 9. SUBIDA Y OPTIMIZACIÓN DE IMÁGENES A WEBP
# ============================================================================

DIMENSIONES_MAX_POR_CATEGORIA = {
    "universos": (1200, 600),
    "personajes": (600, 750),
    "cartas": (450, 630),
    "eventos": (900, 500),
    "resultados": (900, 500),
    "conversaciones": (900, 500),
    "finalizaciones": (900, 500),
}

@admin_router.post(
    "/upload-imagen",
    summary="Subir y optimizar una imagen a formato WebP para cualquier entidad"
)
async def endpoint_upload_imagen(
    file: UploadFile = File(...),
    categoria: str = Query(..., pattern="^(universos|personajes|cartas|eventos|resultados|conversaciones|finalizaciones)$")
):
    """
    Recibe un archivo de imagen en cualquier formato (JPG, PNG, WebP), valida su tamaño,
    lo redimensiona según su categoría y lo guarda comprimido en formato WebP en el servidor.
    """
    extensiones_validas = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".bmp", ".gif"}
    nombre_original = file.filename or "imagen"
    _, ext = os.path.splitext(nombre_original.lower())

    if ext not in extensiones_validas:
        raise HTTPException(
            status_code=400,
            detail=f"Formato de archivo '{ext}' no soportado. Permitidos: {', '.join(extensiones_validas)}"
        )

    contenido = await file.read()
    if len(contenido) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="La imagen no puede superar los 10 MB.")

    try:
        img = Image.open(io.BytesIO(contenido))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo procesar la imagen: {str(e)}")

    # Asegurar modo de color compatible con WebP (RGBA si tiene canal alpha, RGB en otro caso)
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
    else:
        img = img.convert("RGB")

    # Redimensionar proporcionalmente sin distorsionar
    max_dims = DIMENSIONES_MAX_POR_CATEGORIA.get(categoria, (900, 600))
    img.thumbnail(max_dims, Image.Resampling.LANCZOS)

    # Limpiar nombre base y crear nombre único
    slug_limpio = re.sub(r"[^a-zA-Z0-9_\-]", "", os.path.splitext(nombre_original)[0].lower())[:25]
    if not slug_limpio:
        slug_limpio = "img"
    filename_webp = f"{slug_limpio}_{uuid.uuid4().hex[:6]}.webp"

    # Ruta de almacenamiento estático en disco
    directorio_base = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "static",
        "narrative",
        categoria
    )
    os.makedirs(directorio_base, exist_ok=True)
    ruta_destino = os.path.join(directorio_base, filename_webp)

    # Guardar en WebP con compresión de alta calidad
    try:
        img.save(ruta_destino, "WEBP", quality=82, method=4)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al guardar la imagen WebP: {str(e)}")

    tamanio_bytes = os.path.getsize(ruta_destino)

    return {
        "url": f"/assets/narrative/{categoria}/{filename_webp}",
        "filename": filename_webp,
        "categoria": categoria,
        "ancho": img.width,
        "alto": img.height,
        "tamanio_kb": round(tamanio_bytes / 1024, 1)
    }

