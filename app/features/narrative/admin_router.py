from fastapi import APIRouter, Query, Path, HTTPException
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
    ConversacionResponse
)
from app.features.narrative.service import (
    crear_o_actualizar_universo,
    obtener_universos,
    obtener_universo_por_id,
    eliminar_universo,
    crear_o_actualizar_personaje,
    obtener_personajes,
    eliminar_personaje,
    crear_o_actualizar_carta,
    obtener_cartas,
    eliminar_carta,
    crear_o_actualizar_resultado,
    obtener_resultados,
    eliminar_resultado,
    crear_o_actualizar_evento,
    obtener_eventos,
    eliminar_evento,
    crear_o_actualizar_conversacion,
    obtener_conversaciones,
    eliminar_conversacion,
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

@admin_router.get("/personajes", response_model=List[PersonajeResponse], summary="Listar personajes (con filtro universo)")
async def endpoint_listar_personajes(universo_id: Optional[str] = Query(None)):
    return await obtener_personajes(universo_id=universo_id)

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

@admin_router.get("/cartas", response_model=List[CartaResponse], summary="Listar cartas (con filtro universo)")
async def endpoint_listar_cartas(universo_id: Optional[str] = Query(None)):
    return await obtener_cartas(universo_id=universo_id)

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

@admin_router.get("/resultados", response_model=List[ResultadoResponse], summary="Listar resultados (con filtro universo)")
async def endpoint_listar_resultados(universo_id: Optional[str] = Query(None)):
    return await obtener_resultados(universo_id=universo_id)

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

@admin_router.get("/eventos", response_model=List[EventoResponse], summary="Listar eventos (con filtro universo)")
async def endpoint_listar_eventos(universo_id: Optional[str] = Query(None)):
    return await obtener_eventos(universo_id=universo_id)

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

@admin_router.get("/conversaciones", response_model=List[ConversacionResponse], summary="Listar conversaciones (con filtro universo)")
async def endpoint_listar_conversaciones(universo_id: Optional[str] = Query(None)):
    return await obtener_conversaciones(universo_id=universo_id)

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
# 8. GENERADOR MENSUAL DE DESAFÍOS
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
