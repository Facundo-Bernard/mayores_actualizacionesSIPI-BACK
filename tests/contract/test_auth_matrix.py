"""Matriz de autenticación por grupo de endpoint, congelada sobre el comportamiento actual."""

import pytest

pytestmark = pytest.mark.contract


@pytest.mark.asyncio
async def test_public_endpoints_work_without_token(client, seeded_challenge):
    await seeded_challenge(game_id="wordle", date="2099-03-01")

    response = await client.get(
        "/api/challenges/date/2099-03-01",
        params={"game_id": "wordle", "difficulty": "standard"},
    )
    assert response.status_code == 200

    response = await client.get("/api/economy/config")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_upsert_challenge_is_public_without_token(client, cleanup):
    """Bug congelado (plan §2): POST /api/challenges permite pisar un desafío y su solución."""
    payload = {
        "game_id": "wordle",
        "date": "2099-03-02",
        "difficulty": "standard",
        "title": "Público",
        "config": {"solution": "PUBLIC"},
    }
    cleanup.add("daily_challenges", {"game_id": "wordle", "date": "2099-03-02"})

    response = await client.post("/api/challenges", json=payload)
    assert response.status_code == 200
    assert response.json()["config"]["solution"] == "PUBLIC"


@pytest.mark.asyncio
async def test_player_endpoints_require_token(client, seeded_user, make_token):
    response = await client.get("/api/economy/me")
    assert response.status_code == 401

    user = await seeded_user()
    token = make_token(user["id"])

    response = await client.get("/api/economy/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["user_id"] == user["id"]


@pytest.mark.asyncio
async def test_admin_endpoints_require_admin(client, seeded_user, make_token):
    params = {"year": 2099, "game_id": "wordle"}

    response = await client.get("/api/challenges/admin/status", params=params)
    assert response.status_code == 401

    player = await seeded_user(tipo_usuario=1)
    player_token = make_token(player["id"])

    response = await client.get(
        "/api/challenges/admin/status",
        params=params,
        headers={"Authorization": f"Bearer {player_token}"},
    )
    assert response.status_code == 403

    admin = await seeded_user(tipo_usuario=2)
    admin_token = make_token(admin["id"], tipo_usuario=2)

    response = await client.get(
        "/api/challenges/admin/status",
        params=params,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
