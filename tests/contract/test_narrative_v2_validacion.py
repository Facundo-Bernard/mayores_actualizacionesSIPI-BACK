"""Contrato del validador admin de grafos V2 (POST /api/narrative/admin/v2/validar)."""

import pytest

from app.features.narrative.constants import COLL_V2_EVENTS

pytestmark = pytest.mark.contract

URL = "/api/narrative/admin/v2/validar"


def _nodo(nodo_id: str, *, es_final: bool, siguiente: str | None = None) -> dict:
    return {
        "id": nodo_id,
        "hablante_id": "narrador",
        "texto": f"Texto {nodo_id}",
        "es_final": es_final,
        "opciones": (
            []
            if es_final
            else [{"id": f"opt_{nodo_id}", "texto": "Continuar", "siguiente_nodo": siguiente}]
        ),
        "resultado_texto": "Cierre" if es_final else "",
        "impactos_recursos": [],
        "impactos_afinidad": [],
        "impactos_tags": [],
    }


def _grafo(nodo_inicio: dict, nodo_fin: dict) -> dict:
    return {
        "_id": "evt_validador_contract",
        "universo_id": "universo_validador",
        "titulo": "Evento validador",
        "imagen": "/x.webp",
        "nodo_raiz": "inicio",
        "nodos": {"inicio": nodo_inicio, "fin": nodo_fin},
    }


@pytest.mark.asyncio
async def test_validar_grafo_inline_valido(client, admin_override):
    grafo = _grafo(_nodo("inicio", es_final=False, siguiente="fin"), _nodo("fin", es_final=True))

    response = await client.post(URL, json={"tipo": "evento", "grafo": grafo})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["invalidos"] == 0
    assert body["resultados"][0]["valido"] is True


@pytest.mark.asyncio
async def test_validar_grafo_inline_reporta_referencia_inexistente(client, admin_override):
    grafo = _grafo(_nodo("inicio", es_final=False, siguiente="no_existe"), _nodo("fin", es_final=True))

    response = await client.post(URL, json={"tipo": "evento", "grafo": grafo})

    assert response.status_code == 200
    resultado = response.json()["resultados"][0]
    assert resultado["valido"] is False
    assert "referencia_inexistente" in {h["codigo"] for h in resultado["errores"]}


@pytest.mark.asyncio
async def test_validar_grafo_inline_exige_tipo(client, admin_override):
    grafo = _grafo(_nodo("inicio", es_final=False, siguiente="fin"), _nodo("fin", es_final=True))

    response = await client.post(URL, json={"grafo": grafo})

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_validar_tipo_invalido_es_400(client, admin_override):
    response = await client.post(URL, json={"tipo": "desconocido"})

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_validar_grafo_guardado_y_404_si_no_existe(client, test_db, cleanup, admin_override):
    grafo = _grafo(_nodo("inicio", es_final=False, siguiente="fin"), _nodo("fin", es_final=True))
    await test_db[COLL_V2_EVENTS].replace_one({"_id": grafo["_id"]}, grafo, upsert=True)
    cleanup.add(COLL_V2_EVENTS, {"_id": grafo["_id"]})

    encontrado = await client.post(URL, json={"tipo": "evento", "grafo_id": grafo["_id"]})
    assert encontrado.status_code == 200
    assert encontrado.json()["resultados"][0]["grafo_id"] == grafo["_id"]

    inexistente = await client.post(URL, json={"tipo": "evento", "grafo_id": "evt_no_existe"})
    assert inexistente.status_code == 404
