"""
test_narrative_v2_desenlaces_tags.py
Suite de tests de integración para las extensiones del motor V2:
1. Desenlaces ponderados: una opción puede sortear entre varios nodos destino por peso.
2. Impactos de tags: un nodo terminal otorga tags permanentes al reino (run.tags_activos).
Verifica además el anti-spoiler: los desenlaces no se filtran al cliente.
"""

import pytest

import asyncio
from unittest.mock import patch

from app.core.database import connect_to_mongo, get_database
from app.features.narrative.constants import (
    COLL_V2_EVENTS,
    COLL_RUNS
)
from app.features.narrative.engine.graph_engine import graph_engine


def test_v2_desenlaces_y_tags():
    asyncio.run(_ejecutar_tests())


async def _ejecutar_tests():
    await connect_to_mongo()
    db = get_database()

    test_user_id = 777002
    date_str = "2026-12-28"
    # Limpiar runs residuales de ejecuciones previas
    await db[COLL_RUNS].delete_many({"user_id": test_user_id, "game_id": "narrativo"})

    # Grafo sintético: opción con desenlaces ponderados (fin_a peso 0, fin_b peso 100)
    grafo = {
        "_id": "evt_test_desenlaces_tags",
        "universo_id": "corte_medieval",
        "titulo": "Prueba de desenlaces y tags",
        "imagen": "",
        "nodo_raiz": "inicio",
        "nodos": {
            "inicio": {
                "id": "inicio",
                "hablante_id": "narrador",
                "texto": "Una decisión con dos desenlaces posibles.",
                "es_final": False,
                "opciones": [
                    {
                        "id": "opt_azar",
                        "texto": "Arriesgar",
                        "desenlaces": [
                            {"nodo": "fin_a", "peso": 0},
                            {"nodo": "fin_b", "peso": 100}
                        ]
                    }
                ]
            },
            "fin_a": {
                "id": "fin_a",
                "hablante_id": "narrador",
                "texto": "Desenlace A.",
                "es_final": True,
                "opciones": [],
                "resultado_texto": "Resultó A.",
                "impactos_recursos": [],
                "impactos_afinidad": []
            },
            "fin_b": {
                "id": "fin_b",
                "hablante_id": "narrador",
                "texto": "Desenlace B.",
                "es_final": True,
                "opciones": [],
                "resultado_texto": "Resultó B.",
                "impactos_recursos": [],
                "impactos_afinidad": [],
                "impactos_tags": ["favor_baron"]
            }
        }
    }
    await db[COLL_V2_EVENTS].replace_one({"_id": grafo["_id"]}, grafo, upsert=True)

    run = {
        "_id": f"run_desenlaces_tags_{test_user_id}",
        "user_id": test_user_id,
        "date": date_str,
        "game_id": "narrativo",
        "universo_id": "corte_medieval",
        "fase_actual": "TOMA_DECISION_EVENTO",
        "status": "CONTINUA",
        "recursos": {"oro": 50, "pueblo": 50, "ejercito": 50, "fe": 50},
        "afinidad": {"pj_canciller_elena": 50},
        "eventos_jugados": [],
        "conversaciones_jugadas": [],
        "grafo_activo": None
    }
    await db[COLL_RUNS].replace_one({"_id": run["_id"]}, run, upsert=True)

    # ========================================================================
    # TEST 1: Anti-spoiler — el inicio no expone desenlaces ni destino
    # ========================================================================
    estado_inicio = await graph_engine.iniciar_grafo_en_partida(
        run=run, grafo=grafo, tipo="evento", fase="TOMA_DECISION_EVENTO"
    )
    assert estado_inicio.nodo_actual.id == "inicio"
    assert len(estado_inicio.nodo_actual.opciones) == 1
    opcion_cliente = estado_inicio.nodo_actual.opciones[0].model_dump()
    assert "desenlaces" not in opcion_cliente
    assert "siguiente_nodo" not in opcion_cliente
    print("[OK] Test 1: Los desenlaces ponderados no se filtran al cliente.")

    # ========================================================================
    # TEST 2: Sorteo determinista (fin_a peso 0) resuelve a fin_b
    # ========================================================================
    with patch("app.features.narrative.engine.graph_engine.random.random", return_value=0.99):
        estado = await graph_engine.avanzar_nodo(run, "opt_azar")

    assert estado.nodo_actual.id == "fin_b", f"Se esperaba fin_b, se obtuvo {estado.nodo_actual.id}"
    assert estado.fase_actual == "BALANCE_MES"
    print("[OK] Test 2: El sorteo ponderado resuelve al desenlace de mayor peso.")

    # ========================================================================
    # TEST 3: El nodo final otorga tags permanentes al reino
    # ========================================================================
    assert estado.nodo_actual.impactos_tags == ["favor_baron"]
    assert run["tags_activos"] == ["favor_baron"]
    run_bd = await db[COLL_RUNS].find_one({"_id": run["_id"]})
    assert "favor_baron" in run_bd["tags_activos"]
    print("[OK] Test 3: El tag 'favor_baron' quedó registrado en run.tags_activos.")

    # Limpieza
    await db[COLL_V2_EVENTS].delete_one({"_id": "evt_test_desenlaces_tags"})
    await db[COLL_RUNS].delete_many({"user_id": test_user_id, "game_id": "narrativo"})
    print("\n[SUCCESS] ¡La suite de Desenlaces Ponderados y Tags V2 pasó exitosamente al 100%!")

pytestmark = pytest.mark.integration
