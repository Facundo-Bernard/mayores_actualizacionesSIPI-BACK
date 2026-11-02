"""Reloj único del backend: el día de juego se decide en America/Argentina/Buenos_Aires."""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

ART = ZoneInfo("America/Argentina/Buenos_Aires")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_art() -> datetime:
    return datetime.now(ART)


def today_art() -> date:
    return now_art().date()


def today_str() -> str:
    return today_art().isoformat()
