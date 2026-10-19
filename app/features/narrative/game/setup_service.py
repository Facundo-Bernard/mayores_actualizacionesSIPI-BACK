"""
setup_service.py
Gestión de la Fase 0 (Setup Diario):
- Configuración de recursos del universo y caché en memoria.
- Consulta de oferta inicial de 5 personajes y 5 cartas para el día.
- Reinicio de partidas limpias.
- Inicialización V2 de partida eligiendo 3 consejeros y 3 cartas de apoyo iniciales.
"""

import random
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import HTTPException

from app.core.database import get_database
from app.features.narrative.constants import (
    COLL_SETTINGS,
    COLL_CHARACTERS,
    COLL_CARDS,
    COLL_RUNS,
    COLL_CHALLENGES
)
from app.features.narrative.enums import (
    RunPhaseEnum,
    DisparadorEnum
)
from app.features.narrative.schemas.catalog_schemas import (
    PersonajeResponse,
    CartaResponse,
    FinalizacionResponse
)
from app.features.narrative.schemas.game_schemas import (
    SetupDesafioResponse,
    IniciarPartidaRequest,
    IniciarPartidaV2Response
)
from app.features.narrative.schemas.rules_schemas import EfectoSchema
from app.features.narrative.engine.rule_engine import despachar_efectos
from app.features.narrative.game.endings_service import (
    verificar_colapso_recursos,
    sincronizar_intento_usuario
)

logger = logging.getLogger(__name__)

# ============================================================================
# CACHÉ EN MEMORIA DE METADATOS DE RECURSOS POR UNIVERSO
# ============================================================================

_RECURSOS_MAPA_CACHE: Dict[str, Dict[str, Dict[str, Any]]] = {}

def invalidar_cache_recursos_universo(universo_id: Optional[str] = None):
    """Invalida la caché de metadatos de recursos para un universo o todos."""
    if universo_id and universo_id in _RECURSOS_MAPA_CACHE:
        _RECURSOS_MAPA_CACHE.pop(universo_id, None)
    else:
        _RECURSOS_MAPA_CACHE.clear()

async def _obtener_mapa_recursos_universo(universo_id: str) -> Dict[str, Dict[str, Any]]:
    """Carga los límites (min, max) y metadatos de recursos configurados para el universo (con caché en memoria)."""
    if universo_id in _RECURSOS_MAPA_CACHE:
        return _RECURSOS_MAPA_CACHE[universo_id]

    db = get_database()
    u = await db[COLL_SETTINGS].find_one({"_id": universo_id})
    if not u or "recursos" not in u:
        return {}
    mapa = {r["clave"]: r for r in u["recursos"]}
    _RECURSOS_MAPA_CACHE[universo_id] = mapa
    return mapa

# ============================================================================
# SETUP DIARIO Y REINICIO
# ============================================================================

async def obtener_setup_desafio(user_id: int, date: str) -> SetupDesafioResponse:
    """Retorna los 5 personajes y 5 cartas ofrecidas para la selección inicial (Fase 0)."""
    db = get_database()
    challenge = await db[COLL_CHALLENGES].find_one({"game_id": "narrativo", "date": date})
    if not challenge:
        raise HTTPException(
            status_code=404,
            detail=f"No se ha configurado el desafío narrativo para la fecha {date}."
        )

    cfg = challenge.get("config", {})
    universo_id = cfg.get("universo_id")

    universo_doc = await db[COLL_SETTINGS].find_one({"_id": universo_id})
    if not universo_doc:
        raise HTTPException(status_code=404, detail=f"El universo '{universo_id}' no existe.")

    # Cargar los 5 personajes ofrecidos
    p_ids = cfg.get("setup_corte_ofrecidos_ids", [])
    personajes_docs = await db[COLL_CHARACTERS].find({"_id": {"$in": p_ids}}).to_list(length=10)

    # Cargar las 5 cartas ofrecidas
    c_ids = cfg.get("setup_cartas_ofrecidas_ids", [])
    cartas_docs = await db[COLL_CARDS].find({"_id": {"$in": c_ids}}).to_list(length=10)

    # Verificar si el alumno ya tiene una partida iniciada para este día
    run_activa = await db[COLL_RUNS].find_one({"user_id": user_id, "date": date, "game_id": "narrativo"})

    return SetupDesafioResponse(
        date=date,
        universo_id=universo_id,
        universo_nombre=universo_doc.get("nombre", universo_id),
        universo_descripcion=universo_doc.get("descripcion", ""),
        atributos_iniciales=cfg.get("atributos_iniciales", {}),
        personajes_ofrecidos=[PersonajeResponse(**p) for p in personajes_docs],
        cartas_ofrecidas=[CartaResponse(**c) for c in cartas_docs],
        tiene_partida_activa=bool(run_activa),
        fase_partida_activa=run_activa.get("fase_actual") if run_activa else None
    )

async def reiniciar_partida(user_id: int, date: str) -> Dict[str, Any]:
    """Elimina la run del día para reiniciar la partida limpia desde Fase 0."""
    db = get_database()
    res = await db[COLL_RUNS].delete_one({"user_id": user_id, "date": date, "game_id": "narrativo"})
    return {
        "success": True,
        "message": f"Partida del {date} reiniciada con éxito.",
        "eliminada": res.deleted_count > 0
    }

# ============================================================================
# FASE 0: INICIALIZACIÓN V2 DE LA PARTIDA
# ============================================================================

