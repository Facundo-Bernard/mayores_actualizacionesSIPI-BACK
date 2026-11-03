"""
modals_service.py
Consultas de lectura comunes a ambos motores:
- Modal de la bitácora mensual (historial).
- Modal de inventario (cartas en mano y tags activos).
- Modal de corte activa (personajes asignados y afinidad).
- Modal de epílogo / finalización detallada.
"""

import logging

from fastapi import HTTPException

from app.core.database import get_database
from app.features.narrative.constants import (
    COLL_CHARACTERS,
    COLL_CARDS,
    COLL_RUNS
)
from app.features.narrative.schemas.catalog_schemas import (
    PersonajeResponse,
    CartaResponse,
    FinalizacionResponse
)
from app.features.narrative.schemas.game_schemas import (
    HistorialPartidaResponse,
    InventarioPartidaResponse,
    PersonajeCorteDetalle,
    CortePartidaResponse,
    FinalizacionPartidaResponse,
)
from app.features.narrative.game.identity import filtro_run

logger = logging.getLogger(__name__)

async def obtener_historial_partida(user_id: int, date: str) -> HistorialPartidaResponse:
    """Consulta la bitácora mensual acumulada de los meses transcurridos en la partida."""
    db = get_database()
    run = await db[COLL_RUNS].find_one(filtro_run(user_id, date))
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
    run = await db[COLL_RUNS].find_one(filtro_run(user_id, date))
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
    run = await db[COLL_RUNS].find_one(filtro_run(user_id, date))
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
    run = await db[COLL_RUNS].find_one(filtro_run(user_id, date))
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
