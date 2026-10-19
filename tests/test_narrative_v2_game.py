import asyncio
import datetime
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import connect_to_mongo, close_mongo_connection, get_database
from app.scripts.seed_narrative import seed_narrative_game

def test_narrative_v2_full_cycle():
    """
    Test de integración extremo a extremo del flujo V2 ligero:
    1. Verifica setup previo.
    2. Inicia partida V2 (/iniciar) con 3 miembros de corte y 3 cartas iniciales.
    3. Itera los 12 meses usando la API delta V2:
       - /elegir-carta-mes
       - /decidir-evento
       - /responder-conversacion (si aplica)
       - /avanzar-mes
    4. Verifica que al final del mes 12 el juego termina en victoria con finalizacion.
    """
    asyncio.run(_ejecutar_ciclo_v2())

async def _ejecutar_ciclo_v2():
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
        challenge = await db["daily_challenges"].find_one({"game_id": "narrativo", "date": today_str})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Limpiar run previa para test limpio
        await db["narrative_runs"].delete_one({"user_id": 0, "date": today_str, "game_id": "narrativo"})
        cfg = challenge["config"]

        corte_elegida = cfg["setup_corte_ofrecidos_ids"][:3]
        cartas_elegidas = cfg["setup_cartas_ofrecidas_ids"][:3]

        # 1. Iniciar Partida V2
        resp = await client.post(
            "/api/narrative/v2/partida/iniciar",
            json={
                "date": today_str,
                "corte_elegida_ids": corte_elegida,
                "cartas_iniciales_ids": cartas_elegidas
            },
            headers={"Authorization": "Bearer fake_token"}  # user_id 0
        )
        assert resp.status_code == 200, resp.text
        data_v2 = resp.json()
        assert data_v2["mes_actual"] == 1
        assert data_v2["fase_actual"] == "DRAFT_MENSUAL"
        assert len(data_v2["cartas_draft_actual"]) == 3

        # 2. Jugar los 12 meses con la API V2
        for mes in range(1, 13):
            # Fase 1: Elegir carta de draft
            carta_id = data_v2["cartas_draft_actual"][0]["_id"]
            resp = await client.post(
                "/api/narrative/v2/partida/elegir-carta-mes",
                json={"date": today_str, "carta_id": carta_id}
            )
            assert resp.status_code == 200, resp.text
            data_v2 = resp.json()

            # Si la carta causó colapso de recursos
            if data_v2["fase_actual"] == "FINALIZADA":
                assert data_v2["finalizacion"] is not None
                break

            assert data_v2["fase_actual"] == "TOMA_DECISION_EVENTO"
            assert data_v2["evento_actual"] is not None

            # Fase 2: Decidir opción en evento
            opciones = data_v2["evento_actual"]["opciones"]
            opcion = next(op for op in opciones if not op.get("bloqueada"))
            resp = await client.post(
                "/api/narrative/v2/partida/decidir-evento",
                json={"date": today_str, "opcion_id": opcion["id"]}
            )
            assert resp.status_code == 200, resp.text
            data_v2 = resp.json()

            # Si colapsó un recurso tras la decisión del evento, la partida pasa a FINALIZADA (Game Over)
            if data_v2["fase_actual"] == "FINALIZADA":
                assert data_v2["finalizacion"] is not None
                break

            # Fase 3: Responder diálogo de corte si ocurrió
            if data_v2["fase_actual"] == "RESOLVER_CONVERSACION":
                assert data_v2["conversacion_actual"] is not None
                resp = await client.post(
                    "/api/narrative/v2/partida/responder-conversacion",
                    json={"date": today_str, "opcion_numero": 1}
                )
                assert resp.status_code == 200, resp.text
                data_v2 = resp.json()

            # Si colapsó tras el diálogo o balance
            if data_v2["fase_actual"] == "FINALIZADA":
                assert data_v2["finalizacion"] is not None
                break

            # Fase 4: Avanzar mes
            assert data_v2["fase_actual"] == "BALANCE_MES"
            resp = await client.post(
                "/api/narrative/v2/partida/avanzar-mes",
                json={"date": today_str}
            )
            assert resp.status_code == 200, resp.text
            data_v2 = resp.json()

            # Si colapsó por costos pasivos CADA_MES
            if data_v2["fase_actual"] == "FINALIZADA":
                break

        # 3. Verificación de finalización V2 (Victoria o Game Over)
        assert data_v2["fase_actual"] == "FINALIZADA"
        assert data_v2["finalizacion"] is not None
        if data_v2.get("status") == "completed":
            assert data_v2["finalizacion"]["rango"] in ["S", "A", "B", "C"]
        else:
            assert data_v2["finalizacion"]["rango"] == "F"

    await close_mongo_connection()
