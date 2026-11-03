"""Fase 4: el middleware responde 429 ante ráfagas en rutas sensibles."""

import uuid

import pytest

from app.core.config import settings
from app.core.rate_limit import rate_limiter

pytestmark = pytest.mark.contract


@pytest.fixture(autouse=True)
def _limpiar_limiter():
    rate_limiter.reset()
    yield
    rate_limiter.reset()


@pytest.mark.asyncio
async def test_economy_devuelve_429_al_exceder_limite(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ECONOMY_PER_MINUTE", 1)
    token = f"Bearer {uuid.uuid4().hex}"

    primera = await client.get("/api/economy/config", headers={"Authorization": token})
    segunda = await client.get("/api/economy/config", headers={"Authorization": token})

    assert primera.status_code == 200
    assert primera.headers["X-RateLimit-Limit"] == "1"
    assert segunda.status_code == 429
    assert segunda.json()["success"] is False
    assert int(segunda.headers["Retry-After"]) >= 1


@pytest.mark.asyncio
async def test_rutas_no_sensibles_no_se_limitan(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ECONOMY_PER_MINUTE", 1)
    token = f"Bearer {uuid.uuid4().hex}"

    for _ in range(3):
        response = await client.get("/", headers={"Authorization": token})
        assert response.status_code == 200
