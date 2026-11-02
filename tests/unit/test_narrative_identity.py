"""Aislamiento de partidas de invitados por X-Guest-Id (D6)."""

import pytest
from fastapi import HTTPException

from app.features.narrative.game.identity import (
    _normalizar_guest_id,
    cargar_guest_id,
    filtro_run,
    id_run,
    resolver_identidad,
)

pytestmark = pytest.mark.unit

DATE = "2099-06-01"


async def _activar_guest(valor):
    dependency = cargar_guest_id(valor)
    await dependency.__anext__()
    return dependency


@pytest.mark.asyncio
async def test_invitado_recibe_id_negativo_estable_y_aislado():
    dep = await _activar_guest("guest-alfa")
    try:
        interno, guest_id = resolver_identidad(0)
        assert guest_id == "guest-alfa"
        assert interno < 0
        assert filtro_run(0, DATE) == {
            "user_id": interno,
            "date": DATE,
            "game_id": "narrativo",
            "guest_id": "guest-alfa",
        }
        assert id_run(0, DATE) == f"run_guest_guest-alfa_{DATE}"
        assert resolver_identidad(0)[0] == interno
    finally:
        await dep.aclose()


@pytest.mark.asyncio
async def test_invitados_distintos_no_comparten_partida():
    dep_a = await _activar_guest("guest-alfa")
    try:
        interno_a = resolver_identidad(0)[0]
        id_a = id_run(0, DATE)
    finally:
        await dep_a.aclose()

    dep_b = await _activar_guest("guest-beta")
    try:
        interno_b = resolver_identidad(0)[0]
        id_b = id_run(0, DATE)
    finally:
        await dep_b.aclose()

    assert interno_a != interno_b
    assert id_a != id_b


@pytest.mark.asyncio
async def test_usuario_autenticado_ignora_guest_id():
    dep = await _activar_guest("guest-alfa")
    try:
        interno, guest_id = resolver_identidad(4242)
        assert (interno, guest_id) == (4242, None)
        assert "guest_id" not in filtro_run(4242, DATE)
        assert id_run(4242, DATE) == f"run_4242_{DATE}"
    finally:
        await dep.aclose()


@pytest.mark.asyncio
async def test_sin_guest_id_conserva_comportamiento_legacy():
    dep = await _activar_guest(None)
    try:
        assert resolver_identidad(0) == (0, None)
        assert filtro_run(0, DATE) == {
            "user_id": 0,
            "date": DATE,
            "game_id": "narrativo",
        }
        assert id_run(0, DATE) == f"run_0_{DATE}"
    finally:
        await dep.aclose()


def test_guest_id_invalido_es_rechazado():
    with pytest.raises(HTTPException) as exc:
        _normalizar_guest_id("no vale con espacios")
    assert exc.value.status_code == 400

    assert _normalizar_guest_id("  guest_ok-1  ") == "guest_ok-1"
    assert _normalizar_guest_id("   ") is None
