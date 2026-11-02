"""Siembra idempotente: arrancar el backend no debe pisar ediciones del admin ni el flag motor."""

import pytest

from app.features.narrative.constants import COLL_SETTINGS, COLL_V2_EVENTS
from app.features.narrative.schemas import RecursoDefinicionSchema, UniversoCreateRequest
from app.scripts.seed_narrative import _insertar_si_no_existe
from app.scripts.seed_narrative_v2_graphs import seed_v2_graphs

pytestmark = pytest.mark.contract


def _universo(universo_id: str, nombre: str) -> UniversoCreateRequest:
    return UniversoCreateRequest(
        id=universo_id,
        nombre=nombre,
        descripcion="Universo de prueba",
        recursos=[RecursoDefinicionSchema(clave="oro", nombre="Oro")],
    )


@pytest.mark.asyncio
async def test_insertar_si_no_existe_respeta_documento_y_motor(test_db, cleanup):
    universo_id = "universo_seed_idempotente"
    await test_db[COLL_SETTINGS].replace_one(
        {"_id": universo_id},
        {
            "_id": universo_id,
            "nombre": "Editado por el admin",
            "descripcion": "Custom",
            "motor": "v2",
            "recursos": [{"clave": "oro", "nombre": "Oro"}],
        },
        upsert=True,
    )
    cleanup.add(COLL_SETTINGS, {"_id": universo_id})

    await _insertar_si_no_existe(COLL_SETTINGS, _universo(universo_id, "Nombre del seed"))
    guardado = await test_db[COLL_SETTINGS].find_one({"_id": universo_id})

    assert guardado["nombre"] == "Editado por el admin"
    assert guardado["motor"] == "v2"


@pytest.mark.asyncio
async def test_insertar_si_no_existe_crea_documento_ausente(test_db, cleanup):
    universo_id = "universo_seed_nuevo"
    cleanup.add(COLL_SETTINGS, {"_id": universo_id})

    await _insertar_si_no_existe(COLL_SETTINGS, _universo(universo_id, "Creado por el seed"))
    guardado = await test_db[COLL_SETTINGS].find_one({"_id": universo_id})

    assert guardado is not None
    assert guardado["nombre"] == "Creado por el seed"
    assert guardado["motor"] == "v1"


@pytest.mark.asyncio
async def test_seed_v2_repetido_no_pisa_ediciones(test_db, cleanup):
    marca = "marca_edicion_manual"
    evento_id = "evt_cometa_caido_v2"

    await seed_v2_graphs()
    await test_db[COLL_V2_EVENTS].update_one({"_id": evento_id}, {"$set": {marca: True}})
    cleanup.add(COLL_V2_EVENTS, {marca: True})

    await seed_v2_graphs()
    guardado = await test_db[COLL_V2_EVENTS].find_one({"_id": evento_id})

    assert guardado is not None
    assert guardado.get(marca) is True
