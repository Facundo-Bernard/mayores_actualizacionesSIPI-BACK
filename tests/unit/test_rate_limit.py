"""Ventana deslizante del rate limiter y mapeo de ámbitos por ruta."""

import pytest

from app.core.rate_limit import RateLimiter, _scope_para

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_permite_hasta_el_limite():
    limiter = RateLimiter()
    for i in range(3):
        permitido, _ = await limiter.allow("k", limit=3, window=60, now=1000.0 + i)
        assert permitido is True


@pytest.mark.asyncio
async def test_bloquea_al_exceder_el_limite_con_reintento():
    limiter = RateLimiter()
    for i in range(3):
        await limiter.allow("k", limit=3, window=60, now=1000.0 + i)

    permitido, reintento = await limiter.allow("k", limit=3, window=60, now=1003.0)

    assert permitido is False
    assert reintento >= 1
    assert reintento <= 61


@pytest.mark.asyncio
async def test_la_ventana_se_desliza_y_libera_cupo():
    limiter = RateLimiter()
    for i in range(2):
        await limiter.allow("k", limit=2, window=60, now=1000.0 + i)
    bloqueado, _ = await limiter.allow("k", limit=2, window=60, now=1002.0)
    assert bloqueado is False

    # Los dos hits iniciales salieron de la ventana de 60 s.
    permitido, _ = await limiter.allow("k", limit=2, window=60, now=1061.0)
    assert permitido is True


@pytest.mark.asyncio
async def test_claves_distintas_no_comparten_cupo():
    limiter = RateLimiter()
    await limiter.allow("a", limit=1, window=60, now=1000.0)

    permitido, _ = await limiter.allow("b", limit=1, window=60, now=1000.0)

    assert permitido is True


def test_scope_para_mapea_rutas_sensibles():
    assert _scope_para("/api/economy/lives")[0] == "/api/economy"
    assert _scope_para("/api/economy")[0] == "/api/economy"
    assert _scope_para("/api/games/attempts/wordle")[0] == "/api/games/attempts"
    assert _scope_para("/api/narrative/v2/avanzar")[0] == "/api/narrative"
    assert _scope_para("/api/challenges/today") is None
    assert _scope_para("/") is None
