import asyncio
import datetime
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import connect_to_mongo, close_mongo_connection, get_database
from app.scripts.seed_narrative import seed_narrative_game

def test_narrative_full_cycle():
    """
    Test de integración extremo a extremo del motor narrativo:
    1. Verifica catálogo de reglas ECA.
    2. Verifica universo medieval y sus entidades sembradas.
    3. Inicia una partida con 3 miembros de corte y 3 cartas de apoyo.
    4. Simula el ciclo completo de 12 meses (Draft -> Evento -> Decisión -> Conversación -> Balance).
    5. Verifica que alcance el epílogo final y estatus completado sin errores.
    """
    asyncio.run(_ejecutar_ciclo_completo())

async def _ejecutar_ciclo_completo():
    await connect_to_mongo()
    await seed_narrative_game()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Catálogo de reglas
        resp = await client.get("/api/narrative/admin/catalogo-reglas")
        assert resp.status_code == 200
        catalogo = resp.json()
        assert "disparadores" in catalogo
        assert "operadores" in catalogo
        assert "tipos_condicion" in catalogo
        assert "tipos_accion" in catalogo

        # 2. Universo medieval
        resp = await client.get("/api/narrative/admin/universos")
        assert resp.status_code == 200
        universos = resp.json()
        assert any(u["_id"] == "corte_medieval" for u in universos)

        # 3. Iniciar Partida
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")

        # Obtener el desafío del día para elegir exactamente de los 5 personajes y 5 cartas ofrecidos
        db = get_database()
        challenge = await db["daily_challenges"].find_one({"game_id": "narrativo", "date": today_str})
        assert challenge is not None, "El desafío diario para hoy no fue encontrado"

        cfg = challenge["config"]
        corte_elegida = cfg["setup_corte_ofrecidos_ids"][:3]
        cartas_elegidas = cfg["setup_cartas_ofrecidas_ids"][:3]

        init_payload = {
            "date": today_str,
            "corte_elegida_ids": corte_elegida,
            "cartas_iniciales_ids": cartas_elegidas
        }

        # Limpiar run previa para test limpio
        await db["narrative_runs"].delete_one({"user_id": 0, "date": today_str, "game_id": "narrativo"})

        resp = await client.post("/api/narrative/partida/iniciar", json=init_payload)
        assert resp.status_code == 200, resp.text
        estado = resp.json()
        assert estado["run"]["mes_actual"] == 1
        assert estado["run"]["fase_actual"] == "DRAFT_MENSUAL"
        assert len(estado["cartas_draft_actual"]) == 3

        # 4. Jugar los 12 meses
        for mes in range(1, 13):
            # Fase 1: Draft de cartas
            assert estado["run"]["fase_actual"] == "DRAFT_MENSUAL"
            assert len(estado["cartas_draft_actual"]) > 0
            carta_id = estado["cartas_draft_actual"][0]["_id"]
            resp = await client.post(
                "/api/narrative/partida/elegir-carta-mes",
                json={"date": today_str, "carta_id": carta_id}
            )
            assert resp.status_code == 200, resp.text
            estado = resp.json()

            # Fase 2: Toma de decisión
            assert estado["run"]["fase_actual"] == "TOMA_DECISION_EVENTO"
            assert estado["evento_actual"] is not None
            opciones = estado["evento_actual"]["opciones"]
            assert len(opciones) > 0

            # Elegir primera opción disponible no bloqueada
            opcion = next(op for op in opciones if not op.get("bloqueada"))
            resp = await client.post(
                "/api/narrative/partida/decidir-evento",
                json={"date": today_str, "opcion_id": opcion["id"]}
            )
            assert resp.status_code == 200, resp.text
            estado = resp.json()

            # Fase 3: Diálogo de corte (si ocurrió)
            if estado["run"]["fase_actual"] == "RESOLVER_CONVERSACION":
                assert estado["conversacion_actual"] is not None
                resp = await client.post(
                    "/api/narrative/partida/responder-conversacion",
                    json={"date": today_str, "opcion_numero": 1}
                )
                assert resp.status_code == 200, resp.text
                estado = resp.json()

            # Fase 4: Balance mensual y avanzar
            assert estado["run"]["fase_actual"] == "BALANCE_MES"
            resp = await client.post(
                "/api/narrative/partida/avanzar-mes",
                json={"date": today_str}
            )
            assert resp.status_code == 200, resp.text
            estado = resp.json()

        # 5. Verificación de Fin de Año
        assert estado["run"]["fase_actual"] == "FINALIZADA"
        assert estado["run"]["status"] == "completed"
        assert estado["epilogo_final"] is not None
        assert estado["epilogo_final"]["rango"] in ["S", "A", "B", "C"]
        assert len(estado["run"]["historial_mensual"]) == 12

    await close_mongo_connection()
