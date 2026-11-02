"""Contratos mínimos de app/shared: reloj ART, errores de dominio y clave de ledger."""

import re
from datetime import timedelta

import pytest

from app.shared.clock import now_art, now_utc, today_art, today_str
from app.shared.errors import DomainError
from app.shared.ledger import LedgerKey, LedgerResult

pytestmark = pytest.mark.unit


def test_clock_uses_argentina_time():
    assert now_art().utcoffset() == timedelta(hours=-3)
    assert now_utc().utcoffset() == timedelta(0)
    assert today_art() == now_art().date()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", today_str())


def test_domain_error_defaults_and_detail():
    error = DomainError("No se puede acreditar dos veces")
    assert error.code == "domain_error"
    assert error.http_status == 400
    assert error.to_detail() == {
        "code": "domain_error",
        "message": "No se puede acreditar dos veces",
    }

    override = DomainError(
        "Partida ya completada",
        code="replay_rejected",
        http_status=409,
        detail={"game_id": "wordle"},
    )
    assert override.to_detail() == {
        "code": "replay_rejected",
        "message": "Partida ya completada",
        "game_id": "wordle",
    }


def test_ledger_key_separates_difficulties():
    easy = LedgerKey(user_id=1, motivo="game_completion", game_id="crucigrama", date="2026-11-02", difficulty="facil")
    hard = LedgerKey(user_id=1, motivo="game_completion", game_id="crucigrama", date="2026-11-02", difficulty="dificil")

    assert easy.business_key != hard.business_key
    assert easy.business_key == (1, "game_completion", "crucigrama", "2026-11-02", "facil")
    assert easy.idempotency_key == "game_completion:1:crucigrama:2026-11-02:facil"
    assert hard.idempotency_key == "game_completion:1:crucigrama:2026-11-02:dificil"
    assert LedgerResult(applied=True, puntos=100, saldo=250).applied is True
