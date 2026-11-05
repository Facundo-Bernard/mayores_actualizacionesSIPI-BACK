"""N1: creación exclusiva, transición única, proyección coherente, identidad D03 y reinicio D07."""

import asyncio

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.features.narrative.constants import (
    COLL_CARDS,
    COLL_CHALLENGES,
    COLL_CHARACTERS,
    COLL_RUNS,
    COLL_RUNS_ARCHIVE,
    COLL_SETTINGS,
    COLL_USER_ATTEMPTS,
    COLL_V2_EVENTS,
)
from app.features.narrative.game import setup_service
from app.features.narrative.game.motor_v2 import v2_graph_service
from app.features.narrative.game.motor_v2.graph_engine import graph_engine
from app.features.narrative.game.run_repository import archivar_run, crear_run
from app.features.narrative.game.setup_service import iniciar_partida, reiniciar_partida
from app.features.narrative.schemas.game_schemas import IniciarPartidaRequest

pytestmark = pytest.mark.contract

DATE = "2099-07-01"
UNIVERSO = "universo_n1"
PJS = ["pj_n1_a", "pj_n1_b", "pj_n1_c"]
CARTAS = ["carta_n1_a", "carta_n1_b", "carta_n1_c"]
DRAFT = ["draft_n1_a", "draft_n1_b", "draft_n1_c"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _config(atributos: dict | None = None) -> dict:
    return {
        "universo_id": UNIVERSO,
        "atributos_iniciales": atributos or {
            "oro": 50,
            "pueblo": 50,
            "ejercito": 50,
            "fe": 50,
        },
        "setup_corte_ofrecidos_ids": PJS,
        "setup_cartas_ofrecidas_ids": CARTAS,
        "pool_eventos_disponibles_ids": [],
        "pool_cartas_mensuales_ids": DRAFT,
        "pool_conversaciones_ids": [],
    }


async def _seed_escenario(db, cleanup, atributos: dict | None = None) -> None:
    await db[COLL_CHALLENGES].replace_one(
        {"game_id": "narrativo", "date": DATE},
        {"game_id": "narrativo", "date": DATE, "config": _config(atributos)},
        upsert=True,
    )
    cleanup.add(COLL_CHALLENGES, {"game_id": "narrativo", "date": DATE})

    universo = {
        "_id": UNIVERSO,
        "nombre": "Universo N1",
        "descripcion": "",
        "motor": "v2",
        "recursos": [
            {"clave": clave, "nombre": clave.capitalize(), "min": 0, "max": 100, "inicial": 50}
            for clave in ("oro", "pueblo", "ejercito", "fe")
        ],
    }
    await db[COLL_SETTINGS].replace_one({"_id": UNIVERSO}, universo, upsert=True)
    cleanup.add(COLL_SETTINGS, {"_id": UNIVERSO})

    for pid in PJS:
        personaje = {
            "_id": pid,
            "universo_id": UNIVERSO,
            "nombre": pid,
            "titulo": "Consejero",
            "descripcion": "",
            "afinidad_inicial": 50,
            "efectos": [],
            "conversaciones": [],
        }
        await db[COLL_CHARACTERS].replace_one({"_id": pid}, personaje, upsert=True)
        cleanup.add(COLL_CHARACTERS, {"_id": pid})

    for cid in CARTAS + DRAFT:
        carta = {
            "_id": cid,
            "universo_id": UNIVERSO,
            "categoria": "bonus",
            "nombre": cid,
            "descripcion": "",
            "tags": [],
            "efectos": [],
        }
        await db[COLL_CARDS].replace_one({"_id": cid}, carta, upsert=True)
        cleanup.add(COLL_CARDS, {"_id": cid})


async def _seed_run(db, cleanup, user_id: int, **extra) -> dict:
    run = {
        "_id": f"run_n1_{user_id}_{DATE}",
        "user_id": user_id,
        "date": DATE,
        "game_id": "narrativo",
        "universo_id": UNIVERSO,
        "motor": "v2",
        "generation": 1,
        "mes_actual": 1,
        "fase_actual": "TOMA_DECISION_EVENTO",
        "status": "in_progress",
        "recursos": {"oro": 50, "pueblo": 50, "ejercito": 50, "fe": 50},
        "afinidad": {"pj_n1_a": 50},
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
        "version": 0,
    }
    run.update(extra)
    await db[COLL_RUNS].replace_one({"_id": run["_id"]}, run, upsert=True)
    cleanup.add(COLL_RUNS, {"_id": run["_id"]})
    return run


def _pedido() -> IniciarPartidaRequest:
    return IniciarPartidaRequest(
        date=DATE,
        corte_elegida_ids=PJS,
        cartas_iniciales_ids=CARTAS,
    )


@pytest.mark.asyncio
async def test_inicio_concurrente_inserta_una_sola_run(test_db, cleanup, monkeypatch):
    await _seed_escenario(test_db, cleanup)
    user_id = 910001
    cleanup.add(COLL_RUNS, {"user_id": user_id, "date": DATE})
    cleanup.add(COLL_RUNS_ARCHIVE, {"user_id": user_id, "date": DATE})

    crear_real = crear_run
    llegadas: list[str] = []
    barrera = asyncio.Event()

    async def _crear_con_barrera(run):
        llegadas.append(run["_id"])
        if len(llegadas) == 2:
            barrera.set()
        await asyncio.wait_for(barrera.wait(), timeout=5)
        await crear_real(run)

    monkeypatch.setattr(setup_service, "crear_run", _crear_con_barrera)

    resultados = await asyncio.gather(
        iniciar_partida(user_id, _pedido()),
        iniciar_partida(user_id, _pedido()),
    )

    assert len(resultados) == 2
    docs = await test_db[COLL_RUNS].find(
        {"user_id": user_id, "date": DATE, "game_id": "narrativo"}
    ).to_list(None)
    assert len(docs) == 1
    assert len(llegadas) == 2
    assert {r.mes_actual for r in resultados} == {1}


@pytest.mark.asyncio
async def test_inicio_perdedor_no_liquida_recompensa(test_db, cleanup, monkeypatch):
    await _seed_escenario(test_db, cleanup, atributos={"oro": 0, "pueblo": 50, "ejercito": 50, "fe": 50})
    user_id = 910002
    cleanup.add(COLL_RUNS, {"user_id": user_id, "date": DATE})
    cleanup.add(COLL_RUNS_ARCHIVE, {"user_id": user_id, "date": DATE})
    cleanup.add(COLL_USER_ATTEMPTS, {"user_id": user_id, "date": DATE})

    crear_real = crear_run
    llegadas: list[str] = []
    barrera = asyncio.Event()

    async def _crear_con_barrera(run):
        llegadas.append(run["_id"])
        if len(llegadas) == 2:
            barrera.set()
        await asyncio.wait_for(barrera.wait(), timeout=5)
        await crear_real(run)

    recompensas: list[int] = []

    async def _sync(run):
        recompensas.append(run["user_id"])
        return 25

    monkeypatch.setattr(setup_service, "crear_run", _crear_con_barrera)
    monkeypatch.setattr(setup_service, "sincronizar_intento_usuario", _sync)

    await asyncio.gather(
        iniciar_partida(user_id, _pedido()),
        iniciar_partida(user_id, _pedido()),
    )

    assert len(llegadas) == 2
    assert recompensas == [user_id]


@pytest.mark.asyncio
async def test_inicio_de_grafo_no_escribe_hasta_confirmar(test_db, cleanup):
    user_id = 910003
    evento = {
        "_id": "evt_n1_grafo",
        "universo_id": UNIVERSO,
        "titulo": "Evento N1",
        "imagen": "/assets/narrative/eventos/default.webp",
        "nodo_raiz": "nodo_inicio",
        "nodos": {
            "nodo_inicio": {
                "id": "nodo_inicio",
                "hablante_id": "narrador",
                "texto": "Inicio",
                "es_final": False,
                "opciones": [{"id": "opt_seguir", "texto": "Seguir", "siguiente_nodo": "nodo_fin"}],
            },
            "nodo_fin": {
                "id": "nodo_fin",
                "hablante_id": "narrador",
                "texto": "Fin",
                "es_final": True,
                "opciones": [],
            },
        },
    }
    await test_db[COLL_V2_EVENTS].replace_one({"_id": evento["_id"]}, evento, upsert=True)
    cleanup.add(COLL_V2_EVENTS, {"_id": evento["_id"]})
    run = await _seed_run(test_db, cleanup, user_id)

    await graph_engine.iniciar_grafo_en_partida(
        run=run,
        grafo=evento,
        tipo="evento",
        fase="TOMA_DECISION_EVENTO",
    )

    assert run["grafo_activo"]["grafo_id"] == evento["_id"]
    en_base = await test_db[COLL_RUNS].find_one({"_id": run["_id"]})
    assert en_base["grafo_activo"] is None
    assert en_base.get("version", 0) == 0

    await v2_graph_service.iniciar_evento_mes_v2(user_id, DATE)

    confirmado = await test_db[COLL_RUNS].find_one({"_id": run["_id"]})
    assert confirmado["grafo_activo"]["grafo_id"] == evento["_id"]
    assert confirmado["version"] == 1


@pytest.mark.asyncio
async def test_fallo_antes_de_confirmar_deja_el_run_intacto(test_db, cleanup, monkeypatch):
    user_id = 910004
    evento = {
        "_id": "evt_n1_fallo",
        "universo_id": UNIVERSO,
        "titulo": "Evento N1",
        "imagen": "/assets/narrative/eventos/default.webp",
        "nodo_raiz": "nodo_inicio",
        "nodos": {
            "nodo_inicio": {
                "id": "nodo_inicio",
                "hablante_id": "narrador",
                "texto": "Inicio",
                "es_final": False,
                "opciones": [],
            }
        },
    }
    await test_db[COLL_V2_EVENTS].replace_one({"_id": evento["_id"]}, evento, upsert=True)
    cleanup.add(COLL_V2_EVENTS, {"_id": evento["_id"]})
    run = await _seed_run(test_db, cleanup, user_id)

    persistir_real = v2_graph_service.persistir_run

    async def _fallar_al_confirmar(_run):
        raise RuntimeError("fallo inyectado antes de confirmar")

    monkeypatch.setattr(v2_graph_service, "persistir_run", _fallar_al_confirmar)
    with pytest.raises(RuntimeError):
        await v2_graph_service.iniciar_evento_mes_v2(user_id, DATE)

    en_base = await test_db[COLL_RUNS].find_one({"_id": run["_id"]})
    assert en_base["grafo_activo"] is None
    assert en_base["fase_actual"] == "TOMA_DECISION_EVENTO"
    assert en_base.get("version", 0) == 0

    monkeypatch.setattr(v2_graph_service, "persistir_run", persistir_real)
    await v2_graph_service.iniciar_evento_mes_v2(user_id, DATE)

    confirmado = await test_db[COLL_RUNS].find_one({"_id": run["_id"]})
    assert confirmado["grafo_activo"]["grafo_id"] == evento["_id"]
    assert confirmado["version"] == 1


@pytest.mark.asyncio
async def test_proyeccion_usa_el_run_ya_leido(monkeypatch):
    run = {
        "_id": "run_proyeccion",
        "fase_actual": "TOMA_DECISION_EVENTO",
        "status": "in_progress",
        "recursos": {"oro": 10},
        "afinidad": {"pj_n1_a": 40},
        "grafo_activo": {
            "tipo": "evento",
            "grafo_id": "evt_proyeccion",
            "nodo_actual_id": "nodo_actual",
        },
    }
    grafo = {
        "_id": "evt_proyeccion",
        "titulo": "Evento",
        "imagen": "",
        "nodos": {
            "nodo_actual": {
                "id": "nodo_actual",
                "hablante_id": "narrador",
                "texto": "Texto",
                "es_final": False,
                "opciones": [],
            }
        },
    }

    async def _obtener_grafo(_tipo, _grafo_id):
        return grafo

    async def _no_releer(_user_id, _date):
        raise AssertionError("La proyección no debe volver a consultar el run por usuario/fecha.")

    monkeypatch.setattr(v2_graph_service.graph_engine, "obtener_grafo", _obtener_grafo)
    monkeypatch.setattr(v2_graph_service, "_obtener_run_activo", _no_releer)

    estado = await v2_graph_service.proyectar_grafo_actual(run)
    assert estado is not None
    assert estado.nodo_actual.id == "nodo_actual"
    assert estado.fase_actual == "TOMA_DECISION_EVENTO"


@pytest.mark.asyncio
async def test_invitado_emitido_por_backend_aisla_partidas(
    client, test_db, cleanup, make_guest_credential
):
    await _seed_escenario(test_db, cleanup)

    emision_a = await client.post("/api/auth/guest-credential")
    assert emision_a.status_code == 200
    datos_a = emision_a.json()
    assert datos_a["guest_id"] and datos_a["credential"]

    reemision = await client.post(
        "/api/auth/guest-credential",
        headers={"X-Guest-Credential": datos_a["credential"]},
    )
    assert reemision.status_code == 200
    assert reemision.json()["guest_id"] == datos_a["guest_id"]

    guest_b, headers_b = make_guest_credential()
    headers_a = {"X-Guest-Credential": datos_a["credential"]}
    cleanup.add(COLL_RUNS, {"guest_id": datos_a["guest_id"], "date": DATE})
    cleanup.add(COLL_RUNS, {"guest_id": guest_b, "date": DATE})

    inicio = await client.post(
        "/api/narrative/v2/partida/iniciar",
        json={"date": DATE, "corte_elegida_ids": PJS, "cartas_iniciales_ids": CARTAS},
        headers=headers_a,
    )
    assert inicio.status_code == 200, inicio.text

    estado_a = await client.get(f"/api/narrative/v2/partida/estado?date={DATE}", headers=headers_a)
    assert estado_a.status_code == 200

    estado_b = await client.get(f"/api/narrative/v2/partida/estado?date={DATE}", headers=headers_b)
    assert estado_b.status_code == 404

    sin_credencial = await client.get(f"/api/narrative/v2/partida/estado?date={DATE}")
    assert sin_credencial.status_code == 401

    solo_header_legacy = await client.get(
        f"/api/narrative/v2/partida/estado?date={DATE}",
        headers={"X-Guest-Id": datos_a["guest_id"]},
    )
    assert solo_header_legacy.status_code == 401


@pytest.mark.asyncio
async def test_jwt_invalido_no_cae_a_invitado(client, make_guest_credential):
    _, headers = make_guest_credential()
    headers["Authorization"] = "Bearer token-invalido"
    respuesta = await client.get(
        f"/api/narrative/v2/partida/estado?date={DATE}",
        headers=headers,
    )
    assert respuesta.status_code == 401


@pytest.mark.asyncio
async def test_cuenta_inactiva_y_servicio_denegado(
    client, seeded_user, make_token
):
    inactivo = await seeded_user(activo=False)
    respuesta = await client.get(
        f"/api/narrative/v2/partida/estado?date={DATE}",
        headers=_auth(make_token(inactivo["id"])),
    )
    assert respuesta.status_code == 403

    jugador = await seeded_user()
    token_sin_servicio = make_token(
        jugador["id"],
        servicios={settings.SERVICE_KEY: False, "cognijuegos": False},
    )
    respuesta = await client.get(
        f"/api/narrative/v2/partida/estado?date={DATE}",
        headers=_auth(token_sin_servicio),
    )
    assert respuesta.status_code == 403


@pytest.mark.asyncio
async def test_reinicio_con_generacion_y_version(test_db, cleanup):
    await _seed_escenario(test_db, cleanup)
    user_id = 910010
    run = await _seed_run(test_db, cleanup, user_id, version=2)
    cleanup.add(COLL_RUNS, {"user_id": user_id, "date": DATE})
    cleanup.add(COLL_RUNS_ARCHIVE, {"user_id": user_id, "date": DATE})

    with pytest.raises(HTTPException) as exc:
        await reiniciar_partida(user_id, DATE, expected_version=1)
    assert exc.value.status_code == 409
    assert await test_db[COLL_RUNS].find_one({"_id": run["_id"]}) is not None

    resultado = await reiniciar_partida(user_id, DATE, expected_version=2)
    assert resultado["success"] is True
    assert resultado["next_generation"] == 2
    assert await test_db[COLL_RUNS].find_one({"_id": run["_id"]}) is None
    archivado = await test_db[COLL_RUNS_ARCHIVE].find_one({"_id": run["_id"]})
    assert archivado is not None
    assert archivado["generation"] == 1

    nueva = await iniciar_partida(user_id, _pedido())
    assert nueva.mes_actual == 1
    activa = await test_db[COLL_RUNS].find_one({"user_id": user_id, "date": DATE})
    assert activa["_id"] == f"run_{user_id}_{DATE}_g2"
    assert activa["generation"] == 2

    with pytest.raises(HTTPException) as exc:
        await reiniciar_partida(user_id, DATE, expected_version=2)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_archivar_run_concurrente_solo_gana_una_vez(test_db, cleanup):
    user_id = 910011
    run = await _seed_run(test_db, cleanup, user_id, version=0)
    cleanup.add(COLL_RUNS_ARCHIVE, {"_id": run["_id"]})

    await archivar_run(run, expected_version=0)
    with pytest.raises(HTTPException) as exc:
        await archivar_run(run, expected_version=0)
    assert exc.value.status_code == 409

    archivado = await test_db[COLL_RUNS_ARCHIVE].find_one({"_id": run["_id"]})
    assert archivado is not None
    assert await test_db[COLL_RUNS].find_one({"_id": run["_id"]}) is None
