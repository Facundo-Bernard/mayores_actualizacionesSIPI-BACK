"""Contratos P0 del narrativo: fases, motor y grafo activo no pueden saltarse."""

import pytest

from app.features.narrative.constants import (
    COLL_RUNS,
    COLL_V2_CONVERSATIONS,
    COLL_V2_EVENTOS_ESPECIALES,
    COLL_V2_EVENTS,
)

pytestmark = pytest.mark.contract

DATE = "2099-03-15"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _nodo(id_nodo: str, *, es_final: bool, siguiente: str | None = None) -> dict:
    return {
        "id": id_nodo,
        "hablante_id": "narrador",
        "texto": f"Texto de {id_nodo}",
        "es_final": es_final,
        "opciones": (
            []
            if es_final
            else [{"id": f"opt_{id_nodo}", "texto": "Continuar", "siguiente_nodo": siguiente}]
        ),
        "resultado_texto": "Desenlace de prueba" if es_final else "",
        "impactos_recursos": [],
        "impactos_afinidad": [],
        "impactos_tags": [],
    }


async def _seed_run(
    db,
    cleanup,
    *,
    user_id: int,
    universo_id: str,
    motor: str = "v2",
    fase: str = "TOMA_DECISION_EVENTO",
    status: str = "in_progress",
    grafo_activo: dict | None = None,
) -> dict:
    run = {
        "_id": f"run_guard_{user_id}_{DATE}",
        "user_id": user_id,
        "date": DATE,
        "game_id": "narrativo",
        "universo_id": universo_id,
        "motor": motor,
        "mes_actual": 1,
        "fase_actual": fase,
        "status": status,
        "recursos": {"oro": 50, "pueblo": 50, "ejercito": 50, "fe": 50},
        "afinidad": {"pj_guard": 50},
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
        "grafo_activo": grafo_activo,
    }
    await db[COLL_RUNS].replace_one({"_id": run["_id"]}, run, upsert=True)
    cleanup.add(COLL_RUNS, {"_id": run["_id"]})
    return run


async def _seed_evento(db, cleanup, universo_id: str) -> dict:
    evento = {
        "_id": f"evt_guard_{universo_id}",
        "universo_id": universo_id,
        "titulo": "Evento guarda",
        "imagen": "/assets/narrative/eventos/default.webp",
        "nodo_raiz": "nodo_inicio",
        "nodos": {
            "nodo_inicio": _nodo("nodo_inicio", es_final=False, siguiente="nodo_fin"),
            "nodo_fin": _nodo("nodo_fin", es_final=True),
        },
    }
    await db[COLL_V2_EVENTS].replace_one({"_id": evento["_id"]}, evento, upsert=True)
    cleanup.add(COLL_V2_EVENTS, {"_id": evento["_id"]})
    return evento


async def _seed_conversacion(db, cleanup, universo_id: str) -> dict:
    conv = {
        "_id": f"conv_guard_{universo_id}",
        "universo_id": universo_id,
        "titulo": "Conversación guarda",
        "imagen": "/assets/narrative/conversaciones/default.webp",
        "requisitos": [],
        "nodo_raiz": "nodo_inicio",
        "nodos": {
            "nodo_inicio": _nodo("nodo_inicio", es_final=False, siguiente="nodo_fin"),
            "nodo_fin": _nodo("nodo_fin", es_final=True),
        },
    }
    await db[COLL_V2_CONVERSATIONS].replace_one({"_id": conv["_id"]}, conv, upsert=True)
    cleanup.add(COLL_V2_CONVERSATIONS, {"_id": conv["_id"]})
    return conv


@pytest.mark.asyncio
async def test_iniciar_evento_grafo_inicia_una_vez_y_bloquea_reroll(
    client, test_db, cleanup, make_token
):
    user_id = 810001
    universo_id = "universo_guard_evento_ok"
    await _seed_evento(test_db, cleanup, universo_id)
    await _seed_run(test_db, cleanup, user_id=user_id, universo_id=universo_id)

    headers = _auth(make_token(user_id))
    url = f"/api/narrative/v2/partida/iniciar-evento-grafo?date={DATE}"

    primero = await client.post(url, headers=headers)
    assert primero.status_code == 200
    assert primero.json()["grafo_id"] == f"evt_guard_{universo_id}"

    guardado = await test_db[COLL_RUNS].find_one({"user_id": user_id, "date": DATE})
    assert guardado["grafo_activo"]["grafo_id"] == f"evt_guard_{universo_id}"

    reroll = await client.post(url, headers=headers)
    assert reroll.status_code == 409


