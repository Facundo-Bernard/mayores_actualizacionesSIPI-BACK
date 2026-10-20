"""
seed_narrative.py
Script de siembra inicial de contenido para el juego narrativo (Crónicas de la Corte Real).
Carga el universo, personajes, cartas, resultados, eventos y conversaciones iniciales,
y opcionalmente genera los desafíos diarios para el mes actual.
"""

import asyncio
import logging
from datetime import datetime

from app.core.database import get_database, connect_to_mongo
from app.features.narrative.admin.crud_service import (
    crear_o_actualizar_universo,
    crear_o_actualizar_personaje,
    crear_o_actualizar_carta,
    crear_o_actualizar_resultado,
    crear_o_actualizar_evento,
    crear_o_actualizar_conversacion,
)
from app.features.narrative.admin.challenge_service import generar_mes_narrativo
from app.features.narrative.schemas import (
    UniversoCreateRequest,
    RecursoDefinicionSchema,
    PersonajeCreateRequest,
    PersonajeConversacionProbabilidad,
    CartaCreateRequest,
    ResultadoCreateRequest,
    EventoCreateRequest,
    OpcionEventoSchema,
    ResultadoPosibleSchema,
    ModificadorProbabilidadSchema,
    CondicionSchema,
    AccionSchema,
    EfectoSchema,
    ImpactoAfinidadSchema,
    ConversacionCreateRequest,
    ConversacionRequisitoSchema,
    ConversacionFraseSchema,
    ConversacionDecisionSchema
)
from app.features.narrative.enums import (
    DisparadorEnum,
    OperadorEnum,
    TipoCondicionEnum,
    TipoAccionEnum,
    TipoCalculoEnum,
    CategoriaCartaEnum,
    TipoResultadoEnum
)

logger = logging.getLogger(__name__)

UNIVERSO_ID = "corte_medieval"

