"""
test_narrative_v2_graphs.py
Suite de tests de integración para el Motor Narrativo Genérico V2 basado en Grafos de Decisión.
Verifica:
1. Contrato estricto y sanitización anti-spoilers (to_cliente_schema).
2. Arcos Narrativos (desbloqueo condicional de eventos con requisitos_eventos_previos).
3. Navegación paso a paso (nodos intermedios vs nodos terminales).
4. Persistencia atómica de impactos en recursos, afinidad e historial en MongoDB.
5. Llamadas HTTP directas a través de /api/narrative/v2/partida/avanzar-nodo.
"""

import pytest

import asyncio
import datetime
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import connect_to_mongo, get_database
from app.core.security import create_access_token
from app.features.narrative.constants import (
    COLL_V2_EVENTS,
    COLL_V2_CONVERSATIONS,
    COLL_RUNS
)
from app.features.narrative.schemas.v2_graph_schemas import (
    NodoNarrativoSchema,
    OpcionNodoSchema,
    ImpactoRecursoSchema,
    ImpactoAfinidadSchema
)
from app.features.narrative.game.motor_v2.graph_engine import graph_engine
from app.scripts.seed_narrative_v2_graphs import seed_v2_graphs

def test_v2_graph_full_suite():
    asyncio.run(_ejecutar_tests_v2())

