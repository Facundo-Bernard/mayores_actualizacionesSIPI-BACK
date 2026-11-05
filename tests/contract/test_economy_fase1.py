"""Contratos de Fase 1: recarga fija, pistas idempotentes, ledger y ajustes admin."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.shared.ledger import reconcile_pending_ledger

pytestmark = pytest.mark.contract


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_refill_lives_charges_fixed_server_price(client, test_db, seeded_user, make_token):
    user = await seeded_user(puntos=500)
    token = make_token(user["id"])

    response = await client.post("/api/economy/refill-lives", headers=_auth(token))
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["puntos"] == 450

    stored = await test_db["usuarios"].find_one({"id": user["id"]})
    assert stored["puntos"] == 450


@pytest.mark.asyncio
async def test_refill_lives_ignores_client_quantity_and_cost(
    client, test_db, seeded_user, make_token
):
    user = await seeded_user(puntos=500)
    token = make_token(user["id"])

    response = await client.post(
        "/api/economy/refill-lives",
        json={"cantidad": 999, "vidas": 999, "costo": 1},
        headers=_auth(token),
    )
    assert response.status_code == 200
    assert response.json()["puntos"] == 450


@pytest.mark.asyncio
async def test_refill_lives_without_balance_returns_400(client, test_db, seeded_user, make_token):
    user = await seeded_user(puntos=10)
    token = make_token(user["id"])

    response = await client.post("/api/economy/refill-lives", headers=_auth(token))
    assert response.status_code == 400

    stored = await test_db["usuarios"].find_one({"id": user["id"]})
    assert stored["puntos"] == 10


@pytest.mark.asyncio
async def test_refill_lives_requires_token(client):
    response = await client.post("/api/economy/refill-lives")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_adjust_is_atomic_and_audited(
    client, test_db, seeded_user, admin_override
):
    user = await seeded_user(puntos=0, vidas=0)

    response = await client.post(
        "/api/admin/economy/user/adjust",
        json={"identificador": str(user["id"]), "vidas_sumar": -10, "puntos_sumar": -10},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["vidas"] == 0
    assert body["puntos"] == 0

    stored = await test_db["usuarios"].find_one({"id": user["id"]})
    assert stored["vidas"] == 0
    assert stored["puntos"] == 0

    audit = await test_db["economy_ledger"].find_one(
        {"user_id": user["id"], "motivo": "admin_adjust"}
    )
    assert audit is not None
    assert audit["metadata"]["actor"] == 900001


@pytest.mark.asyncio
async def test_hint_charges_once_and_returns_same_content(
    client, test_db, seeded_user, seeded_challenge, make_token
):
    await seeded_challenge(
        game_id="wordle",
        date="2099-05-01",
        config={"solution": "TEST", "hints": ["Empieza con T"]},
    )
    user = await seeded_user(puntos=100)
    token = make_token(user["id"])
    payload = {"game_id": "wordle", "date": "2099-05-01", "hint_index": 0}

    first = await client.post("/api/economy/use-hint", json=payload, headers=_auth(token))
    assert first.status_code == 200
    assert first.json()["puntos_descontados"] == 20
    assert first.json()["pista"] == "Empieza con T"
    assert first.json()["puntos_restantes"] == 80

    second = await client.post("/api/economy/use-hint", json=payload, headers=_auth(token))
    assert second.status_code == 200
    assert second.json()["puntos_descontados"] == 0
    assert second.json()["pista"] == "Empieza con T"
    assert second.json()["puntos_restantes"] == 80

    stored = await test_db["usuarios"].find_one({"id": user["id"]})
    assert stored["puntos"] == 80


@pytest.mark.asyncio
async def test_hint_without_content_does_not_charge(
    client, test_db, seeded_user, seeded_challenge, make_token
):
    await seeded_challenge(game_id="wordle", date="2099-05-02", config={})
    user = await seeded_user(puntos=100)
    token = make_token(user["id"])

    response = await client.post(
        "/api/economy/use-hint",
        json={"game_id": "wordle", "date": "2099-05-02", "hint_index": 0},
        headers=_auth(token),
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["puntos_descontados"] == 0
    assert response.json()["pista"] is None

    stored = await test_db["usuarios"].find_one({"id": user["id"]})
    assert stored["puntos"] == 100


@pytest.mark.asyncio
async def test_hint_without_balance_does_not_leave_pending_record(
    client, test_db, seeded_user, seeded_challenge, make_token
):
    await seeded_challenge(
        game_id="wordle",
        date="2099-05-03",
        config={"solution": "TEST", "hints": ["Ayuda"]},
    )
    user = await seeded_user(puntos=5)
    token = make_token(user["id"])

    response = await client.post(
        "/api/economy/use-hint",
        json={"game_id": "wordle", "date": "2099-05-03", "hint_index": 0},
        headers=_auth(token),
    )
    assert response.status_code == 400
    assert await test_db["user_hints"].count_documents({"user_id": user["id"]}) == 0

    stored = await test_db["usuarios"].find_one({"id": user["id"]})
    assert stored["puntos"] == 5


@pytest.mark.asyncio
async def test_hint_infers_difficulty_from_attempt(
    client, test_db, seeded_user, seeded_challenge, make_token, cleanup
):
    await seeded_challenge(
        game_id="crucigrama",
        date="2099-05-04",
        difficulty="facil",
        config={"words": [{"direction": "Horiz.", "number": 1, "clue": "Pista fácil"}]},
    )
    await seeded_challenge(
        game_id="crucigrama",
        date="2099-05-04",
        difficulty="dificil",
        config={"words": [{"direction": "Vert.", "number": 2, "clue": "Pista difícil"}]},
    )
    user = await seeded_user(puntos=100)
    cleanup.add("user_attempts", {"user_id": user["id"]})
    await test_db["user_attempts"].insert_one(
        {
            "user_id": user["id"],
            "game_id": "crucigrama",
            "date": "2099-05-04",
            "difficulty": "dificil",
            "status": "in_progress",
        }
    )
    token = make_token(user["id"])

    response = await client.post(
        "/api/economy/use-hint",
        json={"game_id": "crucigrama", "date": "2099-05-04", "hint_index": 0},
        headers=_auth(token),
    )
    assert response.status_code == 200
    assert "difícil" in (response.json()["pista"] or "")

    record = await test_db["user_hints"].find_one({"user_id": user["id"]})
    assert record["difficulty"] == "dificil"


@pytest.mark.asyncio
async def test_concurrent_completion_credits_once(
    client, test_db, seeded_user, make_token
):
    user = await seeded_user(puntos=0)
    token = make_token(user["id"])
    payload = {
        "game_id": "wordle",
        "date": "2099-05-05",
        "status": "completed",
        "word": "TEST",
        "attempts": 1,
        "grade": "S",
    }

    responses = await asyncio.gather(
        client.post("/api/games/attempts", json=payload, headers=_auth(token)),
        client.post("/api/games/attempts", json=payload, headers=_auth(token)),
    )
    assert all(r.status_code == 200 for r in responses)
    assert sum(r.json()["puntos_ganados"] for r in responses) == 100

    stored = await test_db["usuarios"].find_one({"id": user["id"]})
    assert stored["puntos"] == 100
    seats = await test_db["economy_ledger"].count_documents(
        {"user_id": user["id"], "motivo": "attempt", "status": "applied"}
    )
    assert seats == 1


@pytest.mark.asyncio
async def test_pending_ledger_is_reconciled_once(test_db, seeded_user):
    user = await seeded_user(puntos=0)
    key = f"attempt:{user['id']}:wordle:2099-05-06:standard"
    await test_db["economy_ledger"].insert_one(
        {
            "_id": key,
            "idempotency_key": key,
            "user_id": user["id"],
            "motivo": "attempt",
            "game_id": "wordle",
            "date": "2099-05-06",
            "difficulty": "standard",
            "puntos": 25,
            "status": "pending",
            "created_at": datetime.now(timezone.utc) - timedelta(minutes=5),
        }
    )

    await reconcile_pending_ledger(older_than_seconds=0)
    first = await test_db["usuarios"].find_one({"id": user["id"]})
    assert first["puntos"] == 25

    seat = await test_db["economy_ledger"].find_one({"_id": key})
    assert seat["status"] == "applied"
    assert seat["saldo_despues"] == 25

    await reconcile_pending_ledger(older_than_seconds=0)
    second = await test_db["usuarios"].find_one({"id": user["id"]})
    assert second["puntos"] == 25
