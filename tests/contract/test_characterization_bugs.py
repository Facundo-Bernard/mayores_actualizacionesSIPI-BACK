"""Bugs corregidos en Fase 1, congelados con el comportamiento esperado.

Cada test documenta una decisión deliberada del plan. Si el comportamiento
vuelve a cambiar, debe actualizarse a propósito.
"""

import pytest

pytestmark = pytest.mark.contract


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_attempts_without_token_returns_401_and_writes_nothing(client, test_db):
    response = await client.post(
        "/api/games/attempts",
        json={
            "user_id": 888888,
            "game_id": "wordle",
            "date": "2099-04-01",
            "status": "completed",
            "word": "TEST",
            "attempts": 1,
            "grade": "S",
        },
    )
    assert response.status_code == 401
    assert await test_db["user_attempts"].count_documents({"user_id": 888888}) == 0


@pytest.mark.asyncio
async def test_attempts_token_id_wins_over_body_user_id(
    client, test_db, seeded_user, make_token
):
    attacker = await seeded_user(puntos=0)
    victim_id = 888888
    token = make_token(attacker["id"])

    response = await client.post(
        "/api/games/attempts",
        json={
            "user_id": victim_id,
            "game_id": "wordle",
            "date": "2099-04-01",
            "status": "completed",
            "word": "TEST",
            "attempts": 1,
            "grade": "S",
        },
        headers=_auth(token),
    )
    assert response.status_code == 200
    assert response.json()["user_id"] == attacker["id"]

    stored = await test_db["user_attempts"].find_one(
        {"user_id": attacker["id"], "game_id": "wordle", "date": "2099-04-01"}
    )
    assert stored is not None
    assert await test_db["user_attempts"].count_documents({"user_id": victim_id}) == 0