async def _ejecutar_tests_v2():
    await connect_to_mongo()
    db = get_database()

    # Asegurar siembra de grafos V2
    if await db[COLL_V2_EVENTS].count_documents({}) == 0:
        await seed_v2_graphs()

    # ========================================================================
    # TEST 1: Sanitización Anti-Spoilers (to_cliente_schema)
    # ========================================================================
    nodo_interno = NodoNarrativoSchema(
        id="nodo_prueba",
        hablante_id="pj_comandante_marcus",
        texto="Planteo militar de prueba.",
        es_final=False,
        opciones=[
            OpcionNodoSchema(
                id="opt_1",
                texto="Atacar al amanecer",
                siguiente_nodo="nodo_secreto_futuro"
            )
        ],
        resultado_texto="Desenlace oculto",
        impactos_recursos=[ImpactoRecursoSchema(recurso="oro", delta=-20)],
        impactos_afinidad=[ImpactoAfinidadSchema(personaje_id="pj_elena", delta=10)]
    )

    nodo_cliente = nodo_interno.to_cliente_schema()
    cliente_dict = nodo_cliente.model_dump()

    # Validar que NO expone siguiente_nodo
    assert "siguiente_nodo" not in cliente_dict["opciones"][0]
    assert cliente_dict["opciones"][0]["texto"] == "Atacar al amanecer"
    # Como es_final == False, resultado e impactos deben estar limpios
    assert cliente_dict["resultado_texto"] == ""
    assert cliente_dict["impactos_recursos"] == []
    assert cliente_dict["impactos_afinidad"] == []
    print("\n[OK] Test 1: Sanitización anti-spoilers verificada.")

    # ========================================================================
    # TEST 2: Arcos Narrativos (requisitos_eventos_previos)
    # ========================================================================
    run_simulada = {
        "_id": "run_test_arcos",
        "user_id": 9999,
        "date": "2026-10-23",
        "universo_id": "corte_medieval",
        "eventos_jugados": [],
        "recursos": {"oro": 50, "pueblo": 50, "ejercito": 50, "fe": 50},
        "afinidad": {"pj_canciller_elena": 50, "pj_comandante_marcus": 50}
    }

    # Sin el cometa jugado, 'evt_secta_cometa_v2' NO debe ser sorteable
    evento_sorteado = await graph_engine.sortear_evento_v2(
        run=run_simulada,
        pool_ids=["evt_secta_cometa_v2"]
    )
    assert evento_sorteado is None, "El evento derivado no debió sortearse sin su requisito previo."

    # Ahora simulamos que el cometa ya se jugó
    run_simulada["eventos_jugados"].append("evt_cometa_caido_v2")
    evento_sorteado_ok = await graph_engine.sortear_evento_v2(
        run=run_simulada,
        pool_ids=["evt_secta_cometa_v2"]
    )
    assert evento_sorteado_ok is not None
    assert evento_sorteado_ok["_id"] == "evt_secta_cometa_v2"
    print("[OK] Test 2: Arcos narrativos condicionales verificados exitosamente.")

    # ========================================================================
    # TEST 3: Navegación de Grafo Paso a Paso con Persistencia
    # ========================================================================
    today_str = "2026-12-31"
    test_user_id = 999999
    await db[COLL_RUNS].delete_many({"user_id": test_user_id, "date": today_str})

    run_db = {
        "_id": f"run_v2_graph_test_{test_user_id}_{today_str}",
        "user_id": test_user_id,
        "date": today_str,
        "game_id": "narrativo",
        "universo_id": "corte_medieval",
        "motor": "v2",
        "fase_actual": "TOMA_DECISION_EVENTO",
        "status": "in_progress",
        "recursos": {"oro": 50, "pueblo": 50, "ejercito": 50, "fe": 50},
        "afinidad": {
            "pj_canciller_elena": 50,
            "pj_comandante_marcus": 50,
            "pj_alquimista_vera": 50,
            "pj_obispo_tomas": 50,
            "pj_ladrona_sylvia": 50
        },
        "eventos_jugados": [],
        "conversaciones_jugadas": [],
        "grafo_activo": None
    }
    await db[COLL_RUNS].replace_one({"_id": run_db["_id"]}, run_db, upsert=True)

    # 3.1 Iniciar evento cometa
    evento_cometa = await db[COLL_V2_EVENTS].find_one({"_id": "evt_cometa_caido_v2"})
    assert evento_cometa is not None

    estado_inicio = await graph_engine.iniciar_grafo_en_partida(
        run=run_db,
        grafo=evento_cometa,
        tipo="evento",
        fase="TOMA_DECISION_EVENTO"
    )
    assert estado_inicio.nodo_actual.id == "nodo_avistamiento"
    assert len(estado_inicio.nodo_actual.opciones) == 2
    assert estado_inicio.nodo_actual.es_final is False

    # 3.2 Avanzar por la opción A (Guardia -> nodo intermedio)
    estado_paso_1 = await graph_engine.avanzar_nodo(
        run=run_db,
        opcion_id="opt_enviar_guardia"
    )
    assert estado_paso_1.nodo_actual.id == "nodo_represion_crater"
    assert estado_paso_1.nodo_actual.hablante_id == "pj_comandante_marcus"
    assert estado_paso_1.nodo_actual.es_final is False
    assert len(estado_paso_1.nodo_actual.opciones) == 2

    # 3.3 Avanzar a la opción final (Mano dura -> desenlace)
    # Se fuerza que NO se dispare la conversación incidental (40%) para un test determinista.
    with patch("app.features.narrative.game.motor_v2.graph_engine.random.random", return_value=0.99):
        estado_paso_final = await graph_engine.avanzar_nodo(
            run=run_db,
            opcion_id="opt_mano_dura"
        )
    assert estado_paso_final.nodo_actual.es_final is True
    assert estado_paso_final.fase_actual == "BALANCE_MES"

    # Verificar que aplicó los deltas en recursos y afinidad
    # cierre_militar_cometa: ejercito +15, fe -10, Marcus +10, Tomas -15
    assert estado_paso_final.recursos["ejercito"] == 65
    assert estado_paso_final.recursos["fe"] == 40
    assert estado_paso_final.afinidad["pj_comandante_marcus"] == 60
    assert estado_paso_final.afinidad["pj_obispo_tomas"] == 35

    # Verificar persistencia en MongoDB
    run_en_base = await db[COLL_RUNS].find_one({"_id": run_db["_id"]})
    assert run_en_base["recursos"]["ejercito"] == 65
    assert run_en_base["afinidad"]["pj_comandante_marcus"] == 60
    assert "evt_cometa_caido_v2" in run_en_base["eventos_jugados"]
    assert run_en_base["grafo_activo"] is None
    print("[OK] Test 3: Navegación de grafo y consecuencias atómicas verificadas.")

    # ========================================================================
    # TEST 4: Verificación de Endpoint HTTP (/avanzar-nodo)
    # ========================================================================
    # Preparamos una conversación V2 en la partida
    conv_doc = await db[COLL_V2_CONVERSATIONS].find_one({"_id": "conv_disputa_tesoro_militar_v2"})
    assert conv_doc is not None

    await graph_engine.iniciar_grafo_en_partida(
        run=run_db,
        grafo=conv_doc,
        tipo="conversacion",
        fase="RESOLVER_CONVERSACION"
    )

    transport = ASGITransport(app=app)
    token = create_access_token({"id": test_user_id})
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Llamada HTTP al endpoint V2
        resp = await client.post(
            "/api/narrative/v2/partida/avanzar-nodo",
            json={
                "date": today_str,
                "opcion_id": "opt_escuchar_marcus"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["grafo_id"] == "conv_disputa_tesoro_militar_v2"
        assert data["nodo_actual"]["id"] == "marcus_planteo"
        assert data["nodo_actual"]["hablante_id"] == "pj_comandante_marcus"
        assert len(data["nodo_actual"]["opciones"]) == 2
        print("[OK] Test 4: Endpoint HTTP /api/narrative/v2/partida/avanzar-nodo verificado.")

    # ========================================================================
    # TEST 5: Opciones Condicionales Reactivas y Sorteo con Sinergias
    # ========================================================================
    from app.features.narrative.schemas.rules_schemas import CondicionSchema
    from app.features.narrative.enums import TipoCondicionEnum, OperadorEnum

    nodo_condicional = NodoNarrativoSchema(
        id="nodo_bifurcacion_condicional",
        hablante_id="narrador",
        texto="Un dilema con ramas exigentes.",
        es_final=False,
        opciones=[
            OpcionNodoSchema(
                id="opt_libre",
                texto="Ruta abierta para todos",
                siguiente_nodo="paso_normal"
            ),
            OpcionNodoSchema(
                id="opt_oro_alto",
                texto="Comprar el salvoconducto (-40 Oro)",
                siguiente_nodo="paso_salvoconducto",
                condiciones=[
                    CondicionSchema(
                        tipo=TipoCondicionEnum.COMPARAR_RECURSO,
                        clave="oro",
                        operador=OperadorEnum.MAYOR_IGUAL,
                        valor=80
                    )
                ],
                bloqueo_modo="deshabilitada"
            ),
            OpcionNodoSchema(
                id="opt_secreta_elena",
                texto="Enviar mensaje secreto a Elena",
                siguiente_nodo="paso_elena_rescate",
                condiciones=[
                    CondicionSchema(
                        tipo=TipoCondicionEnum.AFINIDAD_PERSONAJE,
                        personaje_id="pj_canciller_elena",
                        operador=OperadorEnum.MAYOR_IGUAL,
                        valor=75
                    )
                ],
                bloqueo_modo="oculta"
            )
        ]
    )

    # Estado con oro=50 y afinidad_elena=50
    run_reactiva = {
        "_id": "run_test_reactiva",
        "recursos": {"oro": 50, "pueblo": 50, "ejercito": 50, "fe": 50},
        "afinidad": {"pj_canciller_elena": 50}
    }

    schema_cliente_bloqueado = nodo_condicional.to_cliente_schema(run_reactiva)
    opts = {o.id: o for o in schema_cliente_bloqueado.opciones}

    # 1. opt_libre debe estar disponible
    assert opts["opt_libre"].disponible is True
    assert opts["opt_libre"].motivo_bloqueo is None

    # 2. opt_oro_alto debe estar visible pero bloqueada con motivo
    assert opts["opt_oro_alto"].disponible is False
    assert "Requiere Oro >= 80" in opts["opt_oro_alto"].motivo_bloqueo

    # 3. opt_secreta_elena debe estar OCULTA (no presente en la lista)
    assert "opt_secreta_elena" not in opts

    # 4. Intentar avanzar con opt_oro_alto bloqueada debe disparar HTTPException 400
    grafo_prueba_cond = {
        "_id": "evt_prueba_condicional",
        "nodo_raiz": "nodo_bifurcacion_condicional",
        "nodos": {
            "nodo_bifurcacion_condicional": nodo_condicional.model_dump(),
            "paso_salvoconducto": {
                "id": "paso_salvoconducto",
                "hablante_id": "narrador",
                "texto": "Compraste el salvoconducto.",
                "es_final": True,
                "opciones": [],
                "impactos_recursos": [],
                "impactos_afinidad": []
            }
        }
    }
    await db[COLL_V2_EVENTS].replace_one({"_id": grafo_prueba_cond["_id"]}, grafo_prueba_cond, upsert=True)

    run_sim_bloqueo = {
        "_id": "run_sim_bloqueo",
        "recursos": {"oro": 50},
        "grafo_activo": {
            "tipo": "evento",
            "grafo_id": "evt_prueba_condicional",
            "nodo_actual_id": "nodo_bifurcacion_condicional"
        }
    }

    try:
        from fastapi import HTTPException
        await graph_engine.avanzar_nodo(run_sim_bloqueo, "opt_oro_alto")
        assert False, "Debió rechazar avanzar con una opción bloqueada."
    except HTTPException as e:
        assert e.status_code == 400
        assert "está bloqueada" in e.detail

    # 5. Si el jugador reúne 90 de Oro y 80 de afinidad con Elena:
    run_reactiva_rica = {
        "_id": "run_test_reactiva_rica",
        "recursos": {"oro": 90, "pueblo": 50, "ejercito": 50, "fe": 50},
        "afinidad": {"pj_canciller_elena": 80}
    }
    schema_cliente_desbloqueado = nodo_condicional.to_cliente_schema(run_reactiva_rica)
    opts_desb = {o.id: o for o in schema_cliente_desbloqueado.opciones}
    assert opts_desb["opt_oro_alto"].disponible is True
    assert "opt_secreta_elena" in opts_desb
    assert opts_desb["opt_secreta_elena"].disponible is True
    print("[OK] Test 5: Opciones condicionales, candados amigables y ramas secretas verificadas.")

    # Limpieza
    await db[COLL_V2_EVENTS].delete_one({"_id": "evt_prueba_condicional"})
    await db[COLL_RUNS].delete_one({"_id": run_db["_id"]})
    print("\n[SUCCESS] ¡Toda la suite de pruebas del Motor Narrativo V2 pasó exitosamente al 100%!")

pytestmark = pytest.mark.integration
