"""El panel compilado se sirve desde /admin como SPA, sin romper assets ni el fallback."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app, static_admin_dir

pytestmark = pytest.mark.unit

ADMIN_DIR = Path(static_admin_dir)


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_admin_entry_sirve_el_index_y_conserva_query():
    async with _client() as client:
        response = await client.get("/admin?ticket=abc123")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'id="root"' in response.text


@pytest.mark.asyncio
async def test_admin_deep_link_cae_al_index():
    async with _client() as client:
        response = await client.get("/admin/login")

    assert response.status_code == 200
    assert 'id="root"' in response.text


@pytest.mark.asyncio
async def test_admin_sirve_assets_compilados():
    asset = next((ADMIN_DIR / "assets").glob("*.js"))

    async with _client() as client:
        response = await client.get(f"/admin/assets/{asset.name}")

    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_admin_asset_faltante_es_404_y_no_index():
    async with _client() as client:
        response = await client.get("/admin/assets/no-existe.js")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_admin_conserva_test_narrativo():
    async with _client() as client:
        response = await client.get("/admin/test-narrativo.html")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
