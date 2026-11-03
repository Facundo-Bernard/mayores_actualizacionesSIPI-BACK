"""Matriz motor × endpoint: cada motor resuelve su ciclo con su propia superficie.

- V1 plano: elegir-carta-mes devuelve `evento_actual`; decidir-evento/responder-conversacion operan.
- V2 grafos: elegir-carta-mes devuelve `grafo_actual`; la resolución plana responde 409.
- Ambos exponen `motor` en elegir-carta-mes y estado.
"""

import pytest

from app.features.narrative.constants import (
    COLL_CARDS,
    COLL_CHALLENGES,
    COLL_EVENTS,
    COLL_RESULTS,
    COLL_RUNS,
    COLL_V2_EVENTS,
)

pytestmark = pytest.mark.contract

DATE = "2099-04-20"
UNIVERSO = "universo_motor_matrix"
CARD_DRAFT = "carta_matrix_draft"
EVENTO_V1 = "evt_matrix_v1"
RESULTADO_V1 = "res_matrix_v1"
EVENTO_V2 = "evt_matrix_v2"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _config() -> dict:
    return {
        "universo_id": UNIVERSO,
        "atributos_iniciales": {"oro": 50, "pueblo": 50, "ejercito": 50, "fe": 50},
        "setup_corte_ofrecidos_ids": ["pj_matrix"],
        "setup_cartas_ofrecidas_ids": ["carta_matrix_inicial"],
        "pool_eventos_disponibles_ids": [EVENTO_V1],
        "pool_cartas_mensuales_ids": [CARD_DRAFT],
        "pool_conversaciones_ids": [],
    }


def _run(user_id: int, motor: str) -> dict:
    return {
        "_id": f"run_matrix_{motor}_{user_id}",
        "user_id": user_id,
        "date": DATE,
        "game_id": "narrativo",
        "universo_id": UNIVERSO,
        "motor": motor,
        "mes_actual": 1,
        "fase_actual": "DRAFT_MENSUAL",
        "status": "in_progress",
        "recursos": {"oro": 50, "pueblo": 50, "ejercito": 50, "fe": 50},
        "afinidad": {"pj_matrix": 50},
        "cartas_en_mano": [],
        "tags_activos": [],
        "turno_actual": {
            "cartas_ofrecidas_ids": [CARD_DRAFT],
            "carta_elegida_id": None,
            "evento_actual_id": None,
            "opcion_elegida_id": None,
            "resultado_obtenido_id": None,
            "conversacion_actual_id": None,
        },
        "eventos_jugados": [],
        "conversaciones_jugadas": [],
        "historial_mensual": [],
        "version": 0,
    }


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


async def _seed_escenario(db, cleanup) -> None:
    await db[COLL_CHALLENGES].replace_one(
        {"game_id": "narrativo", "date": DATE},
        {"game_id": "narrativo", "date": DATE, "config": _config()},
        upsert=True,
    )
    cleanup.add(COLL_CHALLENGES, {"game_id": "narrativo", "date": DATE})

    carta = {
        "_id": CARD_DRAFT,
        "universo_id": UNIVERSO,
        "categoria": "bonus",
        "nombre": "Carta matrix",
        "descripcion": "Carta de prueba",
        "tags": [],
        "efectos": [],
    }
    await db[COLL_CARDS].replace_one({"_id": CARD_DRAFT}, carta, upsert=True)
    cleanup.add(COLL_CARDS, {"_id": CARD_DRAFT})

    resultado = {
        "_id": RESULTADO_V1,
        "universo_id": UNIVERSO,
        "titulo": "Desenlace matrix",
        "texto": "Desenlace de prueba",
        "tipo_resultado": "neutro",
        "efectos": [],
        "impacto_afinidad": [],
    }
    await db[COLL_RESULTS].replace_one({"_id": RESULTADO_V1}, resultado, upsert=True)
    cleanup.add(COLL_RESULTS, {"_id": RESULTADO_V1})

    evento_v1 = {
        "_id": EVENTO_V1,
        "universo_id": UNIVERSO,
        "titulo": "Evento plano matrix",
        "descripcion": "Evento de prueba",
        "imagen": "/assets/narrative/eventos/default.webp",
        "tags_tematicos": [],
        "peso_base": 100.0,
        "opciones": [
            {
                "id": "op_a",
                "texto": "Opción A",
                "es_secreta": False,
                "condiciones": [],
                "resultados_posibles": [{"resultado_id": RESULTADO_V1, "peso_base": 100.0}],
            }
        ],
    }
    await db[COLL_EVENTS].replace_one({"_id": EVENTO_V1}, evento_v1, upsert=True)
    cleanup.add(COLL_EVENTS, {"_id": EVENTO_V1})

    evento_v2 = {
        "_id": EVENTO_V2,
        "universo_id": UNIVERSO,
        "titulo": "Evento grafo matrix",
        "imagen": "/assets/narrative/eventos/default.webp",
        "nodo_raiz": "nodo_inicio",
        "nodos": {
            "nodo_inicio": _nodo("nodo_inicio", es_final=False, siguiente="nodo_fin"),
            "nodo_fin": _nodo("nodo_fin", es_final=True),
        },
    }
    await db[COLL_V2_EVENTS].replace_one({"_id": EVENTO_V2}, evento_v2, upsert=True)
    cleanup.add(COLL_V2_EVENTS, {"_id": EVENTO_V2})


