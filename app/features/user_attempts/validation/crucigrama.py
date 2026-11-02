"""Crucigrama: la grilla del usuario y las palabras declaradas deben estar completas."""

from typing import Any, Dict

from app.features.user_attempts.validation.base import (
    Submission,
    ValidationResult,
    accept,
    normalize_word,
)


def _expected_letter(cell: Any) -> str:
    if not isinstance(cell, dict) or cell.get("is_block"):
        return ""
    return normalize_word(cell.get("letter"))


def validate(config: Dict[str, Any], submission: Submission) -> ValidationResult:
    cells = config.get("cells")
    if not isinstance(cells, list) or not cells:
        return ValidationResult(False, "challenge_sin_grilla", submission.attempts, submission.errors, False)

    user_grid = (submission.game_data or {}).get("userGrid")
    if not isinstance(user_grid, list) or len(user_grid) != len(cells):
        return ValidationResult(False, "grilla_ausente", submission.attempts, submission.errors, False)

    for row_index, row in enumerate(cells):
        user_row = user_grid[row_index]
        if not isinstance(row, list) or not isinstance(user_row, list) or len(user_row) != len(row):
            return ValidationResult(False, "grilla_incompleta", submission.attempts, submission.errors, False)
        for col_index, cell in enumerate(row):
            expected = _expected_letter(cell)
            if expected and normalize_word(user_row[col_index]) != expected:
                return ValidationResult(False, "grilla_incorrecta", submission.attempts, submission.errors, False)

    expected_words = {
        normalize_word(w.get("word") if isinstance(w, dict) else w)
        for w in (config.get("words") or [])
    }
    expected_words.discard("")
    if not expected_words:
        return ValidationResult(False, "challenge_sin_palabras", submission.attempts, submission.errors, False)

    submitted_words = set()
    for item in submission.guesses:
        raw = item.get("word") if isinstance(item, dict) else item
        submitted_words.add(normalize_word(raw))

    if expected_words - submitted_words:
        return ValidationResult(False, "palabras_incompletas", submission.attempts, submission.errors, False)

    return accept(submission.attempts, submission.errors)
