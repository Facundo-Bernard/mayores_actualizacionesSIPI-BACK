"""Contratos de Fase 2: validación server-side por flag y tiempo autoritativo."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings

pytestmark = pytest.mark.contract


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _sudoku_solution() -> list[list[int]]:
    return [[((row * 3 + row // 3 + col) % 9) + 1 for col in range(9)] for row in range(9)]


def _sudoku_cells(solution: list[list[int]]) -> list[list[dict]]:
    return [[{"row": r, "col": c, "value": value} for c, value in enumerate(row)] for r, row in enumerate(solution)]


@pytest.mark.asyncio
async def test_wordle_forged_completion_is_rejected_and_uncredited(
    client, test_db, seeded_user, seeded_challenge, make_token, monkeypatch
):
    monkeypatch.setattr(settings, "GRADING_ENFORCE_WORDLE", True)
    await seeded_challenge(game_id="wordle", date="2099-06-01", config={"solution": "TEST"})
    user = await seeded_user(puntos=0)

    response = await client.post(
        "/api/games/attempts",
        json={
            "game_id": "wordle",
            "date": "2099-06-01",
            "status": "completed",
            "word": "CASAS",
            "guesses": [{"word": "CASAS", "statuses": ["absent"] * 5}],
            "attempts": 1,
            "grade": "S",
            "score": 100,
            "stars": 3,
        },
        headers=_auth(make_token(user["id"])),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["puntos_ganados"] == 0
    assert body["grade"] == "F"
    assert body["score"] == 0
    assert body["stars"] == 0

    stored = await test_db["user_attempts"].find_one(
        {"user_id": user["id"], "game_id": "wordle", "date": "2099-06-01"}
    )
    assert stored["validation_status"] == "rejected"
    assert stored["validation_reason"] == "solucion_no_encontrada"

    updated = await test_db["usuarios"].find_one({"id": user["id"]})
    assert updated["puntos"] == 0
    assert await test_db["economy_ledger"].count_documents(
        {"user_id": user["id"], "motivo": "attempt"}
    ) == 0


@pytest.mark.asyncio
async def test_wordle_valid_submission_ignores_client_grade(
    client, test_db, seeded_user, seeded_challenge, make_token, monkeypatch
):
    monkeypatch.setattr(settings, "GRADING_ENFORCE_WORDLE", True)
    await seeded_challenge(game_id="wordle", date="2099-06-02", config={"solution": "TEST"})
    user = await seeded_user(puntos=0)

    response = await client.post(
        "/api/games/attempts",
        json={
            "game_id": "wordle",
            "date": "2099-06-02",
            "status": "completed",
            "word": "TEST",
            "guesses": [{"word": "CASAS"}, {"word": "PLAYA"}, {"word": "TEST"}],
            "attempts": 1,
            "grade": "S",
            "score": 100,
            "stars": 3,
        },
        headers=_auth(make_token(user["id"])),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["grade"] == "B"
    assert body["score"] == 75
    assert body["stars"] == 2
    assert body["attempts"] == 3
    assert body["puntos_ganados"] == 75

    stored = await test_db["user_attempts"].find_one(
        {"user_id": user["id"], "game_id": "wordle", "date": "2099-06-02"}
    )
    assert stored["validation_status"] == "validated"


@pytest.mark.asyncio
async def test_rejected_wordle_allows_legit_retry_once(
    client, test_db, seeded_user, seeded_challenge, make_token, monkeypatch
):
    monkeypatch.setattr(settings, "GRADING_ENFORCE_WORDLE", True)
    await seeded_challenge(game_id="wordle", date="2099-06-03", config={"solution": "TEST"})
    user = await seeded_user(puntos=0)
    token = make_token(user["id"])

    forged = await client.post(
        "/api/games/attempts",
        json={
            "game_id": "wordle",
            "date": "2099-06-03",
            "status": "completed",
            "word": "CASAS",
            "guesses": [{"word": "CASAS"}],
            "attempts": 1,
            "grade": "S",
        },
        headers=_auth(token),
    )
    assert forged.json()["puntos_ganados"] == 0

    legit = await client.post(
        "/api/games/attempts",
        json={
            "game_id": "wordle",
            "date": "2099-06-03",
            "status": "completed",
            "word": "TEST",
            "guesses": [{"word": "TEST"}],
            "attempts": 1,
        },
        headers=_auth(token),
    )
    assert legit.status_code == 200
    assert legit.json()["puntos_ganados"] == 100
    assert legit.json()["grade"] == "S"

    stored = await test_db["user_attempts"].find_one(
        {"user_id": user["id"], "game_id": "wordle", "date": "2099-06-03"}
    )
    assert stored["validation_status"] == "validated"
    assert stored["by_difficulty"]["standard"]["validation_status"] == "validated"

    updated = await test_db["usuarios"].find_one({"id": user["id"]})
    assert updated["puntos"] == 100
    assert await test_db["economy_ledger"].count_documents(
        {"user_id": user["id"], "motivo": "attempt", "status": "applied"}
    ) == 1


@pytest.mark.asyncio
async def test_wordle_flag_off_keeps_client_grade(
    client, seeded_user, seeded_challenge, make_token
):
    assert settings.GRADING_ENFORCE_WORDLE is False
    await seeded_challenge(game_id="wordle", date="2099-06-04", config={"solution": "TEST"})
    user = await seeded_user(puntos=0)

    response = await client.post(
        "/api/games/attempts",
        json={
            "game_id": "wordle",
            "date": "2099-06-04",
            "status": "completed",
            "word": "CASAS",
            "guesses": [{"word": "CASAS"}],
            "attempts": 1,
            "grade": "S",
        },
        headers=_auth(make_token(user["id"])),
    )

    assert response.status_code == 200
    assert response.json()["grade"] == "S"
    assert response.json()["puntos_ganados"] == 100


@pytest.mark.asyncio
async def test_sopa_completion_requires_every_word(
    client, test_db, seeded_user, seeded_challenge, make_token, monkeypatch
):
    monkeypatch.setattr(settings, "GRADING_ENFORCE_SOPA", True)
    config = {"words": ["MANZANA", "PERA", "LIMON", "UVA"]}
    await seeded_challenge(game_id="sopa_letras", date="2099-06-05", config=config)

    partial_user = await seeded_user(puntos=0)
    partial = await client.post(
        "/api/games/attempts",
        json={
            "game_id": "sopa_letras",
            "date": "2099-06-05",
            "status": "completed",
            "word": "Frutas",
            "guesses": ["MANZANA", "PERA"],
            "attempts": 2,
            "game_data": {"errors": 0},
        },
        headers=_auth(make_token(partial_user["id"])),
    )
    assert partial.status_code == 200
    assert partial.json()["puntos_ganados"] == 0
    stored = await test_db["user_attempts"].find_one({"user_id": partial_user["id"]})
    assert stored["validation_reason"] == "palabras_incompletas"

    complete_user = await seeded_user(puntos=0)
    complete = await client.post(
        "/api/games/attempts",
        json={
            "game_id": "sopa_letras",
            "date": "2099-06-05",
            "status": "completed",
            "word": "Frutas",
            "guesses": ["MANZANA", "PERA", "LIMON", "UVA"],
            "attempts": 4,
            "game_data": {"errors": 0},
        },
        headers=_auth(make_token(complete_user["id"])),
    )
    assert complete.status_code == 200
    assert complete.json()["puntos_ganados"] == 100
    assert complete.json()["grade"] == "S"


@pytest.mark.asyncio
async def test_sudoku_completion_requires_full_matching_grid(
    client, test_db, seeded_user, seeded_challenge, make_token, monkeypatch
):
    monkeypatch.setattr(settings, "GRADING_ENFORCE_SUDOKU", True)
    solution = _sudoku_solution()
    await seeded_challenge(game_id="sudoku", date="2099-06-06", config={"solution": solution})

    valid_user = await seeded_user(puntos=0)
    valid = await client.post(
        "/api/games/attempts",
        json={
            "game_id": "sudoku",
            "date": "2099-06-06",
            "status": "won",
            "attempts": 1,
            "remaining_attempts": 4,
            "game_data": {"cells": _sudoku_cells(solution), "errors": 0},
        },
        headers=_auth(make_token(valid_user["id"])),
    )
    assert valid.status_code == 200
    assert valid.json()["puntos_ganados"] == 100
    assert valid.json()["grade"] == "S"

    wrong_cells = _sudoku_cells(solution)
    wrong_cells[0][0]["value"] = 0
    invalid_user = await seeded_user(puntos=0)
    invalid = await client.post(
        "/api/games/attempts",
        json={
            "game_id": "sudoku",
            "date": "2099-06-06",
            "status": "won",
            "attempts": 1,
            "remaining_attempts": 4,
            "game_data": {"cells": wrong_cells, "errors": 0},
        },
        headers=_auth(make_token(invalid_user["id"])),
    )
    assert invalid.status_code == 200
    assert invalid.json()["puntos_ganados"] == 0
    stored = await test_db["user_attempts"].find_one({"user_id": invalid_user["id"]})
    assert stored["validation_reason"] == "grilla_incompleta"


@pytest.mark.asyncio
async def test_crucigrama_resolves_challenge_by_difficulty(
    client, test_db, seeded_user, seeded_challenge, make_token, monkeypatch
):
    monkeypatch.setattr(settings, "GRADING_ENFORCE_CRUCIGRAMA", True)
    await seeded_challenge(
        game_id="crucigrama",
        date="2099-06-07",
        difficulty="facil",
        config={
            "cells": [
                [{"is_block": False, "letter": "S"}, {"is_block": False, "letter": "O"}],
                [{"is_block": True, "letter": ""}, {"is_block": True, "letter": ""}],
            ],
            "words": [{"word": "SO"}],
        },
    )
    await seeded_challenge(
        game_id="crucigrama",
        date="2099-06-07",
        difficulty="dificil",
        config={
            "cells": [
                [{"is_block": False, "letter": "L"}, {"is_block": False, "letter": "A"}],
                [{"is_block": True, "letter": ""}, {"is_block": True, "letter": ""}],
            ],
            "words": [{"word": "LA"}],
        },
    )
    user = await seeded_user(puntos=0)
    token = make_token(user["id"])
    base = {
        "game_id": "crucigrama",
        "date": "2099-06-07",
        "status": "completed",
        "attempts": 1,
        "guesses": ["LA"],
        "game_data": {"difficulty": "dificil", "userGrid": [["L", "A"], ["", ""]], "errors": 0},
    }

    hard = await client.post("/api/games/attempts", json=base, headers=_auth(token))
    assert hard.status_code == 200
    assert hard.json()["puntos_ganados"] == 100
    assert hard.json()["attempts"] == 1

    easy = await client.post(
        "/api/games/attempts",
        json={
            **base,
            "difficulty": "facil",
            "guesses": ["SO"],
            "game_data": {"difficulty": "facil", "userGrid": [["S", "O"], ["", ""]], "errors": 0},
        },
        headers=_auth(token),
    )
    assert easy.status_code == 200
    assert easy.json()["puntos_ganados"] == 100

    stored = await test_db["user_attempts"].find_one(
        {"user_id": user["id"], "game_id": "crucigrama", "date": "2099-06-07"}
    )
    assert stored["by_difficulty"]["facil"]["validation_status"] == "validated"
    assert stored["by_difficulty"]["dificil"]["validation_status"] == "validated"


@pytest.mark.asyncio
async def test_enabled_game_without_challenge_rejects_completion(
    client, test_db, seeded_user, make_token, monkeypatch
):
    monkeypatch.setattr(settings, "GRADING_ENFORCE_WORDLE", True)
    user = await seeded_user(puntos=0)

    response = await client.post(
        "/api/games/attempts",
        json={
            "game_id": "wordle",
            "date": "2099-06-08",
            "status": "completed",
            "word": "TEST",
            "guesses": [{"word": "TEST"}],
            "attempts": 1,
        },
        headers=_auth(make_token(user["id"])),
    )

    assert response.status_code == 200
    assert response.json()["puntos_ganados"] == 0
    stored = await test_db["user_attempts"].find_one({"user_id": user["id"]})
    assert stored["validation_reason"] == "desafio_no_encontrado"


@pytest.mark.asyncio
async def test_server_time_flags_suspicious_client_time(
    client, test_db, seeded_user, seeded_challenge, make_token, monkeypatch
):
    monkeypatch.setattr(settings, "GRADING_ENFORCE_SUDOKU", True)
    solution = _sudoku_solution()
    await seeded_challenge(game_id="sudoku", date="2099-06-09", config={"solution": solution})
    user = await seeded_user(puntos=0)
    token = make_token(user["id"])
    query = {"user_id": user["id"], "game_id": "sudoku", "date": "2099-06-09"}

    progress = await client.post(
        "/api/games/attempts",
        json={"game_id": "sudoku", "date": "2099-06-09", "status": "in_progress", "attempts": 0},
        headers=_auth(token),
    )
    assert progress.status_code == 200

    started = datetime.now(timezone.utc) - timedelta(seconds=400)
    await test_db["user_attempts"].update_one(
        query,
        {"$set": {"started_at": started, "by_difficulty.standard.started_at": started}},
    )

    final = await client.post(
        "/api/games/attempts",
        json={
            "game_id": "sudoku",
            "date": "2099-06-09",
            "status": "won",
            "attempts": 1,
            "remaining_attempts": 4,
            "time_taken_seconds": 1,
            "game_data": {"cells": _sudoku_cells(solution), "timeTaken": 1, "errors": 0},
        },
        headers=_auth(token),
    )

    assert final.status_code == 200
    assert final.json()["grade"] == "B"
    assert final.json()["score"] == 75
    stored = await test_db["user_attempts"].find_one(query)
    assert stored["time_suspect"] is True
    assert stored["server_elapsed_seconds"] >= 399


@pytest.mark.asyncio
async def test_consistent_client_time_is_not_flagged(
    client, test_db, seeded_user, seeded_challenge, make_token, monkeypatch
):
    monkeypatch.setattr(settings, "GRADING_ENFORCE_SUDOKU", True)
    solution = _sudoku_solution()
    await seeded_challenge(game_id="sudoku", date="2099-06-10", config={"solution": solution})
    user = await seeded_user(puntos=0)
    token = make_token(user["id"])
    query = {"user_id": user["id"], "game_id": "sudoku", "date": "2099-06-10"}

    await client.post(
        "/api/games/attempts",
        json={"game_id": "sudoku", "date": "2099-06-10", "status": "in_progress", "attempts": 0},
        headers=_auth(token),
    )
    started = datetime.now(timezone.utc) - timedelta(seconds=100)
    await test_db["user_attempts"].update_one(
        query,
        {"$set": {"started_at": started, "by_difficulty.standard.started_at": started}},
    )

    final = await client.post(
        "/api/games/attempts",
        json={
            "game_id": "sudoku",
            "date": "2099-06-10",
            "status": "won",
            "attempts": 1,
            "remaining_attempts": 4,
            "time_taken_seconds": 95,
            "game_data": {"cells": _sudoku_cells(solution), "timeTaken": 95, "errors": 0},
        },
        headers=_auth(token),
    )

    assert final.status_code == 200
    assert final.json()["grade"] == "S"
    stored = await test_db["user_attempts"].find_one(query)
    assert stored.get("time_suspect") is not True
    assert stored["started_at"] is not None
    assert 95 <= stored["server_elapsed_seconds"] <= 120
