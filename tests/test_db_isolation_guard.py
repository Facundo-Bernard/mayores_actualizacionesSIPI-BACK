"""Guardas puras de aislamiento: validan URI, host y base antes de abrir Mongo."""

from unittest.mock import AsyncMock

import pytest

import conftest as fixtures
from app.core.database import validate_test_mongodb_config

pytestmark = pytest.mark.unit

TEST_DB_NAME = "mayores_actualizaciones_test"


@pytest.mark.asyncio
async def test_base_distinta_en_path_se_rechaza_antes_de_conectar(monkeypatch):
    monkeypatch.setattr(fixtures.settings, "MONGO_HOST", None)
    monkeypatch.setattr(
        fixtures.settings,
        "MONGO_URI",
        "mongodb://localhost:27017/base_productiva",
    )
    connect_mock = AsyncMock()
    monkeypatch.setattr(fixtures, "connect_to_mongo", connect_mock)
    fixture = fixtures.test_db.__wrapped__()

    with pytest.raises(ValueError, match="base_productiva"):
        await fixture.__anext__()

    connect_mock.assert_not_awaited()


def test_uri_sin_path_usa_nombre_configurado():
    url = "mongodb://127.0.0.1:27017?authSource=admin"

    assert validate_test_mongodb_config(url, TEST_DB_NAME) == TEST_DB_NAME


def test_localhost_evil_com_es_rechazado():
    url = f"mongodb://localhost.evil.com/{TEST_DB_NAME}"

    with pytest.raises(ValueError, match="localhost.evil.com"):
        validate_test_mongodb_config(url, TEST_DB_NAME)


def test_credenciales_y_query_aceptan_host_y_base_validos():
    url = (
        "mongodb://user:p%40ss@localhost:27017/"
        f"{TEST_DB_NAME}?authSource=admin&retryWrites=true"
    )

    assert validate_test_mongodb_config(url, TEST_DB_NAME) == TEST_DB_NAME


def test_mongodb_srv_valido_es_aceptado():
    url = f"mongodb+srv://localhost/{TEST_DB_NAME}?retryWrites=true"

    assert validate_test_mongodb_config(url, TEST_DB_NAME) == TEST_DB_NAME


def test_lista_de_hosts_con_uno_no_local_es_rechazada():
    url = (
        "mongodb://localhost:27017,127.0.0.1:27018,example.com:27017/"
        f"{TEST_DB_NAME}"
    )

    with pytest.raises(ValueError, match="example.com"):
        validate_test_mongodb_config(url, TEST_DB_NAME)
