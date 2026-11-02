"""Concurrencia optimista e historial V2 de las partidas narrativas."""

import pytest
from fastapi import HTTPException

from app.features.narrative.constants import (
    COLL_CHALLENGES,
    COLL_RUNS,
    COLL_V2_EVENTOS_ESPECIALES,
)
from app.features.narrative.game.run_repository import persistir_run

pytestmark = pytest.mark.contract

DATE = "2099-04-20"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _nodo(nodo_id: str, *, es_final: bool, siguiente: str | None = None) -> dict:
    return {
        "id": nodo_id,
        "hablante_id": "narrador",
        "texto": f"Texto {nodo_id}",
        "es_final": es_final,
        "opciones": (
            []
            if es_final
            else [{"id": f"opt_{nodo_id}", "texto": "Continuar", "siguiente_nodo": siguiente}]
        ),
        "resultado_texto": "Desenlace de prueba" if es_final else "",
        "impactos_recursos": [],
        "impactos_afinidad": [],
        "impactos_tags": [],
    }


async def _seed_run(db, cleanup, *, user_id: int, **extra) -> dict:
    run = {
        "_id": f"run_hist_{user_id}_{DATE}",
        "user_id": user_id,
        "date": DATE,
        "game_id": "narrativo",
        "universo_id": f"universo_hist_{user_id}",
        "motor": "v2",
        "mes_actual": 3,
        "fase_actual": "TOMA_DECISION_EVENTO",
        "status": "in_progress",
        "recursos": {"oro": 50, "pueblo": 50, "ejercito": 50, "fe": 50},
        "afinidad": {"pj_hist": 50},
        "cartas_en_mano": [],
        "tags_activos": [],
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
        "grafo_activo": None,
    }
    run.update(extra)
    await db[COLL_RUNS].replace_one({"_id": run["_id"]}, run, upsert=True)
    cleanup.add(COLL_RUNS, {"_id": run["_id"]})
    return run


@pytest.mark.asyncio
async def test_persistir_run_rechaza_version_obsoleta(test_db, cleanup):
    run = {"_id": "run_version_stale", "version": 3, "recursos": {"oro": 50}}
    await test_db[COLL_RUNS].replace_one({"_id": run["_id"]}, run, upsert=True)
    cleanup.add(COLL_RUNS, {"_id": run["_id"]})

    await test_db[COLL_RUNS].update_one({"_id": run["_id"]}, {"$set": {"version": 4}})
    run["recursos"]["oro"] = 10

    with pytest.raises(HTTPException) as exc:
        await persistir_run(run)

    assert exc.value.status_code == 409
    guardado = await test_db[COLL_RUNS].find_one({"_id": run["_id"]})
    assert guardado["recursos"]["oro"] == 50


@pytest.mark.asyncio
async def test_persistir_run_acepta_documento_legacy_sin_version(test_db, cleanup):
    run = {"_id": "run_version_legacy", "recursos": {"oro": 50}}
    await test_db[COLL_RUNS].replace_one({"_id": run["_id"]}, run, upsert=True)
    cleanup.add(COLL_RUNS, {"_id": run["_id"]})

    run["recursos"]["oro"] = 40
    await persistir_run(run)

    guardado = await test_db[COLL_RUNS].find_one({"_id": run["_id"]})
    assert guardado["version"] == 1
    assert guardado["recursos"]["oro"] == 40


@pytest.mark.asyncio
async def test_historial_v2_registra_decision_y_desenlace(
    client, test_db, cleanup, make_token, seeded_challenge
):
    user_id = 820001
    universo_id = f"universo_hist_{user_id}"
    grafo = {
        "_id": f"esp_hist_{user_id}",
        "universo_id": universo_id,
        "personaje_id": "pj_hist",
        "direccion": "lealtad",
        "titulo": "Evento especial historial",
        "nodo_raiz": "nodo_inicio",
        "nodos": {
            "nodo_inicio": _nodo("nodo_inicio", es_final=False, siguiente="nodo_fin"),
            "nodo_fin": _nodo("nodo_fin", es_final=True),
        },
    }
    await test_db[COLL_V2_EVENTOS_ESPECIALES].replace_one({"_id": grafo["_id"]}, grafo, upsert=True)
    cleanup.add(COLL_V2_EVENTOS_ESPECIALES, {"_id": grafo["_id"]})

    await _seed_run(
        test_db,
        cleanup,
        user_id=user_id,
        grafo_activo={
            "tipo": "evento_especial",
            "grafo_id": grafo["_id"],
            "nodo_actual_id": "nodo_inicio",
        },
    )
    await seeded_challenge(
        game_id="narrativo",
        date=DATE,
        difficulty="normal",
        config={"pool_cartas_mensuales_ids": []},
    )

    headers = _auth(make_token(user_id))
    avance = await client.post(
        "/api/narrative/v2/partida/avanzar-nodo",
        json={"date": DATE, "opcion_id": "opt_nodo_inicio"},
        headers=headers,
    )
    assert avance.status_code == 200

    guardado = await test_db[COLL_RUNS].find_one({"_id": f"run_hist_{user_id}_{DATE}"})
    decision = guardado["historial_grafos"][-1]
    assert decision["mes"] == 3
    assert decision["tipo"] == "evento_especial"
    assert decision["grafo_id"] == grafo["_id"]
    assert decision["opcion_elegida_id"] == "opt_nodo_inicio"
    assert decision["resultado_obtenido_id"] == "nodo_fin"
    assert decision["resultado_texto"] == "Desenlace de prueba"

    cierre = await client.post(
        "/api/narrative/v2/partida/avanzar-mes",
        json={"date": DATE},
        headers=headers,
    )
    assert cierre.status_code == 200

    guardado = await test_db[COLL_RUNS].find_one({"_id": f"run_hist_{user_id}_{DATE}"})
    historial_mes = guardado["historial_mensual"][-1]
    assert historial_mes["mes"] == 3
    assert historial_mes["opcion_elegida_id"] == "opt_nodo_inicio"
    assert historial_mes["resultado_id"] == "nodo_fin"
    assert historial_mes["decisiones_v2"][0]["resultado_texto"] == "Desenlace de prueba"
    assert guardado["mes_actual"] == 4
