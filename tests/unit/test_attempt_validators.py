"""Validadores puros de Fase 2: no requieren Mongo ni HTTP."""

import pytest

from app.features.user_attempts.validation.base import Submission
from app.features.user_attempts.validation.crucigrama import validate as validate_crucigrama
from app.features.user_attempts.validation.sopa import validate as validate_sopa
from app.features.user_attempts.validation.sudoku import validate as validate_sudoku
from app.features.user_attempts.validation.wordle import validate as validate_wordle

pytestmark = pytest.mark.unit


def _sudoku_solution() -> list[list[int]]:
    return [[((row * 3 + row // 3 + col) % 9) + 1 for col in range(9)] for row in range(9)]


def _sudoku_cells(solution: list[list[int]]) -> list[list[dict]]:
    return [[{"row": r, "col": c, "value": value} for c, value in enumerate(row)] for r, row in enumerate(solution)]


def test_wordle_counts_attempts_from_guesses_and_ignores_forged_attempts():
    config = {"solution": "TEST", "max_attempts": 6}
    submission = Submission(
        word="TEST",
        guesses=[{"word": "CASAS"}, {"word": "PLAYA"}, {"word": "TEST"}],
        attempts=1,
    )

    result = validate_wordle(config, submission)

    assert result.valid is True
    assert result.attempts == 3
    assert result.completed is True


def test_wordle_normalizes_accents():
    result = validate_wordle(
        {"solution": "LAPIZ", "max_attempts": 6},
        Submission(word="LÁPIZ", guesses=[], attempts=1),
    )

    assert result.valid is True
    assert result.attempts == 1


def test_wordle_rejects_missing_solution():
    result = validate_wordle(
        {"solution": "TEST", "max_attempts": 6},
        Submission(word="CASAS", guesses=[{"word": "CASAS"}], attempts=1),
    )

    assert result.valid is False
    assert result.reason == "solucion_no_encontrada"
    assert result.completed is False


def test_wordle_rejects_exceeding_max_attempts():
    guesses = [{"word": f"AAAA{i}"} for i in range(6)] + [{"word": "TEST"}]
    result = validate_wordle({"solution": "TEST", "max_attempts": 6}, Submission(guesses=guesses, attempts=7))

    assert result.valid is False
    assert result.reason == "intentos_excedidos"


def test_wordle_without_config_solution_is_rejected():
    result = validate_wordle({}, Submission(word="TEST", guesses=[{"word": "TEST"}], attempts=1))
    assert result.valid is False
    assert result.reason == "challenge_sin_solucion"


def test_sopa_requires_all_words():
    config = {"words": ["MANZANA", "PERA", "LIMON", "UVA"]}

    partial = validate_sopa(config, Submission(guesses=["MANZANA", "PERA"], attempts=2, errors=1))
    assert partial.valid is False
    assert partial.reason == "palabras_incompletas"
    assert partial.attempts == 2

    complete = validate_sopa(config, Submission(guesses=["MANZANA", "PERA", "LIMON", "UVA"], attempts=4, errors=1))
    assert complete.valid is True
    assert complete.attempts == 4


def test_sopa_ignores_unknown_words():
    result = validate_sopa({"words": ["UVA"]}, Submission(guesses=["UVA", "INVENTADA"], attempts=2))
    assert result.valid is True
    assert result.attempts == 1


def test_sudoku_accepts_grid_matching_solution():
    solution = _sudoku_solution()
    result = validate_sudoku(
        {"solution": solution},
        Submission(game_data={"cells": _sudoku_cells(solution)}, errors=1),
    )

    assert result.valid is True
    assert result.attempts == 1


def test_sudoku_rejects_incomplete_grid():
    solution = _sudoku_solution()
    cells = _sudoku_cells(solution)
    cells[0][0]["value"] = 0

    result = validate_sudoku({"solution": solution}, Submission(game_data={"cells": cells}))

    assert result.valid is False
    assert result.reason == "grilla_incompleta"


def test_sudoku_rejects_wrong_digit():
    solution = _sudoku_solution()
    cells = _sudoku_cells(solution)
    cells[4][4]["value"] = (cells[4][4]["value"] % 9) + 1

    result = validate_sudoku({"solution": solution}, Submission(game_data={"cells": cells}))

    assert result.valid is False
    assert result.reason == "grilla_incorrecta"


def _crucigrama_config() -> dict:
    return {
        "cells": [
            [{"is_block": False, "letter": "S"}, {"is_block": False, "letter": "O"}, {"is_block": True, "letter": ""}],
            [{"is_block": False, "letter": "L"}, {"is_block": False, "letter": "A"}, {"is_block": True, "letter": ""}],
        ],
        "words": [{"word": "SOL"}, {"word": "LA"}],
    }


def test_crucigrama_accepts_matching_grid_and_words():
    result = validate_crucigrama(
        _crucigrama_config(),
        Submission(game_data={"userGrid": [["S", "O", ""], ["L", "A", ""]]}, guesses=["SOL", "LA"], attempts=1),
    )

    assert result.valid is True
    assert result.completed is True


def test_crucigrama_rejects_wrong_letter():
    result = validate_crucigrama(
        _crucigrama_config(),
        Submission(game_data={"userGrid": [["S", "X", ""], ["L", "A", ""]]}, guesses=["SOL", "LA"], attempts=1),
    )

    assert result.valid is False
    assert result.reason == "grilla_incorrecta"


def test_crucigrama_rejects_missing_declared_words():
    result = validate_crucigrama(
        _crucigrama_config(),
        Submission(game_data={"userGrid": [["S", "O", ""], ["L", "A", ""]]}, guesses=["SOL"], attempts=1),
    )

    assert result.valid is False
    assert result.reason == "palabras_incompletas"
