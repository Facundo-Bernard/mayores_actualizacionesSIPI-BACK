"""Estado común del turno para recargas/F5: expone el motor activo y el grafo V2 si lo hubiera."""

from fastapi import HTTPException

from app.core.database import get_database
from app.features.narrative.constants import (
    COLL_CARDS,
    COLL_RESULTS,
    COLL_EVENTS,
    COLL_CONVERSATIONS,
    COLL_RUNS,
)
from app.features.narrative.schemas.catalog_schemas import (
    CartaResponse,
    ResultadoResponse,
    ConversacionResponse,
    FinalizacionResponse,
)
from app.features.narrative.schemas.game_schemas import (
    EventoTurnoResponse,
    EstadoTurnoResponse,
)
from app.features.narrative.engine.event_director import calcular_opciones_evento
from app.features.narrative.game.motor_v2.v2_graph_service import obtener_grafo_actual_v2
from app.features.narrative.game.identity import filtro_run


async def obtener_turno_actual(user_id: int, date: str) -> EstadoTurnoResponse:
    """Retorna el estado reactivo del turno actual para sincronización de frontend o recarga F5."""
    db = get_database()
    run = await db[COLL_RUNS].find_one(filtro_run(user_id, date))
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
            opciones=opciones_calc,
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
        finalizacion=FinalizacionResponse(**run["finalizacion"]) if run.get("finalizacion") else None,
        grafo_actual=await obtener_grafo_actual_v2(user_id, date),
        motor=run.get("motor", "v1"),
    )
