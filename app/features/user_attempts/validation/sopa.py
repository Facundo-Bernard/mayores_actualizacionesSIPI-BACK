"""Sopa de letras: solo se completa cuando están todas las palabras del desafío."""

from typing import Any, Dict

from app.features.user_attempts.validation.base import (
    Submission,
    ValidationResult,
    accept,
    normalize_word,
)


def validate(config: Dict[str, Any], submission: Submission) -> ValidationResult:
    expected = [normalize_word(w) for w in (config.get("words") or [])]
    expected = [w for w in expected if w]
    if not expected:
        return ValidationResult(False, "challenge_sin_palabras", submission.attempts, submission.errors, False)

    found: list[str] = []
    for item in submission.guesses:
        raw = item.get("word") if isinstance(item, dict) else item
        word = normalize_word(raw)
        if word in expected and word not in found:
            found.append(word)

    if len(found) < len(expected):
        return ValidationResult(False, "palabras_incompletas", len(found), submission.errors, False)

    return accept(len(found), submission.errors)
