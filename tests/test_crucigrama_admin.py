"""
test_crucigrama_admin.py
End-to-end del diseñador administrativo de máscaras: auth, CRUD, publicación,
aplicación al calendario y preferencia de plantillas en la generación mensual.

Requiere MongoDB accesible (igual que el resto de las suites de integración).
"""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import connect_to_mongo, db_instance, get_database
from app.core.dependencies import get_current_admin
from app.features.daily_challenges import service as daily_service
from app.features.daily_challenges.crucigrama.bans import (
    get_global_banned_words,
    set_global_banned_words,
)
from app.features.daily_challenges.crucigrama.templates_facil import CRUCIGRAMA_TEMPLATES
from app.features.daily_challenges.crucigrama_admin.service import (
    get_scheduled_published_config,
)
from app.main import app

BASE = "/api/challenges/admin/crucigrama/templates"
PATTERN = CRUCIGRAMA_TEMPLATES[0]["pattern"]
THEME = "Máscara de Prueba Admin"
FECHA_MANUAL = "2030-01-15"
FECHA_AGENDADA = "2030-01-16"
FECHA_CONFLICTO = "2030-01-17"
FECHA_GENERACION = "2027-02-01"


def test_crucigrama_admin_flow():
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
    if fechas:
        await db["daily_challenges"].delete_many(
            {"game_id": "crucigrama", "date": {"$in": fechas}}
        )
    await set_global_banned_words(bans_globales, updated_by="test-cleanup")


