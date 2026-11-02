"""Wordle: la solución debe aparecer en los intentos; el servidor cuenta los intentos."""

from typing import Any, Dict

from app.features.user_attempts.validation.base import (
    Submission,
    ValidationResult,
    accept,
    coerce_int,
    normalize_word,
)

DEFAULT_MAX_ATTEMPTS = 6


def validate(config: Dict[str, Any], submission: Submission) -> ValidationResult:
    solution = normalize_word(config.get("solution"))
    if not solution:
        return ValidationResult(False, "challenge_sin_solucion", submission.attempts, submission.errors, False)

    guessed: list[str] = []
    for item in submission.guesses:
        raw = item.get("word") if isinstance(item, dict) else item
        word = normalize_word(raw)
        if word:
            guessed.append(word)

    if solution in guessed:
        attempts = guessed.index(solution) + 1
    elif normalize_word(submission.word) == solution:
        attempts = max(len(submission.guesses), submission.attempts, 1)
    else:
        return ValidationResult(
            False,
            "solucion_no_encontrada",
            len(submission.guesses),
            submission.errors,
            False,
        )

    max_attempts = coerce_int(config.get("max_attempts"), DEFAULT_MAX_ATTEMPTS) or DEFAULT_MAX_ATTEMPTS
    if attempts > max_attempts:
        return ValidationResult(False, "intentos_excedidos", attempts, submission.errors, False)

    return accept(attempts, submission.errors)
