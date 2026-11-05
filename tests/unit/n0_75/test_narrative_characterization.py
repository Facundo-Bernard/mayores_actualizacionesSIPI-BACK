"""N0 #75: caracterización pura del narrativo común/V2 y del defecto 0% heredado.

Las fixtures no están adaptadas por edad y no ejercitan preferencias de conversación:
D06 queda expresamente fuera de alcance. Los dobles solo reemplazan lecturas y escrituras;
no se presenta esta suite como evidencia de persistencia Mongo.
"""

from copy import deepcopy

import pytest

from app.features.narrative.constants import (
    COLL_CARDS,
    COLL_CHALLENGES,
    COLL_CHARACTERS,
    COLL_ENDINGS,
    COLL_RUNS,
    COLL_SETTINGS,
    COLL_V2_EVENTS,
)
from app.features.narrative.engine import event_director
from app.features.narrative.engine.rule_engine import evaluar_condicion, ejecutar_accion
from app.features.narrative.game import endings_service, setup_service, transition_service
from app.features.narrative.game import turn_service as coordinador_comun
from app.features.narrative.game import universe_resources
from app.features.narrative.game.motor_v2 import graph_engine as graph_engine_module
from app.features.narrative.game.motor_v2.graph_engine import GraphTraversalEngine
from app.features.narrative.schemas.game_schemas import (
    AvanzarMesRequest,
    ElegirCartaMesRequest,
    IniciarPartidaRequest,
)
from app.features.narrative.schemas.v2_graph_schemas import NodoNarrativoSchema

from .narrative_fixtures import (
    FakeDB,
    carta_n0,
    desafio_n0,
    efecto_recurso_n0,
    evento_n0,
    nodo_n0,
    personaje_n0,
    run_n0,
    universo_n0,
)

pytestmark = pytest.mark.unit


@pytest.mark.comportamiento_preservado
@pytest.mark.asyncio
async def test_coordinador_adquiere_carta_ofrecida_aplica_efecto_y_deriva_a_v2(monkeypatch):
    """La fase común conserva inventario, tags y AL_OBTENER antes de abrir el grafo V2."""
    run = run_n0(
        fase_actual="DRAFT_MENSUAL",
        recursos={"oro": 50},
        turno_actual={"cartas_ofrecidas_ids": ["carta_elegida"]},
    )
    carta = carta_n0(
        "carta_elegida",
        tags=["Comercio"],
        efectos=[efecto_recurso_n0("oro", -5, disparador="al_obtener")],
    )
    db = FakeDB({COLL_RUNS: [run], COLL_CARDS: [carta]})
    monkeypatch.setattr(coordinador_comun, "get_database", lambda: db)

    async def recursos_mapa(_universo_id):
        return {"oro": {"min": 0, "max": 100}}

    async def sin_colapso(_run):
        return None

    llamadas_v2 = []

    async def iniciar_v2(run_recibido, turno_recibido):
        llamadas_v2.append((run_recibido, turno_recibido))
        return "grafo_v2_iniciado"

    async def no_debe_usar_v1(*_args):
        raise AssertionError("Una run V2 no debe derivar al motor plano V1")

    monkeypatch.setattr(coordinador_comun, "obtener_mapa_recursos_universo", recursos_mapa)
    monkeypatch.setattr(coordinador_comun, "verificar_colapso_recursos", sin_colapso)
    monkeypatch.setattr(coordinador_comun, "iniciar_evento_grafo_mes", iniciar_v2)
    monkeypatch.setattr(coordinador_comun, "sortear_evento_plano", no_debe_usar_v1)

    resultado = await coordinador_comun.elegir_carta_mes(
        75, ElegirCartaMesRequest(date="2099-01-01", carta_id="carta_elegida")
    )

    assert resultado == "grafo_v2_iniciado"
    assert run["cartas_en_mano"] == ["carta_elegida"]
    assert run["tags_activos"] == ["Comercio"]
    assert run["recursos"] == {"oro": 45}
    assert run["turno_actual"]["carta_elegida_id"] == "carta_elegida"
    assert llamadas_v2 == [(run, run["turno_actual"])]


