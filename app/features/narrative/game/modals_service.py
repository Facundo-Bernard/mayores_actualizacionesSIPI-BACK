"""
modals_service.py
Consultas bajo demanda para la interfaz de usuario:
- Modales de la bitácora mensual (historial).
- Modal de inventario (cartas en mano y tags activos).
- Modal de corte activa (personajes asignados y afinidad).
- Modal de epílogo / finalización detallada.
- Sincronización reactiva del turno actual (recargas F5 o reconexión).
- Consultas atómicas de evento, diálogo, resultado y draft activo.
"""

import logging
from typing import Optional, List, Dict, Any
from fastapi import HTTPException

from app.core.database import get_database
from app.features.narrative.constants import (
    COLL_CHARACTERS,
    COLL_CARDS,
    COLL_RESULTS,
    COLL_EVENTS,
    COLL_CONVERSATIONS,
    COLL_RUNS
)
from app.features.narrative.schemas.catalog_schemas import (
    PersonajeResponse,
    CartaResponse,
    ResultadoResponse,
    ConversacionResponse,
    FinalizacionResponse
)
from app.features.narrative.schemas.game_schemas import (
    EventoTurnoResponse,
    HistorialPartidaResponse,
    InventarioPartidaResponse,
    PersonajeCorteDetalle,
    CortePartidaResponse,
    FinalizacionPartidaResponse,
    EstadoTurnoResponse
)
from app.features.narrative.engine.event_director import calcular_opciones_evento

logger = logging.getLogger(__name__)

async def obtener_historial_partida(user_id: int, date: str) -> HistorialPartidaResponse:
    """Consulta la bitácora mensual acumulada de los meses transcurridos en la partida."""
    db = get_database()
    run = await db[COLL_RUNS].find_one({"user_id": user_id, "date": date, "game_id": "narrativo"})
    if not run:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")
    return HistorialPartidaResponse(
        date=date,
        mes_actual=run.get("mes_actual", 1),
        status=run.get("status", "in_progress"),
        fase_actual=run.get("fase_actual", ""),
        historial_mensual=run.get("historial_mensual", [])
    )

async def obtener_inventario_partida(user_id: int, date: str) -> InventarioPartidaResponse:
    """Consulta las cartas en mano y tags activos acumulados por el jugador."""
    db = get_database()
    run = await db[COLL_RUNS].find_one({"user_id": user_id, "date": date, "game_id": "narrativo"})
    if not run:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")
    cartas_ids = run.get("cartas_en_mano", [])
    docs = await db[COLL_CARDS].find({"_id": {"$in": cartas_ids}}).to_list(None) if cartas_ids else []
    return InventarioPartidaResponse(
        date=date,
        cartas=[CartaResponse(**d) for d in docs],
        tags_activos=run.get("tags_activos", [])
    )

async def obtener_corte_partida(user_id: int, date: str) -> CortePartidaResponse:
    """Consulta los miembros activos de la corte y sus afinidades numéricas actuales."""
    db = get_database()
    run = await db[COLL_RUNS].find_one({"user_id": user_id, "date": date, "game_id": "narrativo"})
    if not run:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")
    afinidades = run.get("afinidad", {})
    corte_ids = list(afinidades.keys()) or run.get("corte_activa", [])
    docs = await db[COLL_CHARACTERS].find({"_id": {"$in": corte_ids}}).to_list(None) if corte_ids else []
    corte_detalle = [
        PersonajeCorteDetalle(
            personaje=PersonajeResponse(**d),
            afinidad=afinidades.get(d["_id"], 50)
        )
        for d in docs
    ]
    return CortePartidaResponse(
        date=date,
        corte=corte_detalle,
        afinidad=afinidades
    )

async def obtener_finalizacion_partida(user_id: int, date: str) -> FinalizacionPartidaResponse:
    """Consulta la tarjeta de finalización o derrota al término de la partida."""
    db = get_database()
    run = await db[COLL_RUNS].find_one({"user_id": user_id, "date": date, "game_id": "narrativo"})
    if not run:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")
    fin_doc = run.get("finalizacion")
    fin_resp = FinalizacionResponse(**fin_doc) if fin_doc else None
    return FinalizacionPartidaResponse(
        date=date,
        status=run.get("status", "in_progress"),
        mes_actual=run.get("mes_actual", 1),
        finalizacion=fin_resp,
        epilogo_final=fin_doc
    )