async def _seed_run(db, cleanup, run: dict) -> None:
    await db[COLL_RUNS].replace_one({"_id": run["_id"]}, run, upsert=True)
    cleanup.add(COLL_RUNS, {"_id": run["_id"]})


@pytest.mark.asyncio
async def test_motor_v1_resuelve_ciclo_plano(client, test_db, cleanup, make_token):
    user_id = 820001
    await _seed_escenario(test_db, cleanup)
    await _seed_run(test_db, cleanup, _run(user_id, "v1"))
    headers = _auth(make_token(user_id))

    elegir = await client.post(
        "/api/narrative/v2/partida/elegir-carta-mes",
        json={"date": DATE, "carta_id": CARD_DRAFT},
        headers=headers,
    )
    assert elegir.status_code == 200, elegir.text
    data = elegir.json()
    assert data["motor"] == "v1"
    assert data["evento_actual"]["id"] == EVENTO_V1
    assert data["grafo_actual"] is None

    estado = await client.get(f"/api/narrative/v2/partida/estado?date={DATE}", headers=headers)
    assert estado.status_code == 200
    assert estado.json()["motor"] == "v1"

    decidir = await client.post(
        "/api/narrative/v2/partida/decidir-evento",
        json={"date": DATE, "opcion_id": "op_a"},
        headers=headers,
    )
    assert decidir.status_code == 200, decidir.text
    assert decidir.json()["resultado_actual"]["_id"] == RESULTADO_V1
    assert decidir.json()["fase_actual"] == "BALANCE_MES"

    avanzar = await client.post(
        "/api/narrative/v2/partida/avanzar-mes",
        json={"date": DATE},
        headers=headers,
    )
    assert avanzar.status_code == 200, avanzar.text
    assert avanzar.json()["fase_actual"] == "DRAFT_MENSUAL"


@pytest.mark.asyncio
async def test_motor_v2_inicia_grafo_y_rechaza_resolucion_plana(
    client, test_db, cleanup, make_token
):
    user_id = 820002
    await _seed_escenario(test_db, cleanup)
    await _seed_run(test_db, cleanup, _run(user_id, "v2"))
    headers = _auth(make_token(user_id))

    elegir = await client.post(
        "/api/narrative/v2/partida/elegir-carta-mes",
        json={"date": DATE, "carta_id": CARD_DRAFT},
        headers=headers,
    )
    assert elegir.status_code == 200, elegir.text
    data = elegir.json()
    assert data["motor"] == "v2"
    assert data["evento_actual"] is None
    assert data["grafo_actual"]["grafo_id"] == EVENTO_V2

    estado = await client.get(f"/api/narrative/v2/partida/estado?date={DATE}", headers=headers)
    assert estado.status_code == 200
    estado_data = estado.json()
    assert estado_data["motor"] == "v2"
    assert estado_data["grafo_actual"]["grafo_id"] == EVENTO_V2

    decidir = await client.post(
        "/api/narrative/v2/partida/decidir-evento",
        json={"date": DATE, "opcion_id": "op_a"},
        headers=headers,
    )
    assert decidir.status_code == 409

    responder = await client.post(
        "/api/narrative/v2/partida/responder-conversacion",
        json={"date": DATE, "opcion_numero": 1},
        headers=headers,
    )
    assert responder.status_code == 409

    avanzar = await client.post(
        "/api/narrative/v2/partida/avanzar-nodo",
        json={"date": DATE, "opcion_id": "opt_nodo_inicio"},
        headers=headers,
    )
    assert avanzar.status_code == 200, avanzar.text
    assert avanzar.json()["nodo_actual"]["es_final"] is True
    assert avanzar.json()["fase_actual"] == "BALANCE_MES"


def test_endpoints_planos_deprecados_y_campo_motor_en_openapi():
    from app.main import app

    spec = app.openapi()
    paths = spec["paths"]

    planos = [
        ("/api/narrative/v2/partida/decidir-evento", "post"),
        ("/api/narrative/v2/partida/responder-conversacion", "post"),
        ("/api/narrative/partida/evento-actual", "get"),
        ("/api/narrative/partida/conversacion-actual", "get"),
        ("/api/narrative/partida/resultado-actual", "get"),
        ("/api/narrative/partida/draft-actual", "get"),
    ]
    for path, metodo in planos:
        assert paths[path][metodo].get("deprecated") is True, f"{metodo.upper()} {path}"

    schemas = spec["components"]["schemas"]
    assert "motor" in schemas["ElegirCartaMesV2Response"]["properties"]
    assert "motor" in schemas["EstadoTurnoResponse"]["properties"]