@pytest.mark.comportamiento_preservado
@pytest.mark.asyncio
async def test_seleccion_v2_respeta_universo_requisitos_y_tags_de_contenido(monkeypatch):
    """Universo, historial y requisitos filtran; tags de contenido y crisis ponderan."""
    eventos = [
        evento_n0(
            "evt_objetivo",
            peso_base=10,
            tags_tematicos=["CORTE", "comercio", "Oro"],
            requisitos_eventos_previos=["evt_previo"],
            requisitos_personajes=["pj_cero"],
        ),
        evento_n0("evt_plano"),
        evento_n0("evt_previo"),
        evento_n0("evt_arco_incompleto", requisitos_eventos_previos=["evt_ausente"]),
        evento_n0("evt_sin_personaje", requisitos_personajes=["pj_ausente"]),
        evento_n0(
            "evt_condicion_bloqueada",
            condiciones_disparo=[
                {"tipo": "comparar_recurso", "clave": "oro", "operador": ">=", "valor": 25}
            ],
        ),
        evento_n0("evt_otro_universo", universo_id="otro_universo"),
    ]
    db = FakeDB(
        {
            COLL_V2_EVENTS: eventos,
            COLL_CHARACTERS: [personaje_n0("pj_cero", tags=["corte"], afinidad=0)],
            COLL_CARDS: [carta_n0("carta_clave", tags=["COMERCIO"])],
        }
    )
    run = run_n0(
        afinidad={"pj_cero": 0},
        corte_activa=["pj_fallback_no_debe_reemplazar_afinidad"],
        cartas_en_mano=["carta_clave"],
        recursos={"oro": 10},
        eventos_jugados=["evt_previo"],
    )
    sorteos = []

    def choices_controlado(population, weights, k):
        sorteos.append(([evento["_id"] for evento in population], list(weights)))
        assert k == 1
        return [population[0]]

    monkeypatch.setattr(graph_engine_module, "get_database", lambda: db)
    monkeypatch.setattr(graph_engine_module.random, "choices", choices_controlado)

    seleccionado = await GraphTraversalEngine().sortear_evento_v2(
        run=run, pool_ids=None, universo_id="universo_n0"
    )

    assert seleccionado["_id"] == "evt_objetivo"
    # 10 base x2 corte x2.5 cartas x3 crisis; la afinidad 0 sigue siendo corte activa.
    assert sorteos == [(["evt_objetivo", "evt_plano"], [150.0, 100.0])]
    assert db[COLL_V2_EVENTS].find_queries == [{"universo_id": "universo_n0"}]


@pytest.mark.comportamiento_preservado
def test_afinidad_cero_es_valor_presente_y_conserva_membresia_de_corte():
    """El backend no confunde un cero explícito con ausencia ni con el default 50."""
    run = run_n0(afinidad={"pj_cero": 0}, corte_activa=["pj_fallback"])

    assert evaluar_condicion({"tipo": "tiene_personaje", "personaje_id": "pj_cero"}, run)
    assert not evaluar_condicion({"tipo": "tiene_personaje", "personaje_id": "pj_fallback"}, run)
    assert evaluar_condicion(
        {"tipo": "afinidad_personaje", "personaje_id": "pj_cero", "operador": "==", "valor": 0},
        run,
    )
    assert evaluar_condicion(
        {"tipo": "afinidad_personaje", "personaje_id": "pj_cero", "operador": "<", "valor": 15},
        run,
    )


@pytest.mark.defecto_caracterizado
def test_defecto_afinidad_ausente_se_sintetiza_como_50_en_reglas_eca():
    """Defecto E07: una clave ausente vale 50 y MODIFICAR_AFINIDAD puede crearla.

    D04 exige validar personajes desconocidos; este test no convierte el default en regla futura.
    """
    run = run_n0(afinidad={}, corte_activa=["pj_fallback"])

    assert evaluar_condicion({"tipo": "tiene_personaje", "personaje_id": "pj_fallback"}, run)
    assert evaluar_condicion(
        {"tipo": "afinidad_personaje", "personaje_id": "pj_ausente", "operador": "==", "valor": 50},
        run,
    )

    ejecutar_accion(
        {"tipo": "modificar_afinidad", "personaje_id": "pj_ausente", "valor": 5}, run
    )

    assert run["afinidad"] == {"pj_ausente": 55}