async def iniciar_partida_v2(user_id: int, req: IniciarPartidaRequest) -> IniciarPartidaV2Response:
    """
    [V2 Nativo] Fase 0: Inicializa la partida con 3 miembros de corte y 3 cartas de apoyo.
    Retorna únicamente los recursos iniciales y las 3 cartas de draft del Mes 1.
    """
    db = get_database()

    # 1. Verificar si ya existe run activa
    run = await db[COLL_RUNS].find_one({"user_id": user_id, "date": req.date, "game_id": "narrativo"})
    if not run:
        # Obtener desafío diario
        challenge = await db[COLL_CHALLENGES].find_one({"game_id": "narrativo", "date": req.date})
        if not challenge:
            raise HTTPException(status_code=404, detail=f"No existe desafío narrativo para la fecha {req.date}.")

        cfg = challenge.get("config", {})
        universo_id = cfg.get("universo_id")

        # Validaciones de regla 3 de 5
        if len(req.corte_elegida_ids) != 3:
            raise HTTPException(status_code=400, detail="Debes seleccionar exactamente 3 personajes para la corte.")
        if len(req.cartas_iniciales_ids) != 3:
            raise HTTPException(status_code=400, detail="Debes seleccionar exactamente 3 cartas de apoyo iniciales.")

        for pid in req.corte_elegida_ids:
            if pid not in cfg.get("setup_corte_ofrecidos_ids", []):
                raise HTTPException(status_code=400, detail=f"El personaje '{pid}' no estaba en la oferta inicial.")

        for cid in req.cartas_iniciales_ids:
            if cid not in cfg.get("setup_cartas_ofrecidas_ids", []):
                raise HTTPException(status_code=400, detail=f"La carta '{cid}' no estaba en la oferta inicial.")

        # Cargar límites de recursos y entidades iniciales
        recursos_mapa = await _obtener_mapa_recursos_universo(universo_id)
        recursos_actuales = dict(cfg.get("atributos_iniciales", {}))

        personajes_docs = await db[COLL_CHARACTERS].find(
            {"_id": {"$in": req.corte_elegida_ids}}
        ).to_list(None)
        cartas_docs = await db[COLL_CARDS].find(
            {"_id": {"$in": req.cartas_iniciales_ids}}
        ).to_list(None)

        afinidades = {p["_id"]: p.get("afinidad_inicial", 50) for p in personajes_docs}
        tags_activos = set()
        for c in cartas_docs:
            for t in c.get("tags", []):
                tags_activos.add(t)

        run = {
            "_id": f"run_{user_id}_{req.date}",
            "user_id": user_id,
            "date": req.date,
            "game_id": "narrativo",
            "universo_id": universo_id,
            "mes_actual": 1,
            "fase_actual": RunPhaseEnum.DRAFT_MENSUAL.value,
            "status": "in_progress",
            "recursos": recursos_actuales,
            "afinidad": afinidades,
            "cartas_en_mano": req.cartas_iniciales_ids,
            "tags_activos": list(tags_activos),
            "turno_actual": {
                "cartas_ofrecidas_ids": [],
                "carta_elegida_id": None,
                "evento_actual_id": None,
                "opcion_elegida_id": None,
                "resultado_obtenido_id": None,
                "conversacion_actual_id": None
            },
            "eventos_jugados": [],
            "conversaciones_jugadas": [],
            "historial_mensual": [],
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        # Aplicar efectos "al_obtener" de la corte y cartas iniciales
        for p in personajes_docs:
            efectos_p = [EfectoSchema(**e) for e in p.get("efectos", [])]
            despachar_efectos(DisparadorEnum.AL_OBTENER, run, efectos_p, recursos_mapa)

        for c in cartas_docs:
            efectos_c = [EfectoSchema(**e) for e in c.get("efectos", [])]
            despachar_efectos(DisparadorEnum.AL_OBTENER, run, efectos_c, recursos_mapa)

        # Si colapsó recurso con las cartas iniciales:
        derrota = await verificar_colapso_recursos(run)
        if derrota:
            await db[COLL_RUNS].replace_one({"_id": run["_id"]}, run, upsert=True)
            await sincronizar_intento_usuario(run)
            fin_resp = FinalizacionResponse(**run["finalizacion"]) if run.get("finalizacion") else None
            return IniciarPartidaV2Response(
                mes_actual=run["mes_actual"],
                fase_actual=run["fase_actual"],
                recursos=run["recursos"],
                afinidad=run["afinidad"],
                cartas_draft_actual=[],
                finalizacion=fin_resp
            )

        # Sortear las 3 cartas para el Draft del Mes 1
        pool_mensuales = cfg.get("pool_cartas_mensuales_ids", [])
        cartas_ofrecidas_mes = random.sample(pool_mensuales, min(3, len(pool_mensuales)))
        run["turno_actual"]["cartas_ofrecidas_ids"] = cartas_ofrecidas_mes
        await db[COLL_RUNS].replace_one({"_id": run["_id"]}, run, upsert=True)

    # Cargar ÚNICAMENTE las 3 cartas del draft actual para responder al frontend V2
    draft_ids = run.get("turno_actual", {}).get("cartas_ofrecidas_ids", [])
    draft_docs = await db[COLL_CARDS].find({"_id": {"$in": draft_ids}}).to_list(None) if draft_ids else []
    cartas_draft_resp = [CartaResponse(**c) for c in draft_docs]

    fin_resp = FinalizacionResponse(**run["finalizacion"]) if run.get("finalizacion") else None
    return IniciarPartidaV2Response(
        mes_actual=run["mes_actual"],
        fase_actual=run["fase_actual"],
        recursos=run["recursos"],
        afinidad=run["afinidad"],
        cartas_draft_actual=cartas_draft_resp,
        finalizacion=fin_resp
    )
