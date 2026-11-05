"""Fixtures y dobles mínimos de N0 #75; no abren sockets ni persisten datos."""

from copy import deepcopy


class FakeCursor:
    def __init__(self, documents):
        self._documents = documents

    async def to_list(self, length=None):
        documents = self._documents if length is None else self._documents[:length]
        return deepcopy(documents)


class FakeCollection:
    """Solo implementa las consultas equality/$in usadas por los servicios bajo prueba."""

    def __init__(self, documents=()):
        self.documents = list(documents)
        self.find_queries = []
        self.find_one_queries = []

    @staticmethod
    def _matches(document, query):
        for key, expected in query.items():
            actual = document.get(key)
            if isinstance(expected, dict) and "$in" in expected:
                if actual not in expected["$in"]:
                    return False
            elif actual != expected:
                return False
        return True

    def find(self, query, projection=None):
        self.find_queries.append(deepcopy(query))
        return FakeCursor([doc for doc in self.documents if self._matches(doc, query)])

    async def find_one(self, query, projection=None, sort=None):
        self.find_one_queries.append(deepcopy(query))
        matches = [doc for doc in self.documents if self._matches(doc, query)]
        if sort:
            for key, direction in reversed(list(sort)):
                matches.sort(key=lambda doc: doc.get(key, 0) or 0, reverse=direction < 0)
        # Motor entrega un dict mutable al servicio; conservar esa referencia permite
        # observar exactamente las mutaciones de dominio sin implementar escrituras.
        return matches[0] if matches else None


class FakeDB:
    def __init__(self, collections=None):
        self._collections = {
            name: FakeCollection(documents)
            for name, documents in (collections or {}).items()
        }

    def __getitem__(self, name):
        return self._collections.setdefault(name, FakeCollection())


def run_n0(**overrides):
    run = {
        "_id": "run_75_2099-01-01",
        "user_id": 75,
        "date": "2099-01-01",
        "game_id": "narrativo",
        "universo_id": "universo_n0",
        "motor": "v2",
        "mes_actual": 1,
        "fase_actual": "BALANCE_MES",
        "status": "in_progress",
        "recursos": {"oro": 50, "fe": 50},
        "afinidad": {"pj_a": 50},
        "cartas_en_mano": [],
        "tags_activos": [],
        "turno_actual": {
            "cartas_ofrecidas_ids": [],
            "carta_elegida_id": None,
            "evento_actual_id": None,
            "opcion_elegida_id": None,
            "resultado_obtenido_id": None,
            "conversacion_actual_id": None,
        },
        "eventos_jugados": [],
        "conversaciones_jugadas": [],
        "historial_mensual": [],
        "historial_grafos": [],
    }
    run.update(overrides)
    return run


def efecto_recurso_n0(clave, valor, *, disparador="cada_mes", tipo_calculo="fijo"):
    return {
        "disparador": disparador,
        "condiciones": [],
        "accion": {
            "tipo": "modificar_recurso",
            "clave": clave,
            "valor": valor,
            "tipo_calculo": tipo_calculo,
        },
    }


def personaje_n0(personaje_id="pj_a", *, tags=None, efectos=None, afinidad=50):
    return {
        "_id": personaje_id,
        "universo_id": "universo_n0",
        "nombre": personaje_id,
        "titulo": "Consejero de prueba",
        "imagen": "/pj.webp",
        "descripcion": "Fixture no adaptada por edad.",
        "pros": [],
        "cons": [],
        "tags": list(tags or []),
        "afinidad_inicial": afinidad,
        "efectos": list(efectos or []),
        "conversaciones": [],
    }


def carta_n0(carta_id="carta_a", *, tags=None, efectos=None):
    return {
        "_id": carta_id,
        "universo_id": "universo_n0",
        "categoria": "item",
        "nombre": carta_id,
        "descripcion": "Fixture no adaptada por edad.",
        "imagen": "/carta.webp",
        "tags": list(tags or []),
        "efectos": list(efectos or []),
    }


def universo_n0(**overrides):
    universo = {
        "_id": "universo_n0",
        "nombre": "Universo N0",
        "descripcion": "Universo sintético.",
        "icono": "crown",
        "imagen": "/universo.webp",
        "motor": "v2",
        "reciclaje_eventos_v2": False,
        "recursos": [
            {"clave": "oro", "nombre": "Oro", "min": 0, "max": 100, "inicial": 50},
            {"clave": "fe", "nombre": "Fe", "min": 0, "max": 100, "inicial": 50},
        ],
    }
    universo.update(overrides)
    return universo


def desafio_n0(*, corte=None, cartas=None, pool=None):
    return {
        "game_id": "narrativo",
        "date": "2099-01-01",
        "config": {
            "universo_id": "universo_n0",
            "atributos_iniciales": {"oro": 50, "fe": 50},
            "setup_corte_ofrecidos_ids": list(corte or []),
            "setup_cartas_ofrecidas_ids": list(cartas or []),
            "pool_cartas_mensuales_ids": list(pool or []),
        },
    }


def evento_n0(evento_id, **overrides):
    evento = {
        "_id": evento_id,
        "universo_id": "universo_n0",
        "titulo": evento_id,
        "imagen": "/evento.webp",
        "peso_base": 100.0,
        "tags_tematicos": [],
        "requisitos_eventos_previos": [],
        "requisitos_personajes": [],
        "condiciones_disparo": [],
        "nodo_raiz": "inicio",
        "nodos": {},
    }
    evento.update(overrides)
    return evento


def nodo_n0(nodo_id, *, final=False, opciones=None, **overrides):
    nodo = {
        "id": nodo_id,
        "hablante_id": "narrador",
        "texto": f"Texto {nodo_id}",
        "es_final": final,
        "opciones": list(opciones or []),
        "resultado_texto": "Cierre" if final else "",
        "impactos_recursos": [],
        "impactos_afinidad": [],
        "impactos_tags": [],
    }
    nodo.update(overrides)
    return nodo
