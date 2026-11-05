"""Red de seguridad de la suite: toda ejecución queda aislada en la base de test."""

import datetime
import importlib
import os
import uuid

TEST_DB_NAME = "mayores_actualizaciones_test"

# Debe definirse antes de importar app.*: pydantic-settings prioriza el entorno sobre .env.
os.environ["MONGODB_DB_NAME"] = TEST_DB_NAME
os.environ.pop("MONGO_DB_NAME", None)
os.environ.setdefault("TZ", "America/Argentina/Buenos_Aires")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.database import (
    close_mongo_connection,
    connect_to_mongo,
    db_instance,
    validate_test_mongodb_config,
)
from app.main import app


def _validate_test_database():
    assert settings.effective_db_name == TEST_DB_NAME, (
        f"La suite debe usar {TEST_DB_NAME}, pero la configuración apunta a "
        f"'{settings.effective_db_name}'."
    )
    return validate_test_mongodb_config(settings.mongodb_connection_url, TEST_DB_NAME)


@pytest.fixture(scope="session", autouse=True)
def db_guard():
    """Falla antes de cualquier test si la configuración no apunta a la base de test local."""
    _validate_test_database()
    yield


@pytest.fixture
def api_app():
    return app


@pytest_asyncio.fixture
async def test_db():
    _validate_test_database()
    await connect_to_mongo()
    db = db_instance.db
    assert db.name == TEST_DB_NAME, f"Conectado a '{db.name}', se esperaba '{TEST_DB_NAME}'."
    yield db
    await close_mongo_connection()


@pytest_asyncio.fixture
async def client(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


@pytest.fixture
def admin_override():
    """Reemplaza la dependencia de admin para probar endpoints administrativos."""
    from app.core.dependencies import get_current_admin

    app.dependency_overrides[get_current_admin] = lambda: {
        "id": 900001,
        "name": "Admin Test",
        "tipo_usuario": 2,
        "activo": True,
    }
    yield
    app.dependency_overrides.pop(get_current_admin, None)


@pytest.fixture
def make_token():
    from app.core.security import create_access_token

    def _make(user_id: int, tipo_usuario: int = 1, **extra):
        payload = {
            "id": user_id,
            "email": f"user{user_id}@test.local",
            "name": f"User {user_id}",
            "tipo_usuario": tipo_usuario,
            "servicios": {settings.SERVICE_KEY: True},
        }
        payload.update(extra)
        return create_access_token(payload)

    return _make


@pytest.fixture
def make_guest_credential():
    """Emite una credencial de invitado firmada y sus headers para pruebas HTTP."""
    from app.core.security import crear_credencial_invitado, generar_guest_id

    def _make(guest_id: str | None = None):
        guest_id = guest_id or generar_guest_id()
        return guest_id, {"X-Guest-Credential": crear_credencial_invitado(guest_id)}

    return _make


class _Cleanup:
    def __init__(self):
        self._ops = []

    def add(self, collection: str, query: dict):
        self._ops.append((collection, query))
        return query

    async def run(self, db):
        for collection, query in reversed(self._ops):
            await db[collection].delete_many(query)


@pytest_asyncio.fixture
async def cleanup(test_db):
    tracker = _Cleanup()
    yield tracker
    await tracker.run(test_db)


@pytest_asyncio.fixture
async def seeded_user(test_db, cleanup):
    async def _seed(puntos: int = 0, vidas: int = 10, tipo_usuario: int = 1, **extra):
        user_id = extra.pop("id", 700000 + uuid.uuid4().int % 100000)
        doc = {
            "id": user_id,
            "name": f"User {user_id}",
            "email": f"user{user_id}@test.local",
            "tipo_usuario": tipo_usuario,
            "activo": True,
            "puntos": puntos,
            "vidas": vidas,
            "estado_id": 2,
            "estado_codigo": "ACTIVO",
            "progresos": [],
            **extra,
        }
        await test_db["usuarios"].insert_one(doc)
        cleanup.add("usuarios", {"id": user_id})
        cleanup.add("user_attempts", {"user_id": user_id})
        cleanup.add("economy_ledger", {"user_id": user_id})
        cleanup.add("user_hints", {"user_id": user_id})
        return doc

    return _seed


@pytest_asyncio.fixture
async def seeded_challenge(test_db, cleanup):
    async def _seed(
        game_id: str = "wordle",
        date: str = "2099-01-01",
        difficulty: str = "standard",
        config: dict | None = None,
        **extra,
    ):
        now = datetime.datetime.now(datetime.timezone.utc)
        query = {"game_id": game_id, "date": date, "difficulty": difficulty}
        doc = {
            **query,
            "title": f"{game_id} de prueba",
            "config": config if config is not None else {"solution": "TEST"},
            "created_at": now,
            "updated_at": now,
            **extra,
        }
        await test_db["daily_challenges"].replace_one(query, doc, upsert=True)
        cleanup.add("daily_challenges", query)
        return doc

    return _seed


@pytest.fixture
def freeze_today(monkeypatch):
    """Congela datetime.now() en los módulos indicados (por defecto, servicio de desafíos)."""

    def _freeze(value, modules=("app.features.daily_challenges.service",)):
        fixed = (
            value
            if isinstance(value, datetime.datetime)
            else datetime.datetime.combine(value, datetime.time(12, 0))
        )

        class FrozenDateTime(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed.replace(tzinfo=tz) if tz is not None else fixed

        for module_name in modules:
            module = importlib.import_module(module_name)
            monkeypatch.setattr(module, "datetime", FrozenDateTime)
        return fixed.date()

    return _freeze
