"""
test_crucigrama_bans.py
Vetos globales: normalización, exclusión en la generación (fácil/difícil) y
cableado de la generación mensual.
"""

import asyncio

import pytest

from app.features.daily_challenges.crucigrama.bans import clean_words
from app.features.daily_challenges.crucigrama.generator import (
    generate_crucigrama_challenge_for_date,
)


def test_clean_words_normaliza_deduplica_y_ordena():
    assert clean_words([" noche ", "NOCHE", "Albañil", "casa2", "AB"]) == [
        "ALBAÑIL",
        "NOCHE",
    ]


def test_clean_words_estricto_rechaza_longitud():
    with pytest.raises(ValueError):
        clean_words(["AB"], estricto=True)


def test_generador_facil_excluye_vetadas():
    base = generate_crucigrama_challenge_for_date("2026-11-11", "facil")
    vetada = base["words"][0]["word"]

    con_veto = generate_crucigrama_challenge_for_date(
        "2026-11-11", "facil", banned_words=[vetada]
    )

    assert vetada not in {w["word"] for w in con_veto["words"]}


def test_generador_dificil_excluye_vetadas():
    base = generate_crucigrama_challenge_for_date("2026-11-12", "dificil")
    vetada = base["words"][0]["word"]

    con_veto = generate_crucigrama_challenge_for_date(
        "2026-11-12", "dificil", banned_words=[vetada]
    )

    assert vetada not in {w["word"] for w in con_veto["words"]}


def test_generacion_mensual_recibe_vetos_globales():
    asyncio.run(_mensual())


async def _mensual():
    from app.core.database import connect_to_mongo, get_database
    from app.features.daily_challenges import service as daily_service

    await connect_to_mongo()
    try:
        await get_database().client.admin.command("ping")
    except Exception:
        pytest.skip("MongoDB no accesible para la suite de integración.")

    fecha = "2029-01-01"
    coleccion = get_database()["daily_challenges"]
    await coleccion.delete_many({"game_id": "crucigrama", "date": fecha})
    llamadas = []

    original_monthrange = daily_service.calendar.monthrange
    original_generador = daily_service.generate_crucigrama_challenge_for_date
    original_bans = daily_service.get_global_banned_words

    async def _bans_falsos():
        return ["NOCHE"]

    def _generador_falso(fecha_dia, dificultad, banned_words=None):
        llamadas.append((fecha_dia, dificultad, tuple(banned_words or ())))
        return {
            "theme": "Prueba",
            "grid_size": 7,
            "cells": [],
            "words": [],
            "total_words": 0,
            "date": fecha_dia,
        }

    daily_service.calendar.monthrange = lambda year, month: (0, 1)
    daily_service.get_global_banned_words = _bans_falsos
    daily_service.generate_crucigrama_challenge_for_date = _generador_falso
    try:
        resultado = await daily_service.generate_and_save_crucigrama_month(
            2029, 1, force=True
        )
    finally:
        daily_service.calendar.monthrange = original_monthrange
        daily_service.generate_crucigrama_challenge_for_date = original_generador
        daily_service.get_global_banned_words = original_bans
        await coleccion.delete_many({"game_id": "crucigrama", "date": fecha})

    assert resultado["success"]
    assert llamadas, "La generación mensual debe invocar al generador real."
    assert all(bans == ("NOCHE",) for _, _, bans in llamadas)

pytestmark = pytest.mark.integration