@pytest.mark.comportamiento_preservado
def test_tags_son_llaves_exactas_en_condiciones_y_se_deduplican_al_otorgar():
    """Las condiciones ECA usan igualdad exacta; no se inventa normalización de tags."""
    run = run_n0(tags_activos=["Comercio"])

    assert evaluar_condicion({"tipo": "tiene_tag", "tag": "Comercio"}, run)
    assert not evaluar_condicion({"tipo": "tiene_tag", "tag": "comercio"}, run)

    for _ in range(2):
        ejecutar_accion({"tipo": "otorgar_tag", "tag": "Comercio"}, run)
    ejecutar_accion({"tipo": "otorgar_tag", "tag": "comercio"}, run)

    assert run["tags_activos"] == ["Comercio", "comercio"]


@pytest.mark.defecto_caracterizado
@pytest.mark.asyncio
async def test_defecto_seleccion_inicial_acepta_duplicados_y_colapsa_contenido(monkeypatch):
    """Defecto E04: tres IDs no garantizan tres elementos distintos.

    La consulta $in aplica una sola copia de los efectos y la corte queda con dos claves;
    D04 aprueba rechazar estos duplicados iniciales en V2.
    """
    db = FakeDB(
        {
            COLL_RUNS: [],
            COLL_CHALLENGES: [
                desafio_n0(
                    corte=["pj_a", "pj_b"],
                    cartas=["carta_a", "carta_b"],
                    pool=["carta_draft"],
                )
            ],
            COLL_SETTINGS: [universo_n0()],
            COLL_CHARACTERS: [
                personaje_n0("pj_a", afinidad=0),
                personaje_n0("pj_b"),
            ],
            COLL_CARDS: [
                carta_n0(
                    "carta_a",
                    tags=["Comercio"],
                    efectos=[efecto_recurso_n0("oro", 5, disparador="al_obtener")],
                ),
                carta_n0("carta_b", tags=["Fe"]),
                carta_n0("carta_draft"),
            ],
        }
    )
    monkeypatch.setattr(setup_service, "get_database", lambda: db)

    async def recursos_mapa(_universo_id):
        return {"oro": {"min": 0, "max": 100}, "fe": {"min": 0, "max": 100}}

    async def sin_colapso(_run):
        return None

    creadas = []

    async def capturar_creacion(run):
        creadas.append(deepcopy(run))

    monkeypatch.setattr(setup_service, "obtener_mapa_recursos_universo", recursos_mapa)
    monkeypatch.setattr(setup_service, "verificar_colapso_recursos", sin_colapso)
    monkeypatch.setattr(setup_service, "crear_run", capturar_creacion)
    monkeypatch.setattr(
        setup_service.random, "sample", lambda population, k: list(population)[:k]
    )

    response = await setup_service.iniciar_partida(
        75,
        IniciarPartidaRequest(
            date="2099-01-01",
            corte_elegida_ids=["pj_a", "pj_a", "pj_b"],
            cartas_iniciales_ids=["carta_a", "carta_a", "carta_b"],
        ),
    )

    assert len(creadas) == 1
    assert response.motor == "v2"
    assert response.afinidad == {"pj_a": 0, "pj_b": 50}
    assert response.recursos["oro"] == 55  # No son 60: $in devuelve carta_a una vez.
    assert creadas[0]["cartas_en_mano"] == ["carta_a", "carta_a", "carta_b"]
    assert set(creadas[0]["tags_activos"]) == {"Comercio", "Fe"}