@pytest.mark.asyncio
async def test_iniciar_evento_grafo_rechaza_salto_de_fase(client, test_db, cleanup, make_token):
    user_id = 810002
    universo_id = "universo_guard_evento_fase"
    await _seed_evento(test_db, cleanup, universo_id)
    await _seed_run(
        test_db,
        cleanup,
        user_id=user_id,
        universo_id=universo_id,
        fase="DRAFT_MENSUAL",
    )

    response = await client.post(
        f"/api/narrative/v2/partida/iniciar-evento-grafo?date={DATE}",
        headers=_auth(make_token(user_id)),
    )
    assert response.status_code == 409

    guardado = await test_db[COLL_RUNS].find_one({"user_id": user_id, "date": DATE})
    assert guardado["grafo_activo"] is None


@pytest.mark.asyncio
async def test_iniciar_evento_grafo_rechaza_partida_finalizada(
    client, test_db, cleanup, make_token
):
    user_id = 810003
    universo_id = "universo_guard_evento_fin"
    await _seed_evento(test_db, cleanup, universo_id)
    await _seed_run(
        test_db,
        cleanup,
        user_id=user_id,
        universo_id=universo_id,
        fase="FINALIZADA",
        status="completed",
    )

    response = await client.post(
        f"/api/narrative/v2/partida/iniciar-evento-grafo?date={DATE}",
        headers=_auth(make_token(user_id)),
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_iniciar_evento_grafo_rechaza_motor_v1(client, test_db, cleanup, make_token):
    user_id = 810004
    universo_id = "universo_guard_evento_v1"
    await _seed_evento(test_db, cleanup, universo_id)
    await _seed_run(
        test_db,
        cleanup,
        user_id=user_id,
        universo_id=universo_id,
        motor="v1",
    )

    response = await client.post(
        f"/api/narrative/v2/partida/iniciar-evento-grafo?date={DATE}",
        headers=_auth(make_token(user_id)),
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_iniciar_conversacion_grafo_exige_fase_y_motor(
    client, test_db, cleanup, make_token
):
    user_id = 810005
    universo_id = "universo_guard_conversacion"
    await _seed_conversacion(test_db, cleanup, universo_id)
    await _seed_run(
        test_db,
        cleanup,
        user_id=user_id,
        universo_id=universo_id,
        fase="TOMA_DECISION_EVENTO",
    )

    headers = _auth(make_token(user_id))
    url = f"/api/narrative/v2/partida/iniciar-conversacion-grafo?date={DATE}"

    salto_de_fase = await client.post(url, headers=headers)
    assert salto_de_fase.status_code == 409

    await test_db[COLL_RUNS].update_one(
        {"user_id": user_id, "date": DATE},
        {"$set": {"fase_actual": "RESOLVER_CONVERSACION"}},
    )
    iniciada = await client.post(url, headers=headers)
    assert iniciada.status_code == 200
    assert iniciada.json()["grafo_id"] == f"conv_guard_{universo_id}"

    await test_db[COLL_RUNS].update_one(
        {"user_id": user_id, "date": DATE},
        {"$set": {"motor": "v1", "grafo_activo": None}},
    )
    motor_v1 = await client.post(url, headers=headers)
    assert motor_v1.status_code == 409


@pytest.mark.asyncio
async def test_avanzar_nodo_rechaza_motor_v1_y_partida_finalizada(
    client, test_db, cleanup, make_token
):
    grafo_activo = {
        "tipo": "evento",
        "grafo_id": "evt_inexistente_guard",
        "nodo_actual_id": "nodo_inicio",
    }
    user_v1 = 810006
    await _seed_run(
        test_db,
        cleanup,
        user_id=user_v1,
        universo_id="universo_guard_avanzar_v1",
        motor="v1",
        grafo_activo=grafo_activo,
    )
    respuesta_v1 = await client.post(
        "/api/narrative/v2/partida/avanzar-nodo",
        json={"date": DATE, "opcion_id": "opt_cualquiera"},
        headers=_auth(make_token(user_v1)),
    )
    assert respuesta_v1.status_code == 409

    user_fin = 810007
    await _seed_run(
        test_db,
        cleanup,
        user_id=user_fin,
        universo_id="universo_guard_avanzar_fin",
        fase="FINALIZADA",
        status="completed",
        grafo_activo=grafo_activo,
    )
    respuesta_fin = await client.post(
        "/api/narrative/v2/partida/avanzar-nodo",
        json={"date": DATE, "opcion_id": "opt_cualquiera"},
        headers=_auth(make_token(user_fin)),
    )
    assert respuesta_fin.status_code == 409


@pytest.mark.asyncio
async def test_avanzar_nodo_doble_avance_persiste_y_limpia(
    client, test_db, cleanup, make_token
):
    user_id = 810008
    universo_id = "universo_guard_avanzar_ok"
    grafo = {
        "_id": f"esp_guard_{universo_id}",
        "universo_id": universo_id,
        "personaje_id": "pj_guard",
        "direccion": "lealtad",
        "titulo": "Evento especial guarda",
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
        universo_id=universo_id,
        grafo_activo={
            "tipo": "evento_especial",
            "grafo_id": grafo["_id"],
            "nodo_actual_id": "nodo_inicio",
        },
    )

    headers = _auth(make_token(user_id))
    payload = {"date": DATE, "opcion_id": "opt_nodo_inicio"}

    primero = await client.post("/api/narrative/v2/partida/avanzar-nodo", json=payload, headers=headers)
    assert primero.status_code == 200
    assert primero.json()["nodo_actual"]["es_final"] is True
    assert primero.json()["fase_actual"] == "BALANCE_MES"

    guardado = await test_db[COLL_RUNS].find_one({"user_id": user_id, "date": DATE})
    assert guardado["grafo_activo"] is None
    assert guardado["turno_actual"]["opcion_elegida_id"] == "opt_nodo_inicio"
    assert guardado["turno_actual"]["resultado_obtenido_id"] == "nodo_fin"

    doble = await client.post("/api/narrative/v2/partida/avanzar-nodo", json=payload, headers=headers)
    assert doble.status_code == 409


@pytest.mark.asyncio
async def test_avanzar_nodo_rechaza_nodo_actual_inexistente(client, test_db, cleanup, make_token):
    user_id = 810009
    universo_id = "universo_guard_avanzar_nodo"
    await _seed_evento(test_db, cleanup, universo_id)
    await _seed_run(
        test_db,
        cleanup,
        user_id=user_id,
        universo_id=universo_id,
        grafo_activo={
            "tipo": "evento",
            "grafo_id": f"evt_guard_{universo_id}",
            "nodo_actual_id": "nodo_que_no_existe",
        },
    )

    response = await client.post(
        "/api/narrative/v2/partida/avanzar-nodo",
        json={"date": DATE, "opcion_id": "opt_cualquiera"},
        headers=_auth(make_token(user_id)),
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_endpoints_v1_rechazan_partida_v2(client, test_db, cleanup, make_token):
    user_id = 810010
    await _seed_run(
        test_db,
        cleanup,
        user_id=user_id,
        universo_id="universo_guard_v1_endpoints",
        fase="TOMA_DECISION_EVENTO",
    )
    headers = _auth(make_token(user_id))

    decidir = await client.post(
        "/api/narrative/v2/partida/decidir-evento",
        json={"date": DATE, "opcion_id": "op_a"},
        headers=headers,
    )
    assert decidir.status_code == 409

    await test_db[COLL_RUNS].update_one(
        {"user_id": user_id, "date": DATE},
        {"$set": {"fase_actual": "RESOLVER_CONVERSACION"}},
    )
    responder = await client.post(
        "/api/narrative/v2/partida/responder-conversacion",
        json={"date": DATE, "opcion_numero": 1},
        headers=headers,
    )
    assert responder.status_code == 409
