"""
modals.py (Motor V1)
Consultas atómicas del motor plano: evento, diálogo, resultado y draft activo.
Estas rutas quedan deprecadas cuando el universo migra al motor de grafos V2.
"""

import logging
from typing import Optional, List

from fastapi import HTTPException

from app.core.database import get_database
from app.features.narrative.constants import (
    COLL_CARDS,
    COLL_RESULTS,
    COLL_EVENTS,
    COLL_CONVERSATIONS,
    COLL_RUNS
)
from app.features.narrative.schemas.catalog_schemas import (
    CartaResponse,
    ResultadoResponse,
    ConversacionResponse
)
from app.features.narrative.schemas.game_schemas import EventoTurnoResponse
from app.features.narrative.engine.event_director import calcular_opciones_evento
from app.features.narrative.game.identity import filtro_run

logger = logging.getLogger(__name__)

_AVISOS_EMITIDOS: set[str] = set()


def _avisar_deprecado(nombre: str) -> None:
    if nombre not in _AVISOS_EMITIDOS:
        _AVISOS_EMITIDOS.add(nombre)
        logger.warning(
            "Endpoint plano V1 '%s' en desuso; se retirará cuando los universos migren a V2.",
            nombre,
        )


async def obtener_evento_actual_partida(user_id: int, date: str) -> Optional[EventoTurnoResponse]:
    """Retorna únicamente el evento activo del mes con sus opciones y probabilidades calculadas."""
    _avisar_deprecado("evento-actual")
    db = get_database()
    run = await db[COLL_RUNS].find_one(filtro_run(user_id, date))
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
    _avisar_deprecado("conversacion-actual")
    db = get_database()
    run = await db[COLL_RUNS].find_one(filtro_run(user_id, date))
    if not run:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")
    conv_id = run.get("turno_actual", {}).get("conversacion_actual_id")
    if not conv_id:
        return None
    conv_doc = await db[COLL_CONVERSATIONS].find_one({"_id": conv_id})
    return ConversacionResponse(**conv_doc) if conv_doc else None

async def obtener_resultado_actual_partida(user_id: int, date: str) -> Optional[ResultadoResponse]:
    """Retorna únicamente el resultado del desenlace recién resuelto."""
    _avisar_deprecado("resultado-actual")
    db = get_database()
    run = await db[COLL_RUNS].find_one(filtro_run(user_id, date))
    if not run:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")
    res_id = run.get("turno_actual", {}).get("resultado_obtenido_id")
    if not res_id:
        return None
    res_doc = await db[COLL_RESULTS].find_one({"_id": res_id})
    return ResultadoResponse(**res_doc) if res_doc else None

async def obtener_draft_actual_partida(user_id: int, date: str) -> List[CartaResponse]:
    """Retorna las 3 cartas ofrecidas en el draft del mes activo."""
    _avisar_deprecado("draft-actual")
    db = get_database()
    run = await db[COLL_RUNS].find_one(filtro_run(user_id, date))
    if not run:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")
    draft_ids = run.get("turno_actual", {}).get("cartas_ofrecidas_ids", [])
    if not draft_ids:
        return []
    docs = await db[COLL_CARDS].find({"_id": {"$in": draft_ids}}).to_list(None)
    return [CartaResponse(**d) for d in docs]