@pytest.mark.comportamiento_preservado
@pytest.mark.asyncio
async def test_pasivos_mensuales_de_corte_y_carta_aplican_perdida_y_colapso(monkeypatch):
    """Al entrar al mes 2 se despachan solo CADA_MES; llegar a cero cierra la run."""
    run = run_n0(
        recursos={"oro": 5},
        afinidad={"pj_a": 50},
        cartas_en_mano=["carta_costo"],
    )
    personaje = personaje_n0(
        "pj_a",
        efectos=[
            efecto_recurso_n0("oro", -2),
            efecto_recurso_n0("oro", -40, disparador="al_obtener"),
        ],
    )
    carta = carta_n0("carta_costo", efectos=[efecto_recurso_n0("oro", -3)])
    db = FakeDB(
        {
            COLL_RUNS: [run],
            COLL_CHARACTERS: [personaje],
            COLL_CARDS: [carta],
            COLL_SETTINGS: [universo_n0()],
            COLL_ENDINGS: [
                {
                    "_id": "fin_oro_n0",
                    "universo_id": "universo_n0",
                    "recurso_clave": "oro",
                    "tipo": "derrota_recurso",
                    "titulo": "Sin oro",
                    "texto": "El costo mensual agotó el oro.",
                    "imagen": "/fin.webp",
                    "rango": "F",
                }
            ],
        }
    )
    monkeypatch.setattr(transition_service, "get_database", lambda: db)
    monkeypatch.setattr(endings_service, "get_database", lambda: db)

    async def recursos_mapa(_universo_id):
        return {"oro": {"min": 0, "max": 100}}

    async def persistir(run_persistido, campos=None):
        assert run_persistido is run

    async def sincronizar(run_sincronizado):
        assert run_sincronizado is run
        return 0

    def no_debe_sortear_draft(*_args):
        raise AssertionError("Una derrota por pasivos no debe abrir draft")

    monkeypatch.setattr(transition_service, "obtener_mapa_recursos_universo", recursos_mapa)
    monkeypatch.setattr(transition_service, "persistir_run", persistir)
    monkeypatch.setattr(transition_service, "sincronizar_intento_usuario", sincronizar)
    monkeypatch.setattr(transition_service.random, "sample", no_debe_sortear_draft)

    response = await transition_service.avanzar_mes(75, AvanzarMesRequest(date="2099-01-01"))

    assert response.mes_actual == 2
    assert response.fase_actual == "FINALIZADA"
    assert response.status == "game_over"
    assert response.recursos == {"oro": 0}
    assert response.cartas_draft_actual == []
    assert response.finalizacion.id == "fin_oro_n0"
    assert run["historial_mensual"][0]["recursos_fin_mes"] == {"oro": 5}


@pytest.mark.defecto_caracterizado
@pytest.mark.asyncio
async def test_defecto_copias_posteriores_en_mano_ejecutan_pasivo_una_sola_vez(monkeypatch):
    """Defecto E06: $in pierde multiplicidad y dos copias producen un solo pasivo.

    D04 dispone instancias con pasivos por copia para adquisiciones posteriores; el test
    congela la conducta vigente sin validarla como resultado objetivo.
    """
    run = run_n0(
        recursos={"oro": 50},
        afinidad={},
        corte_activa=[],
        cartas_en_mano=["carta_duplicada", "carta_duplicada"],
    )
    draft_ids = ["draft_a", "draft_b", "draft_c"]
    db = FakeDB(
        {
            COLL_RUNS: [run],
            COLL_CHARACTERS: [],
            COLL_CARDS: [
                carta_n0(
                    "carta_duplicada", efectos=[efecto_recurso_n0("oro", -7)]
                ),
                *(carta_n0(carta_id) for carta_id in draft_ids),
            ],
            COLL_CHALLENGES: [desafio_n0(pool=draft_ids)],
        }
    )
    monkeypatch.setattr(transition_service, "get_database", lambda: db)

    async def recursos_mapa(_universo_id):
        return {"oro": {"min": 0, "max": 100}}

    async def sin_colapso(_run):
        return None

    async def persistir(_run, campos=None):
        return None

    monkeypatch.setattr(transition_service, "obtener_mapa_recursos_universo", recursos_mapa)
    monkeypatch.setattr(transition_service, "verificar_colapso_recursos", sin_colapso)
    monkeypatch.setattr(transition_service, "persistir_run", persistir)
    monkeypatch.setattr(
        transition_service.random, "sample", lambda population, k: list(population)[:k]
    )

    response = await transition_service.avanzar_mes(75, AvanzarMesRequest(date="2099-01-01"))

    assert response.recursos == {"oro": 43}  # Una pérdida de 7, no dos.
    assert run["cartas_en_mano"] == ["carta_duplicada", "carta_duplicada"]
    assert [carta.id for carta in response.cartas_draft_actual] == draft_ids
    assert db[COLL_CARDS].find_queries[0]["_id"]["$in"] == [
        "carta_duplicada",
        "carta_duplicada",
    ]


