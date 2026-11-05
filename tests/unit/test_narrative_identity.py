"""Identidad efectiva del narrativo: usuarios por JWT y invitados por credencial firmada (D03)."""

from datetime import timedelta

import pytest
from fastapi import HTTPException

from app.core.security import (
    crear_credencial_invitado,
    decode_guest_credential,
    generar_guest_id,
)
from app.features.narrative.game import identity
from app.features.narrative.game.identity import (
    filtro_run,
    id_run,
    obtener_identidad_narrativa,
    resolver_identidad,
)

pytestmark = pytest.mark.unit

DATE = "2099-06-01"


async def _activar(authorization=None, credential=None):
    dep = obtener_identidad_narrativa(authorization, credential)
    try:
        user_id = await dep.__anext__()
    except StopAsyncIteration:  # pragma: no cover - defensivo
        raise AssertionError("La dependencia no devolvió una identidad.")
    return user_id, dep


@pytest.mark.asyncio
async def test_invitado_firmado_recibe_id_negativo_estable_y_aislado():
    credential = crear_credencial_invitado("guest-alfa")
    user_id, dep = await _activar(credential=credential)
    try:
        assert user_id == 0
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
    finally:
        await dep.aclose()


@pytest.mark.asyncio
async def test_invitados_distintos_no_comparten_partida():
    cred_a = crear_credencial_invitado("guest-alfa")
    _, dep_a = await _activar(credential=cred_a)
    try:
        interno_a = resolver_identidad(0)[0]
        id_a = id_run(0, DATE)
    finally:
        await dep_a.aclose()

    cred_b = crear_credencial_invitado("guest-beta")
    _, dep_b = await _activar(credential=cred_b)
    try:
        interno_b = resolver_identidad(0)[0]
        id_b = id_run(0, DATE)
    finally:
        await dep_b.aclose()

    assert interno_a != interno_b
    assert id_a != id_b


@pytest.mark.asyncio
async def test_usuario_autenticado_ignora_credencial_de_invitado(monkeypatch):
    async def _fake_current_user(_credentials):
        return {"id": 4242}

    monkeypatch.setattr(identity, "get_current_user", _fake_current_user)

    credential = crear_credencial_invitado("guest-alfa")
    user_id, dep = await _activar("Bearer token-valido", credential)
    try:
        assert user_id == 4242
        assert resolver_identidad(user_id) == (4242, None)
        assert "guest_id" not in filtro_run(4242, DATE)
        assert id_run(4242, DATE) == f"run_4242_{DATE}"
    finally:
        await dep.aclose()


@pytest.mark.asyncio
async def test_sin_credencial_responde_401():
    dep = obtener_identidad_narrativa(None, None)
    with pytest.raises(HTTPException) as exc:
        await dep.__anext__()
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_credencial_invalida_responde_401():
    dep = obtener_identidad_narrativa(None, "no-es-un-jwt")
    with pytest.raises(HTTPException) as exc:
        await dep.__anext__()
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_credencial_expirada_responde_401():
    credential = crear_credencial_invitado("guest-alfa", expires_delta=timedelta(seconds=-1))
    dep = obtener_identidad_narrativa(None, credential)
    with pytest.raises(HTTPException) as exc:
        await dep.__anext__()
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_jwt_invalido_no_se_degrada_a_invitado():
    credential = crear_credencial_invitado("guest-alfa")
    dep = obtener_identidad_narrativa("Bearer token-invalido", credential)
    with pytest.raises(HTTPException) as exc:
        await dep.__anext__()
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_credencial_de_usuario_no_sirve_como_invitado():
    from app.core.security import create_access_token

    token_usuario = create_access_token({"id": 10, "email": "u@test.local"})
    dep = obtener_identidad_narrativa(None, token_usuario)
    with pytest.raises(HTTPException) as exc:
        await dep.__anext__()
    assert exc.value.status_code == 401


def test_credencial_de_invitado_se_reconoce_y_conserva_guest_id():
    guest_id = generar_guest_id()
    credential = crear_credencial_invitado(guest_id)
    payload = decode_guest_credential(credential)
    assert payload["sub"] == guest_id
    assert payload["typ"] == "guest"


def test_credencial_de_invitado_no_es_jwt_de_usuario():
    from app.core.security import decode_access_token

    credential = crear_credencial_invitado("guest-alfa")
    assert decode_access_token(credential) is None
