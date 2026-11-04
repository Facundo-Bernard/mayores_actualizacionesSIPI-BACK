"""Cliente RAE: caché negativa, reintentos, espaciado y persistencia atómica."""

import json
import os
import time
import urllib.error

import pytest

import app.core.rae_client as rae

pytestmark = pytest.mark.unit


class _Respuesta:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture
def cliente(monkeypatch, tmp_path):
    monkeypatch.setattr(rae, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(rae, "CACHE_PATH", str(tmp_path / "definiciones_cache.json"))
    monkeypatch.setattr(rae, "_DEFINICIONES_CACHE", {})
    monkeypatch.setattr(rae, "_NEGATIVE_CACHE", {})
    monkeypatch.setattr(rae, "_ACENTOS_MAP", {})
    monkeypatch.setattr(rae, "_DIRTY", False)
    monkeypatch.setattr(rae, "_LAST_FLUSH", 0.0)
    monkeypatch.setattr(rae, "_NEXT_CALL_AT", 0.0)
    monkeypatch.setattr(rae, "_FLUSH_TIMER", None)
    monkeypatch.setattr(rae, "_load_acentos_map", lambda: {})
    monkeypatch.setattr(rae.settings, "RAE_API_KEY", None)
    monkeypatch.setattr(rae.settings, "RAE_MIN_INTERVAL_MS", 0)
    monkeypatch.setattr(rae.settings, "RAE_MAX_RETRIES", 1)
    monkeypatch.setattr(rae.settings, "RAE_RETRY_BASE_SECONDS", 0.0)
    monkeypatch.setattr(rae.settings, "RAE_MAX_BACKOFF_SECONDS", 10.0)
    monkeypatch.setattr(rae.settings, "RAE_NEGATIVE_CACHE_TTL_SECONDS", 300)
    monkeypatch.setattr(rae.settings, "RAE_CACHE_FLUSH_SECONDS", 0)
    return rae


def test_definicion_exitosa_se_persiste_de_forma_atomica(cliente, monkeypatch):
    llamadas = []

    def urlopen(req, timeout=0):
        llamadas.append(req.full_url)
        return _Respuesta(
            {"data": {"meanings": [{"senses": [
                {"raw": "Edificio destinado a la atención de enfermos."}
            ]}]}}
        )

    monkeypatch.setattr(cliente.urllib.request, "urlopen", urlopen)

    definicion = cliente.fetch_rae_definition("hospital")

    assert definicion == "Edificio destinado a la atención de enfermos."
    assert len(llamadas) == 1
    with open(cliente.CACHE_PATH, encoding="utf-8") as f:
        cache = json.load(f)
    assert cache["HOSPITAL"] == definicion
    assert not os.path.exists(cliente.CACHE_PATH + ".tmp")


def test_429_agota_reintentos_y_marca_cache_negativa(cliente, monkeypatch):
    llamadas = []

    def urlopen(req, timeout=0):
        llamadas.append(req.full_url)
        raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {"Retry-After": "0"}, None)

    monkeypatch.setattr(cliente.urllib.request, "urlopen", urlopen)

    assert cliente.fetch_rae_definition("aceite") is None
    assert len(llamadas) == 2  # intento inicial + 1 reintento configurado por el fixture

    assert cliente.fetch_rae_definition("aceite") is None
    assert len(llamadas) == 2  # la caché negativa evita volver a llamar


def test_respuesta_sin_acepcion_marca_cache_negativa(cliente, monkeypatch):
    llamadas = []

    def urlopen(req, timeout=0):
        llamadas.append(req.full_url)
        return _Respuesta({"data": {"meanings": []}})

    monkeypatch.setattr(cliente.urllib.request, "urlopen", urlopen)

    assert cliente.fetch_rae_definition("zzzz") is None
    assert cliente.fetch_rae_definition("zzzz") is None
    assert len(llamadas) == 1


def test_retry_delay_respeta_retry_after(cliente):
    error = urllib.error.HTTPError(
        "https://rae-api.com", 429, "Too Many Requests", {"Retry-After": "7"}, None
    )

    assert cliente._retry_delay(error, attempt=0) == 7.0


def test_retry_delay_usa_backoff_con_tope(cliente, monkeypatch):
    monkeypatch.setattr(cliente.settings, "RAE_RETRY_BASE_SECONDS", 1.0)
    monkeypatch.setattr(cliente.settings, "RAE_MAX_BACKOFF_SECONDS", 5.0)
    error = urllib.error.HTTPError("https://rae-api.com", 503, "Unavailable", {}, None)

    primer_intento = cliente._retry_delay(error, attempt=0)
    intento_alto = cliente._retry_delay(error, attempt=6)

    assert 1.0 <= primer_intento <= 1.3
    assert intento_alto == 5.0


def test_espaciado_global_entre_llamadas(cliente, monkeypatch):
    monkeypatch.setattr(cliente.settings, "RAE_MIN_INTERVAL_MS", 80)
    monkeypatch.setattr(cliente, "_NEXT_CALL_AT", 0.0)

    inicio = time.monotonic()
    cliente._wait_for_call_slot()
    cliente._wait_for_call_slot()
    transcurrido = time.monotonic() - inicio

    assert transcurrido >= 0.06
