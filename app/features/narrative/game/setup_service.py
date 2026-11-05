"""
setup_service.py
Fase 0 común a ambos motores:
- Oferta diaria de personajes y cartas para la selección inicial.
- Creación de la partida (el motor se toma del universo).
- Reinicio de la partida del día.
"""

import random
import logging
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import HTTPException

from app.core.database import get_database
from app.features.narrative.constants import (
    COLL_SETTINGS,
    COLL_CHARACTERS,
    COLL_CARDS,
    COLL_RUNS,
    COLL_RUNS_ARCHIVE,
    COLL_CHALLENGES,
)
from app.features.narrative.enums import RunPhaseEnum, DisparadorEnum
from app.features.narrative.schemas.catalog_schemas import (
    PersonajeResponse,
    CartaResponse,
    FinalizacionResponse,
)
from app.features.narrative.schemas.game_schemas import (
    IniciarPartidaRequest,
    IniciarPartidaV2Response,
    SetupDesafioResponse,
)
from app.features.narrative.schemas.rules_schemas import EfectoSchema
from app.features.narrative.engine.rule_engine import despachar_efectos, evaluar_condiciones
from app.features.narrative.engine.catalog_loader import obtener_catalogos_universo
from app.features.narrative.game.endings_service import (
    verificar_colapso_recursos,
    sincronizar_intento_usuario,
)
from app.features.narrative.game.run_repository import (
    RunAlreadyExistsError,
    archivar_run,
    crear_run,
)
from app.features.narrative.game.identity import filtro_run, id_run, resolver_identidad
from app.features.narrative.game.universe_resources import obtener_mapa_recursos_universo

logger = logging.getLogger(__name__)


async def _proxima_generacion(user_id: int, date: str) -> int:
    """La primera run es 1; tras archivar la activa, la siguiente continúa la secuencia."""
    db = get_database()
    filtro = filtro_run(user_id, date)
    activa = await db[COLL_RUNS].find_one(filtro, {"generation": 1})
    if activa:
        return int(activa.get("generation") or 1)

    archivada = await db[COLL_RUNS_ARCHIVE].find_one(
        filtro,
        {"generation": 1},
        sort=[("generation", -1)],
    )
    return int((archivada or {}).get("generation") or 0) + 1


def _respuesta_inicio(
    run: Dict[str, Any],
    cartas_draft_actual: list,
    puntos_ganados: int | None = None,
) -> IniciarPartidaV2Response:
    fin_resp = FinalizacionResponse(**run["finalizacion"]) if run.get("finalizacion") else None
    return IniciarPartidaV2Response(
        mes_actual=run["mes_actual"],
        fase_actual=run["fase_actual"],
        recursos=run["recursos"],
        afinidad=run["afinidad"],
        cartas_draft_actual=cartas_draft_actual,
        finalizacion=fin_resp,
        motor=run.get("motor", "v1"),
        puntos_ganados=puntos_ganados,
    )


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

    estado_eval = run_activa or {
        "recursos": cfg.get("atributos_iniciales", {}),
        "afinidad": {},
        "corte_activa": [],
        "tags_activos": [],
        "cartas_en_mano": [],
    }

    # Filtrar personajes y cartas que cumplan condiciones_aparicion
    p_elegibles = [p for p in personajes_docs if evaluar_condiciones(p.get("condiciones_aparicion", []), estado_eval)]
    if len(p_elegibles) >= 3:
        personajes_docs = p_elegibles

    c_elegibles = [c for c in cartas_docs if evaluar_condiciones(c.get("condiciones_aparicion", []), estado_eval)]
    if len(c_elegibles) >= 3:
        cartas_docs = c_elegibles

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


