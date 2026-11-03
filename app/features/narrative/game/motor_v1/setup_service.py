"""
setup_service.py (Motor V1)
Fase 0 legacy: consulta de la oferta diaria de personajes y cartas, y reinicio de partida.
"""

import logging
from typing import Dict, Any

from fastapi import HTTPException

from app.core.database import get_database
from app.features.narrative.constants import (
    COLL_SETTINGS,
    COLL_CHARACTERS,
    COLL_CARDS,
    COLL_RUNS,
    COLL_CHALLENGES,
)
from app.features.narrative.schemas.catalog_schemas import (
    PersonajeResponse,
    CartaResponse,
)
from app.features.narrative.schemas.game_schemas import SetupDesafioResponse
from app.features.narrative.game.identity import filtro_run

logger = logging.getLogger(__name__)


async def obtener_setup_desafio(user_id: int, date: str) -> SetupDesafioResponse:
    """Retorna los 5 personajes y 5 cartas ofrecidas para la selección inicial (Fase 0)."""
    db = get_database()
    challenge = await db[COLL_CHALLENGES].find_one({"game_id": "narrativo", "date": date})
    if not challenge:
        raise HTTPException(
            status_code=404,
            detail=f"No se ha configurado el desafío narrativo para la fecha {date}.",
        )

    cfg = challenge.get("config", {})
    universo_id = cfg.get("universo_id")

    universo_doc = await db[COLL_SETTINGS].find_one({"_id": universo_id})
    if not universo_doc:
        raise HTTPException(status_code=404, detail=f"El universo '{universo_id}' no existe.")

    p_ids = cfg.get("setup_corte_ofrecidos_ids", [])
    personajes_docs = await db[COLL_CHARACTERS].find({"_id": {"$in": p_ids}}).to_list(length=10)

    c_ids = cfg.get("setup_cartas_ofrecidas_ids", [])
    cartas_docs = await db[COLL_CARDS].find({"_id": {"$in": c_ids}}).to_list(length=10)

    run_activa = await db[COLL_RUNS].find_one(filtro_run(user_id, date))

    return SetupDesafioResponse(
        date=date,
        universo_id=universo_id,
        universo_nombre=universo_doc.get("nombre", universo_id),
        universo_descripcion=universo_doc.get("descripcion", ""),
        atributos_iniciales=cfg.get("atributos_iniciales", {}),
        personajes_ofrecidos=[PersonajeResponse(**p) for p in personajes_docs],
        cartas_ofrecidas=[CartaResponse(**c) for c in cartas_docs],
        tiene_partida_activa=bool(run_activa),
        fase_partida_activa=run_activa.get("fase_actual") if run_activa else None,
    )


async def reiniciar_partida(user_id: int, date: str) -> Dict[str, Any]:
    """Elimina la run del día para reiniciar la partida limpia desde Fase 0."""
    db = get_database()
    res = await db[COLL_RUNS].delete_one(filtro_run(user_id, date))
    return {
        "success": True,
        "message": f"Partida del {date} reiniciada con éxito.",
        "eliminada": res.deleted_count > 0,
    }
