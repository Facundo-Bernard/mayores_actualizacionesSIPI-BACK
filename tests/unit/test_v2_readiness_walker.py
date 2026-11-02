"""Recorrido de grafos del dry-run de readiness V2."""

import random

import pytest

from scripts.v2_readiness import aplicar_impactos, caminar_grafo, siguiente_nodo

pytestmark = pytest.mark.unit


def _nodo(nodo_id, *, es_final=False, opciones=None, texto="Texto", resultado="Cierre", **extra):
    return {
        "id": nodo_id,
        "hablante_id": "narrador",
        "texto": texto,
        "es_final": es_final,
        "opciones": opciones or [],
        "resultado_texto": resultado,
        **extra,
    }


def _grafo(nodos, raiz="inicio"):
    return {"nodo_raiz": raiz, "nodos": nodos}


def test_recorre_grafo_valido_hasta_el_final():
    grafo = _grafo(
        {
            "inicio": _nodo(
                "inicio", opciones=[{"id": "opt_1", "texto": "Seguir", "siguiente_nodo": "medio"}]
            ),
            "medio": _nodo(
                "medio", opciones=[{"id": "opt_2", "texto": "Cerrar", "siguiente_nodo": "fin"}]
            ),
            "fin": _nodo("fin", es_final=True),
        }
    )

    recorrido = caminar_grafo(grafo, random.Random(1))

    assert recorrido.ok
    assert recorrido.visitados == ["inicio", "medio", "fin"]
    assert recorrido.final_alcanzado


def test_detecta_ciclo():
    grafo = _grafo(
        {
            "inicio": _nodo(
                "inicio", opciones=[{"id": "opt_1", "texto": "Volver", "siguiente_nodo": "inicio"}]
            )
        }
    )

    recorrido = caminar_grafo(grafo, random.Random(1))

    assert recorrido.problema == "ciclo:inicio"
    assert not recorrido.final_alcanzado


def test_soft_lock_cuando_todas_las_opciones_estan_bloqueadas():
    grafo = _grafo(
        {
            "inicio": _nodo(
                "inicio", opciones=[{"id": "opt_1", "texto": "Seguir", "siguiente_nodo": "fin"}]
            ),
            "fin": _nodo("fin", es_final=True),
        }
    )

    recorrido = caminar_grafo(grafo, random.Random(1), puede_elegir=lambda _n, _o: False)

    assert recorrido.problema == "soft_lock:inicio"


def test_nodo_sin_opciones_es_error_estructural():
    grafo = _grafo({"inicio": _nodo("inicio")})

    recorrido = caminar_grafo(grafo, random.Random(1))

    assert recorrido.problema == "nodo_sin_opciones:inicio"


def test_destino_inexistente():
    grafo = _grafo(
        {
            "inicio": _nodo(
                "inicio", opciones=[{"id": "opt_1", "texto": "Ir", "siguiente_nodo": "fantasma"}]
            )
        }
    )

    recorrido = caminar_grafo(grafo, random.Random(1))

    assert recorrido.problema == "nodo_inexistente:fantasma"


def test_opcion_sin_destino():
    grafo = _grafo(
        {"inicio": _nodo("inicio", opciones=[{"id": "opt_1", "texto": "Ir", "siguiente_nodo": None}])}
    )

    recorrido = caminar_grafo(grafo, random.Random(1))

    assert recorrido.problema == "opcion_sin_destino:inicio:opt_1"


def test_reporta_textos_vacios_para_el_frontend():
    grafo = _grafo(
        {
            "inicio": _nodo(
                "inicio",
                texto="",
                opciones=[{"id": "opt_1", "texto": "Ir", "siguiente_nodo": "fin"}],
            ),
            "fin": _nodo("fin", es_final=True, resultado=""),
        }
    )

    recorrido = caminar_grafo(grafo, random.Random(1))

    assert recorrido.final_alcanzado
    assert recorrido.errores_render == ["texto_vacio:inicio", "resultado_vacio:fin"]
    assert not recorrido.ok


def test_desenlaces_ponderados_ignoran_pesos_no_positivos():
    opcion = {
        "id": "opt_1",
        "texto": "Sortear",
        "desenlaces": [
            {"nodo": "invalido_cero", "peso": 0},
            {"nodo": "invalido_negativo", "peso": -2},
            {"nodo": "valido", "peso": 1.5},
        ],
    }

    for seed in range(20):
        assert siguiente_nodo(opcion, random.Random(seed)) == "valido"


def test_sin_desenlaces_usa_siguiente_nodo():
    assert siguiente_nodo({"siguiente_nodo": "fin"}, random.Random(1)) == "fin"
    assert siguiente_nodo({"siguiente_nodo": ""}, random.Random(1)) is None


def test_aplicar_impactos_clampa_y_deduplica_tags():
    run = {
        "recursos": {"oro": 95, "fe": 3},
        "afinidad": {"pj_elena": 98, "pj_marcus": 5},
        "tags_activos": ["guerra"],
    }
    nodo = {
        "impactos_recursos": [
            {"recurso": "Oro", "delta": 20},
            {"recurso": "fe", "delta": -10},
            {"recurso": "inexistente", "delta": 5},
        ],
        "impactos_afinidad": [
            {"personaje_id": "pj_elena", "delta": 10},
            {"personaje_id": "pj_marcus", "delta": -20},
        ],
        "impactos_tags": ["guerra", "comercio"],
    }

    aplicar_impactos(nodo, run)

    assert run["recursos"] == {"oro": 100, "fe": 0}
    assert run["afinidad"] == {"pj_elena": 100, "pj_marcus": 0}
    assert run["tags_activos"] == ["guerra", "comercio"]
