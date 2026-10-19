import asyncio
import datetime
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import connect_to_mongo, close_mongo_connection, get_database
from app.scripts.seed_narrative import seed_narrative_game

def test_narrative_queries_and_modals():
    """
    Test de integración para endpoints de catálogo, setup y consultas bajo demanda (modales):
    1. Verifica catálogo de reglas ECA y configuración de universos.
    2. Consulta el setup diario (/api/narrative/partida/setup).
    3. Inicia una partida V2 y prueba las consultas modales (/corte, /inventario, /historial).
    4. Prueba el endpoint de reinicio (/api/narrative/partida/reiniciar).
    """
    asyncio.run(_ejecutar_pruebas_consultas())

async def _ejecutar_pruebas_consultas():
    await connect_to_mongo()
    db = get_database()

    # Omitir seed si la base de datos ya contiene personajes para no sobreescribir imágenes del usuario
    if await db["narrative_characters"].count_documents({}) == 0:
        await seed_narrative_game()

    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    challenge = await db["daily_challenges"].find_one({"game_id": "narrativo", "date": today_str})
    if not challenge:
        from app.features.narrative.admin.challenge_service import generar_mes_narrativo
        now = datetime.datetime.now()
        await generar_mes_narrativo(year=now.year, month=now.month, universo_id="corte_medieval")

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

        # 3. Setup de partida
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        db = get_database()
        await db["narrative_runs"].delete_one({"user_id": 0, "date": today_str, "game_id": "narrativo"})

        resp = await client.get(f"/api/narrative/partida/setup?date={today_str}")
        assert resp.status_code == 200, resp.text
        setup_data = resp.json()
        assert setup_data["tiene_partida_activa"] is False
        assert len(setup_data["personajes_ofrecidos"]) == 5
        assert len(setup_data["cartas_ofrecidas"]) == 5

        # 4. Iniciar partida con V2
        corte_elegida = [p["_id"] for p in setup_data["personajes_ofrecidos"][:3]]
        cartas_elegidas = [c["_id"] for c in setup_data["cartas_ofrecidas"][:3]]

        init_payload = {
            "date": today_str,
            "corte_elegida_ids": corte_elegida,
            "cartas_iniciales_ids": cartas_elegidas
        }
        resp = await client.post("/api/narrative/v2/partida/iniciar", json=init_payload)
        assert resp.status_code == 200, resp.text

        # 5. Consultas bajo demanda (modales)
        # Corte
        resp = await client.get(f"/api/narrative/partida/corte?date={today_str}")
        assert resp.status_code == 200
        corte_data = resp.json()
        assert len(corte_data["corte"]) == 3

        # Inventario
        resp = await client.get(f"/api/narrative/partida/inventario?date={today_str}")
        assert resp.status_code == 200
        inv_data = resp.json()
        assert len(inv_data["cartas"]) == 3

        # Historial
        resp = await client.get(f"/api/narrative/partida/historial?date={today_str}")
        assert resp.status_code == 200
        hist_data = resp.json()
        assert hist_data["mes_actual"] == 1

        # 6. Reiniciar partida
        resp = await client.post("/api/narrative/partida/reiniciar", json={"date": today_str})
        assert resp.status_code == 200
        assert resp.json()["eliminada"] is True

        # Verificar que el setup vuelve a marcar sin partida activa
        resp = await client.get(f"/api/narrative/partida/setup?date={today_str}")
        assert resp.status_code == 200
        assert resp.json()["tiene_partida_activa"] is False

    await close_mongo_connection()