@pytest.mark.comportamiento_preservado
@pytest.mark.asyncio
async def test_mes_12_cierra_sin_pasivos_sin_draft_y_sin_mes_13(monkeypatch):
    """El balance del mes 12 conserva recursos, guarda historia y termina en victoria."""
    run = run_n0(
        mes_actual=12,
        recursos={"oro": 80, "fe": 80},
        cartas_en_mano=["carta_con_costo"],
        historial_grafos=[
            {
                "mes": 12,
                "tipo": "evento",
                "grafo_id": "evt_final",
                "opcion_elegida_id": "opt_final",
                "resultado_obtenido_id": "fin",
            }
        ],
    )
    db = FakeDB({COLL_RUNS: [run], COLL_SETTINGS: [universo_n0()]})
    monkeypatch.setattr(transition_service, "get_database", lambda: db)

    async def no_debe_aplicar_pasivos(_universo_id):
        raise AssertionError("Mes 12 no debe cargar definiciones para pasivos del mes 13")

    def no_debe_sortear(*_args):
        raise AssertionError("Mes 12 no debe sortear otro draft")

    persistidas = []

    async def persistir(run_persistido, campos=None):
        persistidas.append(deepcopy(run_persistido))

    async def sincronizar(_run):
        return 123

    monkeypatch.setattr(
        transition_service, "obtener_mapa_recursos_universo", no_debe_aplicar_pasivos
    )
    monkeypatch.setattr(transition_service.random, "sample", no_debe_sortear)
    monkeypatch.setattr(transition_service, "persistir_run", persistir)
    monkeypatch.setattr(transition_service, "sincronizar_intento_usuario", sincronizar)

    response = await transition_service.avanzar_mes(75, AvanzarMesRequest(date="2099-01-01"))

    assert response.mes_actual == 12
    assert response.fase_actual == "FINALIZADA"
    assert response.status == "completed"
    assert response.recursos == {"oro": 80, "fe": 80}
    assert response.cartas_draft_actual == []
    assert response.finalizacion.rango == "S"
    assert response.puntos_ganados == 123
    assert run["historial_mensual"][0]["mes"] == 12
    assert run["historial_mensual"][0]["decisiones_v2"] == run["historial_grafos"]
    assert len(persistidas) == 1
    assert db[COLL_CHARACTERS].find_queries == []
    assert db[COLL_CARDS].find_queries == []


@pytest.mark.defecto_caracterizado
def test_defecto_proyeccion_0_por_ciento_puede_ganar_en_el_sorteo(monkeypatch):
    """Defecto E08: proyección clampea a 0 y sorteo clampea el mismo peso a 0.1.

    D05 aprueba unificar pesos para que lo mostrado como 0% nunca se sortee. Este caso
    pertenece al director plano heredado y queda como reproducción, no como regla V2.
    """
    opcion = {
        "id": "opt_azar",
        "texto": "Arriesgar",
        "resultados_posibles": [
            {
                "resultado_id": "res_cero_proyectado",
                "peso_base": 40,
                "modificadores_probabilidad": [
                    {
                        "condicion": {"tipo": "tiene_tag", "tag": "desafio"},
                        "delta_peso": -40,
                        "explicacion": "El modificador anula el peso",
                    }
                ],
            },
            {"resultado_id": "res_positivo", "peso_base": 60},
        ],
    }
    evento = {"opciones": [opcion]}
    run = run_n0(tags_activos=["desafio"])
    resultados = {
        "res_cero_proyectado": {"titulo": "Cero proyectado"},
        "res_positivo": {"titulo": "Positivo"},
    }

    proyeccion = event_director.calcular_opciones_evento(evento, run, resultados)[0]
    assert [(item.resultado_id, item.porcentaje) for item in proyeccion.probabilidades] == [
        ("res_cero_proyectado", 0.0),
        ("res_positivo", 100.0),
    ]

    pesos_sorteados = []

    def choices_controlado(ids, weights, k):
        pesos_sorteados.append(list(weights))
        assert k == 1
        return [ids[0]]

    monkeypatch.setattr(event_director.random, "choices", choices_controlado)

    ganador = event_director.sortear_resultado_opcion(opcion, run)

    assert ganador == "res_cero_proyectado"
    assert pesos_sorteados == [[0.1, 60.0]]


