"""
v2_graph_service.py
Servicio de orquestación de partidas para el Motor Narrativo Genérico V2 (Grafos).
Maneja la consulta del estado reactivo del grafo activo y la transición paso a paso (avanzar-nodo).
"""

import logging
from typing import Optional, Dict, Any
from fastapi import HTTPException

from app.core.database import get_database
from app.features.narrative.constants import (
    COLL_RUNS
)
from app.features.narrative.enums import RunPhaseEnum
from app.features.narrative.schemas.v2_graph_schemas import (
    AvanzarNodoV2Request,
    EstadoGrafoV2Response,
    NodoNarrativoSchema
)
from app.features.narrative.game.motor_v2.graph_engine import graph_engine
from app.features.narrative.game.identity import filtro_run
from app.features.narrative.game.run_repository import persistir_run

logger = logging.getLogger(__name__)

_FASES_EVENTO = {RunPhaseEnum.TOMA_DECISION_EVENTO.value}
_FASES_CONVERSACION = {RunPhaseEnum.RESOLVER_CONVERSACION.value}


async def _obtener_run_activo(user_id: int, date: str) -> Dict[str, Any]:
    db = get_database()
    run = await db[COLL_RUNS].find_one(filtro_run(user_id, date))
    if not run:
        raise HTTPException(status_code=404, detail="Partida no encontrada para la fecha especificada.")
    return run


def _exigir_partida_v2_en_fase(
    run: Dict[str, Any],
    *,
    fases_permitidas: set,
    accion: str,
    exigir_sin_grafo: bool = True
) -> None:
    """Rechaza con 409 cualquier intento de operar un grafo fuera del estado permitido."""
    motor = run.get("motor", "v1")
    if motor != "v2":
        raise HTTPException(
            status_code=409,
            detail=f"'{accion}' requiere una partida con motor v2 (motor actual: '{motor}')."
        )

    status = run.get("status", "in_progress")
    if status != "in_progress":
        raise HTTPException(
            status_code=409,
            detail=f"'{accion}' no está disponible: la partida no está en curso (status: '{status}')."
        )

    fase = run.get("fase_actual")
    if fase not in fases_permitidas:
        fases = ", ".join(sorted(fases_permitidas))
        raise HTTPException(
            status_code=409,
            detail=f"'{accion}' no está disponible en la fase '{fase}' (fases permitidas: {fases})."
        )

    if exigir_sin_grafo and run.get("grafo_activo"):
        raise HTTPException(
            status_code=409,
            detail=f"'{accion}' no puede ejecutarse: ya hay un grafo activo en la partida."
        )

async def obtener_grafo_actual_v2(user_id: int, date: str) -> Optional[EstadoGrafoV2Response]:
    """
    Retorna el estado del nodo activo en el que se encuentra el jugador (para F5 o recargas).
    Si no hay ningún grafo activo en la partida, retorna None.
    """
    run = await _obtener_run_activo(user_id, date)
    return await proyectar_grafo_actual(run)


async def proyectar_grafo_actual(run: Dict[str, Any]) -> Optional[EstadoGrafoV2Response]:
    """Proyecta el grafo desde una copia de run ya leída, sin volver a consultar por usuario/fecha."""
    grafo_activo = run.get("grafo_activo")
    if not grafo_activo:
        return None

    tipo = grafo_activo["tipo"]
    grafo_id = grafo_activo["grafo_id"]
    nodo_actual_id = grafo_activo["nodo_actual_id"]

    grafo = await graph_engine.obtener_grafo(tipo, grafo_id)
    if not grafo:
        return None

    nodos = grafo.get("nodos", {})
    nodo_data = nodos.get(nodo_actual_id)
    if not nodo_data:
        return None

    nodo_schema = NodoNarrativoSchema(**nodo_data)
    nodo_cliente = nodo_schema.to_cliente_schema(run)

    return EstadoGrafoV2Response(
        fase_actual=run.get("fase_actual", RunPhaseEnum.TOMA_DECISION_EVENTO.value),
        grafo_id=grafo_id,
        tipo=tipo,
        titulo=grafo.get("titulo", ""),
        imagen=grafo.get("imagen", ""),
        nodo_actual=nodo_cliente,
        afinidad=run.get("afinidad") if nodo_schema.es_final else None,
        recursos=run.get("recursos") if nodo_schema.es_final else None,
        status=run.get("status", "CONTINUA")
    )

async def avanzar_nodo_v2(user_id: int, req: AvanzarNodoV2Request) -> EstadoGrafoV2Response:
    """
    Avanza un paso en el grafo activo de la partida.
    """
    run = await _obtener_run_activo(user_id, req.date)

    if run.get("motor", "v1") != "v2":
        raise HTTPException(
            status_code=409,
            detail="'avanzar-nodo' requiere una partida con motor v2."
        )

    if run.get("status", "in_progress") != "in_progress" or run.get("fase_actual") == RunPhaseEnum.FINALIZADA.value:
        raise HTTPException(
            status_code=409,
            detail="'avanzar-nodo' no está disponible: la partida ya se encuentra finalizada."
        )

    if not run.get("grafo_activo"):
        raise HTTPException(
            status_code=409,
            detail="'avanzar-nodo' no está disponible: no hay ningún evento o conversación activo."
        )

    return await graph_engine.avanzar_nodo(run, req.opcion_id)

async def iniciar_evento_mes_v2(user_id: int, date: str) -> EstadoGrafoV2Response:
    """
    Inicia un evento V2 para el mes actual de la partida, sorteando de narrative_v2_events por universo.
    """
    run = await _obtener_run_activo(user_id, date)
    _exigir_partida_v2_en_fase(
        run,
        fases_permitidas=_FASES_EVENTO,
        accion="iniciar-evento-grafo"
    )

    evento = await graph_engine.sortear_evento_v2(
        run=run,
        pool_ids=None,
        universo_id=run.get("universo_id", "corte_medieval")
    )

    if not evento:
        raise HTTPException(
            status_code=404,
            detail="No se encontraron eventos V2 disponibles o elegibles para sortear."
        )

    estado = await graph_engine.iniciar_grafo_en_partida(
        run=run,
        grafo=evento,
        tipo="evento",
        fase=RunPhaseEnum.TOMA_DECISION_EVENTO.value
    )
    await persistir_run(run)
    return estado

async def iniciar_conversacion_mes_v2(user_id: int, date: str) -> Optional[EstadoGrafoV2Response]:
    """
    Inicia una conversación V2 si los requisitos de corte se cumplen.
    """
    run = await _obtener_run_activo(user_id, date)
    _exigir_partida_v2_en_fase(
        run,
        fases_permitidas=_FASES_CONVERSACION,
        accion="iniciar-conversacion-grafo"
    )

    conv = await graph_engine.sortear_conversacion_v2(
        run=run,
        pool_ids=None,
        universo_id=run.get("universo_id", "corte_medieval")
    )

    if not conv:
        return None

    estado = await graph_engine.iniciar_grafo_en_partida(
        run=run,
        grafo=conv,
        tipo="conversacion",
        fase=RunPhaseEnum.RESOLVER_CONVERSACION.value
    )
    await persistir_run(run)
    return estado
