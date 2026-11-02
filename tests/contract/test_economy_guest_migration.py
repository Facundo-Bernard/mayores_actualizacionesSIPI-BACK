"""Migración única de puntos de invitado a la cuenta autenticada (D4/D6)."""

import pytest

pytestmark = pytest.mark.contract

TOPE = 250


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _seeded_config(test_db, cleanup):
    await test_db["configuracion_economia"].replace_one(
        {"_id": "global_economy"},
        {"_id": "global_economy", "guest_migration_max_points": TOPE},
        upsert=True,
    )
    cleanup.add("configuracion_economia", {"_id": "global_economy"})


@pytest.mark.asyncio
async def test_migracion_aplica_tope_y_audita(client, test_db, cleanup, make_token, seeded_user):
    await _seeded_config(test_db, cleanup)
    user = await seeded_user(puntos=5)
    user_id = user["id"]
    cleanup.add("economy_ledger", {"_id": f"guest_migration:{user_id}"})

    respuesta = await client.post(
        "/api/economy/guest-migration",
        json={"guest_id": "invitado-migra-01", "puntos": TOPE + 500},
        headers=_auth(make_token(user_id)),
    )
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["success"] is True
    assert cuerpo["ya_migrado"] is False
    assert cuerpo["puntos_solicitados"] == TOPE + 500
    assert cuerpo["puntos_migrados"] == TOPE
    assert cuerpo["tope"] == TOPE
    assert cuerpo["puntos_totales"] == 5 + TOPE

    usuario = await test_db["usuarios"].find_one({"id": user_id})
    assert usuario["puntos"] == 5 + TOPE
    assert usuario["guest_migration_applied"] is True
    assert usuario["guest_migration_guest_id"] == "invitado-migra-01"

    auditoria = await test_db["economy_ledger"].find_one({"_id": f"guest_migration:{user_id}"})
    assert auditoria["motivo"] == "guest_migration"
    assert auditoria["status"] == "applied"
    assert auditoria["metadata"]["solicitado"] == TOPE + 500
    assert auditoria["metadata"]["aplicado"] == TOPE
    assert auditoria["metadata"]["tope"] == TOPE


@pytest.mark.asyncio
async def test_segundo_reclamo_no_suma_puntos(client, test_db, cleanup, make_token, seeded_user):
    await _seeded_config(test_db, cleanup)
    user = await seeded_user(puntos=0)
    user_id = user["id"]
    cleanup.add("economy_ledger", {"_id": f"guest_migration:{user_id}"})
    headers = _auth(make_token(user_id))

    primero = await client.post(
        "/api/economy/guest-migration",
        json={"guest_id": "invitado-migra-02", "puntos": 100},
        headers=headers,
    )
    assert primero.status_code == 200
    saldo = primero.json()["puntos_totales"]
    assert saldo == 100

    segundo = await client.post(
        "/api/economy/guest-migration",
        json={"guest_id": "otro-invitado", "puntos": 900},
        headers=headers,
    )
    assert segundo.status_code == 200
    cuerpo = segundo.json()
    assert cuerpo["success"] is False
    assert cuerpo["ya_migrado"] is True
    assert cuerpo["puntos_migrados"] == 0
    assert cuerpo["puntos_totales"] == saldo

    usuario = await test_db["usuarios"].find_one({"id": user_id})
    assert usuario["puntos"] == saldo


@pytest.mark.asyncio
async def test_migracion_sin_puntos_no_marca_la_cuenta(client, test_db, cleanup, make_token, seeded_user):
    await _seeded_config(test_db, cleanup)
    user = await seeded_user(puntos=0)
    user_id = user["id"]

    respuesta = await client.post(
        "/api/economy/guest-migration",
        json={"guest_id": "invitado-vacio", "puntos": 0},
        headers=_auth(make_token(user_id)),
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["puntos_migrados"] == 0

    usuario = await test_db["usuarios"].find_one({"id": user_id})
    assert "guest_migration_applied" not in usuario


@pytest.mark.asyncio
async def test_migracion_requiere_autenticacion(client, seeded_user):
    user = await seeded_user(puntos=0)
    respuesta = await client.post(
        "/api/economy/guest-migration",
        json={"guest_id": "invitado-anon", "puntos": 100},
    )
    assert respuesta.status_code == 401
