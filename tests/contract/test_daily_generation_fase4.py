"""Fase 4: seeds no destructivos y regeneración forzada protegida por intentos."""

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.features.daily_challenges.service import assert_month_regenerable
from app.scripts.seed_challenges import WORDLE_AGOSTO_2026, seed_wordle_challenges
from app.scripts.seed_sopa_letras import seed_sopa_letras_challenges

pytestmark = pytest.mark.contract


def _attempt(user_id: int, game_id: str, date: str) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "user_id": user_id,
        "game_id": game_id,
        "date": date,
        "difficulty": "standard",
        "status": "completed",
        "created_at": now,
        "updated_at": now,
    }


@pytest.mark.asyncio
async def test_assert_month_regenerable_blocks_month_with_attempts(test_db, cleanup):
    await test_db["user_attempts"].insert_one(_attempt(810001, "sudoku", "2031-03-14"))
    cleanup.add("user_attempts", {"user_id": 810001})

    with pytest.raises(HTTPException) as exc:
        await assert_month_regenerable("sudoku", 2031, 3)

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_assert_month_regenerable_allows_month_without_attempts(test_db):
    await assert_month_regenerable("sudoku", 2031, 4)


@pytest.mark.asyncio
async def test_admin_generate_month_uses_force_false_by_default(
    client, admin_override, monkeypatch
):
    import importlib

    router_module = importlib.import_module("app.features.daily_challenges.router")
    llamadas = []

    async def _stub(year, month, force=False):
        llamadas.append((year, month, force))
        return {"success": True, "generated_count": 0}

    monkeypatch.setattr(router_module, "generate_and_save_sudoku_month", _stub)

    response = await client.post(
        "/api/challenges/admin/generate-month",
        params={"year": 2031, "month": 5, "game_id": "sudoku"},
    )

    assert response.status_code == 200
    assert llamadas == [(2031, 5, False)]


@pytest.mark.asyncio
async def test_admin_generate_month_force_returns_409_with_attempts(
    client, test_db, cleanup, admin_override
):
    await test_db["user_attempts"].insert_one(_attempt(810002, "sudoku", "2031-06-02"))
    cleanup.add("user_attempts", {"user_id": 810002})

    response = await client.post(
        "/api/challenges/admin/generate-month",
        params={"year": 2031, "month": 6, "game_id": "sudoku", "force": "true"},
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_seed_wordle_no_pisa_ediciones(test_db, cleanup):
    fecha = WORDLE_AGOSTO_2026[0]["date"]
    query = {"game_id": "wordle", "date": fecha, "difficulty": "standard"}
    await test_db["daily_challenges"].update_one(
        query, {"$set": {"editado_por_admin": True}}, upsert=True
    )
    cleanup.add(
        "daily_challenges",
        {"game_id": "wordle", "date": {"$gte": "2026-08-01", "$lte": "2026-10-31"}},
    )

    await seed_wordle_challenges()

    guardado = await test_db["daily_challenges"].find_one(query)
    assert guardado.get("editado_por_admin") is True


@pytest.mark.asyncio
async def test_seed_sopa_no_pisa_ediciones(test_db, cleanup):
    from app.scripts.seed_sopa_letras import SOPA_LETRAS_RAW_DATA

    fecha = SOPA_LETRAS_RAW_DATA[0][0]
    query = {"game_id": "sopa_letras", "date": fecha, "difficulty": "standard"}
    await test_db["daily_challenges"].update_one(
        query, {"$set": {"editado_por_admin": True}}, upsert=True
    )
    cleanup.add(
        "daily_challenges",
        {"game_id": "sopa_letras", "date": {"$gte": "2026-08-01", "$lte": "2026-10-31"}},
    )

    await seed_sopa_letras_challenges()

    guardado = await test_db["daily_challenges"].find_one(query)
    assert guardado.get("editado_por_admin") is True