async def _ejecutar_flujo():
    ids_creados = []
    bans_originales = await get_global_banned_words()
    await set_global_banned_words([], updated_by="test-setup")
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Auth: sin token, el router debe rechazar
        sin_token = await client.post(f"{BASE}/validate", json={"pattern": PATTERN})
        assert sin_token.status_code in (401, 403), sin_token.text
        sin_token_bans = await client.get(f"{BASE}/global-bans")
        assert sin_token_bans.status_code in (401, 403), sin_token_bans.text

        app.dependency_overrides[get_current_admin] = lambda: {
            "id": 1,
            "email": "admin@test.local",
            "tipo_usuario": 2,
        }
        try:
            # 2. Validar máscara en vivo (sin persistir)
            validacion = await client.post(
                f"{BASE}/validate",
                json={"pattern": PATTERN, "difficulty": "facil"},
            )
            assert validacion.status_code == 200, validacion.text
            reporte = validacion.json()
            assert reporte["valid"], reporte["errors"]
            assert reporte["solvable"], reporte
            assert reporte["slots"], "El panel necesita los slots para ofrecer anclas."
            assert reporte["solution_words"]
            assert reporte["prefer_curated"] is True

            slots_validos = [s for s in reporte["slots"] if s["crossings"] > 0][:2]
            anclas = {
                s["id"]: reporte["solution_words"][s["id"]] for s in slots_validos
            }
            validacion_anclas = await client.post(
                f"{BASE}/validate",
                json={"pattern": PATTERN, "difficulty": "facil", "anchors": anclas},
            )
            assert validacion_anclas.status_code == 200
            assert validacion_anclas.json()["anchors"] == anclas

            # 2b. Semilla distinta -> solución distinta
            otra_semilla = await client.post(
                f"{BASE}/validate",
                json={"pattern": PATTERN, "difficulty": "facil", "seed": "semilla-b"},
            )
            assert otra_semilla.status_code == 200
            reporte_b = otra_semilla.json()
            assert reporte_b["solvable"], reporte_b
            assert reporte_b["seed"] == "semilla-b"
            assert reporte_b["solution_words"] != reporte["solution_words"]

            slot_libre = next(
                s["id"] for s in reporte["slots"] if s["id"] not in anclas
            )
            palabra_vetada = reporte_b["solution_words"][slot_libre]

            con_veto = await client.post(
                f"{BASE}/validate",
                json={
                    "pattern": PATTERN,
                    "difficulty": "facil",
                    "seed": "semilla-veto",
                    "banned_words": [palabra_vetada],
                },
            )
            assert con_veto.status_code == 200
            veto_json = con_veto.json()
            assert veto_json["solvable"], veto_json
            assert veto_json["banned_words"] == [palabra_vetada]
            assert palabra_vetada not in veto_json["solution_words"].values()

            con_fijada = await client.post(
                f"{BASE}/validate",
                json={
                    "pattern": PATTERN,
                    "difficulty": "facil",
                    "seed": "semilla-fijada",
                    "fixed_words": {slot_libre: palabra_vetada},
                },
            )
            assert con_fijada.status_code == 200
            fijada_json = con_fijada.json()
            assert fijada_json["solvable"], fijada_json
            assert fijada_json["solution_words"][slot_libre] == palabra_vetada
            assert fijada_json["fixed_words"] == {slot_libre: palabra_vetada}

            # 2c. Vetos globales: normalización, merge en validate y bloqueo en publish
            bans_iniciales = await client.get(f"{BASE}/global-bans")
            assert bans_iniciales.status_code == 200, bans_iniciales.text
            assert bans_iniciales.json()["banned_words"] == []

            palabra_global = reporte["solution_words"][slot_libre]
            extras = [w for w in ("NOCHE", "ALBAÑIL") if w not in anclas.values()]
            bans_put = await client.put(
                f"{BASE}/global-bans",
                json={"banned_words": [*extras, " noche ", palabra_global]},
            )
            assert bans_put.status_code == 200, bans_put.text
            bans_json = bans_put.json()
            assert bans_json["banned_words"] == sorted(
                {*extras, "NOCHE", palabra_global}
            )
            assert bans_json["updated_by"] == "admin@test.local"

            bans_invalidos = await client.put(
                f"{BASE}/global-bans", json={"banned_words": ["AB"]}
            )
            assert bans_invalidos.status_code == 422, bans_invalidos.text

            validacion_global = await client.post(
                f"{BASE}/validate",
                json={"pattern": PATTERN, "difficulty": "facil", "seed": "con-globales"},
            )
            assert validacion_global.status_code == 200
            global_json = validacion_global.json()
            assert global_json["solvable"], global_json
            assert global_json["global_banned_words"] == bans_json["banned_words"]
            assert global_json["banned_words"] == []
            palabras_global = set(global_json["solution_words"].values())
            assert not palabras_global & set(bans_json["banned_words"])

            # Publicar una grilla resuelta antes de los vetos -> 400 por palabra vetada
            tpl_global = await client.post(
                BASE,
                json={
                    "name": "Máscara veto global",
                    "pattern": PATTERN,
                    "difficulty": "facil",
                },
            )
            assert tpl_global.status_code == 200, tpl_global.text
            tpl_global_id = tpl_global.json()["id"]
            ids_creados.append(tpl_global_id)

            rechazo_global = await client.post(
                f"{BASE}/{tpl_global_id}/publish",
                json={"solution_grid": reporte["solution"]},
            )
            assert rechazo_global.status_code == 400, rechazo_global.text
            assert "vetada" in rechazo_global.json()["detail"].lower()

            # 3. Ancla inexistente -> 400
            invalida = await client.post(
                f"{BASE}/validate",
                json={"pattern": PATTERN, "anchors": {"NO_EXISTE": "CASA"}},
            )
            assert invalida.status_code == 200
            assert not invalida.json()["valid"]

            creada_invalida = await client.post(
                BASE,
                json={
                    "name": "Máscara inválida",
                    "pattern": PATTERN,
                    "anchors": {"NO_EXISTE": "CASA"},
                },
            )
            assert creada_invalida.status_code == 400, creada_invalida.text

            # 4. Crear borrador con anclas
            creada = await client.post(
                BASE,
                json={
                    "name": "Máscara Admin Test",
                    "theme": THEME,
                    "pattern": PATTERN,
                    "difficulty": "facil",
                    "anchors": anclas,
                    "notes": "Prueba automatizada",
                },
            )
            assert creada.status_code == 200, creada.text
            tpl = creada.json()
            ids_creados.append(tpl["id"])
            assert tpl["status"] == "draft"
            assert tpl["size"] == 7
            assert tpl["anchors"] == anclas
            assert tpl["solution_grid"] is None

            # 5. Listar y obtener
            listado = await client.get(BASE, params={"status": "draft", "limit": 100})
            assert listado.status_code == 200
            assert any(item["id"] == tpl["id"] for item in listado.json()["items"])

            detalle = await client.get(f"{BASE}/{tpl['id']}")
            assert detalle.status_code == 200
            assert detalle.json()["name"] == "Máscara Admin Test"

            # 6. Editar mientras es borrador
            editada = await client.put(
                f"{BASE}/{tpl['id']}", json={"name": "Máscara Admin Test (editada)"}
            )
            assert editada.status_code == 200, editada.text
            assert editada.json()["name"] == "Máscara Admin Test (editada)"

            # 7. Publicar agendada con la solución aprobada en el editor
            aprobada = await client.post(
                f"{BASE}/validate",
                json={
                    "pattern": PATTERN,
                    "difficulty": "facil",
                    "anchors": anclas,
                    "seed": "publicada",
                },
            )
            assert aprobada.status_code == 200, aprobada.text
            assert aprobada.json()["solvable"], aprobada.text
            grilla_aprobada = aprobada.json()["solution"]

            publicada = await client.post(
                f"{BASE}/{tpl['id']}/publish",
                json={
                    "scheduled_date": FECHA_AGENDADA,
                    "solution_grid": grilla_aprobada,
                    "seed": "publicada",
                },
            )
            assert publicada.status_code == 200, publicada.text
            pub = publicada.json()
            assert pub["template"]["status"] == "published"
            assert pub["template"]["scheduled_date"] == FECHA_AGENDADA
            assert pub["template"]["solution_grid"] == grilla_aprobada
            assert pub["template"]["last_seed"] == "publicada"
            assert pub["template"]["solution_grid"]
            assert pub["template"]["clues"]
            assert pub["template"]["published_config"]["total_words"] == pub["template"]["total_words"]
            assert pub["applied_to"]["date"] == FECHA_AGENDADA
            assert pub["applied_to"]["overwritten"] is False

            grids = pub["template"]["solution_grid"]
            for r, fila in enumerate(PATTERN):
                for c, ch in enumerate(fila):
                    if ch == "#":
                        assert grids[r][c] == "#"
                    else:
                        assert grids[r][c].isalpha()

            agendado = await get_database()["daily_challenges"].find_one(
                {"game_id": "crucigrama", "date": FECHA_AGENDADA, "difficulty": "facil"}
            )
            assert agendado is not None
            assert agendado["config"]["theme"] == THEME
            assert agendado["config"]["date"] == FECHA_AGENDADA

            # 8. Aplicar a una fecha manual
            aplicada = await client.post(
                f"{BASE}/{tpl['id']}/apply",
                json={"date": FECHA_MANUAL, "force": True},
            )
            assert aplicada.status_code == 200, aplicada.text
            assert aplicada.json()["overwritten"] is False

            repetida = await client.post(
                f"{BASE}/{tpl['id']}/apply",
                json={"date": FECHA_MANUAL, "force": False},
            )
            assert repetida.status_code == 409, repetida.text

            forzada = await client.post(
                f"{BASE}/{tpl['id']}/apply",
                json={"date": FECHA_MANUAL, "force": True},
            )
            assert forzada.status_code == 200
            assert forzada.json()["overwritten"] is True

            manual = await get_database()["daily_challenges"].find_one(
                {"game_id": "crucigrama", "date": FECHA_MANUAL, "difficulty": "facil"}
            )
            assert manual["config"]["cells"] == pub["template"]["published_config"]["cells"]

            # 9. Segunda plantilla en la misma fecha/dificultad -> 409
            segunda = await client.post(
                BASE,
                json={
                    "name": "Máscara conflicto",
                    "theme": THEME,
                    "pattern": PATTERN,
                    "difficulty": "facil",
                },
            )
            assert segunda.status_code == 200, segunda.text
            tpl2 = segunda.json()
            ids_creados.append(tpl2["id"])

            publicada_conflicto = await client.post(
                f"{BASE}/{tpl2['id']}/publish",
                json={"scheduled_date": FECHA_CONFLICTO},
            )
            assert publicada_conflicto.status_code == 200, publicada_conflicto.text

            # Publicar una grilla que contiene una palabra vetada -> 400
            grid_conflicto = publicada_conflicto.json()["template"]["solution_grid"]
            palabra_conflicto = next(iter(publicada_conflicto.json()["template"]["clues"]))
            rechazo_veto = await client.post(
                f"{BASE}/{tpl2['id']}/publish",
                json={
                    "scheduled_date": FECHA_CONFLICTO,
                    "solution_grid": grid_conflicto,
                    "banned_words": [palabra_conflicto],
                },
            )
            assert rechazo_veto.status_code == 400, rechazo_veto.text

            # Reagendar la segunda sobre la fecha de la primera -> conflicto
            conflicto = await client.post(
                f"{BASE}/{tpl2['id']}/publish",
                json={"scheduled_date": FECHA_AGENDADA},
            )
            assert conflicto.status_code == 409, conflicto.text

            # 10. Eliminar una publicada -> 409; archivar y luego publicar la segunda
            borrar_publicada = await client.delete(f"{BASE}/{tpl2['id']}")
            assert borrar_publicada.status_code == 409

            archivada = await client.post(f"{BASE}/{tpl['id']}/archive")
            assert archivada.status_code == 200, archivada.text
            assert archivada.json()["status"] == "archived"

            reagendada = await client.post(
                f"{BASE}/{tpl2['id']}/publish", json={"scheduled_date": FECHA_AGENDADA}
            )
            assert reagendada.status_code == 200, reagendada.text
            assert reagendada.json()["template"]["status"] == "published"

            # 11. Integración con la generación mensual: la plantilla agenda gana
            tpl_agendada = await client.post(
                BASE,
                json={
                    "name": "Máscara generación",
                    "theme": THEME,
                    "pattern": PATTERN,
                    "difficulty": "facil",
                },
            )
            tpl3 = tpl_agendada.json()
            ids_creados.append(tpl3["id"])
            publicada_gen = await client.post(
                f"{BASE}/{tpl3['id']}/publish",
                json={"scheduled_date": FECHA_GENERACION},
            )
            assert publicada_gen.status_code == 200, publicada_gen.text

            config_agendada = await get_scheduled_published_config(FECHA_GENERACION, "facil")
            assert config_agendada is not None
            assert config_agendada["theme"] == THEME
            assert await get_scheduled_published_config(FECHA_GENERACION, "dificil") is None

            # Simular un mes de un solo día para no generar 28 tableros
            llamadas_generador = []
            generador_real = daily_service.generate_crucigrama_challenge_for_date

            def _espia(fecha, dificultad, **kwargs):
                llamadas_generador.append(
                    (fecha, dificultad, tuple(kwargs.get("banned_words") or ()))
                )
                return generador_real(fecha, dificultad, **kwargs)

            original_monthrange = daily_service.calendar.monthrange
            daily_service.generate_crucigrama_challenge_for_date = _espia
            daily_service.calendar.monthrange = lambda year, month: (0, 1)
            try:
                resultado = await daily_service.generate_and_save_crucigrama_month(
                    2027, 2, force=True
                )
            finally:
                daily_service.generate_crucigrama_challenge_for_date = generador_real
                daily_service.calendar.monthrange = original_monthrange

            assert resultado["success"]
            assert (FECHA_GENERACION, "facil") not in [
                (fecha, dificultad) for fecha, dificultad, _ in llamadas_generador
            ]
            assert (FECHA_GENERACION, "dificil") in [
                (fecha, dificultad) for fecha, dificultad, _ in llamadas_generador
            ]
            assert llamadas_generador
            assert all(
                bans == tuple(bans_json["banned_words"])
                for _, _, bans in llamadas_generador
            ), llamadas_generador

            generado = await get_database()["daily_challenges"].find_one(
                {"game_id": "crucigrama", "date": FECHA_GENERACION, "difficulty": "facil"}
            )
            assert generado is not None
            assert generado["config"]["theme"] == THEME
            assert generado["config"]["date"] == FECHA_GENERACION

            # 12. Borrado de borradores/archivadas
            eliminada = await client.delete(f"{BASE}/{tpl['id']}")
            assert eliminada.status_code == 200, eliminada.text
            assert (await client.get(f"{BASE}/{tpl['id']}")).status_code == 404

            await client.post(f"{BASE}/{tpl2['id']}/archive")
            await client.post(f"{BASE}/{tpl3['id']}/archive")
        finally:
            app.dependency_overrides.clear()
            await _limpiar(
                ids_creados,
                [FECHA_MANUAL, FECHA_AGENDADA, FECHA_CONFLICTO, FECHA_GENERACION],
                bans_originales,
            )

pytestmark = pytest.mark.integration