@pytest.mark.comportamiento_preservado
@pytest.mark.asyncio
async def test_v2_peso_cero_no_se_sortea_y_terminal_conserva_perdidas_tags_y_cero(monkeypatch):
    """V2 usa peso mínimo 0, oculta destinos y aplica una sola vez los impactos finales."""
    inicio = nodo_n0(
        "inicio",
        opciones=[
            {
                "id": "opt_azar",
                "texto": "Arriesgar",
                "desenlaces": [
                    {"nodo": "fin_cero", "peso": 0},
                    {"nodo": "fin_valido", "peso": 5},
                ],
            }
        ],
    )
    fin_valido = nodo_n0(
        "fin_valido",
        final=True,
        impactos_recursos=[{"recurso": "oro", "delta": -10}],
        impactos_afinidad=[{"personaje_id": "pj_cero", "delta": -10}],
        impactos_tags=["Comercio", "Comercio"],
    )
    grafo = evento_n0(
        "evt_peso_cero",
        nodos={
            "inicio": inicio,
            "fin_cero": nodo_n0("fin_cero", final=True),
            "fin_valido": fin_valido,
        },
    )
    run = run_n0(
        fase_actual="TOMA_DECISION_EVENTO",
        recursos={"oro": 50},
        afinidad={"pj_cero": 0},
        tags_activos=["Comercio"],
        grafo_activo={
            "tipo": "evento",
            "grafo_id": "evt_peso_cero",
            "nodo_actual_id": "inicio",
        },
    )
    db = FakeDB({COLL_V2_EVENTS: [grafo]})
    monkeypatch.setattr(graph_engine_module, "get_database", lambda: db)

    async def recursos_mapa(_universo_id):
        return {"oro": {"min": 0, "max": 100}}

    async def sin_colapso(_run):
        return None

    async def persistir(_run, campos=None):
        return None

    def choices_controlado(nodos, weights, k):
        assert list(weights) == [0.0, 5.0]
        assert k == 1
        return [nodos[1]]

    monkeypatch.setattr(universe_resources, "obtener_mapa_recursos_universo", recursos_mapa)
    monkeypatch.setattr(endings_service, "verificar_colapso_recursos", sin_colapso)
    monkeypatch.setattr(graph_engine_module, "persistir_run", persistir)
    monkeypatch.setattr(graph_engine_module.random, "choices", choices_controlado)
    monkeypatch.setattr(graph_engine_module.random, "random", lambda: 0.99)

    opcion_cliente = NodoNarrativoSchema(**inicio).to_cliente_schema(run).opciones[0]
    assert "desenlaces" not in opcion_cliente.model_dump()
    assert "siguiente_nodo" not in opcion_cliente.model_dump()

    estado = await GraphTraversalEngine().avanzar_nodo(run, "opt_azar")

    assert estado.nodo_actual.id == "fin_valido"
    assert estado.fase_actual == "BALANCE_MES"
    assert estado.recursos == {"oro": 40}
    assert estado.afinidad == {"pj_cero": 0}
    assert run["tags_activos"] == ["Comercio"]
    assert run["eventos_jugados"] == ["evt_peso_cero"]
    assert run["turno_actual"]["resultado_obtenido_id"] == "fin_valido"


@pytest.mark.comportamiento_preservado
@pytest.mark.parametrize(
    ("antes", "despues", "cruces_esperados"),
    [
        pytest.param(94, 95, [("pj", "lealtad")], id="lealtad_exacta_95"),
        pytest.param(95, 100, [], id="lealtad_ya_estaba_en_umbral"),
        pytest.param(100, 95, [], id="llegar_a_95_desde_arriba_no_es_cruce_al_alza"),
        pytest.param(15, 14, [("pj", "traicion")], id="traicion_exacta_menor_15"),
        pytest.param(14, 13, [], id="traicion_ya_estaba_bajo_umbral"),
        pytest.param(16, 15, [], id="llegar_a_15_no_es_traicion"),
        pytest.param(15, 15, [], id="permanecer_en_15_no_es_cruce"),
    ],
)
def test_umbrales_detectan_solo_cruce_lealtad_desde_95_y_traicion_bajo_15(
    antes, despues, cruces_esperados
):
    """Los especiales se disparan por cruce, no por permanecer en una zona de afinidad."""
    cruces = GraphTraversalEngine()._detectar_cruces_afinidad(
        {"pj": antes}, {"pj": despues}
    )

    assert cruces == cruces_esperados
