"""
test_crucigrama_recurrencia.py
Plantillas recurrentes (día del mes): persistencia, unicidad, re-solución por
fecha y prioridad frente a una fecha exacta en la generación mensual.

Requiere MongoDB accesible (igual que el resto de las suites de integración).
"""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import connect_to_mongo, db_instance, get_database
from app.core.dependencies import get_current_admin
from app.features.daily_challenges import service as daily_service
from app.features.daily_challenges.games import crucigrama as crucigrama_game
from app.features.daily_challenges.crucigrama import published_templates
from app.features.daily_challenges.crucigrama.bans import (
    get_global_banned_words,
    set_global_banned_words,
)
from app.features.daily_challenges.crucigrama.templates_facil import CRUCIGRAMA_TEMPLATES
from app.features.daily_challenges.crucigrama_admin import service as admin_service
from app.main import app

BASE = "/api/challenges/admin/crucigrama/templates"
PATTERN = CRUCIGRAMA_TEMPLATES[0]["pattern"]
THEME = "Recurrente de Prueba"
THEME_EXACTA = "Fecha Exacta de Prueba"
FECHA_EXACTA = "2031-01-05"
DIAS_GENERADOS = [f"2031-01-{dia:02d}" for dia in range(1, 6)]


def test_crucigrama_recurrencia_flow():
    asyncio.run(_main())


async def _main():
    await connect_to_mongo()
    try:
        await db_instance.client.admin.command("ping")
    except Exception:
        pytest.skip("MongoDB no accesible para la suite de integración.")
    await _ejecutar_flujo()


async def _limpiar(ids, fechas, bans_globales):
    db = get_database()
    if ids:
        await db["crucigrama_templates"].delete_many({"id": {"$in": ids}})
    await db["daily_challenges"].delete_many(
        {"game_id": "crucigrama", "date": {"$in": fechas}}
    )
    await set_global_banned_words(bans_globales, updated_by="test-cleanup")


async def _crear(client, **extra):
    payload = {
        "name": "Recurrente",
        "theme": THEME,
        "pattern": PATTERN,
        "difficulty": "facil",
        **extra,
    }
    return await client.post(BASE, json=payload)


