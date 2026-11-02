"""Validación server-side de partidas (Fase 2), activada por flags por juego."""

from typing import Callable, Dict, Optional

from app.core.config import settings
from app.features.user_attempts.validation.base import Submission, ValidationResult
from app.features.user_attempts.validation.challenges import load_challenge_config
from app.features.user_attempts.validation.crucigrama import validate as validate_crucigrama
from app.features.user_attempts.validation.sopa import validate as validate_sopa
from app.features.user_attempts.validation.sudoku import validate as validate_sudoku
from app.features.user_attempts.validation.wordle import validate as validate_wordle

Validator = Callable[[Dict, Submission], ValidationResult]

_VALIDATORS: Dict[str, Validator] = {
    "wordle": validate_wordle,
    "sopa_letras": validate_sopa,
    "sudoku": validate_sudoku,
    "crucigrama": validate_crucigrama,
}

_FLAG_BY_GAME = {
    "wordle": "GRADING_ENFORCE_WORDLE",
    "sopa_letras": "GRADING_ENFORCE_SOPA",
    "sudoku": "GRADING_ENFORCE_SUDOKU",
    "crucigrama": "GRADING_ENFORCE_CRUCIGRAMA",
}


def is_enforcement_enabled(game_id: str) -> bool:
    flag = _FLAG_BY_GAME.get((game_id or "").lower().strip())
    return bool(flag and getattr(settings, flag, False))


async def validate_submission(
    game_id: str,
    date: str,
    difficulty: Optional[str],
    submission: Submission,
) -> ValidationResult:
    validator = _VALIDATORS.get(game_id)
    if validator is None:
        return ValidationResult(
            valid=True,
            reason="juego_sin_validador",
            attempts=submission.attempts,
            errors=submission.errors,
            completed=True,
        )

    config = await load_challenge_config(game_id, date, difficulty)
    if config is None:
        return ValidationResult(
            valid=False,
            reason="desafio_no_encontrado",
            attempts=submission.attempts,
            errors=submission.errors,
            completed=False,
        )

    return validator(config, submission)


__all__ = [
    "Submission",
    "ValidationResult",
    "is_enforcement_enabled",
    "load_challenge_config",
    "validate_submission",
]