async def iniciar_partida(user_id: int, req: IniciarPartidaRequest) -> IniciarPartidaV2Response:
    """
    Fase 0: Inicializa la partida con 3 miembros de corte y 3 cartas de apoyo.
    Retorna los recursos iniciales, las 3 cartas de draft del Mes 1 y el motor del universo.
    """
    db = get_database()

    run = await db[COLL_RUNS].find_one(filtro_run(user_id, req.date))
    if not run:
        challenge = await db[COLL_CHALLENGES].find_one({"game_id": "narrativo", "date": req.date})
        if not challenge:
            raise HTTPException(status_code=404, detail=f"No existe desafío narrativo para la fecha {req.date}.")

        cfg = challenge.get("config", {})
        universo_id = cfg.get("universo_id")

        universo_doc = await db[COLL_SETTINGS].find_one({"_id": universo_id})
        motor = universo_doc.get("motor", "v1") if universo_doc else "v1"

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

        recursos_mapa = await obtener_mapa_recursos_universo(universo_id)
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

        generation = await _proxima_generacion(user_id, req.date)
        run = {
            "_id": id_run(user_id, req.date, generation),
            "user_id": resolver_identidad(user_id)[0],
            "date": req.date,
            "game_id": "narrativo",
            "generation": generation,
            "universo_id": universo_id,
            "motor": motor,
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
                "conversacion_actual_id": None,
            },
            "eventos_jugados": [],
            "conversaciones_jugadas": [],
            "historial_mensual": [],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        guest_id = resolver_identidad(user_id)[1]
        if guest_id:
            run["guest_id"] = guest_id

        # Inicializar tracking de adquisiciones relativas y modificadores
        run["adquisiciones"] = {}
        for p in personajes_docs:
            run["adquisiciones"][str(p["_id"])] = {"mes": 1, "tipo": "personaje"}
        for c in cartas_docs:
            run["adquisiciones"][str(c["_id"])] = {"mes": 1, "tipo": "carta"}
        run["modificadores_pasivos"] = []
        run["limites"] = {
            k: {"min": r.get("min", 0), "max": r.get("max", 100)}
            for k, r in recursos_mapa.items()
        }
        run["variables"] = {}

        cat_acciones, cat_frecuencias = await obtener_catalogos_universo(universo_id, db)

        for p in personajes_docs:
            efectos_p = [EfectoSchema(**e) for e in p.get("efectos", [])]
            despachar_efectos(
                DisparadorEnum.AL_OBTENER,
                run,
                efectos_p,
                recursos_mapa,
                duenio_id=str(p["_id"]),
                mes_actual=1,
                catalogo_acciones=cat_acciones,
                catalogo_frecuencias=cat_frecuencias,
            )

        for c in cartas_docs:
            efectos_c = [EfectoSchema(**e) for e in c.get("efectos", [])]
            despachar_efectos(
                DisparadorEnum.AL_OBTENER,
                run,
                efectos_c,
                recursos_mapa,
                duenio_id=str(c["_id"]),
                mes_actual=1,
                catalogo_acciones=cat_acciones,
                catalogo_frecuencias=cat_frecuencias,
            )

        derrota = await verificar_colapso_recursos(run)
        if not derrota:
            pool_mensuales = cfg.get("pool_cartas_mensuales_ids", [])
            disponibles = [cid for cid in pool_mensuales if cid not in run.get("cartas_en_mano", [])]
            if len(disponibles) < 3:
                disponibles = pool_mensuales

            cartas_docs_map = {c["_id"]: c for c in await db[COLL_CARDS].find({"_id": {"$in": disponibles}}).to_list(None)}
            elegibles = [
                cid for cid in disponibles
                if evaluar_condiciones(cartas_docs_map.get(cid, {}).get("condiciones_aparicion", []), run)
            ]
            candidatas = elegibles if len(elegibles) >= 3 else (elegibles + [cid for cid in disponibles if cid not in elegibles])
            cartas_ofrecidas_mes = random.sample(candidatas, min(3, len(candidatas)))
            run["turno_actual"]["cartas_ofrecidas_ids"] = cartas_ofrecidas_mes

        try:
            await crear_run(run)
        except RunAlreadyExistsError:
            run = await db[COLL_RUNS].find_one(filtro_run(user_id, req.date))
            if not run:
                raise HTTPException(
                    status_code=409,
                    detail="Otra petición creó la partida; recargá el estado antes de reintentar.",
                )
        else:
            if derrota:
                puntos_ganados = await sincronizar_intento_usuario(run)
                return _respuesta_inicio(run, [], puntos_ganados)

    draft_ids = run.get("turno_actual", {}).get("cartas_ofrecidas_ids", [])
    draft_docs = await db[COLL_CARDS].find({"_id": {"$in": draft_ids}}).to_list(None) if draft_ids else []
    cartas_draft_resp = [CartaResponse(**c) for c in draft_docs]
    return _respuesta_inicio(run, cartas_draft_resp)


async def reiniciar_partida(
    user_id: int,
    date: str,
    expected_version: int | None = None,
) -> Dict[str, Any]:
    """Archiva la generación activa y habilita una nueva sin borrar su evidencia."""
    db = get_database()
    run = await db[COLL_RUNS].find_one(filtro_run(user_id, date))
    if not run:
        return {
            "success": False,
            "message": f"No hay una partida activa para reiniciar el {date}.",
            "eliminada": False,
            "previous_run_id": None,
            "next_generation": None,
        }

    generacion_anterior = int(run.get("generation") or 1)
    await archivar_run(run, expected_version)
    return {
        "success": True,
        "message": f"Partida del {date} reiniciada con una nueva generación.",
        "eliminada": True,
        "previous_run_id": run["_id"],
        "next_generation": generacion_anterior + 1,
    }
