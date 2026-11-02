"""Contratos compartidos por los validadores server-side de partidas."""

import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Submission:
    """Vista mínima del intento enviado por el cliente, ya acotada por el schema."""

    word: Optional[str] = None
    guesses: List[Any] = field(default_factory=list)
    attempts: int = 0
    errors: int = 0
    game_data: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    reason: Optional[str] = None
    attempts: Optional[int] = None
    errors: Optional[int] = None
    completed: bool = False


def normalize_word(value: Any) -> str:
    """Normaliza palabras para comparar sin tildes, mayúsculas ni espacios."""
    if value is None:
        return ""
    text = str(value).strip().upper()
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def coerce_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value is None or value == "" or isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def reject(reason: str, submission: Submission) -> ValidationResult:
    return ValidationResult(
        valid=False,
        reason=reason,
        attempts=submission.attempts,
        errors=submission.errors,
        completed=False,
    )


def accept(attempts: Optional[int], errors: Optional[int]) -> ValidationResult:
    return ValidationResult(
        valid=True,
        reason=None,
        attempts=attempts,
        errors=errors,
        completed=True,
    )
