"""Congela los bugs detectados en el relevamiento.

Cada test documenta el comportamiento actual; cuando la Fase 1 los corrija,
estos tests deben actualizarse a propósito, no "arreglarse" para que pasen.
"""

import pytest

pytestmark = pytest.mark.contract


@pytest.mark.asyncio
async def test_attempts_trust_body_user_id_without_token(client, test_db, seeded_user):
    """IDOR congelado: sin token, el body decide de quién es el intento."""
    victim_id = 888888
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
    )
    assert response.status_code == 200
    assert response.json()["user_id"] == victim_id

    stored = await test_db["user_attempts"].find_one(
        {"user_id": victim_id, "game_id": "wordle", "date": "2099-04-01"}
    )
    assert stored is not None
    await test_db["user_attempts"].delete_many({"user_id": victim_id})


@pytest.mark.asyncio
async def test_attempts_without_identity_returns_401(client):
    response = await client.post(
        "/api/games/attempts",
        json={"game_id": "wordle", "date": "2099-04-01", "status": "completed"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_replay_recredits_points(client, test_db, seeded_user):
    """Replay congelado: completed → failed → completed vuelve a acreditar."""
    user = await seeded_user(puntos=0)
    payload = {
        "user_id": user["id"],
        "game_id": "wordle",
        "date": "2099-04-02",
        "status": "completed",
        "word": "TEST",
        "attempts": 1,
        "grade": "S",
    }

    first = await client.post("/api/games/attempts", json=payload)
    assert first.json()["puntos_ganados"] == 100

    failed = await client.post("/api/games/attempts", json={**payload, "status": "failed"})
    assert failed.json()["puntos_ganados"] == 0

    replay = await client.post("/api/games/attempts", json={**payload, "status": "completed"})
    assert replay.json()["puntos_ganados"] == 100

    updated = await test_db["usuarios"].find_one({"id": user["id"]})
    assert updated["puntos"] == 200


@pytest.mark.asyncio
async def test_client_grade_is_authoritative_for_wordle(client, seeded_user):
    """El cliente puede declarar S aunque haya usado los 6 intentos."""
    user = await seeded_user()
    response = await client.post(
        "/api/games/attempts",
        json={
            "user_id": user["id"],
            "game_id": "wordle",
            "date": "2099-04-03",
            "status": "completed",
            "word": "TEST",
            "attempts": 6,
            "grade": "S",
        },
    )
    assert response.status_code == 200
    assert response.json()["grade"] == "S"
    assert response.json()["score"] == 100


@pytest.mark.asyncio
async def test_client_time_controls_grade(client, seeded_user):
    """El tiempo lo manda el cliente: 1 segundo alcanza para S en Sudoku."""
    user = await seeded_user()
    response = await client.post(
        "/api/games/attempts",
        json={
            "user_id": user["id"],
            "game_id": "sudoku",
            "date": "2099-04-04",
            "status": "completed",
            "attempts": 1,
            "time_taken_seconds": 1,
            "game_data": {"timeTaken": 1},
        },
    )
    assert response.status_code == 200
    assert response.json()["grade"] == "S"
    assert response.json()["score"] == 100


@pytest.mark.asyncio
async def test_sudoku_zero_remaining_attempts_awards_s(client, seeded_user):
    """Bug congelado: remaining_attempts == 0 se interpreta como S."""
    user = await seeded_user()
    response = await client.post(
        "/api/games/attempts",
        json={
            "user_id": user["id"],
            "game_id": "sudoku",
            "date": "2099-04-05",
            "status": "completed",
            "attempts": 3,
            "remaining_attempts": 0,
            "game_data": {"errors": 0},
        },
    )
    assert response.status_code == 200
    assert response.json()["grade"] == "S"


@pytest.mark.asyncio
async def test_crucigrama_difficulties_share_the_same_slot(client, test_db, seeded_user):
    """Fácil y difícil comparten clave única: la segunda dificultad no acredita."""
    user = await seeded_user()
    base = {
        "user_id": user["id"],
        "game_id": "crucigrama",
        "date": "2099-04-06",
        "status": "completed",
        "attempts": 1,
        "game_data": {"errors": 0, "difficulty": "facil"},
    }

    easy = await client.post("/api/games/attempts", json=base)
    assert easy.json()["puntos_ganados"] == 100

    hard = await client.post(
        "/api/games/attempts",
        json={**base, "game_data": {"errors": 0, "difficulty": "dificil"}},
    )
    assert hard.json()["puntos_ganados"] == 0

    stored = await test_db["user_attempts"].count_documents(
        {"user_id": user["id"], "game_id": "crucigrama", "date": "2099-04-06"}
    )
    assert stored == 1


@pytest.mark.asyncio
async def test_player_cannot_refill_lives_via_adjust(client, seeded_user, make_token):
    """P0 congelado: la recarga de 4 vidas por 50 puntos llama a un endpoint de admin."""
    user = await seeded_user(puntos=500)
    token = make_token(user["id"])

    response = await client.post(
        "/api/admin/economy/user/adjust",
        json={"identificador": user["email"], "puntos_sumar": -50},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