async def _ejecutar_flujo():
    ids_creados = []
    bans_originales = await get_global_banned_words()
    await set_global_banned_words([], updated_by="test-setup")
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        app.dependency_overrides[get_current_admin] = lambda: {
            "id": 1,
            "email": "admin@test.local",
            "tipo_usuario": 2,
        }
        try:
            # 1. Alta y publicación de una plantilla recurrente (día 4)
            alta = await _crear(client, name="Recurrente día 4", monthly_day=4)
            assert alta.status_code == 200, alta.text
            tpl = alta.json()
            ids_creados.append(tpl["id"])
            assert tpl["monthly_day"] == 4
            assert tpl["status"] == "draft"

            publicada = await client.post(f"{BASE}/{tpl['id']}/publish", json={})
            assert publicada.status_code == 200, publicada.text
            pub = publicada.json()
            assert pub["template"]["monthly_day"] == 4
            assert pub["template"]["status"] == "published"
            assert pub["applied_to"] is None, "Sin fecha exacta no debe tocar el calendario."

            # 2. Conflicto: otra publicada con el mismo día y dificultad -> 409
            alta_b = await _crear(client, name="Recurrente duplicada", monthly_day=4)
            assert alta_b.status_code == 200, alta_b.text
            tpl_b = alta_b.json()
            ids_creados.append(tpl_b["id"])
            conflicto = await client.post(f"{BASE}/{tpl_b['id']}/publish", json={})
            assert conflicto.status_code == 409, conflicto.text
            assert "día 4" in str(conflicto.json())

            # 3. Rango del día del mes
            fuera_rango = await _crear(client, name="Día inválido", monthly_day=32)
            assert fuera_rango.status_code == 422, fuera_rango.text
            cero = await _crear(client, name="Día cero", monthly_day=0)
            assert cero.status_code == 422, cero.text

            # 3b. Día 31: existe en enero, no en febrero
            alta_31 = await _crear(client, name="Recurrente día 31", monthly_day=31)
            assert alta_31.status_code == 200, alta_31.text
            tpl_31 = alta_31.json()
            ids_creados.append(tpl_31["id"])
            pub_31 = await client.post(f"{BASE}/{tpl_31['id']}/publish", json={})
            assert pub_31.status_code == 200, pub_31.text

            # 4. Resolución recurrente: re-resuelve con semilla derivada de la fecha
            llamadas = []
            validate_original = published_templates.validate_pattern

            def _espia_validate(*args, **kwargs):
                llamadas.append(kwargs.get("seed"))
                return validate_original(*args, **kwargs)

            published_templates.validate_pattern = _espia_validate
            try:
                config_enero = await admin_service.get_recurring_published_config(
                    "2031-01-04", "facil"
                )
                config_otro_dia = await admin_service.get_recurring_published_config(
                    "2031-01-06", "facil"
                )
                config_febrero = await admin_service.get_recurring_published_config(
                    "2031-02-04", "facil"
                )
                config_31_febrero = await admin_service.get_recurring_published_config(
                    "2031-02-28", "facil"
                )
            finally:
                published_templates.validate_pattern = validate_original

            assert config_enero is not None
            assert config_enero["theme"] == THEME
            assert config_enero["grid_size"] == 7
            assert config_otro_dia is None
            assert config_febrero is not None
            assert config_febrero["theme"] == THEME
            assert config_31_febrero is None, "Febrero no tiene día 31: se omite."
            assert llamadas == ["2031-01-04", "2031-02-04"]

            # 5. Prioridad: fecha exacta > recurrente en la generación mensual
            alta_exacta = await _crear(
                client,
                name="Exacta 2031-01-05",
                theme=THEME_EXACTA,
                scheduled_date=FECHA_EXACTA,
            )
            assert alta_exacta.status_code == 200, alta_exacta.text
            tpl_exacta = alta_exacta.json()
            ids_creados.append(tpl_exacta["id"])
            pub_exacta = await client.post(
                f"{BASE}/{tpl_exacta['id']}/publish", json={}
            )
            assert pub_exacta.status_code == 200, pub_exacta.text

            fechas_generador = []
            generador_original = crucigrama_game.generate_crucigrama_challenge_for_date

            def _espia_generador(fecha, dificultad, **kwargs):
                fechas_generador.append(fecha)
                return generador_original(fecha, dificultad, **kwargs)

            fechas_recurrente = []
            recurrente_original = crucigrama_game.get_recurring_published_config

            async def _espia_recurrente(fecha, dificultad, *args, **kwargs):
                fechas_recurrente.append(fecha)
                return await recurrente_original(fecha, dificultad, *args, **kwargs)

            monthrange_original = crucigrama_game.calendar.monthrange
            dificultades_original = crucigrama_game.CRUCIGRAMA_DIFFICULTIES
            crucigrama_game.generate_crucigrama_challenge_for_date = _espia_generador
            crucigrama_game.get_recurring_published_config = _espia_recurrente
            crucigrama_game.calendar.monthrange = lambda year, month: (0, 5)
            crucigrama_game.CRUCIGRAMA_DIFFICULTIES = ["facil"]
            try:
                resultado = await daily_service.generate_and_save_crucigrama_month(
                    2031, 1, force=True
                )
            finally:
                crucigrama_game.generate_crucigrama_challenge_for_date = generador_original
                crucigrama_game.get_recurring_published_config = recurrente_original
                crucigrama_game.calendar.monthrange = monthrange_original
                crucigrama_game.CRUCIGRAMA_DIFFICULTIES = dificultades_original

            assert resultado["success"]
            assert fechas_recurrente == [
                "2031-01-01",
                "2031-01-02",
                "2031-01-03",
                "2031-01-04",
            ]
            assert fechas_generador == ["2031-01-01", "2031-01-02", "2031-01-03"]

            docs = {}
            for fecha in DIAS_GENERADOS:
                doc = await get_database()["daily_challenges"].find_one(
                    {"game_id": "crucigrama", "date": fecha, "difficulty": "facil"}
                )
                assert doc is not None, f"Falta el desafío de {fecha}"
                docs[fecha] = doc

            assert docs["2031-01-04"]["config"]["theme"] == THEME
            assert docs["2031-01-04"]["config"]["date"] == "2031-01-04"
            assert docs["2031-01-05"]["config"]["theme"] == THEME_EXACTA
            assert docs["2031-01-01"]["config"]["theme"] != THEME

            # 6. Una plantilla archivada deja de repetirse
            archivada = await client.post(f"{BASE}/{tpl['id']}/archive")
            assert archivada.status_code == 200, archivada.text
            sin_recurrente = await admin_service.get_recurring_published_config(
                "2031-03-04", "facil"
            )
            assert sin_recurrente is None
        finally:
            app.dependency_overrides.clear()
            await _limpiar(ids_creados, DIAS_GENERADOS, bans_originales)

pytestmark = pytest.mark.integration
