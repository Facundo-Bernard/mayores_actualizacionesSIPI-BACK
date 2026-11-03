"""
test_narrative_v2_eventos_especiales.py
Suite de tests de integración para los Eventos Especiales de Afinidad V2.
Verifica el disparo por cruce de umbral en graph_engine.avanzar_nodo:
1. Lealtad: cruzar hacia arriba AFINIDAD_UMBRAL_LEALTAD (>= 95) encadena el grafo especial 'lealtad'.
2. Traición: cruzar hacia abajo AFINIDAD_UMBRAL_TRAICION (< 15) encadena el grafo especial 'traicion'.
3. Sin cruce: no se encadena ningún especial y la partida avanza a BALANCE_MES.
"""

import pytest

import asyncio
from unittest.mock import patch

from app.core.database import connect_to_mongo, get_database
from app.features.narrative.constants import (
    COLL_V2_EVENTS,
    COLL_V2_EVENTOS_ESPECIALES,
    COLL_RUNS
)
from app.features.narrative.game.motor_v2.graph_engine import graph_engine
from app.scripts.seed_narrative_v2_graphs import seed_v2_graphs


def test_v2_eventos_especiales_afinidad():
    asyncio.run(_ejecutar_tests())


async def _ejecutar_tests():
    await connect_to_mongo()
    db = get_database()

    # Asegurar siembra de eventos especiales (lealtad/traición por personaje)
    if await db[COLL_V2_EVENTOS_ESPECIALES].count_documents({}) == 0:
        await seed_v2_graphs()

    test_user_id = 777001

    # Limpiar cualquier run residual de ejecuciones previas fallidas
    await db[COLL_RUNS].delete_many({"user_id": test_user_id, "game_id": "narrativo"})

    # Grafo sintético de evento con dos desenlaces: subir o bajar afinidad de Elena.
    grafo_evento = {
        "_id": "evt_test_disparador_especial",
        "universo_id": "corte_medieval",
        "titulo": "Dilema de prueba de afinidad",
        "imagen": "",
        "nodo_raiz": "inicio",
        "nodos": {
            "inicio": {
                "id": "inicio",
                "hablante_id": "narrador",
                "texto": "Una decisión de prueba sobre la Canciller Elena.",
                "es_final": False,
                "opciones": [
                    {"id": "opt_lealtad", "texto": "Honrar a Elena", "siguiente_nodo": "fin_lealtad"},
                    {"id": "opt_traicion", "texto": "Agraviar a Elena", "siguiente_nodo": "fin_traicion"}
                ]
            },
            "fin_lealtad": {
                "id": "fin_lealtad",
                "hablante_id": "narrador",
                "texto": "Elena se siente honrada.",
                "es_final": True,
                "opciones": [],
                "resultado_texto": "Lealtad de Elena en alza.",
                "impactos_recursos": [],
                "impactos_afinidad": [{"personaje_id": "pj_canciller_elena", "delta": 10}]
            },
            "fin_traicion": {
                "id": "fin_traicion",
                "hablante_id": "narrador",
                "texto": "Elena se siente agraviada.",
                "es_final": True,
                "opciones": [],
                "resultado_texto": "Afinidad de Elena en caída.",
                "impactos_recursos": [],
                "impactos_afinidad": [{"personaje_id": "pj_canciller_elena", "delta": -10}]
            }
        }
    }
    await db[COLL_V2_EVENTS].replace_one({"_id": grafo_evento["_id"]}, grafo_evento, upsert=True)

    def _run_base(run_id, date_str, afinidad_elena):
        return {
            "_id": run_id,
            "user_id": test_user_id,
            "date": date_str,
            "game_id": "narrativo",
            "universo_id": "corte_medieval",
            "fase_actual": "TOMA_DECISION_EVENTO",
            "status": "CONTINUA",
            "recursos": {"oro": 50, "pueblo": 50, "ejercito": 50, "fe": 50},
            "afinidad": {"pj_canciller_elena": afinidad_elena},
            "eventos_jugados": [],
            "conversaciones_jugadas": [],
            "grafo_activo": {
                "tipo": "evento",
                "grafo_id": "evt_test_disparador_especial",
                "nodo_actual_id": "inicio"
            }
        }

    # ========================================================================
    # TEST 1: Cruce de LEALTAD (90 -> 100 >= 95) encadena esp_lealtad_elena
    # ========================================================================
    run_lealtad = _run_base(f"run_esp_lealtad_{test_user_id}", "2026-12-31", 90)
    await db[COLL_RUNS].replace_one({"_id": run_lealtad["_id"]}, run_lealtad, upsert=True)

    estado_lealtad = await graph_engine.avanzar_nodo(run_lealtad, "opt_lealtad")

    assert estado_lealtad.tipo == "evento_especial", f"Se esperaba evento_especial, se obtuvo {estado_lealtad.tipo}"
    assert estado_lealtad.grafo_id == "esp_lealtad_elena"
    assert estado_lealtad.fase_actual == "TOMA_DECISION_EVENTO"
    # Afinidad persistida en la run
    assert run_lealtad["afinidad"]["pj_canciller_elena"] == 100
    assert run_lealtad["grafo_activo"]["tipo"] == "evento_especial"
    run_bd = await db[COLL_RUNS].find_one({"_id": run_lealtad["_id"]})
    assert run_bd["afinidad"]["pj_canciller_elena"] == 100
    print("[OK] Test 1: Cruce de lealtad encadena el evento especial correspondiente.")

    # ========================================================================
    # TEST 2: Cruce de TRAICIÓN (20 -> 10 < 15) encadena esp_traicion_elena
    # ========================================================================
    run_traicion = _run_base(f"run_esp_traicion_{test_user_id}", "2026-12-30", 20)
    await db[COLL_RUNS].replace_one({"_id": run_traicion["_id"]}, run_traicion, upsert=True)

    estado_traicion = await graph_engine.avanzar_nodo(run_traicion, "opt_traicion")

    assert estado_traicion.tipo == "evento_especial", f"Se esperaba evento_especial, se obtuvo {estado_traicion.tipo}"
    assert estado_traicion.grafo_id == "esp_traicion_elena"
    assert run_traicion["afinidad"]["pj_canciller_elena"] == 10
    print("[OK] Test 2: Cruce de traición encadena el evento especial correspondiente.")

    # ========================================================================
    # TEST 3: Sin cruce de umbral NO encadena especial y avanza a BALANCE_MES
    # ========================================================================
    run_sin_cruce = _run_base(f"run_esp_sincruce_{test_user_id}", "2026-12-29", 90)
    await db[COLL_RUNS].replace_one({"_id": run_sin_cruce["_id"]}, run_sin_cruce, upsert=True)

    with patch("app.features.narrative.game.motor_v2.graph_engine.random.random", return_value=0.99):
        estado_sin_cruce = await graph_engine.avanzar_nodo(run_sin_cruce, "opt_traicion")

    assert estado_sin_cruce.tipo == "evento", f"Se esperaba 'evento', se obtuvo {estado_sin_cruce.tipo}"
    assert estado_sin_cruce.fase_actual == "BALANCE_MES"
    assert run_sin_cruce["afinidad"]["pj_canciller_elena"] == 80
    assert not run_sin_cruce.get("especiales_pendientes"), "No debió quedar ningún especial pendiente."
    print("[OK] Test 3: Sin cruce de umbral no se dispara evento especial y se avanza de fase.")

    # Limpieza
    await db[COLL_V2_EVENTS].delete_one({"_id": "evt_test_disparador_especial"})
    await db[COLL_RUNS].delete_many({"user_id": test_user_id, "game_id": "narrativo"})
    print("\n[SUCCESS] ¡La suite de Eventos Especiales de Afinidad V2 pasó exitosamente al 100%!")

pytestmark = pytest.mark.integration
