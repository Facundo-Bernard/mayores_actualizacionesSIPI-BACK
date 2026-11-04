"""Racha diaria derivada de user_attempts, expuesta en /api/economy/me."""

from datetime import timedelta

import pytest

from app.shared.clock import today_art

pytestmark = pytest.mark.contract


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _fecha(dias_atras: int) -> str:
    return (today_art() - timedelta(days=dias_atras)).isoformat()


async def _intento(
    test_db,
    user_id: int,
    fecha: str,
    *,
    game_id: str = "wordle",
    mode: str = "daily",
    status: str = "completed",
    validation_status: str | None = None,
):
    doc = {
        "user_id": user_id,
        "game_id": game_id,
        "date": fecha,
        "mode": mode,
        "status": status,
        "attempts": 1,
        "stars": 3,
        "score": 100,
    }
    if validation_status is not None:
        doc["validation_status"] = validation_status
    await test_db["user_attempts"].insert_one(doc)


async def _economia(client, token: str) -> dict:
    response = await client.get("/api/economy/me", headers=_auth(token))
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_sin_intentos_devuelve_racha_cero(client, seeded_user, make_token):
    user = await seeded_user()
    body = await _economia(client, make_token(user["id"]))

    assert body["racha"] == 0
    assert body["racha_ultima_fecha"] is None
    assert body["racha_hoy_jugada"] is False


@pytest.mark.asyncio
async def test_racha_cuenta_dias_consecutivos_hasta_hoy(
    client, test_db, seeded_user, make_token
):
    user = await seeded_user()
    for dias in (0, 1, 2):
        await _intento(test_db, user["id"], _fecha(dias))

    body = await _economia(client, make_token(user["id"]))

    assert body["racha"] == 3
    assert body["racha_ultima_fecha"] == _fecha(0)
    assert body["racha_hoy_jugada"] is True


@pytest.mark.asyncio
async def test_racha_sigue_viva_si_jugo_ayer(client, test_db, seeded_user, make_token):
    user = await seeded_user()
    for dias in (1, 2):
        await _intento(test_db, user["id"], _fecha(dias))

    body = await _economia(client, make_token(user["id"]))

    assert body["racha"] == 2
    assert body["racha_ultima_fecha"] == _fecha(1)
    assert body["racha_hoy_jugada"] is False


@pytest.mark.asyncio
async def test_racha_se_corta_con_un_hueco(client, test_db, seeded_user, make_token):
    user = await seeded_user()
    for dias in (0, 1, 3):
        await _intento(test_db, user["id"], _fecha(dias))

    body = await _economia(client, make_token(user["id"]))

    assert body["racha"] == 2


@pytest.mark.asyncio
async def test_racha_corta_si_el_ultimo_dia_es_anterior_a_ayer(
    client, test_db, seeded_user, make_token
):
    user = await seeded_user()
    for dias in (2, 3):
        await _intento(test_db, user["id"], _fecha(dias))

    body = await _economia(client, make_token(user["id"]))

    assert body["racha"] == 0
    assert body["racha_ultima_fecha"] == _fecha(2)
    assert body["racha_hoy_jugada"] is False


@pytest.mark.asyncio
async def test_varios_juegos_el_mismo_dia_cuentan_uno(
    client, test_db, seeded_user, make_token
):
    user = await seeded_user()
    hoy = _fecha(0)
    await _intento(test_db, user["id"], hoy, game_id="wordle")
    await _intento(test_db, user["id"], hoy, game_id="sudoku")
    await _intento(test_db, user["id"], _fecha(1), game_id="crucigrama")

    body = await _economia(client, make_token(user["id"]))

    assert body["racha"] == 2


@pytest.mark.asyncio
async def test_intento_rechazado_no_cuenta(client, test_db, seeded_user, make_token):
    user = await seeded_user()
    await _intento(test_db, user["id"], _fecha(0), validation_status="rejected")
    await _intento(test_db, user["id"], _fecha(1))

    body = await _economia(client, make_token(user["id"]))

    assert body["racha"] == 1
    assert body["racha_ultima_fecha"] == _fecha(1)
    assert body["racha_hoy_jugada"] is False


@pytest.mark.asyncio
async def test_modo_campaign_no_cuenta(client, test_db, seeded_user, make_token):
    user = await seeded_user()
    await _intento(test_db, user["id"], _fecha(0), mode="campaign")
    await _intento(test_db, user["id"], _fecha(1))

    body = await _economia(client, make_token(user["id"]))

    assert body["racha"] == 1
    assert body["racha_hoy_jugada"] is False


@pytest.mark.asyncio
async def test_intento_en_curso_no_cuenta(client, test_db, seeded_user, make_token):
    user = await seeded_user()
    await _intento(test_db, user["id"], _fecha(0), status="in_progress")
    await _intento(test_db, user["id"], _fecha(1))

    body = await _economia(client, make_token(user["id"]))

    assert body["racha"] == 1


@pytest.mark.asyncio
async def test_fecha_futura_no_cuenta(client, test_db, seeded_user, make_token):
    user = await seeded_user()
    await _intento(test_db, user["id"], _fecha(-1))
    await _intento(test_db, user["id"], _fecha(1))

    body = await _economia(client, make_token(user["id"]))

    assert body["racha"] == 1
    assert body["racha_ultima_fecha"] == _fecha(1)


@pytest.mark.asyncio
async def test_racha_no_se_mezcla_entre_usuarios(
    client, test_db, seeded_user, make_token
):
    user = await seeded_user()
    otro = await seeded_user()
    for dias in (0, 1, 2):
        await _intento(test_db, otro["id"], _fecha(dias))

    body = await _economia(client, make_token(user["id"]))

    assert body["racha"] == 0