async def obtener_turno_actual(user_id: int, date: str) -> EstadoTurnoResponse:
    """Retorna el estado reactivo del turno actual para sincronización de frontend o recarga F5."""
    db = get_database()
    run = await db[COLL_RUNS].find_one({"user_id": user_id, "date": date, "game_id": "narrativo"})
    if not run:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")

    turno = run.get("turno_actual", {})
    draft_ids = turno.get("cartas_ofrecidas_ids", [])
    evento_id = turno.get("evento_actual_id")
    resultado_id = turno.get("resultado_obtenido_id")
    conversacion_id = turno.get("conversacion_actual_id")

    draft_docs = await db[COLL_CARDS].find({"_id": {"$in": draft_ids}}).to_list(None) if draft_ids else []
    evento_doc = await db[COLL_EVENTS].find_one({"_id": evento_id}) if evento_id else None
    res_doc = await db[COLL_RESULTS].find_one({"_id": resultado_id}) if resultado_id else None
    conv_doc = await db[COLL_CONVERSATIONS].find_one({"_id": conversacion_id}) if conversacion_id else None

    evento_resp = None
    if evento_doc:
        res_ids = {rp.get("resultado_id") for op in evento_doc.get("opciones", []) for rp in op.get("resultados_posibles", [])}
        res_docs = await db[COLL_RESULTS].find({"_id": {"$in": list(res_ids)}}).to_list(None) if res_ids else []
        res_dict = {r["_id"]: r for r in res_docs}
        opciones_calc = calcular_opciones_evento(evento_doc, run, res_dict)
        evento_resp = EventoTurnoResponse(
            id=evento_doc["_id"],
            titulo=evento_doc.get("titulo", ""),
            descripcion=evento_doc.get("descripcion", ""),
            imagen=evento_doc.get("imagen", ""),
            opciones=opciones_calc
        )

    return EstadoTurnoResponse(
        date=date,
        mes_actual=run.get("mes_actual", 1),
        fase_actual=run.get("fase_actual", ""),
        status=run.get("status", "in_progress"),
        recursos=run.get("recursos", {}),
        afinidad=run.get("afinidad", {}),
        cartas_draft_actual=[CartaResponse(**c) for c in draft_docs],
        evento_actual=evento_resp,
        resultado_actual=ResultadoResponse(**res_doc) if res_doc else None,
        conversacion_actual=ConversacionResponse(**conv_doc) if conv_doc else None,
        finalizacion=FinalizacionResponse(**run["finalizacion"]) if run.get("finalizacion") else None
    )

async def obtener_evento_actual_partida(user_id: int, date: str) -> Optional[EventoTurnoResponse]:
    """Retorna únicamente el evento activo del mes con sus opciones y probabilidades calculadas."""
    db = get_database()
    run = await db[COLL_RUNS].find_one({"user_id": user_id, "date": date, "game_id": "narrativo"})
    if not run:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")
    evento_id = run.get("turno_actual", {}).get("evento_actual_id")
    if not evento_id:
        return None
    evento_doc = await db[COLL_EVENTS].find_one({"_id": evento_id})
    if not evento_doc:
        return None
    res_ids = {rp.get("resultado_id") for op in evento_doc.get("opciones", []) for rp in op.get("resultados_posibles", [])}
    res_docs = await db[COLL_RESULTS].find({"_id": {"$in": list(res_ids)}}).to_list(None) if res_ids else []
    res_dict = {r["_id"]: r for r in res_docs}
    opciones_calc = calcular_opciones_evento(evento_doc, run, res_dict)
    return EventoTurnoResponse(
        id=evento_doc["_id"],
        titulo=evento_doc.get("titulo", ""),
        descripcion=evento_doc.get("descripcion", ""),
        imagen=evento_doc.get("imagen", ""),
        opciones=opciones_calc
    )

async def obtener_conversacion_actual_partida(user_id: int, date: str) -> Optional[ConversacionResponse]:
    """Retorna únicamente el diálogo de corte sorteado para el mes activo (o None si no hubo)."""
    db = get_database()
    run = await db[COLL_RUNS].find_one({"user_id": user_id, "date": date, "game_id": "narrativo"})
    if not run:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")
    conv_id = run.get("turno_actual", {}).get("conversacion_actual_id")
    if not conv_id:
        return None
    conv_doc = await db[COLL_CONVERSATIONS].find_one({"_id": conv_id})
    return ConversacionResponse(**conv_doc) if conv_doc else None

async def obtener_resultado_actual_partida(user_id: int, date: str) -> Optional[ResultadoResponse]:
    """Retorna únicamente el resultado del desenlace recién resuelto."""
    db = get_database()
    run = await db[COLL_RUNS].find_one({"user_id": user_id, "date": date, "game_id": "narrativo"})
    if not run:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")
    res_id = run.get("turno_actual", {}).get("resultado_obtenido_id")
    if not res_id:
        return None
    res_doc = await db[COLL_RESULTS].find_one({"_id": res_id})
    return ResultadoResponse(**res_doc) if res_doc else None

async def obtener_draft_actual_partida(user_id: int, date: str) -> List[CartaResponse]:
    """Retorna las 3 cartas ofrecidas en el draft del mes activo."""
    db = get_database()
    run = await db[COLL_RUNS].find_one({"user_id": user_id, "date": date, "game_id": "narrativo"})
    if not run:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")
    draft_ids = run.get("turno_actual", {}).get("cartas_ofrecidas_ids", [])
    if not draft_ids:
        return []
    docs = await db[COLL_CARDS].find({"_id": {"$in": draft_ids}}).to_list(None)
    return [CartaResponse(**d) for d in docs]
