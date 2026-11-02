"""Sudoku: la grilla enviada debe coincidir con la solución oficial."""

from typing import Any, Dict, Optional

from app.features.user_attempts.validation.base import (
    Submission,
    ValidationResult,
    accept,
    coerce_int,
)

GRID_SIZE = 9


def _is_grid(value: Any, size: int) -> bool:
    return (
        isinstance(value, list)
        and len(value) == size
        and all(isinstance(row, list) and len(row) == size for row in value)
    )


def _cell_value(cell: Any) -> Optional[int]:
    raw = cell.get("value") if isinstance(cell, dict) else cell
    return coerce_int(raw, 0)


def validate(config: Dict[str, Any], submission: Submission) -> ValidationResult:
    solution = config.get("solution")
    if not _is_grid(solution, GRID_SIZE):
        return ValidationResult(False, "challenge_sin_solucion", submission.attempts, submission.errors, False)

    cells = (submission.game_data or {}).get("cells")
    if not _is_grid(cells, GRID_SIZE):
        return ValidationResult(False, "grilla_ausente", submission.attempts, submission.errors, False)

    mismatches = 0
    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            value = _cell_value(cells[row][col])
            if value == 0:
                return ValidationResult(False, "grilla_incompleta", submission.errors, submission.errors, False)
            try:
                expected = int(solution[row][col])
            except (TypeError, ValueError):
                return ValidationResult(False, "challenge_sin_solucion", submission.attempts, submission.errors, False)
            if value != expected:
                mismatches += 1

    if mismatches:
        return ValidationResult(False, "grilla_incorrecta", submission.errors, submission.errors, False)

    return accept(submission.errors, submission.errors)
