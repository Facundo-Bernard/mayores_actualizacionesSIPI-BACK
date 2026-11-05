import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import connect_to_mongo


@pytest.mark.asyncio
async def test_admin_operaciones_y_eventos(admin_override):
    await connect_to_mongo()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Operaciones
        resp_ops = await client.get("/api/narrative/admin/operaciones")
        assert resp_ops.status_code == 200
        ops = resp_ops.json()
        assert any(o["primitiva"] == "modificar_recurso" for o in ops)
        assert any(o["primitiva"] == "amortiguar_danio" for o in ops)

        # 2. Eventos de motor
        resp_evts = await client.get("/api/narrative/admin/eventos-motor")
        assert resp_evts.status_code == 200
        evts = resp_evts.json()
        assert any(e["evento_motor"] == "al_obtener" for e in evts)
        assert any(e["evento_motor"] == "inicio_mes" for e in evts)


@pytest.mark.asyncio
async def test_admin_acciones_crud_y_occ(admin_override):
    await connect_to_mongo()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        action_id = "test_accion_tributo"
        universo = "corte_medieval"

        # Cleanup previo por si quedó de un test anterior
        await client.delete(f"/api/narrative/admin/acciones/{action_id}?universo_id={universo}")

        # 1. Crear acción
        payload_create = {
            "_id": action_id,
            "universo_id": universo,
            "nombre": "Tributo Feudal",
            "descripcion": "Recauda impuestos a expensas de la lealtad",
            "primitiva": "modificar_recurso",
            "permitido_en": ["carta", "personaje"],
            "activo": True,
            "version": 1,
        }
        resp_create = await client.post(
            "/api/narrative/admin/acciones",
            json=payload_create,
        )
        assert resp_create.status_code == 201
        data_create = resp_create.json()
        assert (data_create.get("_id") or data_create.get("id")) == action_id
        assert data_create["version"] == 1

        # 2. Obtener por ID
        resp_get = await client.get(
            f"/api/narrative/admin/acciones/{action_id}?universo_id={universo}",
        )
        assert resp_get.status_code == 200
        assert resp_get.json()["nombre"] == "Tributo Feudal"

        # 3. Listar con filtro de universo
        resp_list = await client.get(
            f"/api/narrative/admin/acciones?universo_id={universo}",
        )
        assert resp_list.status_code == 200
        assert any((a.get("_id") or a.get("id")) == action_id for a in resp_list.json())

        # 4. Actualizar con OCC (esperada errónea -> 409)
        resp_occ_err = await client.put(
            f"/api/narrative/admin/acciones/{action_id}?universo_id={universo}",
            json={"nombre": "Tributo Editado", "expected_version": 999},
        )
        assert resp_occ_err.status_code == 409

        # 5. Actualizar con OCC correcta (1 -> 2)
        resp_occ_ok = await client.put(
            f"/api/narrative/admin/acciones/{action_id}?universo_id={universo}",
            json={"nombre": "Tributo Editado", "expected_version": 1},
        )
        assert resp_occ_ok.status_code == 200
        assert resp_occ_ok.json()["version"] == 2
        assert resp_occ_ok.json()["nombre"] == "Tributo Editado"

        # 6. Consultar usos
        resp_usos = await client.get(
            f"/api/narrative/admin/acciones/{action_id}/usos",
        )
        assert resp_usos.status_code == 200
        assert resp_usos.json()["total_usos"] == 0

        # 7. Eliminar acción
        resp_del = await client.delete(
            f"/api/narrative/admin/acciones/{action_id}?universo_id={universo}",
        )
        assert resp_del.status_code == 200

        # 8. Verificar que ya no existe (404)
        resp_404 = await client.get(
            f"/api/narrative/admin/acciones/{action_id}?universo_id={universo}",
        )
        assert resp_404.status_code == 404


@pytest.mark.asyncio
async def test_admin_frecuencias_universo_y_usos(admin_override):
    await connect_to_mongo()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        universo = "corte_medieval"

        # 1. Obtener frecuencias del universo
        resp_get = await client.get(
            f"/api/narrative/admin/frecuencias?universo_id={universo}",
        )
        assert resp_get.status_code == 200
        frec_doc = resp_get.json()
        assert frec_doc["universo_id"] == universo
        assert len(frec_doc["items"]) >= 2
        version_actual = frec_doc["version"]

        # 2. Consultar usos de frecuencia "al_obtener"
        resp_usos = await client.get(
            f"/api/narrative/admin/frecuencias/al_obtener/usos?universo_id={universo}",
        )
        assert resp_usos.status_code == 200
        assert "total_usos" in resp_usos.json()

        # 3. OCC conflict al actualizar frecuencias
        items_payload = frec_doc["items"]
        resp_occ_err = await client.put(
            f"/api/narrative/admin/frecuencias/{universo}",
            json={"items": items_payload, "expected_version": 9999},
        )
        assert resp_occ_err.status_code == 409

        # 4. Actualizar exitosamente con versión correcta
        resp_put_ok = await client.put(
            f"/api/narrative/admin/frecuencias/{universo}",
            json={"items": items_payload, "expected_version": version_actual},
        )
        assert resp_put_ok.status_code == 200
        assert resp_put_ok.json()["version"] == version_actual + 1