@pytest.mark.asyncio
async def test_attempts_gets_require_token(client, seeded_user, make_token):
    user = await seeded_user()
    token = make_token(user["id"])

    assert (await client.get("/api/games/attempts/date/2099-04-10")).status_code == 401
    assert (await client.get("/api/games/attempts", params={"year": 2099})).status_code == 401

    response = await client.get(
        "/api/games/attempts", params={"year": 2099, "month": 4}, headers=_auth(token)
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_attempt_ignores_foreign_query_user_id(
    client, seeded_user, make_token
):
    owner = await seeded_user()
    token = make_token(owner["id"])

    await client.post(
        "/api/games/attempts",
        json={
            "game_id": "wordle",
            "date": "2099-04-11",
            "status": "completed",
            "word": "TEST",
            "attempts": 1,
            "grade": "S",
        },
        headers=_auth(token),
    )

    response = await client.get(
        "/api/games/attempts/date/2099-04-11",
        params={"game_id": "wordle", "user_id": 999999},
        headers=_auth(token),
    )
    assert response.status_code == 200
    assert response.json()["user_id"] == owner["id"]


@pytest.mark.asyncio
async def test_replay_does_not_recredit_points(client, test_db, seeded_user, make_token):
    user = await seeded_user(puntos=0)
    token = make_token(user["id"])
    payload = {
        "game_id": "wordle",
        "date": "2099-04-02",
        "status": "completed",
        "word": "TEST",
        "attempts": 1,
        "grade": "S",
    }

    first = await client.post("/api/games/attempts", json=payload, headers=_auth(token))
    assert first.json()["puntos_ganados"] == 100

    failed = await client.post(
        "/api/games/attempts", json={**payload, "status": "failed"}, headers=_auth(token)
    )
    assert failed.json()["puntos_ganados"] == 0
    assert failed.json()["status"] == "completed"

    replay = await client.post("/api/games/attempts", json=payload, headers=_auth(token))
    assert replay.json()["puntos_ganados"] == 0

    updated = await test_db["usuarios"].find_one({"id": user["id"]})
    assert updated["puntos"] == 100

    stored = await test_db["user_attempts"].find_one(
        {"user_id": user["id"], "game_id": "wordle", "date": "2099-04-02"}
    )
    assert stored["status"] == "completed"
    assert stored["grade"] == "S"

    rejected = await test_db["economy_ledger"].find_one(
        {"user_id": user["id"], "motivo": "replay_rejected"}
    )
    assert rejected is not None


@pytest.mark.asyncio
async def test_client_grade_is_authoritative_for_wordle(client, seeded_user, make_token):
    """Fase 1 mantiene la calificación del cliente; Fase 2 la validará por flag."""
    user = await seeded_user()
    response = await client.post(
        "/api/games/attempts",
        json={
            "game_id": "wordle",
            "date": "2099-04-03",
            "status": "completed",
            "word": "TEST",
            "attempts": 6,
            "grade": "S",
        },
        headers=_auth(make_token(user["id"])),
    )
    assert response.status_code == 200
    assert response.json()["grade"] == "S"
    assert response.json()["score"] == 100


@pytest.mark.asyncio
async def test_client_time_still_controls_grade_in_fase_1(client, seeded_user, make_token):
    """El tiempo server-side llega en Fase 2; se congela el comportamiento actual."""
    user = await seeded_user()
    response = await client.post(
        "/api/games/attempts",
        json={
            "game_id": "sudoku",
            "date": "2099-04-04",
            "status": "completed",
            "attempts": 1,
            "time_taken_seconds": 1,
            "game_data": {"timeTaken": 1},
        },
        headers=_auth(make_token(user["id"])),
    )
    assert response.status_code == 200
    assert response.json()["grade"] == "S"
    assert response.json()["score"] == 100


@pytest.mark.asyncio
async def test_sudoku_zero_remaining_attempts_no_longer_awards_s(
    client, seeded_user, make_token
):
    user = await seeded_user()
    response = await client.post(
        "/api/games/attempts",
        json={
            "game_id": "sudoku",
            "date": "2099-04-05",
            "status": "completed",
            "attempts": 3,
            "remaining_attempts": 0,
            "game_data": {"errors": 0},
        },
        headers=_auth(make_token(user["id"])),
    )
    assert response.status_code == 200
    assert response.json()["grade"] == "B"
    assert response.json()["score"] == 75


@pytest.mark.asyncio
async def test_invalid_numeric_errors_returns_400_not_500(client, seeded_user, make_token):
    user = await seeded_user()
    response = await client.post(
        "/api/games/attempts",
        json={
            "game_id": "sudoku",
            "date": "2099-04-07",
            "status": "completed",
            "attempts": 1,
            "game_data": {"errors": "no-es-un-numero"},
        },
        headers=_auth(make_token(user["id"])),
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_crucigrama_difficulties_credit_once_each(
    client, test_db, seeded_user, make_token
):
    user = await seeded_user()
    token = make_token(user["id"])
    base = {
        "game_id": "crucigrama",
        "date": "2099-04-06",
        "status": "completed",
        "attempts": 1,
        "game_data": {"errors": 0},
    }

    easy = await client.post(
        "/api/games/attempts",
        json={**base, "difficulty": "facil"},
        headers=_auth(token),
    )
    assert easy.json()["puntos_ganados"] == 100

    hard = await client.post(
        "/api/games/attempts",
        json={**base, "difficulty": "dificil"},
        headers=_auth(token),
    )
    assert hard.json()["puntos_ganados"] == 100

    # Replay de la dificultad difícil no vuelve a acreditar.
    hard_replay = await client.post(
        "/api/games/attempts",
        json={**base, "difficulty": "dificil"},
        headers=_auth(token),
    )
    assert hard_replay.json()["puntos_ganados"] == 0

    stored = await test_db["user_attempts"].find_one(
        {"user_id": user["id"], "game_id": "crucigrama", "date": "2099-04-06"}
    )
    assert set(stored["by_difficulty"]) >= {"facil", "dificil"}
    assert stored["by_difficulty"]["facil"]["status"] == "completed"
    assert stored["by_difficulty"]["dificil"]["status"] == "completed"

    updated = await test_db["usuarios"].find_one({"id": user["id"]})
    assert updated["puntos"] == 200

    seats = await test_db["economy_ledger"].count_documents(
        {"user_id": user["id"], "motivo": "attempt", "status": "applied"}
    )
    assert seats == 2


@pytest.mark.asyncio
async def test_player_cannot_refill_lives_via_adjust(client, seeded_user, make_token):
    """El ajuste admin sigue cerrado a jugadores; la recarga usa /refill-lives."""
    user = await seeded_user(puntos=500)
    token = make_token(user["id"])

    response = await client.post(
        "/api/admin/economy/user/adjust",
        json={"identificador": user["email"], "puntos_sumar": -50},
        headers=_auth(token),
    )
    assert response.status_code == 403