async def seed_narrative_game():
    logger.info("[NARRATIVE SEED] Iniciando siembra de contenido narrativo...")

    # 1. UNIVERSO: Crónicas de la Corte Real
    universo = UniversoCreateRequest(
        _id=UNIVERSO_ID,
        nombre="Crónicas de la Corte Real",
        descripcion="Gobierna un reino feudal equilibrando las arcas, la fe, el ejército y el apoyo popular.",
        icono="crown",
        recursos=[
            RecursoDefinicionSchema(clave="oro", nombre="Tesoro Real", icono="coins", min=0, max=100, inicial=50),
            RecursoDefinicionSchema(clave="pueblo", nombre="Apoyo Popular", icono="users", min=0, max=100, inicial=50),
            RecursoDefinicionSchema(clave="ejercito", nombre="Fuerza Militar", icono="shield", min=0, max=100, inicial=50),
            RecursoDefinicionSchema(clave="fe", nombre="Fervor Religioso", icono="church", min=0, max=100, inicial=50)
        ]
    )
    await crear_o_actualizar_universo(universo)

    # 2. PERSONAJES (5 iniciales)
    personajes = [
        PersonajeCreateRequest(
            _id="pj_canciller_elena",
            universo_id=UNIVERSO_ID,
            nombre="Elena de Valoria",
            titulo="Canciller del Reino",
            imagen="/assets/narrative/personajes/elena.webp",
            descripcion="Estratega política y hábil negociadora con los gremios de mercaderes.",
            pros=["+15% de oro en eventos comerciales.", "Desbloquea opciones diplomáticas pacíficas."],
            cons=["-5 de apoyo popular cuando se priorizan tropas."],
            tags=["diplomacia", "comercio", "noble"],
            afinidad_inicial=50,
            efectos=[
                EfectoSchema(
                    disparador=DisparadorEnum.CADA_MES,
                    condiciones=[],
                    accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="oro", valor=10)
                )
            ],
            conversaciones=[
                PersonajeConversacionProbabilidad(idConversacion="conv_disputa_tesoro_militar", probabilidad=0.4)
            ]
        ),
        PersonajeCreateRequest(
            _id="pj_comandante_marcus",
            universo_id=UNIVERSO_ID,
            nombre="Marcus Garra de Hierro",
            titulo="Capitán de la Guardia",
            imagen="/assets/narrative/personajes/marcus.webp",
            descripcion="Veterano de mil batallas. Mantiene el orden y la frontera con disciplina férrea.",
            pros=["+15 de Fuerza Militar inmediata al reclutarlo.", "Aumenta chances de éxito en combate."],
            cons=["Consume 5 de oro cada mes para el pago de su guardia."],
            tags=["militar", "combate", "orden"],
            afinidad_inicial=50,
            efectos=[
                EfectoSchema(
                    disparador=DisparadorEnum.AL_OBTENER,
                    condiciones=[],
                    accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="ejercito", valor=15)
                ),
                EfectoSchema(
                    disparador=DisparadorEnum.CADA_MES,
                    condiciones=[],
                    accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="oro", valor=-5)
                )
            ],
            conversaciones=[
                PersonajeConversacionProbabilidad(idConversacion="conv_disputa_tesoro_militar", probabilidad=0.4),
                PersonajeConversacionProbabilidad(idConversacion="conv_tregua_en_la_sombra", probabilidad=0.3)
            ]
        ),
        PersonajeCreateRequest(
            _id="pj_obispo_tomas",
            universo_id=UNIVERSO_ID,
            nombre="Hermano Tomás",
            titulo="Obispo de la Catedral",
            imagen="/assets/narrative/personajes/tomas.webp",
            descripcion="Guía espiritual respetado por el clero y las masas campesinas.",
            pros=["Aumenta la Fe mensualmente.", "Reduce el descontento en épocas de sequía."],
            cons=["Desconfía de la ciencia y exige diezmos regulares."],
            tags=["fe", "religion", "moral"],
            afinidad_inicial=50,
            efectos=[
                EfectoSchema(
                    disparador=DisparadorEnum.CADA_MES,
                    condiciones=[],
                    accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="fe", valor=5)
                )
            ],
            conversaciones=[
                PersonajeConversacionProbabilidad(idConversacion="conv_herejia_en_laboratorio", probabilidad=0.4)
            ]
        ),
        PersonajeCreateRequest(
            _id="pj_alquimista_vera",
            universo_id=UNIVERSO_ID,
            nombre="Vera la Erudita",
            titulo="Alquimista de la Corte",
            imagen="/assets/narrative/personajes/vera.webp",
            descripcion="Estudiosa de pociones, remedios botánicos y secretos de la materia.",
            pros=["Cura plagas y suministra remedios al pueblo.", "Desbloquea opciones secretas científicas."],
            cons=["Sus experimentos levantan sospechas entre los religiosos (-5 Fe inicial)."],
            tags=["ciencia", "salud", "alquimia"],
            afinidad_inicial=50,
            efectos=[
                EfectoSchema(
                    disparador=DisparadorEnum.AL_OBTENER,
                    condiciones=[],
                    accion=AccionSchema(tipo=TipoAccionEnum.OTORGAR_TAG, tag="remedios_alquimia")
                )
            ],
            conversaciones=[
                PersonajeConversacionProbabilidad(idConversacion="conv_herejia_en_laboratorio", probabilidad=0.4)
            ]
        ),
        PersonajeCreateRequest(
            _id="pj_ladrona_sylvia",
            universo_id=UNIVERSO_ID,
            nombre="Sylvia Niebla",
            titulo="Maestra de Espías",
            imagen="/assets/narrative/personajes/sylvia.webp",
            descripcion="Ojos y oídos en cada callejón y taberna del reino.",
            pros=["Anticipa conspiraciones y rebeliones.", "Desbloquea opciones secretas de intriga."],
            cons=["Los nobles desconfían de su presencia en palacio."],
            tags=["espionaje", "intriga", "sombras"],
            afinidad_inicial=50,
            efectos=[
                EfectoSchema(
                    disparador=DisparadorEnum.AL_OBTENER,
                    condiciones=[],
                    accion=AccionSchema(tipo=TipoAccionEnum.OTORGAR_TAG, tag="red_espias")
                )
            ],
            conversaciones=[
                PersonajeConversacionProbabilidad(idConversacion="conv_tregua_en_la_sombra", probabilidad=0.3)
            ]
        )
    ]
    for p in personajes:
        await crear_o_actualizar_personaje(p)

    # 3. CARTAS (10 cartas variadas)
    cartas = [
        CartaCreateRequest(
            _id="card_sello_real",
            universo_id=UNIVERSO_ID,
            categoria=CategoriaCartaEnum.ITEM,
            nombre="Sello Real de la Corona",
            descripcion="Permite emitir decretos supremos y confiscar bienes con autoridad divina.",
            imagen="/assets/narrative/cards/sello.webp",
            tags=["sello_real", "autoridad"],
            efectos=[EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.OTORGAR_TAG, tag="sello_real"))]
        ),
        CartaCreateRequest(
            _id="card_reserva_trigo",
            universo_id=UNIVERSO_ID,
            categoria=CategoriaCartaEnum.ITEM,
            nombre="Reservas de Grano de Emergencia",
            descripcion="Silos sellados que abastecen a la población en momentos de hambruna.",
            imagen="/assets/narrative/cards/trigo.webp",
            tags=["comida", "abastecimiento"],
            efectos=[EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="pueblo", valor=15))]
        ),
        CartaCreateRequest(
            _id="card_escudo_hierro",
            universo_id=UNIVERSO_ID,
            categoria=CategoriaCartaEnum.ITEM,
            nombre="Escudos de Hierro Forjado",
            descripcion="Equipamiento pesado que fortalece la línea defensiva del ejército.",
            imagen="/assets/narrative/cards/escudo.webp",
            tags=["defensa", "militar"],
            efectos=[EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="ejercito", valor=10))]
        ),
        CartaCreateRequest(
            _id="card_carretas_logistica",
            universo_id=UNIVERSO_ID,
            categoria=CategoriaCartaEnum.ITEM,
            nombre="Carretas de Logística y Transporte",
            descripcion="Mejora el desplazamiento de tropas y víveres por todo el reino.",
            imagen="/assets/narrative/cards/carreta.webp",
            tags=["logistica_militar", "transporte"],
            efectos=[EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.OTORGAR_TAG, tag="logistica_militar"))]
        ),
        CartaCreateRequest(
            _id="card_diezmo_comercial",
            universo_id=UNIVERSO_ID,
            categoria=CategoriaCartaEnum.BONUS,
            nombre="Arancel Aduanero Favorable",
            descripcion="Genera +10 de oro cada mes si el apoyo popular se mantiene >= 40.",
            imagen="/assets/narrative/cards/arancel.webp",
            tags=["comercio", "economia"],
            efectos=[
                EfectoSchema(
                    disparador=DisparadorEnum.CADA_MES,
                    condiciones=[CondicionSchema(tipo=TipoCondicionEnum.COMPARAR_RECURSO, clave="pueblo", operador=OperadorEnum.MAYOR_IGUAL, valor=40)],
                    accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="oro", valor=10)
                )
            ]
        ),
        CartaCreateRequest(
            _id="card_tratado_paz",
            universo_id=UNIVERSO_ID,
            categoria=CategoriaCartaEnum.BONUS,
            nombre="Tratado Fronterizo de No Agresión",
            descripcion="Otorga estabilidad diplomática, sumando +10 de oro y +10 de pueblo.",
            imagen="/assets/narrative/cards/tratado.webp",
            tags=["diplomacia", "paz"],
            efectos=[
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="oro", valor=10)),
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="pueblo", valor=10))
            ]
        ),
        CartaCreateRequest(
            _id="card_festival_cosecha",
            universo_id=UNIVERSO_ID,
            categoria=CategoriaCartaEnum.BONUS,
            nombre="Fiesta Patronal de Otoño",
            descripcion="Organiza banquetes públicos. Gasta 10 de oro pero otorga +20 de pueblo y +10 de fe.",
            imagen="/assets/narrative/cards/festival.webp",
            tags=["moral", "fiesta"],
            efectos=[
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="oro", valor=-10)),
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="pueblo", valor=20)),
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="fe", valor=10))
            ]
        ),
        CartaCreateRequest(
            _id="card_mercenarios",
            universo_id=UNIVERSO_ID,
            categoria=CategoriaCartaEnum.PERSONAJE,
            nombre="Compañía de Mercenarios Veteranos",
            descripcion="Espadas a sueldo: +20 de fuerza militar inmediata a cambio de 15 monedas de oro.",
            imagen="/assets/narrative/cards/mercenarios.webp",
            tags=["militar", "mercenarios"],
            efectos=[
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="ejercito", valor=20)),
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="oro", valor=-15))
            ]
        ),
        CartaCreateRequest(
            _id="card_remedio_herbario",
            universo_id=UNIVERSO_ID,
            categoria=CategoriaCartaEnum.ITEM,
            nombre="Boticario de Campaña",
            descripcion="Frascos de ungüentos y tónicos que mejoran la salud y alivian heridas.",
            imagen="/assets/narrative/cards/pocion.webp",
            tags=["salud", "alquimia"],
            efectos=[EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="pueblo", valor=10))]
        ),
        CartaCreateRequest(
            _id="card_red_espias",
            universo_id=UNIVERSO_ID,
            categoria=CategoriaCartaEnum.BONUS,
            nombre="Red de Informantes Clandestina",
            descripcion="Otorga el tag pasivo 'red_espias' para detectar conspiraciones.",
            imagen="/assets/narrative/cards/espias.webp",
            tags=["espionaje", "informacion"],
            efectos=[EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.OTORGAR_TAG, tag="red_espias"))]
        )
    ]
    for c in cartas:
        await crear_o_actualizar_carta(c)

    # 4. RESULTADOS (15 desenlaces reutilizables y temáticos)
    resultados = [
        ResultadoCreateRequest(
            _id="res_grano_comprado_justo",
            universo_id=UNIVERSO_ID,
            titulo="Cargamentos de Trigo en Palacio",
            texto="Los mercaderes entregaron el grano prometido. Las familias tienen pan caliente en sus mesas.",
            imagen="/assets/narrative/results/grano_exito.webp",
            tipo_resultado=TipoResultadoEnum.POSITIVO,
            efectos=[
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="oro", valor=-15)),
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="pueblo", valor=20))
            ]
        ),
        ResultadoCreateRequest(
            _id="res_estafa_mercaderes",
            universo_id=UNIVERSO_ID,
            titulo="Sacos de Arena y Grano Rancio",
            texto="Los comerciantes cobraron por adelantado y huyeron dejando sacos de grano podrido.",
            imagen="/assets/narrative/results/estafa.webp",
            tipo_resultado=TipoResultadoEnum.NEGATIVO,
            efectos=[
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="oro", valor=-15)),
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="pueblo", valor=-10))
            ]
        ),
        ResultadoCreateRequest(
            _id="res_suministros_asegurados",
            universo_id=UNIVERSO_ID,
            titulo="Graneros Protegidos con Disciplina",
            texto="La guardia custodió los silos y evitó saqueos, manteniendo las raciones estables.",
            imagen="/assets/narrative/results/guardia_victoria.webp",
            tipo_resultado=TipoResultadoEnum.POSITIVO,
            efectos=[
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="ejercito", valor=10)),
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="pueblo", valor=10))
            ]
        ),
        ResultadoCreateRequest(
            _id="res_emboscada_y_perdida",
            universo_id=UNIVERSO_ID,
            titulo="Patrulla Derrotada en el Camino",
            texto="Bandidos y rebeldes emboscaron a la comitiva, robando los suministros y armas.",
            imagen="/assets/narrative/results/emboscada.webp",
            tipo_resultado=TipoResultadoEnum.NEGATIVO,
            efectos=[
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="ejercito", valor=-15)),
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="oro", valor=-10))
            ]
        ),
        ResultadoCreateRequest(
            _id="res_cosecha_salvada_decreto",
            universo_id=UNIVERSO_ID,
            titulo="Decreto Real Acatado sin Resistencia",
            texto="Nadie osó contradecir el Sello Real. Los señores feudales cedieron sus silos a la corona.",
            imagen="/assets/narrative/results/decreto.webp",
            tipo_resultado=TipoResultadoEnum.POSITIVO,
            efectos=[
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="pueblo", valor=25)),
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="fe", valor=10))
            ]
        ),
        ResultadoCreateRequest(
            _id="res_embajador_satisfecho",
            universo_id=UNIVERSO_ID,
            titulo="Alianza Fronteriza Sellada",
            texto="El banquete y las palabras diplomáticas lograron un acuerdo comercial muy ventajoso.",
            imagen="/assets/narrative/results/diplomacia_exito.webp",
            tipo_resultado=TipoResultadoEnum.POSITIVO,
            efectos=[
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="oro", valor=20)),
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="pueblo", valor=10))
            ]
        ),
        ResultadoCreateRequest(
            _id="res_disturbios_populares",
            universo_id=UNIVERSO_ID,
            titulo="Clamor y Protestas en las Calles",
            texto="La multitud marchó frente a las puertas del castillo arrojando piedras e insultos.",
            imagen="/assets/narrative/results/disturbios.webp",
            tipo_resultado=TipoResultadoEnum.NEGATIVO,
            efectos=[
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="pueblo", valor=-20))
            ]
        ),
        ResultadoCreateRequest(
            _id="res_bendicion_catedral",
            universo_id=UNIVERSO_ID,
            titulo="Canto Solemne en la Catedral",
            texto="Las campanas repicaron en bendición del reinado, devolviendo la esperanza a los fieles.",
            imagen="/assets/narrative/results/catedral.webp",
            tipo_resultado=TipoResultadoEnum.POSITIVO,
            efectos=[
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="fe", valor=20)),
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="pueblo", valor=10))
            ]
        ),
        ResultadoCreateRequest(
            _id="res_cura_alquimica",
            universo_id=UNIVERSO_ID,
            titulo="Milagro de la Alquimia",
            texto="Los tónicos botánicos purificadores sanaron la peste y devolvieron el vigor a la corte.",
            imagen="/assets/narrative/results/cura.webp",
            tipo_resultado=TipoResultadoEnum.POSITIVO,
            efectos=[
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="pueblo", valor=25)),
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="fe", valor=10))
            ]
        ),
        ResultadoCreateRequest(
            _id="res_plaga_descontrolada",
            universo_id=UNIVERSO_ID,
            titulo="Epidemia en los Suburbios",
            texto="La enfermedad se extendió sin control por los barrios bajos, causando luto general.",
            imagen="/assets/narrative/results/peste.webp",
            tipo_resultado=TipoResultadoEnum.NEGATIVO,
            efectos=[
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="pueblo", valor=-25)),
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="fe", valor=-10))
            ]
        ),
        ResultadoCreateRequest(
            _id="res_red_espias_exito",
            universo_id=UNIVERSO_ID,
            titulo="Conspiración Desmantelada en las Sombras",
            texto="Los informantes clandestinos interceptaron a los cabecillas traidores en plena noche.",
            imagen="/assets/narrative/results/espias_exito.webp",
            tipo_resultado=TipoResultadoEnum.POSITIVO,
            efectos=[
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="oro", valor=20)),
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="ejercito", valor=15))
            ]
        ),
        ResultadoCreateRequest(
            _id="res_traicion_corte",
            universo_id=UNIVERSO_ID,
            titulo="Puñalada en los Pasillos de Palacio",
            texto="Los conspiradores atacaron por sorpresa antes de ser reducidos, sembrando desconfianza.",
            imagen="/assets/narrative/results/traicion.webp",
            tipo_resultado=TipoResultadoEnum.NEGATIVO,
            efectos=[
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="oro", valor=-15)),
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="pueblo", valor=-10))
            ]
        ),
        ResultadoCreateRequest(
            _id="res_victoria_militar_frontera",
            universo_id=UNIVERSO_ID,
            titulo="Victoria Aplastante en la Frontera",
            texto="Las legiones de la guardia barrieron a los invasores, afianzando la paz del reino.",
            imagen="/assets/narrative/results/victoria_militar.webp",
            tipo_resultado=TipoResultadoEnum.POSITIVO,
            efectos=[
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="ejercito", valor=20)),
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="oro", valor=10))
            ]
        ),
        ResultadoCreateRequest(
            _id="res_inquisicion_controlada",
            universo_id=UNIVERSO_ID,
            titulo="Paz Eclesiástica y Doctrina Firme",
            texto="El juicio se condujo con mesura y caridad, fortaleciendo la fe y la armonía popular.",
            imagen="/assets/narrative/results/inquisicion.webp",
            tipo_resultado=TipoResultadoEnum.POSITIVO,
            efectos=[
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="fe", valor=25)),
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="pueblo", valor=10))
            ]
        ),
        ResultadoCreateRequest(
            _id="res_oro_minas_masivo",
            universo_id=UNIVERSO_ID,
            titulo="El Filón Supremo de la Corona",
            texto="Nuevos métodos multiplicaron el rendimiento de las vetas de plata y oro de las arcas.",
            imagen="/assets/narrative/results/minas.webp",
            tipo_resultado=TipoResultadoEnum.POSITIVO,
            efectos=[
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="oro", valor=30)),
                EfectoSchema(disparador=DisparadorEnum.AL_OBTENER, condiciones=[], accion=AccionSchema(tipo=TipoAccionEnum.MODIFICAR_RECURSO, clave="pueblo", valor=10))
            ]
        )
    ]
    for r in resultados:
        await crear_o_actualizar_resultado(r)

    # 5. EVENTOS DEL AÑO (12 eventos únicos con opciones dinámicas, probabilidades y secretas)
    eventos = [
        # Evento 1: Hambruna y Clima
        EventoCreateRequest(
            _id="evt_helada_cosechas",
            universo_id=UNIVERSO_ID,
            titulo="La Gran Helada en el Valle",
            descripcion="Una ola de frío polar congeló los campos de trigo. Los silos campesinos amenazan con quedar vacíos.",
            imagen="/assets/narrative/events/helada.webp",
            tags_tematicos=["clima", "comida", "crisis", "pueblo"],
            peso_base=100.0,
            opciones=[
                OpcionEventoSchema(
                    id="op_a",
                    texto="Enviar patrullas a custodiar y racionar graneros",
                    es_secreta=False,
                    condiciones=[],
                    resultados_posibles=[
                        ResultadoPosibleSchema(
                            resultado_id="res_suministros_asegurados",
                            peso_base=50.0,
                            modificadores_probabilidad=[
                                ModificadorProbabilidadSchema(
                                    condicion=CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_comandante_marcus"),
                                    delta_peso=35.0,
                                    explicacion="+35% por liderazgo del Comandante Marcus"
                                ),
                                ModificadorProbabilidadSchema(
                                    condicion=CondicionSchema(tipo=TipoCondicionEnum.TIENE_TAG, tag="logistica_militar"),
                                    delta_peso=15.0,
                                    explicacion="+15% por carretas organizadas"
                                )
                            ]
                        ),
                        ResultadoPosibleSchema(resultado_id="res_emboscada_y_perdida", peso_base=50.0)
                    ]
                ),
                OpcionEventoSchema(
                    id="op_b",
                    texto="Comprar grano de emergencia a mercaderes extranjeros",
                    es_secreta=False,
                    condiciones=[],
                    resultados_posibles=[
                        ResultadoPosibleSchema(
                            resultado_id="res_grano_comprado_justo",
                            peso_base=60.0,
                            modificadores_probabilidad=[
                                ModificadorProbabilidadSchema(
                                    condicion=CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_canciller_elena"),
                                    delta_peso=30.0,
                                    explicacion="+30% por negociación de la Canciller Elena"
                                )
                            ]
                        ),
                        ResultadoPosibleSchema(resultado_id="res_estafa_mercaderes", peso_base=40.0)
                    ]
                ),
                OpcionEventoSchema(
                    id="op_c",
                    texto="[Secreto] Decretar requisa general amparado en el Sello Real",
                    es_secreta=True,
                    condiciones=[CondicionSchema(tipo=TipoCondicionEnum.TIENE_TAG, tag="sello_real")],
                    resultados_posibles=[ResultadoPosibleSchema(resultado_id="res_cosecha_salvada_decreto", peso_base=100.0)]
                )
            ]
        ),

        # Evento 2: Diplomacia
        EventoCreateRequest(
            _id="evt_visita_embajador",
            universo_id=UNIVERSO_ID,
            titulo="El Embajador del Reino del Norte",
            descripcion="Un noble extranjero arriba con escolta armada proponiendo un pacto arancelario muy exigente.",
            imagen="/assets/narrative/events/embajador.webp",
            tags_tematicos=["diplomacia", "comercio", "noble", "oro"],
            peso_base=100.0,
            opciones=[
                OpcionEventoSchema(
                    id="op_a",
                    texto="Organizar una recepción fastuosa y firmar el acuerdo",
                    es_secreta=False,
                    condiciones=[],
                    resultados_posibles=[
                        ResultadoPosibleSchema(
                            resultado_id="res_embajador_satisfecho",
                            peso_base=60.0,
                            modificadores_probabilidad=[
                                ModificadorProbabilidadSchema(
                                    condicion=CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_canciller_elena"),
                                    delta_peso=30.0,
                                    explicacion="+30% por carisma de la Canciller Elena"
                                )
                            ]
                        ),
                        ResultadoPosibleSchema(resultado_id="res_disturbios_populares", peso_base=40.0)
                    ]
                ),
                OpcionEventoSchema(
                    id="op_b",
                    texto="Desfile marcial disuasorio e imponer condiciones estrictas",
                    es_secreta=False,
                    condiciones=[],
                    resultados_posibles=[
                        ResultadoPosibleSchema(
                            resultado_id="res_embajador_satisfecho",
                            peso_base=50.0,
                            modificadores_probabilidad=[
                                ModificadorProbabilidadSchema(
                                    condicion=CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_comandante_marcus"),
                                    delta_peso=35.0,
                                    explicacion="+35% por presencia del Comandante Marcus"
                                )
                            ]
                        ),
                        ResultadoPosibleSchema(resultado_id="res_disturbios_populares", peso_base=50.0)
                    ]
                ),
                OpcionEventoSchema(
                    id="op_c",
                    texto="[Secreto] Chantajear a la delegación con cartas interceptadas por espías",
                    es_secreta=True,
                    condiciones=[CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_ladrona_sylvia")],
                    resultados_posibles=[ResultadoPosibleSchema(resultado_id="res_embajador_satisfecho", peso_base=100.0)]
                )
            ]
        ),

        # Evento 3: Peste y Medicina
        EventoCreateRequest(
            _id="evt_brote_peste",
            universo_id=UNIVERSO_ID,
            titulo="Brote de Fiebre en los Suburbios",
            descripcion="Una extraña fiebre debilita a los artesanos y soldados en los cuarteles periféricos.",
            imagen="/assets/narrative/events/peste.webp",
            tags_tematicos=["salud", "crisis", "pueblo"],
            peso_base=95.0,
            opciones=[
                OpcionEventoSchema(
                    id="op_a",
                    texto="Aislar los distritos afectados con cordón sanitario militar",
                    es_secreta=False,
                    condiciones=[],
                    resultados_posibles=[
                        ResultadoPosibleSchema(
                            resultado_id="res_suministros_asegurados",
                            peso_base=50.0,
                            modificadores_probabilidad=[
                                ModificadorProbabilidadSchema(
                                    condicion=CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_comandante_marcus"),
                                    delta_peso=30.0,
                                    explicacion="+30% por disciplina de Marcus"
                                )
                            ]
                        ),
                        ResultadoPosibleSchema(resultado_id="res_plaga_descontrolada", peso_base=50.0)
                    ]
                ),
                OpcionEventoSchema(
                    id="op_b",
                    texto="Llamar a oraciones solemnes y caridad de la iglesia",
                    es_secreta=False,
                    condiciones=[],
                    resultados_posibles=[
                        ResultadoPosibleSchema(
                            resultado_id="res_bendicion_catedral",
                            peso_base=50.0,
                            modificadores_probabilidad=[
                                ModificadorProbabilidadSchema(
                                    condicion=CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_obispo_tomas"),
                                    delta_peso=35.0,
                                    explicacion="+35% por influencia del Hermano Tomás"
                                )
                            ]
                        ),
                        ResultadoPosibleSchema(resultado_id="res_plaga_descontrolada", peso_base=50.0)
                    ]
                ),
                OpcionEventoSchema(
                    id="op_c",
                    texto="[Secreto] Formular antídoto magistral en el laboratorio alquímico",
                    es_secreta=True,
                    condiciones=[CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_alquimista_vera")],
                    resultados_posibles=[ResultadoPosibleSchema(resultado_id="res_cura_alquimica", peso_base=100.0)]
                )
            ]
        ),

        # Evento 4: El Cometa
        EventoCreateRequest(
            _id="evt_cometa_cielo",
            universo_id=UNIVERSO_ID,
            titulo="El Cometa de Medianoche",
            descripcion="Una estela verde cruza el firmamento. El pueblo teme un presagio nefasto y clama en los templos.",
            imagen="/assets/narrative/events/cometa.webp",
            tags_tematicos=["fe", "religion", "moral"],
            peso_base=90.0,
            opciones=[
                OpcionEventoSchema(
                    id="op_a",
                    texto="Financiar procesiones y vigilias de expiación en la catedral",
                    es_secreta=False,
                    condiciones=[],
                    resultados_posibles=[
                        ResultadoPosibleSchema(
                            resultado_id="res_bendicion_catedral",
                            peso_base=60.0,
                            modificadores_probabilidad=[
                                ModificadorProbabilidadSchema(
                                    condicion=CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_obispo_tomas"),
                                    delta_peso=35.0,
                                    explicacion="+35% por prédica de Tomás"
                                )
                            ]
                        ),
                        ResultadoPosibleSchema(resultado_id="res_disturbios_populares", peso_base=40.0)
                    ]
                ),
                OpcionEventoSchema(
                    id="op_b",
                    texto="Bando municipal llamando a la calma y el sosiego",
                    es_secreta=False,
                    condiciones=[],
                    resultados_posibles=[
                        ResultadoPosibleSchema(
                            resultado_id="res_embajador_satisfecho",
                            peso_base=50.0,
                            modificadores_probabilidad=[
                                ModificadorProbabilidadSchema(
                                    condicion=CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_canciller_elena"),
                                    delta_peso=30.0,
                                    explicacion="+30% por oratoria de Elena"
                                )
                            ]
                        ),
                        ResultadoPosibleSchema(resultado_id="res_disturbios_populares", peso_base=50.0)
                    ]
                ),
                OpcionEventoSchema(
                    id="op_c",
                    texto="[Secreto] Explicar el fenómeno astronómico con mediciones ópticas",
                    es_secreta=True,
                    condiciones=[CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_alquimista_vera")],
                    resultados_posibles=[ResultadoPosibleSchema(resultado_id="res_cura_alquimica", peso_base=100.0)]
                )
            ]
        ),

        # Evento 5: Conspiración
        EventoCreateRequest(
            _id="evt_conspiracion_corte",
            universo_id=UNIVERSO_ID,
            titulo="Susurros de Conspiración en la Corte",
            descripcion="Cartas sin firma encontradas en los pasillos acusan a barones de planear un complot contra la corona.",
            imagen="/assets/narrative/events/conspiracion.webp",
            tags_tematicos=["intriga", "orden", "noble"],
            peso_base=90.0,
            opciones=[
                OpcionEventoSchema(
                    id="op_a",
                    texto="Apostar centinelas de confianza y registrar carruajes nobles",
                    es_secreta=False,
                    condiciones=[],
                    resultados_posibles=[
                        ResultadoPosibleSchema(
                            resultado_id="res_suministros_asegurados",
                            peso_base=50.0,
                            modificadores_probabilidad=[
                                ModificadorProbabilidadSchema(
                                    condicion=CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_comandante_marcus"),
                                    delta_peso=35.0,
                                    explicacion="+35% por lealtad de la guardia de Marcus"
                                )
                            ]
                        ),
                        ResultadoPosibleSchema(resultado_id="res_traicion_corte", peso_base=50.0)
                    ]
                ),
                OpcionEventoSchema(
                    id="op_b",
                    texto="Auditar los tributos nobiliarios para asfixiar a los rebeldes",
                    es_secreta=False,
                    condiciones=[],
                    resultados_posibles=[
                        ResultadoPosibleSchema(
                            resultado_id="res_grano_comprado_justo",
                            peso_base=50.0,
                            modificadores_probabilidad=[
                                ModificadorProbabilidadSchema(
                                    condicion=CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_canciller_elena"),
                                    delta_peso=30.0,
                                    explicacion="+30% por agudeza contable de Elena"
                                )
                            ]
                        ),
                        ResultadoPosibleSchema(resultado_id="res_traicion_corte", peso_base=50.0)
                    ]
                ),
                OpcionEventoSchema(
                    id="op_c",
                    texto="[Secreto] Infiltrar informantes en las tabernas de los conjurados",
                    es_secreta=True,
                    condiciones=[CondicionSchema(tipo=TipoCondicionEnum.TIENE_TAG, tag="red_espias")],
                    resultados_posibles=[ResultadoPosibleSchema(resultado_id="res_red_espias_exito", peso_base=100.0)]
                )
            ]
        ),

        # Evento 6: Bandidos en el Paso
        EventoCreateRequest(
            _id="evt_asedio_bandidos",
            universo_id=UNIVERSO_ID,
            titulo="Bandidos en el Paso de Montaña",
            descripcion="Caravanas comerciales han sido asaltadas en las quebradas. El comercio hacia la capital está paralizado.",
            imagen="/assets/narrative/events/bandidos.webp",
            tags_tematicos=["militar", "comercio", "seguridad"],
            peso_base=85.0,
            opciones=[
                OpcionEventoSchema(
                    id="op_a",
                    texto="Lanzar ofensiva militar directa al campamento bandolero",
                    es_secreta=False,
                    condiciones=[],
                    resultados_posibles=[
                        ResultadoPosibleSchema(
                            resultado_id="res_victoria_militar_frontera",
                            peso_base=50.0,
                            modificadores_probabilidad=[
                                ModificadorProbabilidadSchema(
                                    condicion=CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_comandante_marcus"),
                                    delta_peso=35.0,
                                    explicacion="+35% por veteranía de Marcus"
                                ),
                                ModificadorProbabilidadSchema(
                                    condicion=CondicionSchema(tipo=TipoCondicionEnum.TIENE_TAG, tag="defensa"),
                                    delta_peso=15.0,
                                    explicacion="+15% por escudos pesados"
                                )
                            ]
                        ),
                        ResultadoPosibleSchema(resultado_id="res_emboscada_y_perdida", peso_base=50.0)
                    ]
                ),
                OpcionEventoSchema(
                    id="op_b",
                    texto="Negociar amnistía a cambio de despejar el camino",
                    es_secreta=False,
                    condiciones=[],
                    resultados_posibles=[
                        ResultadoPosibleSchema(
                            resultado_id="res_embajador_satisfecho",
                            peso_base=50.0,
                            modificadores_probabilidad=[
                                ModificadorProbabilidadSchema(
                                    condicion=CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_canciller_elena"),
                                    delta_peso=30.0,
                                    explicacion="+30% por diplomacia de Elena"
                                )
                            ]
                        ),
                        ResultadoPosibleSchema(resultado_id="res_emboscada_y_perdida", peso_base=50.0)
                    ]
                ),
                OpcionEventoSchema(
                    id="op_c",
                    texto="[Secreto] Envenenar los barriles del campamento bandido",
                    es_secreta=True,
                    condiciones=[CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_ladrona_sylvia")],
                    resultados_posibles=[ResultadoPosibleSchema(resultado_id="res_victoria_militar_frontera", peso_base=100.0)]
                )
            ]
        ),

        # Evento 7: La Gran Feria
        EventoCreateRequest(
            _id="evt_feria_comercial",
            universo_id=UNIVERSO_ID,
            titulo="La Gran Feria de San Lucas",
            descripcion="Mercaderes de cinco reinos llenan la plaza central con especias, telas y metales preciosos.",
            imagen="/assets/narrative/events/feria.webp",
            tags_tematicos=["comercio", "oro", "sociedad"],
            peso_base=85.0,
            opciones=[
                OpcionEventoSchema(
                    id="op_a",
                    texto="Cobrar el arancel aduanero completo a mercaderes",
                    es_secreta=False,
                    condiciones=[],
                    resultados_posibles=[
                        ResultadoPosibleSchema(
                            resultado_id="res_embajador_satisfecho",
                            peso_base=60.0,
                            modificadores_probabilidad=[
                                ModificadorProbabilidadSchema(
                                    condicion=CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_canciller_elena"),
                                    delta_peso=30.0,
                                    explicacion="+30% por control aduanero de Elena"
                                )
                            ]
                        ),
                        ResultadoPosibleSchema(resultado_id="res_estafa_mercaderes", peso_base=40.0)
                    ]
                ),
                OpcionEventoSchema(
                    id="op_b",
                    texto="Eximir de impuestos para atraer más gremios al reino",
                    es_secreta=False,
                    condiciones=[],
                    resultados_posibles=[
                        ResultadoPosibleSchema(
                            resultado_id="res_grano_comprado_justo",
                            peso_base=60.0,
                            modificadores_probabilidad=[
                                ModificadorProbabilidadSchema(
                                    condicion=CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_obispo_tomas"),
                                    delta_peso=25.0,
                                    explicacion="+25% por bendición a los gremios"
                                )
                            ]
                        ),
                        ResultadoPosibleSchema(resultado_id="res_disturbios_populares", peso_base=40.0)
                    ]
                ),
                OpcionEventoSchema(
                    id="op_c",
                    texto="[Secreto] Decretar monopolio de la corona sobre metales y especias",
                    es_secreta=True,
                    condiciones=[CondicionSchema(tipo=TipoCondicionEnum.TIENE_TAG, tag="sello_real")],
                    resultados_posibles=[ResultadoPosibleSchema(resultado_id="res_oro_minas_masivo", peso_base=100.0)]
                )
            ]
        ),

        # Evento 8: Sequía
        EventoCreateRequest(
            _id="evt_sequia_estival",
            universo_id=UNIVERSO_ID,
            titulo="La Gran Sequía del Estío",
            descripcion="El río principal bajó a niveles mínimos. Los molinos no giran y el ganado languidece.",
            imagen="/assets/narrative/events/sequia.webp",
            tags_tematicos=["clima", "comida", "crisis"],
            peso_base=85.0,
            opciones=[
                OpcionEventoSchema(
                    id="op_a",
                    texto="Racionar pozos y transportar agua con carretas militares",
                    es_secreta=False,
                    condiciones=[],
                    resultados_posibles=[
                        ResultadoPosibleSchema(
                            resultado_id="res_suministros_asegurados",
                            peso_base=50.0,
                            modificadores_probabilidad=[
                                ModificadorProbabilidadSchema(
                                    condicion=CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_comandante_marcus"),
                                    delta_peso=30.0,
                                    explicacion="+30% por orden de Marcus"
                                ),
                                ModificadorProbabilidadSchema(
                                    condicion=CondicionSchema(tipo=TipoCondicionEnum.TIENE_TAG, tag="logistica_militar"),
                                    delta_peso=20.0,
                                    explicacion="+20% por carretas logísticas"
                                )
                            ]
                        ),
                        ResultadoPosibleSchema(resultado_id="res_disturbios_populares", peso_base=50.0)
                    ]
                ),
                OpcionEventoSchema(
                    id="op_b",
                    texto="Rogativas solemnes y procesión por la lluvia",
                    es_secreta=False,
                    condiciones=[],
                    resultados_posibles=[
                        ResultadoPosibleSchema(
                            resultado_id="res_bendicion_catedral",
                            peso_base=50.0,
                            modificadores_probabilidad=[
                                ModificadorProbabilidadSchema(
                                    condicion=CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_obispo_tomas"),
                                    delta_peso=35.0,
                                    explicacion="+35% por rogativas de Tomás"
                                )
                            ]
                        ),
                        ResultadoPosibleSchema(resultado_id="res_disturbios_populares", peso_base=50.0)
                    ]
                ),
                OpcionEventoSchema(
                    id="op_c",
                    texto="[Secreto] Abrir reservas estratégicas de grano y silos subterráneos",
                    es_secreta=True,
                    condiciones=[CondicionSchema(tipo=TipoCondicionEnum.TIENE_TAG, tag="abastecimiento")],
                    resultados_posibles=[ResultadoPosibleSchema(resultado_id="res_cosecha_salvada_decreto", peso_base=100.0)]
                )
            ]
        ),

        # Evento 9: Inquisición
        EventoCreateRequest(
            _id="evt_visita_inquisidor",
            universo_id=UNIVERSO_ID,
            titulo="El Tribunal del Gran Inquisidor",
            descripcion="Legados papales exigen investigar prácticas sospechosas entre los sabios del reino.",
            imagen="/assets/narrative/events/inquisidor.webp",
            tags_tematicos=["fe", "religion", "ley"],
            peso_base=80.0,
            opciones=[
                OpcionEventoSchema(
                    id="op_a",
                    texto="Facilitar la investigación de la curia en la capital",
                    es_secreta=False,
                    condiciones=[],
                    resultados_posibles=[
                        ResultadoPosibleSchema(
                            resultado_id="res_inquisicion_controlada",
                            peso_base=50.0,
                            modificadores_probabilidad=[
                                ModificadorProbabilidadSchema(
                                    condicion=CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_obispo_tomas"),
                                    delta_peso=40.0,
                                    explicacion="+40% por mediación moderada de Tomás"
                                )
                            ]
                        ),
                        ResultadoPosibleSchema(resultado_id="res_disturbios_populares", peso_base=50.0)
                    ]
                ),
                OpcionEventoSchema(
                    id="op_b",
                    texto="Limitar las atribuciones del tribunal con leyes civiles",
                    es_secreta=False,
                    condiciones=[],
                    resultados_posibles=[
                        ResultadoPosibleSchema(
                            resultado_id="res_embajador_satisfecho",
                            peso_base=50.0,
                            modificadores_probabilidad=[
                                ModificadorProbabilidadSchema(
                                    condicion=CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_canciller_elena"),
                                    delta_peso=30.0,
                                    explicacion="+30% por jurisprudencia de Elena"
                                )
                            ]
                        ),
                        ResultadoPosibleSchema(resultado_id="res_traicion_corte", peso_base=50.0)
                    ]
                ),
                OpcionEventoSchema(
                    id="op_c",
                    texto="[Secreto] Sembrar pistas falsas para salvar a los eruditos del patíbulo",
                    es_secreta=True,
                    condiciones=[CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_ladrona_sylvia")],
                    resultados_posibles=[ResultadoPosibleSchema(resultado_id="res_red_espias_exito", peso_base=100.0)]
                )
            ]
        ),

        # Evento 10: Motín del Pan
        EventoCreateRequest(
            _id="evt_motin_campesino",
            universo_id=UNIVERSO_ID,
            titulo="El Motín del Pan",
            descripcion="Gremialistas y campesinos se congregan frente al palacio exigiendo abaratar los alimentos.",
            imagen="/assets/narrative/events/motin.webp",
            tags_tematicos=["pueblo", "crisis", "orden"],
            peso_base=85.0,
            opciones=[
                OpcionEventoSchema(
                    id="op_a",
                    texto="Desplegar a la guardia para disolver los desórdenes",
                    es_secreta=False,
                    condiciones=[],
                    resultados_posibles=[
                        ResultadoPosibleSchema(
                            resultado_id="res_suministros_asegurados",
                            peso_base=50.0,
                            modificadores_probabilidad=[
                                ModificadorProbabilidadSchema(
                                    condicion=CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_comandante_marcus"),
                                    delta_peso=35.0,
                                    explicacion="+35% por contención de Marcus"
                                )
                            ]
                        ),
                        ResultadoPosibleSchema(resultado_id="res_disturbios_populares", peso_base=50.0)
                    ]
                ),
                OpcionEventoSchema(
                    id="op_b",
                    texto="Pactar subsidio temporal con los gremios de panaderos",
                    es_secreta=False,
                    condiciones=[],
                    resultados_posibles=[
                        ResultadoPosibleSchema(
                            resultado_id="res_grano_comprado_justo",
                            peso_base=50.0,
                            modificadores_probabilidad=[
                                ModificadorProbabilidadSchema(
                                    condicion=CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_canciller_elena"),
                                    delta_peso=30.0,
                                    explicacion="+30% por concertación de Elena"
                                )
                            ]
                        ),
                        ResultadoPosibleSchema(resultado_id="res_disturbios_populares", peso_base=50.0)
                    ]
                ),
                OpcionEventoSchema(
                    id="op_c",
                    texto="[Secreto] Repartir sacos de grano de emergencia y saciar a la multitud",
                    es_secreta=True,
                    condiciones=[CondicionSchema(tipo=TipoCondicionEnum.TIENE_TAG, tag="abastecimiento")],
                    resultados_posibles=[ResultadoPosibleSchema(resultado_id="res_cosecha_salvada_decreto", peso_base=100.0)]
                )
            ]
        ),

        # Evento 11: Mina de Plata
        EventoCreateRequest(
            _id="evt_descubrimiento_mina",
            universo_id=UNIVERSO_ID,
            titulo="El Filón de Plata en las Quebradas",
            descripcion="Exploradores descubren una rica veta argentífera en las montañas del norte.",
            imagen="/assets/narrative/events/minas.webp",
            tags_tematicos=["oro", "economia", "riqueza"],
            peso_base=80.0,
            opciones=[
                OpcionEventoSchema(
                    id="op_a",
                    texto="Subastar la concesión de extracción a gremios privados",
                    es_secreta=False,
                    condiciones=[],
                    resultados_posibles=[
                        ResultadoPosibleSchema(
                            resultado_id="res_embajador_satisfecho",
                            peso_base=60.0,
                            modificadores_probabilidad=[
                                ModificadorProbabilidadSchema(
                                    condicion=CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_canciller_elena"),
                                    delta_peso=30.0,
                                    explicacion="+30% por subasta competitiva de Elena"
                                )
                            ]
                        ),
                        ResultadoPosibleSchema(resultado_id="res_estafa_mercaderes", peso_base=40.0)
                    ]
                ),
                OpcionEventoSchema(
                    id="op_b",
                    texto="Militarizar el yacimiento y extraer con batallones de trabajo",
                    es_secreta=False,
                    condiciones=[],
                    resultados_posibles=[
                        ResultadoPosibleSchema(
                            resultado_id="res_victoria_militar_frontera",
                            peso_base=50.0,
                            modificadores_probabilidad=[
                                ModificadorProbabilidadSchema(
                                    condicion=CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_comandante_marcus"),
                                    delta_peso=35.0,
                                    explicacion="+35% por logística militar de Marcus"
                                )
                            ]
                        ),
                        ResultadoPosibleSchema(resultado_id="res_disturbios_populares", peso_base=50.0)
                    ]
                ),
                OpcionEventoSchema(
                    id="op_c",
                    texto="[Secreto] Refinar el mineral con reactivos de lixiviación alquímica",
                    es_secreta=True,
                    condiciones=[CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_alquimista_vera")],
                    resultados_posibles=[ResultadoPosibleSchema(resultado_id="res_oro_minas_masivo", peso_base=100.0)]
                )
            ]
        ),

        # Evento 12: Jubileo
        EventoCreateRequest(
            _id="evt_coronacion_aniversario",
            universo_id=UNIVERSO_ID,
            titulo="El Jubileo Real",
            descripcion="El reino celebra el gran aniversario de la dinastía. Nobles y plebeyos esperan un gran gesto.",
            imagen="/assets/narrative/events/torneo.webp",
            tags_tematicos=["moral", "sociedad", "corona"],
            peso_base=80.0,
            opciones=[
                OpcionEventoSchema(
                    id="op_a",
                    texto="Celebrar un torneo de caballeros y banquetes en las murallas",
                    es_secreta=False,
                    condiciones=[],
                    resultados_posibles=[
                        ResultadoPosibleSchema(
                            resultado_id="res_victoria_militar_frontera",
                            peso_base=60.0,
                            modificadores_probabilidad=[
                                ModificadorProbabilidadSchema(
                                    condicion=CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_comandante_marcus"),
                                    delta_peso=35.0,
                                    explicacion="+35% por pompa marcial de Marcus"
                                )
                            ]
                        ),
                        ResultadoPosibleSchema(resultado_id="res_disturbios_populares", peso_base=40.0)
                    ]
                ),
                OpcionEventoSchema(
                    id="op_b",
                    texto="Gran misa pontifical de acción de gracias en la catedral",
                    es_secreta=False,
                    condiciones=[],
                    resultados_posibles=[
                        ResultadoPosibleSchema(
                            resultado_id="res_bendicion_catedral",
                            peso_base=60.0,
                            modificadores_probabilidad=[
                                ModificadorProbabilidadSchema(
                                    condicion=CondicionSchema(tipo=TipoCondicionEnum.TIENE_PERSONAJE, personaje_id="pj_obispo_tomas"),
                                    delta_peso=35.0,
                                    explicacion="+35% por liturgia de Tomás"
                                )
                            ]
                        ),
                        ResultadoPosibleSchema(resultado_id="res_disturbios_populares", peso_base=40.0)
                    ]
                ),
                OpcionEventoSchema(
                    id="op_c",
                    texto="[Secreto] Emitir edicto de amnistía y condonación bajo el Sello Real",
                    es_secreta=True,
                    condiciones=[CondicionSchema(tipo=TipoCondicionEnum.TIENE_TAG, tag="sello_real")],
                    resultados_posibles=[ResultadoPosibleSchema(resultado_id="res_cosecha_salvada_decreto", peso_base=100.0)]
                )
            ]
        )
    ]

    for e in eventos:
        await crear_o_actualizar_evento(e)

    # 6. CONVERSACIONES DE CORTE (3 diálogos)
    conversaciones = [
        # --- PAREJA 1: ELENA + MARCUS ---
        ConversacionCreateRequest(
            _id="conv_disputa_tesoro_militar",
            universo_id=UNIVERSO_ID,
            titulo="Presupuesto de Campaña",
            requisitos=[
                ConversacionRequisitoSchema(personajeId="pj_canciller_elena"),
                ConversacionRequisitoSchema(personajeId="pj_comandante_marcus")
            ],
            imagen="/assets/narrative/conversations/sala_reuniones.webp",
            frases=[
                ConversacionFraseSchema(personajeId="pj_comandante_marcus", texto="Mis hombres necesitan mejores armaduras y raciones si queremos mantener segura la frontera."),
                ConversacionFraseSchema(personajeId="pj_canciller_elena", texto="Si desviamos más oro a la guarnición, tendremos que subir impuestos a los gremios y asfixiar el comercio.")
            ],
            decisiones=[
                ConversacionDecisionSchema(
                    opcion=1,
                    texto="Respaldar a Elena: cuidar la economía y no sobrecargar arcas",
                    resultado_texto="Marcus aprieta la mandíbula y acata la orden con desagrado.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=15),
                        ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=-15)
                    ]
                ),
                ConversacionDecisionSchema(
                    opcion=2,
                    texto="Respaldar a Marcus: la seguridad de las murallas es prioridad",
                    resultado_texto="Elena toma nota silenciosa, advirtiendo que los balances estarán apretados.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=-15),
                        ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=15)
                    ]
                )
            ]
        ),
        ConversacionCreateRequest(
            _id="conv_patrullas_o_comercio",
            universo_id=UNIVERSO_ID,
            titulo="Peajes y Caravanas Extranjeras",
            requisitos=[
                ConversacionRequisitoSchema(personajeId="pj_canciller_elena"),
                ConversacionRequisitoSchema(personajeId="pj_comandante_marcus")
            ],
            imagen="/assets/narrative/conversations/puerta_ciudad.webp",
            frases=[
                ConversacionFraseSchema(personajeId="pj_comandante_marcus", texto="Propongo registrar a fondo y cobrar peaje a cada caravana que cruce el desfiladero norte para financiar escoltas."),
                ConversacionFraseSchema(personajeId="pj_canciller_elena", texto="Eso espantará a los mercaderes libres. Si la ruta se vuelve lenta y costosa, comerciarán con los reinos vecinos.")
            ],
            decisiones=[
                ConversacionDecisionSchema(
                    opcion=1,
                    texto="Libre tránsito comercial: Priorizar la afluencia de bienes y precios bajos",
                    resultado_texto="Elena sonríe satisfecha; los gremios de comerciantes celebran el decreto real.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=15),
                        ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=-10)
                    ]
                ),
                ConversacionDecisionSchema(
                    opcion=2,
                    texto="Controles estrictos de la guardia: Ninguna carreta entra sin pagar y registrarse",
                    resultado_texto="Marcus redobla las garitas de vigilancia; la frontera es inexpugnable.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=-10),
                        ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=15)
                    ]
                )
            ]
        ),

        # --- PAREJA 2: TOMÁS + VERA ---
        ConversacionCreateRequest(
            _id="conv_herejia_en_laboratorio",
            universo_id=UNIVERSO_ID,
            titulo="Alquimia vs Santa Fe",
            requisitos=[
                ConversacionRequisitoSchema(personajeId="pj_obispo_tomas"),
                ConversacionRequisitoSchema(personajeId="pj_alquimista_vera")
            ],
            imagen="/assets/narrative/conversations/laboratorio.webp",
            frases=[
                ConversacionFraseSchema(personajeId="pj_obispo_tomas", texto="Ese humo sulfúrico que sale de tu torre perturba las oraciones matutinas. Huele a brujería."),
                ConversacionFraseSchema(personajeId="pj_alquimista_vera", texto="Huele a tónico de corteza de sauce, hermano. Gracias a ese humo salvamos a cien niños de la fiebre la semana pasada.")
            ],
            decisiones=[
                ConversacionDecisionSchema(
                    opcion=1,
                    texto="Permitir a Vera continuar con sus investigaciones sin trabas",
                    resultado_texto="Tomás se retira persignándose, murmurando advertencias divinas.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_alquimista_vera", delta=15),
                        ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=-15)
                    ]
                ),
                ConversacionDecisionSchema(
                    opcion=2,
                    texto="Exigir que el clero supervise los remedios y bendiga los preparados",
                    resultado_texto="Vera suspira resignada, guardando sus matraces bajo llave.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_alquimista_vera", delta=-15),
                        ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=15)
                    ]
                )
            ]
        ),
        ConversacionCreateRequest(
            _id="conv_reliquia_o_experimento",
            universo_id=UNIVERSO_ID,
            titulo="El Fragmento del Cometa Sagrado",
            requisitos=[
                ConversacionRequisitoSchema(personajeId="pj_obispo_tomas"),
                ConversacionRequisitoSchema(personajeId="pj_alquimista_vera")
            ],
            imagen="/assets/narrative/conversations/reliquia.webp",
            frases=[
                ConversacionFraseSchema(personajeId="pj_obispo_tomas", texto="Esa piedra caída del cielo debe reposar sobre el altar mayor. Los fieles hallarán consuelo en su brillo celestial."),
                ConversacionFraseSchema(personajeId="pj_alquimista_vera", texto="¡Es un aerolito de propiedades magnéticas únicas! Si pulverizo una pizca, puedo sintetizar aleaciones inoxidables para arados y corazas.")
            ],
            decisiones=[
                ConversacionDecisionSchema(
                    opcion=1,
                    texto="Consagrar el fragmento en la Catedral como milagro divino",
                    resultado_texto="El templo se llena de peregrinos agradecidos. Tomás bendice la corona.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=15),
                        ImpactoAfinidadSchema(personaje_id="pj_alquimista_vera", delta=-15)
                    ]
                ),
                ConversacionDecisionSchema(
                    opcion=2,
                    texto="Entregar el bólido a Vera para investigación metalúrgica",
                    resultado_texto="Vera comienza de inmediato los experimentos en el crisol con brillo en los ojos.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=-15),
                        ImpactoAfinidadSchema(personaje_id="pj_alquimista_vera", delta=15)
                    ]
                )
            ]
        ),

        # --- PAREJA 3: MARCUS + SYLVIA ---
        ConversacionCreateRequest(
            _id="conv_tregua_en_la_sombra",
            universo_id=UNIVERSO_ID,
            titulo="Informes Ocultos",
            requisitos=[
                ConversacionRequisitoSchema(personajeId="pj_comandante_marcus"),
                ConversacionRequisitoSchema(personajeId="pj_ladrona_sylvia")
            ],
            imagen="/assets/narrative/conversations/callejon.webp",
            frases=[
                ConversacionFraseSchema(personajeId="pj_ladrona_sylvia", texto="Tus patrullas hacen demasiado ruido. Asustan a los contrabandistas que me pasan los informes."),
                ConversacionFraseSchema(personajeId="pj_comandante_marcus", texto="Mis patrullas hacen su trabajo, Sylvia. Si tus informantes son honrados, no deberían temer a la ley.")
            ],
            decisiones=[
                ConversacionDecisionSchema(
                    opcion=1,
                    texto="Dar libertad a Sylvia para coordinar sus informantes",
                    resultado_texto="Sylvia sonríe complacida y desaparece en la penumbra.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_ladrona_sylvia", delta=15),
                        ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=-10)
                    ]
                ),
                ConversacionDecisionSchema(
                    opcion=2,
                    texto="Priorizar la presencia visible de la guardia en las calles",
                    resultado_texto="Marcus asiente con orgullo militar mientras Sylvia frunce el ceño.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_ladrona_sylvia", delta=-15),
                        ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=15)
                    ]
                )
            ]
        ),
        ConversacionCreateRequest(
            _id="conv_sabotaje_o_asalto",
            universo_id=UNIVERSO_ID,
            titulo="La Guarida de los Asaltantes",
            requisitos=[
                ConversacionRequisitoSchema(personajeId="pj_comandante_marcus"),
                ConversacionRequisitoSchema(personajeId="pj_ladrona_sylvia")
            ],
            imagen="/assets/narrative/conversations/emboscada.webp",
            frases=[
                ConversacionFraseSchema(personajeId="pj_comandante_marcus", texto="Reuniré tres escuadras de caballería pesada y arrasaremos el campamento bandido al alba."),
                ConversacionFraseSchema(personajeId="pj_ladrona_sylvia", texto="Tienen trampas de estacas en el camino. Déjame enviar dos hombres a quemar sus provisiones y abrir las jaulas desde adentro.")
            ],
            decisiones=[
                ConversacionDecisionSchema(
                    opcion=1,
                    texto="Aprobar el sabotaje encubierto de Sylvia",
                    resultado_texto="El campamento cae sin una sola baja en la guardia, desmoralizado y disperso.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_ladrona_sylvia", delta=15),
                        ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=-10)
                    ]
                ),
                ConversacionDecisionSchema(
                    opcion=2,
                    texto="Ordenar la carga frontal honorable de Marcus",
                    resultado_texto="Los clarines suenan y la guardia destruye el nido bandido con fuerza imponente.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_ladrona_sylvia", delta=-10),
                        ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=15)
                    ]
                )
            ]
        ),

        # --- PAREJA 4: ELENA + VERA ---
        ConversacionCreateRequest(
            _id="conv_financiamiento_botanico",
            universo_id=UNIVERSO_ID,
            titulo="El Jardín de Boticarios Reales",
            requisitos=[
                ConversacionRequisitoSchema(personajeId="pj_canciller_elena"),
                ConversacionRequisitoSchema(personajeId="pj_alquimista_vera")
            ],
            imagen="/assets/narrative/conversations/jardin.webp",
            frases=[
                ConversacionFraseSchema(personajeId="pj_alquimista_vera", texto="Canciller, necesito acondicionar invernaderos con calefacción de carbón para cultivar raíces curativas en invierno."),
                ConversacionFraseSchema(personajeId="pj_canciller_elena", texto="Ese proyecto costaría casi una mensualidad entera del erario. Las arcas deben guardar reservas para imprevistos.")
            ],
            decisiones=[
                ConversacionDecisionSchema(
                    opcion=1,
                    texto="Financiar los invernaderos de Vera como inversión en salud del reino",
                    resultado_texto="Vera comienza de inmediato la siembra; la corte olerá a menta y alcanfor.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_alquimista_vera", delta=15),
                        ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=-10)
                    ]
                ),
                ConversacionDecisionSchema(
                    opcion=2,
                    texto="Congelar los fondos y exigir autofinanciación vendiendo tónicos",
                    resultado_texto="Elena salvaguarda el presupuesto; Vera debe limitar sus experimentos a pequeña escala.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_alquimista_vera", delta=-15),
                        ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=15)
                    ]
                )
            ]
        ),
        ConversacionCreateRequest(
            _id="conv_monopolio_medicinas",
            universo_id=UNIVERSO_ID,
            titulo="Distribución de Ungüentos Reales",
            requisitos=[
                ConversacionRequisitoSchema(personajeId="pj_canciller_elena"),
                ConversacionRequisitoSchema(personajeId="pj_alquimista_vera")
            ],
            imagen="/assets/narrative/conversations/botica.webp",
            frases=[
                ConversacionFraseSchema(personajeId="pj_canciller_elena", texto="Si patentamos tus ungüentos febrífugos a través del gremio de boticarios, obtendremos cuantiosos aranceles comerciales."),
                ConversacionFraseSchema(personajeId="pj_alquimista_vera", texto="¡No son artículos de lujo! Si los gremios fijan el precio, los campesinos pobres volverán a morir de neumonía.")
            ],
            decisiones=[
                ConversacionDecisionSchema(
                    opcion=1,
                    texto="Distribuir los remedios al costo o gratis en plazas públicas",
                    resultado_texto="El pueblo bendice la generosidad de Vera y la corona.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_alquimista_vera", delta=15),
                        ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=-10)
                    ]
                ),
                ConversacionDecisionSchema(
                    opcion=2,
                    texto="Comercializarlos bajo monopolio real para enriquecer el tesoro",
                    resultado_texto="Las arcas recaudan oro rápidamente gracias al lucrativo negocio.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_alquimista_vera", delta=-15),
                        ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=15)
                    ]
                )
            ]
        ),

        # --- PAREJA 5: ELENA + SYLVIA ---
        ConversacionCreateRequest(
            _id="conv_libros_paralelos_sylvia",
            universo_id=UNIVERSO_ID,
            titulo="Libros de Contabilidad Paralelos",
            requisitos=[
                ConversacionRequisitoSchema(personajeId="pj_canciller_elena"),
                ConversacionRequisitoSchema(personajeId="pj_ladrona_sylvia")
            ],
            imagen="/assets/narrative/conversations/despacho.webp",
            frases=[
                ConversacionFraseSchema(personajeId="pj_ladrona_sylvia", texto="Tengo pruebas de que tres barones desvían el impuesto a la lana. Podemos chantajearlos discretamente para triplicar los aportes a la corona."),
                ConversacionFraseSchema(personajeId="pj_canciller_elena", texto="El chantaje socava la autoridad legal. Debemos citarlos ante la corte de justicia y confiscar sus bienes según la ley.")
            ],
            decisiones=[
                ConversacionDecisionSchema(
                    opcion=1,
                    texto="Usar la información en las sombras: chantaje encubierto a los nobles",
                    resultado_texto="Los barones pagan sumas cuantiosas en secreto para no ser deshonrados.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_ladrona_sylvia", delta=15),
                        ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=-10)
                    ]
                ),
                ConversacionDecisionSchema(
                    opcion=2,
                    texto="Llevarlos a juicio público y auditoría oficial transparente",
                    resultado_texto="Elena defiende la majestad de la ley con un proceso ejemplar.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_ladrona_sylvia", delta=-10),
                        ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=15)
                    ]
                )
            ]
        ),
        ConversacionCreateRequest(
            _id="conv_aranceles_puerto_negro",
            universo_id=UNIVERSO_ID,
            titulo="El Muelle Clandestino de la Ría",
            requisitos=[
                ConversacionRequisitoSchema(personajeId="pj_canciller_elena"),
                ConversacionRequisitoSchema(personajeId="pj_ladrona_sylvia")
            ],
            imagen="/assets/narrative/conversations/puerto.webp",
            frases=[
                ConversacionFraseSchema(personajeId="pj_canciller_elena", texto="Debemos enviar alguaciles a cerrar las calas secretas donde atracan barcos sin sellos de aduana."),
                ConversacionFraseSchema(personajeId="pj_ladrona_sylvia", texto="Esos contrabandistas me avisan con dos semanas de antelación si flotas corsarias se aproximan. Déjalos operar.")
            ],
            decisiones=[
                ConversacionDecisionSchema(
                    opcion=1,
                    texto="Tolerar el muelle a cambio de espionaje marítimo vital",
                    resultado_texto="Sylvia mantiene activa su red de alerta costera con éxito.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_ladrona_sylvia", delta=15),
                        ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=-15)
                    ]
                ),
                ConversacionDecisionSchema(
                    opcion=2,
                    texto="Clausurar los fondeaderos y exigir aduanas oficiales",
                    resultado_texto="Elena sella el puerto y recauda los impuestos adeudados.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_ladrona_sylvia", delta=-15),
                        ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=15)
                    ]
                )
            ]
        ),

        # --- PAREJA 6: ELENA + TOMÁS ---
        ConversacionCreateRequest(
            _id="conv_diezmo_eclesiastico_elena",
            universo_id=UNIVERSO_ID,
            titulo="Tierras Exentas de la Iglesia",
            requisitos=[
                ConversacionRequisitoSchema(personajeId="pj_canciller_elena"),
                ConversacionRequisitoSchema(personajeId="pj_obispo_tomas")
            ],
            imagen="/assets/narrative/conversations/catedral.webp",
            frases=[
                ConversacionFraseSchema(personajeId="pj_obispo_tomas", texto="Las abadías del sur reclaman la confirmación de su bula: cero impuestos reales sobre sus viñedos y olivares."),
                ConversacionFraseSchema(personajeId="pj_canciller_elena", texto="Son las tierras más fértiles del reino. Si no pagan una contribución de guerra, arruinaremos a los demás vasallos.")
            ],
            decisiones=[
                ConversacionDecisionSchema(
                    opcion=1,
                    texto="Respetar la exención religiosa en honor a las bendiciones celestiales",
                    resultado_texto="Tomás elogia la piedad de la corte en la misa mayor del domingo.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=15),
                        ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=-15)
                    ]
                ),
                ConversacionDecisionSchema(
                    opcion=2,
                    texto="Gravar las rentas monásticas para financiar el puente real",
                    resultado_texto="Elena asegura los fondos necesarios para las obras civiles.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=-15),
                        ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=15)
                    ]
                )
            ]
        ),

        # --- PAREJA 7: MARCUS + VERA ---
        ConversacionCreateRequest(
            _id="conv_unguentos_de_guerra",
            universo_id=UNIVERSO_ID,
            titulo="El Bálsamo de Resistencia",
            requisitos=[
                ConversacionRequisitoSchema(personajeId="pj_comandante_marcus"),
                ConversacionRequisitoSchema(personajeId="pj_alquimista_vera")
            ],
            imagen="/assets/narrative/conversations/campamento.webp",
            frases=[
                ConversacionFraseSchema(personajeId="pj_alquimista_vera", texto="He preparado una infusión de ginseng y raíces amargas que permite marchar 24 horas sin descanso ni fatiga."),
                ConversacionFraseSchema(personajeId="pj_comandante_marcus", texto="La resistencia de un soldado nace de la disciplina y el entrenamiento, no de pociones extrañas con efectos desconocidos.")
            ],
            decisiones=[
                ConversacionDecisionSchema(
                    opcion=1,
                    texto="Suministrar el brebaje a los centinelas y destacamentos de frontera",
                    resultado_texto="Las patrullas cubren el doble de territorio sin mostrar agotamiento.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_alquimista_vera", delta=15),
                        ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=-10)
                    ]
                ),
                ConversacionDecisionSchema(
                    opcion=2,
                    texto="Prohibir las sustancias y mantener el régimen militar tradicional",
                    resultado_texto="Marcus asiente; la tropa confía en su temple y entrenamiento de hierro.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_alquimista_vera", delta=-10),
                        ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=15)
                    ]
                )
            ]
        ),
        ConversacionCreateRequest(
            _id="conv_fuego_alquimico_defensa",
            universo_id=UNIVERSO_ID,
            titulo="Fuego Griego en las Almenas",
            requisitos=[
                ConversacionRequisitoSchema(personajeId="pj_comandante_marcus"),
                ConversacionRequisitoSchema(personajeId="pj_alquimista_vera")
            ],
            imagen="/assets/narrative/conversations/torre_vigia.webp",
            frases=[
                ConversacionFraseSchema(personajeId="pj_alquimista_vera", texto="Podemos instalar calderas de brea destilada en las puertas de la muralla. Arderá incluso sobre el agua de los fosos."),
                ConversacionFraseSchema(personajeId="pj_comandante_marcus", texto="Un solo chispazo accidental en el polvorín o un viento en contra incendiaría nuestras propias almenas.")
            ],
            decisiones=[
                ConversacionDecisionSchema(
                    opcion=1,
                    texto="Aprobar las calderas alquímicas defensivas",
                    resultado_texto="Las fortificaciones se convierten en una pesadilla flameante para cualquier asediador.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_alquimista_vera", delta=15),
                        ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=-10)
                    ]
                ),
                ConversacionDecisionSchema(
                    opcion=2,
                    texto="Rechazar el fuego inestable y apostar por arqueros veteranos",
                    resultado_texto="Marcus organiza líneas de tiro limpias y seguras sin riesgo de incendio.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_alquimista_vera", delta=-10),
                        ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=15)
                    ]
                )
            ]
        ),

        # --- PAREJA 8: MARCUS + TOMÁS ---
        ConversacionCreateRequest(
            _id="conv_asilo_en_el_templo",
            universo_id=UNIVERSO_ID,
            titulo="El Derecho Sagrado de Asilo",
            requisitos=[
                ConversacionRequisitoSchema(personajeId="pj_comandante_marcus"),
                ConversacionRequisitoSchema(personajeId="pj_obispo_tomas")
            ],
            imagen="/assets/narrative/conversations/templo_altar.webp",
            frases=[
                ConversacionFraseSchema(personajeId="pj_comandante_marcus", texto="Un sargento acusado de traición y robo de armas huyó y se aferró al altar de la catedral. Debo arrestarlo ya."),
                ConversacionFraseSchema(personajeId="pj_obispo_tomas", texto="Quien toca el ara sagrada goza de la protección del Altísimo. Si tus botas armadas cruzan el presbiterio, profanarás la casa de Dios.")
            ],
            decisiones=[
                ConversacionDecisionSchema(
                    opcion=1,
                    texto="Respetar el asilo eclesiástico y permitir que el reo expíe sus culpas con votos",
                    resultado_texto="Tomás elogia el temor de Dios en el corazón de la corona.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=15),
                        ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=-15)
                    ]
                ),
                ConversacionDecisionSchema(
                    opcion=2,
                    texto="Ingresar a la fuerza y ejecutar la justicia militar",
                    resultado_texto="Marcus apresa al criminal; Tomás declara una jornada de luto clerical.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=-15),
                        ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=15)
                    ]
                )
            ]
        ),

        # --- PAREJA 9: SYLVIA + VERA ---
        ConversacionCreateRequest(
            _id="conv_veneno_o_antidoto",
            universo_id=UNIVERSO_ID,
            titulo="La Esencia Silenciosa",
            requisitos=[
                ConversacionRequisitoSchema(personajeId="pj_ladrona_sylvia"),
                ConversacionRequisitoSchema(personajeId="pj_alquimista_vera")
            ],
            imagen="/assets/narrative/conversations/laboratorio.webp",
            frases=[
                ConversacionFraseSchema(personajeId="pj_ladrona_sylvia", texto="Vera, un veneno inodoro que simule un síncope cardíaco nos ahorraría una guerra civil contra el duque rebelde."),
                ConversacionFraseSchema(personajeId="pj_alquimista_vera", texto="Hice un juramento botánico de preservar la vida, no de diseñar instrumentos de asesinato político.")
            ],
            decisiones=[
                ConversacionDecisionSchema(
                    opcion=1,
                    texto="Obligar a Vera a preparar la sustancia por la razón de Estado",
                    resultado_texto="Sylvia recibe el vial mortal; Vera trabaja con amargura y distancia.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_ladrona_sylvia", delta=15),
                        ImpactoAfinidadSchema(personaje_id="pj_alquimista_vera", delta=-20)
                    ]
                ),
                ConversacionDecisionSchema(
                    opcion=2,
                    texto="Respaldar la ética científica de Vera y rechazar el veneno",
                    resultado_texto="Vera agradece la protección real a la dignidad de la ciencia.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_ladrona_sylvia", delta=-15),
                        ImpactoAfinidadSchema(personaje_id="pj_alquimista_vera", delta=15)
                    ]
                )
            ]
        ),

        # --- PAREJA 10: SYLVIA + TOMÁS ---
        ConversacionCreateRequest(
            _id="conv_secretos_de_confesionario",
            universo_id=UNIVERSO_ID,
            titulo="Secreto de Confesión",
            requisitos=[
                ConversacionRequisitoSchema(personajeId="pj_ladrona_sylvia"),
                ConversacionRequisitoSchema(personajeId="pj_obispo_tomas")
            ],
            imagen="/assets/narrative/conversations/confesionario.webp",
            frases=[
                ConversacionFraseSchema(personajeId="pj_ladrona_sylvia", texto="Hermano Tomás, el cabecilla de la conjura se confesó con vos antes de ayer. Decidme su nombre y salvaremos vidas inocentes."),
                ConversacionFraseSchema(personajeId="pj_obispo_tomas", texto="El sigilo sacramental es inviolable. Si revelo una sola palabra dicha bajo penitencia, condenaría mi alma al fuego eterno.")
            ],
            decisiones=[
                ConversacionDecisionSchema(
                    opcion=1,
                    texto="Respetar la santidad del secreto de confesión",
                    resultado_texto="Tomás ora con gratitud; la Iglesia elogia la moralidad del monarca.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=15),
                        ImpactoAfinidadSchema(personaje_id="pj_ladrona_sylvia", delta=-15)
                    ]
                ),
                ConversacionDecisionSchema(
                    opcion=2,
                    texto="Exigir colaboración inmediata en nombre de la supervivencia del reino",
                    resultado_texto="Tomás murmura una pista sutil atormentado por su conciencia; Sylvia actúa de inmediato.",
                    impacto_afinidad=[
                        ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=-15),
                        ImpactoAfinidadSchema(personaje_id="pj_ladrona_sylvia", delta=15)
                    ]
                )
            ]
        )
    ]
    for conv in conversaciones:
        await crear_o_actualizar_conversacion(conv)

    # 7. GENERAR EL MES ACTUAL EN daily_challenges
    ahora = datetime.now()
    res_mes = await generar_mes_narrativo(year=ahora.year, month=ahora.month, universo_id=UNIVERSO_ID)
    logger.info(f"[NARRATIVE SEED] Desafíos generados para {ahora.year}-{ahora.month:02d}: {res_mes['desafios_creados']} días listos.")

    logger.info("[NARRATIVE SEED] ¡Siembra de contenido completada exitosamente!")

if __name__ == "__main__":
    async def main():
        await connect_to_mongo()
        await seed_narrative_game()
    asyncio.run(main())
