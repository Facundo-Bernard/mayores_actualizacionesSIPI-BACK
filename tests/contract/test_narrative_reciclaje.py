"""Reciclaje controlado de eventos V2 para completar los 12 meses."""

import pytest

from app.features.narrative.constants import COLL_SETTINGS, COLL_V2_EVENTS
from app.features.narrative.engine.graph_engine import graph_engine

pytestmark = pytest.mark.contract

UNIVERSO = "universo_reciclaje_v2"


async def _seed_evento(db, cleanup, evento_id: str):
    await db[COLL_V2_EVENTS].replace_one(
        {"_id": evento_id},
        {
            "_id": evento_id,
            "universo_id": UNIVERSO,
            "titulo": evento_id,
            "nodo_raiz": "inicio",
            "nodos": {"inicio": {"id": "inicio", "es_final": True, "texto": "x", "resultado_texto": "y"}},
        },
        upsert=True,
    )
    cleanup.add(COLL_V2_EVENTS, {"_id": evento_id})


async def _seed_universo(db, cleanup, **extra):
    await db[COLL_SETTINGS].replace_one(
        {"_id": UNIVERSO},
        {"_id": UNIVERSO, "nombre": "Universo reciclaje", **extra},
        upsert=True,
    )
    cleanup.add(COLL_SETTINGS, {"_id": UNIVERSO})


@pytest.mark.asyncio
async def test_recicla_solo_con_flag_explicito(test_db, cleanup):
    await _seed_evento(test_db, cleanup, "evt_reciclaje_a")
    await _seed_evento(test_db, cleanup, "evt_reciclaje_b")

    run = {"universo_id": UNIVERSO, "eventos_jugados": ["evt_reciclaje_a", "evt_reciclaje_b"]}
    assert await graph_engine.sortear_evento_v2(run=run, universo_id=UNIVERSO) is None

    run["reciclaje_eventos_v2"] = True
    evento = await graph_engine.sortear_evento_v2(run=run, universo_id=UNIVERSO)

    assert evento["_id"] in {"evt_reciclaje_a", "evt_reciclaje_b"}
    assert run["eventos_jugados"] == []
    assert run["reciclajes_eventos_v2"] == 1


@pytest.mark.asyncio
async def test_recicla_por_configuracion_del_universo(test_db, cleanup):
    await _seed_evento(test_db, cleanup, "evt_reciclaje_c")
    await _seed_universo(test_db, cleanup, reciclaje_eventos_v2=True)

    run = {"universo_id": UNIVERSO, "eventos_jugados": ["evt_reciclaje_c"]}
    evento = await graph_engine.sortear_evento_v2(run=run, universo_id=UNIVERSO)

    assert evento["_id"] == "evt_reciclaje_c"
    assert run["reciclajes_eventos_v2"] == 1


@pytest.mark.asyncio
async def test_sin_eventos_no_recicla_ni_falla(test_db, cleanup):
    run = {"universo_id": "universo_sin_eventos", "eventos_jugados": ["x"]}

    assert await graph_engine.sortear_evento_v2(
        run=run, universo_id="universo_sin_eventos"
    ) is None
    assert "reciclajes_eventos_v2" not in run
