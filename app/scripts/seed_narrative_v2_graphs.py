"""
seed_narrative_v2_graphs.py
Script de siembra inicial para el Motor Narrativo V2 (Grafos de Decisión).
Siembra:
1. narrative_v2_events: Eventos ramificados con soporte para arcos narrativos (requisitos_eventos_previos).
2. narrative_v2_conversations: Diálogos ramificados con requisitos de corte activa.
No modifica ni sobreescribe las colecciones V1 en producción.
"""

import asyncio
import logging
from app.core.database import get_database, connect_to_mongo
from app.features.narrative.constants import (
    COLL_V2_EVENTS,
    COLL_V2_CONVERSATIONS,
    COLL_V2_EVENTOS_ESPECIALES
)
from app.features.narrative.schemas.v2_graph_schemas import (
    EventoV2GrafoSchema,
    ConversacionV2GrafoSchema,
    EventoEspecialV2GrafoSchema,
    NodoNarrativoSchema,
    OpcionNodoSchema,
    ImpactoRecursoSchema,
    ImpactoAfinidadSchema
)
from app.features.narrative.enums import DireccionEventoEspecialEnum

logger = logging.getLogger(__name__)

async def seed_v2_graphs():
    db = get_database()
    logger.info("[NARRATIVE V2 SEED] Sembrando colecciones de grafos V2...")

    # ========================================================================
    # 1. EVENTO 1 (ARCO PARTE 1): El Cometa de la Frontera (Base)
    # ========================================================================
    evento_cometa = EventoV2GrafoSchema(
        _id="evt_cometa_caido_v2",
        universo_id="corte_medieval",
        titulo="El Cometa de la Frontera",
        imagen="/assets/narrative/eventos/default.webp",
        requisitos_eventos_previos=[],
        nodo_raiz="nodo_avistamiento",
        nodos={
            "nodo_avistamiento": NodoNarrativoSchema(
                id="nodo_avistamiento",
                hablante_id="narrador",
                texto="Una bola de fuego celestial surca el cielo nocturno y se estrella en los bosques del norte. Los campesinos claman que es una señal divina.",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(
                        id="opt_enviar_guardia",
                        texto="Enviar a la guardia a acordonar la zona del cráter",
                        siguiente_nodo="nodo_represion_crater"
                    ),
                    OpcionNodoSchema(
                        id="opt_enviar_alquimista",
                        texto="Enviar a Vera la Alquimista a recolectar muestras del mineral",
                        siguiente_nodo="nodo_analisis_alquimico"
                    )
                ]
            ),
            "nodo_represion_crater": NodoNarrativoSchema(
                id="nodo_represion_crater",
                hablante_id="pj_comandante_marcus",
                texto="Marcus informa: 'La milicia ha cercado el bosque. Sin embargo, fanáticos religiosos intentan cruzar el perímetro para adorar la roca estelar'.",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(
                        id="opt_mano_dura",
                        texto="Detener a los fanáticos y confiscar el mineral para armaduras",
                        siguiente_nodo="cierre_militar_cometa"
                    ),
                    OpcionNodoSchema(
                        id="opt_permitir_oracion",
                        texto="Permitir peregrinaciones pacíficas custodiadas por soldados",
                        siguiente_nodo="cierre_fe_cometa"
                    )
                ]
            ),
            "nodo_analisis_alquimico": NodoNarrativoSchema(
                id="nodo_analisis_alquimico",
                hablante_id="pj_alquimista_vera",
                texto="Vera regresa fascinada: 'Majestad, la roca emite un calor perpetuo. Podríamos usarla para fundir metales raros o purificar agua, pero el clero lo considera brujería'.",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(
                        id="opt_financiar_laboratorio",
                        texto="Financiar el laboratorio secreto de Vera con 15 de oro",
                        siguiente_nodo="cierre_ciencia_cometa"
                    ),
                    OpcionNodoSchema(
                        id="opt_donar_a_catedral",
                        texto="Entregar la roca a la catedral para apaciguar a la iglesia",
                        siguiente_nodo="cierre_fe_cometa"
                    )
                ]
            ),
            "cierre_militar_cometa": NodoNarrativoSchema(
                id="cierre_militar_cometa",
                hablante_id="narrador",
                texto="El ejército forja proyectiles con el metal celeste. La fuerza militar aumenta, pero el descontento de los fieles se hace sentir en las calles.",
                es_final=True,
                resultado_texto="El mineral celeste fortaleció las armas del reino (+15 Ejército, -10 Fe).",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="ejercito", delta=15),
                    ImpactoRecursoSchema(recurso="fe", delta=-10)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=10),
                    ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=-15)
                ]
            ),
            "cierre_ciencia_cometa": NodoNarrativoSchema(
                id="cierre_ciencia_cometa",
                hablante_id="narrador",
                texto="Vera destila esencias alquímicas puras. El pueblo recibe tónicos milagrosos, pero las arcas reales asumieron el costo.",
                es_final=True,
                resultado_texto="El progreso científico trajo bienestar popular (-15 Oro, +20 Pueblo).",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="oro", delta=-15),
                    ImpactoRecursoSchema(recurso="pueblo", delta=20)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_alquimista_vera", delta=15),
                    ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=-10)
                ]
            ),
            "cierre_fe_cometa": NodoNarrativoSchema(
                id="cierre_fe_cometa",
                hablante_id="narrador",
                texto="El Hermano Tomás bendice la reliquia en el altar mayor. Una ola de fervor religioso apacigua los temores de los campesinos.",
                es_final=True,
                resultado_texto="La bendición de la reliquia celestial encendió la fe del reino (+20 Fe, +5 Pueblo).",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="fe", delta=20),
                    ImpactoRecursoSchema(recurso="pueblo", delta=5)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=15),
                    ImpactoAfinidadSchema(personaje_id="pj_alquimista_vera", delta=-10)
                ]
            )
        }
    )

    # ========================================================================
    # 2. EVENTO 2 (ARCO PARTE 2): La Secta del Cometa (Requiere Evento 1)
    # ========================================================================
    evento_secta = EventoV2GrafoSchema(
        _id="evt_secta_cometa_v2",
        universo_id="corte_medieval",
        titulo="La Secta de la Estrella Caída",
        imagen="/assets/narrative/eventos/default.webp",
        requisitos_eventos_previos=["evt_cometa_caido_v2"],
        nodo_raiz="inicio_secta",
        nodos={
            "inicio_secta": NodoNarrativoSchema(
                id="inicio_secta",
                hablante_id="narrador",
                texto="Meses después del impacto del cometa, un predicador encapuchado reúne a miles de devotos afirmando que el Rey ya no cuenta con la gracia de los cielos.",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(
                        id="opt_negociar_secta",
                        texto="Enviar a la Canciller Elena a negociar con los cabecillas",
                        siguiente_nodo="rama_negociacion_secta"
                    ),
                    OpcionNodoSchema(
                        id="opt_infiltrar_secta",
                        texto="Ordenar a Sylvia Niebla infiltrar a sus espías en el culto",
                        siguiente_nodo="rama_espionaje_secta"
                    )
                ]
            ),
            "rama_negociacion_secta": NodoNarrativoSchema(
                id="rama_negociacion_secta",
                hablante_id="pj_canciller_elena",
                texto="Elena regresa con el pliego de demandas: 'Piden exención de impuestos para sus aldeas y el reconocimiento formal de su templo'.",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(
                        id="opt_conceder_exencion",
                        texto="Conceder la exención tributaria a cambio de paz social",
                        siguiente_nodo="cierre_paz_secta"
                    ),
                    OpcionNodoSchema(
                        id="opt_rechazar_demandas",
                        texto="Rechazar las demandas y dispersar a la multitud con la guardia",
                        siguiente_nodo="cierre_represion_secta"
                    )
                ]
            ),
            "rama_espionaje_secta": NodoNarrativoSchema(
                id="rama_espionaje_secta",
                hablante_id="pj_ladrona_sylvia",
                texto="Sylvia susurra en la penumbra: 'Descubrí que el profeta es un impostor a sueldo de un barón rebelde. Tengo pruebas de sus sobornos'.",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(
                        id="opt_exhibir_pruebas",
                        texto="Publicar las cartas incriminatorias en la plaza mayor",
                        siguiente_nodo="cierre_desenmascarar_secta"
                    ),
                    OpcionNodoSchema(
                        id="opt_asesinato_silencioso",
                        texto="Eliminar al falso profeta en las sombras sin juicio",
                        siguiente_nodo="cierre_asesinato_secta"
                    )
                ]
            ),
            "cierre_paz_secta": NodoNarrativoSchema(
                id="cierre_paz_secta",
                hablante_id="narrador",
                texto="El culto se calma y bendice al monarca, pero las arcas reales pierden una porción considerable de la recaudación.",
                es_final=True,
                resultado_texto="Se evitó el derramamiento de sangre mediante concesiones (-20 Oro, +15 Pueblo, +10 Fe).",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="oro", delta=-20),
                    ImpactoRecursoSchema(recurso="pueblo", delta=15),
                    ImpactoRecursoSchema(recurso="fe", delta=10)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=10),
                    ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=-15)
                ]
            ),
            "cierre_represion_secta": NodoNarrativoSchema(
                id="cierre_represion_secta",
                hablante_id="narrador",
                texto="La guardia disuelve la manifestación con violencia. El orden se restablece, pero la ira popular hierve bajo la superficie.",
                es_final=True,
                resultado_texto="El orden se mantuvo a punta de espada (+10 Ejército, -25 Pueblo, -10 Fe).",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="ejercito", delta=10),
                    ImpactoRecursoSchema(recurso="pueblo", delta=-25),
                    ImpactoRecursoSchema(recurso="fe", delta=-10)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=15),
                    ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=-10)
                ]
            ),
            "cierre_desenmascarar_secta": NodoNarrativoSchema(
                id="cierre_desenmascarar_secta",
                hablante_id="narrador",
                texto="Las pruebas expuestas desbaratan el engaño. El pueblo abuchea al farsante y aclama la astucia de la corona.",
                es_final=True,
                resultado_texto="La conspiración quedó al descubierto (+25 Pueblo, +15 Fe, +10 Oro).",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="pueblo", delta=25),
                    ImpactoRecursoSchema(recurso="fe", delta=15),
                    ImpactoRecursoSchema(recurso="oro", delta=10)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_ladrona_sylvia", delta=20),
                    ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=10)
                ]
            ),
            "cierre_asesinato_secta": NodoNarrativoSchema(
                id="cierre_asesinato_secta",
                hablante_id="narrador",
                texto="El cabecilla amanece sin vida en su celda. Los seguidores se dispersan aterrorizados, murmurando sobre la mano negra del rey.",
                es_final=True,
                resultado_texto="El peligro fue neutralizado en silencio (+10 Ejército, -15 Fe).",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="ejercito", delta=10),
                    ImpactoRecursoSchema(recurso="fe", delta=-15)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_ladrona_sylvia", delta=15),
                    ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=-20)
                ]
            )
        }
    )

    # ========================================================================
    # 3. EVENTO 3: La Peste de las Marismas
    # ========================================================================
    evento_peste = EventoV2GrafoSchema(
        _id="evt_peste_marismas_v2",
        universo_id="corte_medieval",
        titulo="La Peste de las Marismas",
        imagen="/assets/narrative/eventos/default.webp",
        tags_tematicos=["salud", "ciencia", "fe"],
        requisitos_eventos_previos=[],
        nodo_raiz="brote_marismas",
        nodos={
            "brote_marismas": NodoNarrativoSchema(
                id="brote_marismas",
                hablante_id="narrador",
                texto="Una fiebre pútrida brota en las aldeas del sur y se propaga por las rutas de comercio. Los vecinos entierran a sus muertos y claman pidiendo auxilio al trono.",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(
                        id="opt_vera_remedios",
                        texto="Ordenar a Vera la Erudita preparar un remedio a gran escala",
                        siguiente_nodo="cierre_remedio_vera"
                    ),
                    OpcionNodoSchema(
                        id="opt_tomas_procesion",
                        texto="Convocar a Tomás para una procesión de penitencia y purificación",
                        siguiente_nodo="cierre_procesion_fe"
                    ),
                    OpcionNodoSchema(
                        id="opt_quemar_barrios",
                        texto="Ordenar a Marcus quemar los barrios infectados para contener la plaga",
                        siguiente_nodo="cierre_quema_militar"
                    )
                ]
            ),
            "cierre_remedio_vera": NodoNarrativoSchema(
                id="cierre_remedio_vera",
                hablante_id="narrador",
                texto="Vera destila un tónico a base de hierbas y vinagres. La epidemia cede en semanas, aunque la compra de insumos vació una parte de las arcas.",
                es_final=True,
                resultado_texto="La ciencia contuvo la peste a costa del tesoro real (-15 Oro, +20 Pueblo).",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="oro", delta=-15),
                    ImpactoRecursoSchema(recurso="pueblo", delta=20)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_alquimista_vera", delta=15),
                    ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=-10)
                ]
            ),
            "cierre_procesion_fe": NodoNarrativoSchema(
                id="cierre_procesion_fe",
                hablante_id="narrador",
                texto="El Hermano Tomás guía a los fieles en una vigilia de oración. La fe renovada apacigua el pánico y las aldeas vuelven a abrir sus puertas.",
                es_final=True,
                resultado_texto="La devoción calmó los ánimos y alivió a los enfermos (+20 Fe, +5 Pueblo).",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="fe", delta=20),
                    ImpactoRecursoSchema(recurso="pueblo", delta=5)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=15),
                    ImpactoAfinidadSchema(personaje_id="pj_alquimista_vera", delta=-10)
                ]
            ),
            "cierre_quema_militar": NodoNarrativoSchema(
                id="cierre_quema_militar",
                hablante_id="narrador",
                texto="La guardia aísla y prende fuego a los arrabales contaminados. La plaga se detiene, pero el humo deja un amargo rencor entre los sobrevivientes.",
                es_final=True,
                resultado_texto="La contención militar fue eficaz pero brutal (+10 Ejército, -25 Pueblo, -10 Fe).",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="ejercito", delta=10),
                    ImpactoRecursoSchema(recurso="pueblo", delta=-25),
                    ImpactoRecursoSchema(recurso="fe", delta=-10)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=15),
                    ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=-15)
                ]
            )
        }
    )

    # ========================================================================
    # 4. EVENTO 4: El Embargo de los Gremios
    # ========================================================================
    evento_embargo = EventoV2GrafoSchema(
        _id="evt_embargo_gremios_v2",
        universo_id="corte_medieval",
        titulo="El Embargo de los Gremios",
        imagen="/assets/narrative/eventos/default.webp",
        tags_tematicos=["comercio", "diplomacia", "noble"],
        requisitos_eventos_previos=[],
        nodo_raiz="ultimatum_gremios",
        nodos={
            "ultimatum_gremios": NodoNarrativoSchema(
                id="ultimatum_gremios",
                hablante_id="narrador",
                texto="Los gremios de mercaderes amenazan con detener las caravanas si no se rebajan los nuevos aranceles reales. Las plazas comienzan a quedarse sin pan ni telas.",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(
                        id="opt_negociar_elena",
                        texto="Enviar a la Canciller Elena a renegociar los aranceles",
                        siguiente_nodo="cierre_reduccion_impuestos"
                    ),
                    OpcionNodoSchema(
                        id="opt_confiscar_marcus",
                        texto="Ordenar a Marcus confiscar los almacenes de los gremios",
                        siguiente_nodo="cierre_confiscacion"
                    ),
                    OpcionNodoSchema(
                        id="opt_concesion_parcial",
                        texto="Conceder una rebaja parcial para calmar a los comerciantes",
                        siguiente_nodo="cierre_pacto_comercial"
                    )
                ]
            ),
            "cierre_reduccion_impuestos": NodoNarrativoSchema(
                id="cierre_reduccion_impuestos",
                hablante_id="narrador",
                texto="Elena firma un acuerdo que elimina los aranceles más gravosos. El comercio fluye de nuevo, pero la recaudación del reino se resiente.",
                es_final=True,
                resultado_texto="La diplomacia restauró el comercio a costa del fisco (-20 Oro, +15 Pueblo).",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="oro", delta=-20),
                    ImpactoRecursoSchema(recurso="pueblo", delta=15)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=15),
                    ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=-10)
                ]
            ),
            "cierre_confiscacion": NodoNarrativoSchema(
                id="cierre_confiscacion",
                hablante_id="narrador",
                texto="La guardia irrumpe en los almacenes y reparte las mercancías entre la nobleza. Las arcas se llenan, pero los mercaderes juran venganza.",
                es_final=True,
                resultado_texto="La confiscación engrosó el tesoro pero enemistó al pueblo (+20 Oro, -25 Pueblo, +5 Ejército).",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="oro", delta=20),
                    ImpactoRecursoSchema(recurso="pueblo", delta=-25),
                    ImpactoRecursoSchema(recurso="ejercito", delta=5)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=15),
                    ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=-15)
                ]
            ),
            "cierre_pacto_comercial": NodoNarrativoSchema(
                id="cierre_pacto_comercial",
                hablante_id="narrador",
                texto="El acuerdo a medias aplaca a los gremios sin desangrar la tesorería. Las caravanas reanudan su marcha bajo un clima de mutua desconfianza.",
                es_final=True,
                resultado_texto="La negociación moderada preservó el equilibrio (-10 Oro, +10 Pueblo).",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="oro", delta=-10),
                    ImpactoRecursoSchema(recurso="pueblo", delta=10)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=10),
                    ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=5)
                ]
            )
        }
    )

    # ========================================================================
    # 5. EVENTO 5: El Motín de la Guarnición Norte
    # ========================================================================
    evento_motin = EventoV2GrafoSchema(
        _id="evt_motin_guarnicion_v2",
        universo_id="corte_medieval",
        titulo="El Motín de la Guarnición Norte",
        imagen="/assets/narrative/eventos/default.webp",
        tags_tematicos=["militar", "orden", "combate"],
        requisitos_eventos_previos=[],
        nodo_raiz="motin_norte",
        nodos={
            "motin_norte": NodoNarrativoSchema(
                id="motin_norte",
                hablante_id="narrador",
                texto="La guarnición del norte, sin paga desde hace tres lunas, ha tomado las murallas y exige el pago de sus soldadas so pena de abrir las puertas a los invasores.",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(
                        id="opt_pagar_soldada",
                        texto="Abrir las arcas y pagar a los soldados amotinados",
                        siguiente_nodo="cierre_paga"
                    ),
                    OpcionNodoSchema(
                        id="opt_sofocar_marcus",
                        texto="Enviar a Marcus a sofocar el motín por la fuerza",
                        siguiente_nodo="cierre_represion"
                    ),
                    OpcionNodoSchema(
                        id="opt_licenciar",
                        texto="Licenciar a los cabecillas y disolver la guarnición",
                        siguiente_nodo="cierre_licenciamiento"
                    )
                ]
            ),
            "cierre_paga": NodoNarrativoSchema(
                id="cierre_paga",
                hablante_id="narrador",
                texto="Los cofres reales se abren y los soldados vuelven a sus puestos. La lealtad se restaura, aunque la Canciller frunce el ceño ante el gasto.",
                es_final=True,
                resultado_texto="La soldada se pagó y el orden volvió a un alto precio (-25 Oro, +10 Ejército, +5 Pueblo).",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="oro", delta=-25),
                    ImpactoRecursoSchema(recurso="ejercito", delta=10),
                    ImpactoRecursoSchema(recurso="pueblo", delta=5)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=10),
                    ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=-15)
                ]
            ),
            "cierre_represion": NodoNarrativoSchema(
                id="cierre_represion",
                hablante_id="narrador",
                texto="Marcus asalta las murallas al amanecer y cuelga a los cabecillas. El ejército se disciplina, pero la sangre derramada enfría el ánimo del pueblo.",
                es_final=True,
                resultado_texto="El motín fue aplastado con dureza (+15 Ejército, -20 Pueblo, -5 Fe).",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="ejercito", delta=15),
                    ImpactoRecursoSchema(recurso="pueblo", delta=-20),
                    ImpactoRecursoSchema(recurso="fe", delta=-5)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=15),
                    ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=-10)
                ]
            ),
            "cierre_licenciamiento": NodoNarrativoSchema(
                id="cierre_licenciamiento",
                hablante_id="narrador",
                texto="Los cabecillas son destituidos y la guarnición reducida. El erario respira, pero la frontera queda más desguarnecida que nunca.",
                es_final=True,
                resultado_texto="El licenciamiento ahorró oro pero debilitó la defensa (+15 Oro, -15 Ejército, -10 Pueblo).",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="oro", delta=15),
                    ImpactoRecursoSchema(recurso="ejercito", delta=-15),
                    ImpactoRecursoSchema(recurso="pueblo", delta=-10)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=10),
                    ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=-15)
                ]
            )
        }
    )

    # ========================================================================
    # 6. EVENTO 6: La Gran Sequía
    # ========================================================================
    evento_sequia = EventoV2GrafoSchema(
        _id="evt_sequia_gran_v2",
        universo_id="corte_medieval",
        titulo="La Gran Sequía",
        imagen="/assets/narrative/eventos/default.webp",
        tags_tematicos=["fe", "religion", "moral"],
        requisitos_eventos_previos=[],
        nodo_raiz="sequia_campos",
        nodos={
            "sequia_campos": NodoNarrativoSchema(
                id="sequia_campos",
                hablante_id="narrador",
                texto="Los cielos no derraman lluvia desde hace meses. Los campos se agrietan y la Iglesia exige un diezmo extraordinario para rogar por el retorno de las aguas.",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(
                        id="opt_diezmo_tomas",
                        texto="Entregar el diezmo y convocar rogativas con el Hermano Tomás",
                        siguiente_nodo="cierre_oracion"
                    ),
                    OpcionNodoSchema(
                        id="opt_riego_vera",
                        texto="Encargar a Vera la Erudita construir acueductos y pozos",
                        siguiente_nodo="cierre_acueductos"
                    ),
                    OpcionNodoSchema(
                        id="opt_racionar",
                        texto="Decretar racionamiento de granos en todo el reino",
                        siguiente_nodo="cierre_racionamiento"
                    )
                ]
            ),
            "cierre_oracion": NodoNarrativoSchema(
                id="cierre_oracion",
                hablante_id="narrador",
                texto="Miles de velas se encienden en las catedrales. Sea milagro o azar, una lluvia fina cae sobre los sembradíos y el pueblo canta alabanzas.",
                es_final=True,
                resultado_texto="La fe movilizó a las masas y aplacó la crisis (+20 Fe, +5 Pueblo, -15 Oro).",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="fe", delta=20),
                    ImpactoRecursoSchema(recurso="pueblo", delta=5),
                    ImpactoRecursoSchema(recurso="oro", delta=-15)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=15),
                    ImpactoAfinidadSchema(personaje_id="pj_alquimista_vera", delta=-10)
                ]
            ),
            "cierre_acueductos": NodoNarrativoSchema(
                id="cierre_acueductos",
                hablante_id="narrador",
                texto="Vera dirige la excavación de pozos y canales que rescatan las cosechas. El clero murmura que desafiar la sequía es tentar a los cielos.",
                es_final=True,
                resultado_texto="La ingeniería salvó la cosecha, pese a las sospechas del clero (+20 Pueblo, -15 Oro, -10 Fe).",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="pueblo", delta=20),
                    ImpactoRecursoSchema(recurso="oro", delta=-15),
                    ImpactoRecursoSchema(recurso="fe", delta=-10)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_alquimista_vera", delta=15),
                    ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=-15)
                ]
            ),
            "cierre_racionamiento": NodoNarrativoSchema(
                id="cierre_racionamiento",
                hablante_id="narrador",
                texto="Los graneros reales se abren con cuentagotas y el hambre no llega a las aldeas. La templanza del monarca es bien vista por el pueblo llano.",
                es_final=True,
                resultado_texto="El racionamiento evitó la hambruna sin tocar la fe (+10 Pueblo, +5 Fe, +5 Oro).",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="pueblo", delta=10),
                    ImpactoRecursoSchema(recurso="fe", delta=5),
                    ImpactoRecursoSchema(recurso="oro", delta=5)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=5),
                    ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=10)
                ]
            )
        }
    )

    # ========================================================================
    # 7. EVENTO 7: El Pretendiente del Sur
    # ========================================================================
    evento_pretendiente = EventoV2GrafoSchema(
        _id="evt_pretendiente_trono_v2",
        universo_id="corte_medieval",
        titulo="El Pretendiente del Sur",
        imagen="/assets/narrative/eventos/default.webp",
        tags_tematicos=["intriga", "noble", "diplomacia"],
        requisitos_eventos_previos=[],
        nodo_raiz="pretendiente_sur",
        nodos={
            "pretendiente_sur": NodoNarrativoSchema(
                id="pretendiente_sur",
                hablante_id="narrador",
                texto="Un primo lejano, respaldado por tres casas nobles del sur, reclama el trono alegando un linaje más puro. Sus emisarios recorren el reino ganando adeptos.",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(
                        id="opt_desenmascarar_sylvia",
                        texto="Encargar a Sylvia Niebla desenterrar los trapos sucios del pretendiente",
                        siguiente_nodo="cierre_escandalo"
                    ),
                    OpcionNodoSchema(
                        id="opt_juicio_publico",
                        texto="Someter la disputa a un juicio público ante el clero y los nobles",
                        siguiente_nodo="cierre_juicio"
                    ),
                    OpcionNodoSchema(
                        id="opt_soborno",
                        texto="Comprar la lealtad de las casas nobles con títulos y oro",
                        siguiente_nodo="cierre_compra_lealtad"
                    )
                ]
            ),
            "cierre_escandalo": NodoNarrativoSchema(
                id="cierre_escandalo",
                hablante_id="narrador",
                texto="Los espías de Sylvia sacan a la luz deudas, amantes y cartas falsas. El pretendiente huye en desgracia y el pueblo ríe de su caída.",
                es_final=True,
                resultado_texto="La intriga desarmó la amenaza en las sombras (+20 Pueblo, -10 Oro, -5 Ejército).",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="pueblo", delta=20),
                    ImpactoRecursoSchema(recurso="oro", delta=-10),
                    ImpactoRecursoSchema(recurso="ejercito", delta=-5)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_ladrona_sylvia", delta=15),
                    ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=-10)
                ]
            ),
            "cierre_juicio": NodoNarrativoSchema(
                id="cierre_juicio",
                hablante_id="narrador",
                texto="El Hermano Tomás preside un tribunal que examina los linajes con rigor. El fallo legitima al monarca y apacigua las conciencias del reino.",
                es_final=True,
                resultado_texto="La vía legal fortaleció la legitimidad real (+10 Pueblo, +10 Fe, -5 Oro).",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="pueblo", delta=10),
                    ImpactoRecursoSchema(recurso="fe", delta=10),
                    ImpactoRecursoSchema(recurso="oro", delta=-5)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=10),
                    ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=10)
                ]
            ),
            "cierre_compra_lealtad": NodoNarrativoSchema(
                id="cierre_compra_lealtad",
                hablante_id="narrador",
                texto="Títulos, tierras y oro cambian de manos. Las casas rebeldes se pasan al bando real, aunque el tesoro queda escuálido.",
                es_final=True,
                resultado_texto="La lealtad se compró a precio de rey (-30 Oro, +5 Pueblo, +5 Ejército).",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="oro", delta=-30),
                    ImpactoRecursoSchema(recurso="pueblo", delta=5),
                    ImpactoRecursoSchema(recurso="ejercito", delta=5)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=10),
                    ImpactoAfinidadSchema(personaje_id="pj_ladrona_sylvia", delta=-10)
                ]
            )
        }
    )

    # ========================================================================
    # 3. CONVERSACIÓN V2: Disputa por el Presupuesto Militar
    # ========================================================================
    conv_presupuesto = ConversacionV2GrafoSchema(
        _id="conv_disputa_tesoro_militar_v2",
        universo_id="corte_medieval",
        titulo="Disputa por el Presupuesto de Campaña",
        imagen="/assets/narrative/conversations/default.webp",
        requisitos=["pj_canciller_elena", "pj_comandante_marcus"],
        nodo_raiz="elena_intro",
        nodos={
            "elena_intro": NodoNarrativoSchema(
                id="elena_intro",
                hablante_id="pj_canciller_elena",
                texto="Majestad, las arcas del reino están bajo una fuerte presión. El Comandante Marcus solicita una partida extraordinaria de oro que dejaría a los gremios sin subsidios.",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(
                        id="opt_escuchar_marcus",
                        texto="Escuchar la réplica del Comandante Marcus ➔",
                        siguiente_nodo="marcus_planteo"
                    )
                ]
            ),
            "marcus_planteo": NodoNarrativoSchema(
                id="marcus_planteo",
                hablante_id="pj_comandante_marcus",
                texto="¡De nada servirán los gremios si los invasores quiebran la frontera norte! Necesitamos forjar armaduras y pagar levas ya mismo. ¿Qué ordenáis, Majestad?",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(
                        id="opt_priorizar_defensa",
                        texto="Exigir detalles militares: '¿Qué garantía nos da ese gasto, Marcus?'",
                        siguiente_nodo="marcus_detalles_estrategicos"
                    ),
                    OpcionNodoSchema(
                        id="opt_frenar_gasto",
                        texto="Respaldar a Elena: 'No tocaremos el oro de los mercaderes.'",
                        siguiente_nodo="cierre_elena_ganadora"
                    )
                ]
            ),
            "marcus_detalles_estrategicos": NodoNarrativoSchema(
                id="marcus_detalles_estrategicos",
                hablante_id="pj_comandante_marcus",
                texto="Si fortificamos las tres gargantas del río, contendremos cualquier asedio antes de que toquen los campos de cultivo. Elena exagera el riesgo comercial.",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(
                        id="opt_ordenar_fortificacion",
                        texto="Aprobar el plan: 'Fortificad las gargantas. La orden está sellada.'",
                        siguiente_nodo="cierre_fortificacion_total"
                    ),
                    OpcionNodoSchema(
                        id="opt_pacto_mitad",
                        texto="Acuerdo medio: 'Solo fortificad la principal; compartid el coste.'",
                        siguiente_nodo="cierre_acuerdo_medio"
                    )
                ]
            ),
            "cierre_fortificacion_total": NodoNarrativoSchema(
                id="cierre_fortificacion_total",
                hablante_id="pj_comandante_marcus",
                texto="Marcus golpea su coraza con orgullo: '¡La guardia no os fallará, Majestad!'. Elena guarda silencio y anota el déficit con disgusto en su libro de cuentas.",
                es_final=True,
                resultado_texto="Respaldaste la defensa militar total. La frontera norte es inexpugnable, pero la Canciller Elena advierte que el comercio sufrirá este invierno.",
                impactos_recursos=[],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=15),
                    ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=-15)
                ]
            ),
            "cierre_elena_ganadora": NodoNarrativoSchema(
                id="cierre_elena_ganadora",
                hablante_id="pj_canciller_elena",
                texto="Elena sonríe aliviada: 'Una decisión sabia, Majestad. Los mercaderes sabrán recompensar vuestra prudencia'. Marcus se retira contrariado.",
                es_final=True,
                resultado_texto="Priorizaste el comercio y la estabilidad de las finanzas. Elena afianza su influencia, mientras que la disciplina de la guardia decae.",
                impactos_recursos=[],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=15),
                    ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=-15)
                ]
            ),
            "cierre_acuerdo_medio": NodoNarrativoSchema(
                id="cierre_acuerdo_medio",
                hablante_id="narrador",
                texto="Ambos consejeros asienten a regañadientes ante el arbitrio real. No hubo vencedores ni vencidos, pero el reino mantiene la concordia.",
                es_final=True,
                resultado_texto="Lograste un pacto salomónico. La defensa se refuerza moderadamente y las cuentas del reino se mantienen a flote.",
                impactos_recursos=[],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=8),
                    ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=8)
                ]
            )
        }
    )

    # ========================================================================
    # 4. CONVERSACIÓN V2: Herejía en el Laboratorio
    # ========================================================================
    conv_herejia = ConversacionV2GrafoSchema(
        _id="conv_herejia_laboratorio_v2",
        universo_id="corte_medieval",
        titulo="Herejía en el Laboratorio",
        imagen="/assets/narrative/conversations/default.webp",
        requisitos=["pj_obispo_tomas", "pj_alquimista_vera"],
        nodo_raiz="tomas_intro",
        nodos={
            "tomas_intro": NodoNarrativoSchema(
                id="tomas_intro",
                hablante_id="pj_obispo_tomas",
                texto="Majestad, los vapores y retortas del laboratorio de Vera ofenden a los cielos. El pueblo murmura de brujería y pide que se cierre ese antro.",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(
                        id="opt_escuchar_vera",
                        texto="Dar la palabra a Vera para que defienda su trabajo ➔",
                        siguiente_nodo="vera_defensa"
                    ),
                    OpcionNodoSchema(
                        id="opt_cerrar_lab",
                        texto="Ordenar el cierre inmediato del laboratorio",
                        siguiente_nodo="cierre_cierre_lab"
                    )
                ]
            ),
            "vera_defensa": NodoNarrativoSchema(
                id="vera_defensa",
                hablante_id="pj_alquimista_vera",
                texto="Mis tónicos salvaron a los niños de la aldea baja, y mis filtros purifican el agua estancada. Cerrar el laboratorio es condenar a los pobres a la fiebre.",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(
                        id="opt_respaldar_vera",
                        texto="Respaldar a Vera: 'La ciencia sirve al reino y a sus fieles.'",
                        siguiente_nodo="cierre_ciencia_gana"
                    ),
                    OpcionNodoSchema(
                        id="opt_exigir_vigilancia",
                        texto="Exigir que un clérigo supervise los experimentos",
                        siguiente_nodo="cierre_vigilancia"
                    )
                ]
            ),
            "cierre_ciencia_gana": NodoNarrativoSchema(
                id="cierre_ciencia_gana",
                hablante_id="narrador",
                texto="Vera recibe la bendición real y su fama crece entre el pueblo. Tomás se retira murmurando oraciones de desagravio.",
                es_final=True,
                resultado_texto="Defendiste la ciencia y ganaste el favor popular, a costa del enojo del clero.",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="pueblo", delta=5)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_alquimista_vera", delta=15),
                    ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=-15)
                ]
            ),
            "cierre_vigilancia": NodoNarrativoSchema(
                id="cierre_vigilancia",
                hablante_id="narrador",
                texto="Un monje erudito queda apostado en el laboratorio. La paz vuelve, aunque Vera trabaja ahora bajo la mirada recelosa de la Iglesia.",
                es_final=True,
                resultado_texto="El compromiso calmó a ambos bandos sin entusiasmar a ninguno.",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="pueblo", delta=-5)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=10),
                    ImpactoAfinidadSchema(personaje_id="pj_alquimista_vera", delta=-5)
                ]
            ),
            "cierre_cierre_lab": NodoNarrativoSchema(
                id="cierre_cierre_lab",
                hablante_id="narrador",
                texto="El laboratorio es clausurado y sus frascos rotos en la plaza. El clero celebra, pero los enfermos ya no tienen quien los cure.",
                es_final=True,
                resultado_texto="Cediste ante la presión religiosa, dejando al pueblo sin remedios.",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="pueblo", delta=-10)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=15),
                    ImpactoAfinidadSchema(personaje_id="pj_alquimista_vera", delta=-15)
                ]
            )
        }
    )

    # ========================================================================
    # 5. CONVERSACIÓN V2: Tregua en la Sombra
    # ========================================================================
    conv_tregua = ConversacionV2GrafoSchema(
        _id="conv_tregua_sombra_v2",
        universo_id="corte_medieval",
        titulo="Tregua en la Sombra",
        imagen="/assets/narrative/conversations/default.webp",
        requisitos=["pj_ladrona_sylvia", "pj_comandante_marcus"],
        nodo_raiz="sylvia_intro",
        nodos={
            "sylvia_intro": NodoNarrativoSchema(
                id="sylvia_intro",
                hablante_id="pj_ladrona_sylvia",
                texto="Majestad, necesito oro para pagar informantes en cada puerto y taberna. Marcus dice que es despilfarro, pero sin espías caminaremos a ciegas.",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(
                        id="opt_escuchar_marcus",
                        texto="Escuchar la objeción del Comandante Marcus ➔",
                        siguiente_nodo="marcus_objecion"
                    ),
                    OpcionNodoSchema(
                        id="opt_mediar",
                        texto="Buscar un acuerdo: 'Una red pequeña, con cuentas claras.'",
                        siguiente_nodo="cierre_mediacion"
                    )
                ]
            ),
            "marcus_objecion": NodoNarrativoSchema(
                id="marcus_objecion",
                hablante_id="pj_comandante_marcus",
                texto="¡Con ese oro forjamos lanzas y escudos! Los espías de Sylvia traen rumores, no soldados. ¿Qué preferís, Majestad?",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(
                        id="opt_financiar_sylvia",
                        texto="Financiar la red de espías de Sylvia",
                        siguiente_nodo="cierre_red_espias"
                    ),
                    OpcionNodoSchema(
                        id="opt_rechazar",
                        texto="Respaldar a Marcus y negar los fondos",
                        siguiente_nodo="cierre_rechazo"
                    )
                ]
            ),
            "cierre_red_espias": NodoNarrativoSchema(
                id="cierre_red_espias",
                hablante_id="narrador",
                texto="El oro cambia de manos en callejones oscuros. Sylvia sonríe satisfecha; Marcus golpea la mesa y se marcha.",
                es_final=True,
                resultado_texto="Financiaste el espionaje, ganando ojos en cada rincón del reino.",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="oro", delta=-15)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_ladrona_sylvia", delta=15),
                    ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=-10)
                ]
            ),
            "cierre_rechazo": NodoNarrativoSchema(
                id="cierre_rechazo",
                hablante_id="narrador",
                texto="Marcus recibe el visto bueno y refuerza las armerías. Sylvia se retira en silencio, guardando rencor.",
                es_final=True,
                resultado_texto="Priorizaste el acero sobre los secretos.",
                impactos_recursos=[],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=10),
                    ImpactoAfinidadSchema(personaje_id="pj_ladrona_sylvia", delta=-10)
                ]
            ),
            "cierre_mediacion": NodoNarrativoSchema(
                id="cierre_mediacion",
                hablante_id="narrador",
                texto="Sylvia recibe una suma modesta y Marcus obtiene la promesa de informes útiles para la defensa. Ambos aceptan a regañadientes.",
                es_final=True,
                resultado_texto="El pacto entre espías y soldados mantiene la concordia del consejo.",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="oro", delta=-5)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_ladrona_sylvia", delta=8),
                    ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=8)
                ]
            )
        }
    )

    # ========================================================================
    # 6. CONVERSACIÓN V2: El Diezmo de la Catedral
    # ========================================================================
    conv_diezmo = ConversacionV2GrafoSchema(
        _id="conv_diezmo_catedral_v2",
        universo_id="corte_medieval",
        titulo="El Diezmo de la Catedral",
        imagen="/assets/narrative/conversations/default.webp",
        requisitos=["pj_obispo_tomas", "pj_canciller_elena"],
        nodo_raiz="elena_intro_diezmo",
        nodos={
            "elena_intro_diezmo": NodoNarrativoSchema(
                id="elena_intro_diezmo",
                hablante_id="pj_canciller_elena",
                texto="Majestad, el Hermano Tomás pide oro para levantar un nuevo campanario. Nuestras arcas apenas alcanzan para la paga de la guarnición.",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(
                        id="opt_escuchar_tomas",
                        texto="Escuchar la petición del Hermano Tomás ➔",
                        siguiente_nodo="tomas_planteo"
                    ),
                    OpcionNodoSchema(
                        id="opt_rechazar_directo",
                        texto="Rechazar la obra: 'El reino no puede costear lujos.'",
                        siguiente_nodo="cierre_rechazo_fe"
                    )
                ]
            ),
            "tomas_planteo": NodoNarrativoSchema(
                id="tomas_planteo",
                hablante_id="pj_obispo_tomas",
                texto="No es lujo, Majestad, es devoción. Un templo más alto inspira a los fieles y bendice las cosechas. ¿Negaríais la casa del Señor?",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(
                        id="opt_financiar_catedral",
                        texto="Financiar el campanario con oro del tesoro",
                        siguiente_nodo="cierre_obra_fe"
                    ),
                    OpcionNodoSchema(
                        id="opt_aplazar",
                        texto="Aplazar la obra para un año de mejores cosechas",
                        siguiente_nodo="cierre_aplazamiento"
                    )
                ]
            ),
            "cierre_obra_fe": NodoNarrativoSchema(
                id="cierre_obra_fe",
                hablante_id="narrador",
                texto="Los andamios se alzan sobre la catedral y las campanas nuevas repican en todo el valle. Elena anota el gasto con resignación.",
                es_final=True,
                resultado_texto="La obra complació al clero y elevó la fe, a costa del tesoro.",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="oro", delta=-20),
                    ImpactoRecursoSchema(recurso="fe", delta=10)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=15),
                    ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=-15)
                ]
            ),
            "cierre_aplazamiento": NodoNarrativoSchema(
                id="cierre_aplazamiento",
                hablante_id="narrador",
                texto="Tomás acepta la promesa real de una obra futura. La tesorería respira, aunque el clero queda a la espera.",
                es_final=True,
                resultado_texto="Aplazaste el gasto sin romper con la Iglesia.",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="oro", delta=5)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=10),
                    ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=-10)
                ]
            ),
            "cierre_rechazo_fe": NodoNarrativoSchema(
                id="cierre_rechazo_fe",
                hablante_id="narrador",
                texto="El campanario queda en proyecto. El clero acata la orden, pero los sermones dominicales se vuelven más fríos con la corona.",
                es_final=True,
                resultado_texto="La negativa preservó el oro pero enfrió el fervor.",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="fe", delta=-5)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=15),
                    ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=-15)
                ]
            )
        }
    )

    # ========================================================================
    # 7. CONVERSACIÓN V2: La Botica de la Peste
    # ========================================================================
    conv_botica = ConversacionV2GrafoSchema(
        _id="conv_botica_peste_v2",
        universo_id="corte_medieval",
        titulo="La Botica de la Peste",
        imagen="/assets/narrative/conversations/default.webp",
        requisitos=["pj_alquimista_vera", "pj_canciller_elena"],
        nodo_raiz="elena_intro_botica",
        nodos={
            "elena_intro_botica": NodoNarrativoSchema(
                id="elena_intro_botica",
                hablante_id="pj_canciller_elena",
                texto="Majestad, Vera pide fondos para producir sus remedios en masa. Es un gasto cuantioso y no tenemos certeza de que funcionen a gran escala.",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(
                        id="opt_escuchar_vera",
                        texto="Escuchar el plan de Vera la Erudita ➔",
                        siguiente_nodo="vera_planteo"
                    ),
                    OpcionNodoSchema(
                        id="opt_negar",
                        texto="Negar los fondos: 'El riesgo es demasiado alto.'",
                        siguiente_nodo="cierre_negacion"
                    )
                ]
            ),
            "vera_planteo": NodoNarrativoSchema(
                id="vera_planteo",
                hablante_id="pj_alquimista_vera",
                texto="Si destilo los tónicos en las destilerías reales, puedo abastecer a todas las aldeas del sur antes de la próxima luna. Un reino sano produce más que un reino enfermo.",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(
                        id="opt_financiar_remedios",
                        texto="Financiar la producción masiva de remedios",
                        siguiente_nodo="cierre_remedios"
                    ),
                    OpcionNodoSchema(
                        id="opt_remedio_limitado",
                        texto="Autorizar una producción limitada de prueba",
                        siguiente_nodo="cierre_limitado"
                    )
                ]
            ),
            "cierre_remedios": NodoNarrativoSchema(
                id="cierre_remedios",
                hablante_id="narrador",
                texto="Los tónicos se reparten por las aldeas y las muertes caen en picada. Elena acepta que el oro estuvo bien invertido.",
                es_final=True,
                resultado_texto="La producción masiva salvó vidas y ganó corazones.",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="oro", delta=-15),
                    ImpactoRecursoSchema(recurso="pueblo", delta=15)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_alquimista_vera", delta=15),
                    ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=-10)
                ]
            ),
            "cierre_limitado": NodoNarrativoSchema(
                id="cierre_limitado",
                hablante_id="narrador",
                texto="La producción pequeña surte a las aldeas más cercanas. Vera anota resultados y promete eficacia a mayor escala.",
                es_final=True,
                resultado_texto="La prueba moderada equilibró el gasto y el beneficio.",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="oro", delta=-5),
                    ImpactoRecursoSchema(recurso="pueblo", delta=5)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_alquimista_vera", delta=5),
                    ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=10)
                ]
            ),
            "cierre_negacion": NodoNarrativoSchema(
                id="cierre_negacion",
                hablante_id="narrador",
                texto="Sin remedios, la fiebre se extiende por el sur. Las aldeas entierran a sus ancianos y maldicen la tacañería del trono.",
                es_final=True,
                resultado_texto="La prudencia excesiva costó caro al pueblo.",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="pueblo", delta=-10)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=10),
                    ImpactoAfinidadSchema(personaje_id="pj_alquimista_vera", delta=-10)
                ]
            )
        }
    )

    # ========================================================================
    # 8. CONVERSACIÓN V2: La Conspiración de los Nobles
    # ========================================================================
    conv_conspiracion = ConversacionV2GrafoSchema(
        _id="conv_conspiracion_nobles_v2",
        universo_id="corte_medieval",
        titulo="La Conspiración de los Nobles",
        imagen="/assets/narrative/conversations/default.webp",
        requisitos=["pj_ladrona_sylvia", "pj_canciller_elena"],
        nodo_raiz="sylvia_intro_consp",
        nodos={
            "sylvia_intro_consp": NodoNarrativoSchema(
                id="sylvia_intro_consp",
                hablante_id="pj_ladrona_sylvia",
                texto="Majestad, tres barones sellan cartas secretas para derrocaros. Tengo los nombres y los puntos de reunión. ¿Actuamos ya?",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(
                        id="opt_actuar",
                        texto="Autorizar a Sylvia a desmantelar la conspiración ➔",
                        siguiente_nodo="sylvia_plan"
                    ),
                    OpcionNodoSchema(
                        id="opt_esperar",
                        texto="Aconsejarse con Elena antes de tomar una decisión",
                        siguiente_nodo="cierre_espera"
                    )
                ]
            ),
            "sylvia_plan": NodoNarrativoSchema(
                id="sylvia_plan",
                hablante_id="pj_ladrona_sylvia",
                texto="Puedo dar un golpe en la sombra y arrestar a los cabecillas esta noche, o filtrar las cartas para que el pueblo conozca su traición. Vos elegís.",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(
                        id="opt_golpe_espia",
                        texto="Dar el golpe silencioso y arrestar a los traidores",
                        siguiente_nodo="cierre_golpe"
                    ),
                    OpcionNodoSchema(
                        id="opt_publicar",
                        texto="Publicar las cartas en la plaza mayor",
                        siguiente_nodo="cierre_publicacion"
                    )
                ]
            ),
            "cierre_golpe": NodoNarrativoSchema(
                id="cierre_golpe",
                hablante_id="narrador",
                texto="Los barones amanecen en las mazmorras sin que nadie sepa cómo. La corte entera comprende el mensaje: nadie conspira contra el trono.",
                es_final=True,
                resultado_texto="El golpe quirúrgico desactivó la traición, aunque costó oro.",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="oro", delta=-10),
                    ImpactoRecursoSchema(recurso="ejercito", delta=5)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_ladrona_sylvia", delta=15),
                    ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=-5)
                ]
            ),
            "cierre_publicacion": NodoNarrativoSchema(
                id="cierre_publicacion",
                hablante_id="narrador",
                texto="Las cartas selladas se leen en voz alta ante la multitud. El pueblo abuchea a los barones y aplaude la transparencia del monarca.",
                es_final=True,
                resultado_texto="La verdad pública deshizo la conjura y elevó al trono.",
                impactos_recursos=[
                    ImpactoRecursoSchema(recurso="pueblo", delta=10),
                    ImpactoRecursoSchema(recurso="fe", delta=-5)
                ],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_ladrona_sylvia", delta=10),
                    ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=10)
                ]
            ),
            "cierre_espera": NodoNarrativoSchema(
                id="cierre_espera",
                hablante_id="narrador",
                texto="Elena aconseja cautela y estudiar las alianzas antes de actuar. Sylvia se impacienta, pero acata la orden real.",
                es_final=True,
                resultado_texto="La prudencia ganó tiempo, aunque los espías quedaron a la espera.",
                impactos_recursos=[],
                impactos_afinidad=[
                    ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=10),
                    ImpactoAfinidadSchema(personaje_id="pj_ladrona_sylvia", delta=-10)
                ]
            )
        }
    )

    # ========================================================================
    # 9. EVENTOS ESPECIALES DE AFINIDAD (LEALTAD >= 95 / TRAICIÓN < 15)
    # ========================================================================
    esp_lealtad_elena = EventoEspecialV2GrafoSchema(
        _id="esp_lealtad_elena",
        universo_id="corte_medieval",
        personaje_id="pj_canciller_elena",
        direccion=DireccionEventoEspecialEnum.LEALTAD,
        titulo="El Juramento de la Canciller",
        imagen="/assets/narrative/eventos/default.webp",
        nodo_raiz="juramento_elena",
        nodos={
            "juramento_elena": NodoNarrativoSchema(
                id="juramento_elena",
                hablante_id="pj_canciller_elena",
                texto="Majestad, he servido a esta corona entre intrigas y penurias, y hoy os lo juro sin reservas: haré de vuestras arcas un escudo inexpugnable. ¿Cómo deseáis que selle mi lealtad?",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(id="opt_firma_acuerdos", texto="Encargarle negociar nuevos acuerdos comerciales", siguiente_nodo="cierre_comercio_elena"),
                    OpcionNodoSchema(id="opt_auditoria", texto="Encargarle una auditoría del tesoro para frenar fugas", siguiente_nodo="cierre_auditoria_elena")
                ]
            ),
            "cierre_comercio_elena": NodoNarrativoSchema(
                id="cierre_comercio_elena",
                hablante_id="narrador",
                texto="Elena cierra pactos ventajosos en una gira relámpago. Las caravanas fluyen y el tesoro respira.",
                es_final=True,
                resultado_texto="La lealtad de Elena abrió rutas de oro (+25 Oro, +10 Pueblo).",
                impactos_recursos=[ImpactoRecursoSchema(recurso="oro", delta=25), ImpactoRecursoSchema(recurso="pueblo", delta=10)],
                impactos_afinidad=[]
            ),
            "cierre_auditoria_elena": NodoNarrativoSchema(
                id="cierre_auditoria_elena",
                hablante_id="narrador",
                texto="La auditoría destapa a un recaudador corrupto. El oro recuperado vuelve a las arcas reales.",
                es_final=True,
                resultado_texto="La vigilancia de Elena recuperó fondos desviados (+15 Oro, +10 Fe).",
                impactos_recursos=[ImpactoRecursoSchema(recurso="oro", delta=15), ImpactoRecursoSchema(recurso="fe", delta=10)],
                impactos_afinidad=[]
            )
        }
    )

    esp_traicion_elena = EventoEspecialV2GrafoSchema(
        _id="esp_traicion_elena",
        universo_id="corte_medieval",
        personaje_id="pj_canciller_elena",
        direccion=DireccionEventoEspecialEnum.TRAICION,
        titulo="El Desvío de la Canciller",
        imagen="/assets/narrative/eventos/default.webp",
        nodo_raiz="desvio_elena",
        nodos={
            "desvio_elena": NodoNarrativoSchema(
                id="desvio_elena",
                hablante_id="narrador",
                texto="Los libros del tesoro no cuadran. Testigos aseguran que la Canciller Elena desvía oro a cofres privados y negocia a espaldas del trono. ¿Cómo respondéis?",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(id="opt_juicio", texto="Someterla a juicio público y confiscar sus bienes", siguiente_nodo="cierre_juicio_elena"),
                    OpcionNodoSchema(id="opt_perdon", texto="Confrontarla en privado y darle una última oportunidad", siguiente_nodo="cierre_perdon_elena")
                ]
            ),
            "cierre_juicio_elena": NodoNarrativoSchema(
                id="cierre_juicio_elena",
                hablante_id="narrador",
                texto="El juicio condena a Elena y el reino recupera lo desviado, pero la corte queda sin su mano conciliadora.",
                es_final=True,
                resultado_texto="La justicia prevaleció a un alto costo político (+20 Oro, -15 Pueblo).",
                impactos_recursos=[ImpactoRecursoSchema(recurso="oro", delta=20), ImpactoRecursoSchema(recurso="pueblo", delta=-15)],
                impactos_afinidad=[ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=-20)]
            ),
            "cierre_perdon_elena": NodoNarrativoSchema(
                id="cierre_perdon_elena",
                hablante_id="narrador",
                texto="Elena confiesa entre lágrimas y devuelve parte de lo robado. El escándalo se sofoca, pero la desconfianza queda.",
                es_final=True,
                resultado_texto="La misericordia evitó el escándalo, aunque el daño persiste (+5 Oro, -10 Pueblo).",
                impactos_recursos=[ImpactoRecursoSchema(recurso="oro", delta=5), ImpactoRecursoSchema(recurso="pueblo", delta=-10)],
                impactos_afinidad=[ImpactoAfinidadSchema(personaje_id="pj_canciller_elena", delta=-5)]
            )
        }
    )

    esp_lealtad_marcus = EventoEspecialV2GrafoSchema(
        _id="esp_lealtad_marcus",
        universo_id="corte_medieval",
        personaje_id="pj_comandante_marcus",
        direccion=DireccionEventoEspecialEnum.LEALTAD,
        titulo="El Voto de Hierro",
        imagen="/assets/narrative/eventos/default.webp",
        nodo_raiz="voto_marcus",
        nodos={
            "voto_marcus": NodoNarrativoSchema(
                id="voto_marcus",
                hablante_id="pj_comandante_marcus",
                texto="Majestad, mi espada y mi guardia os pertenecen hasta la muerte. Decidme cómo forjar vuestra seguridad y lo haré sin dudar.",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(id="opt_guardia_real", texto="Fundar una guardia real de élite bajo su mando", siguiente_nodo="cierre_guardia_marcus"),
                    OpcionNodoSchema(id="opt_frontera", texto="Reforzar las murallas y la frontera norte", siguiente_nodo="cierre_frontera_marcus")
                ]
            ),
            "cierre_guardia_marcus": NodoNarrativoSchema(
                id="cierre_guardia_marcus",
                hablante_id="narrador",
                texto="Los mejores soldados del reino juran ante el trono. El palacio se vuelve inexpugnable.",
                es_final=True,
                resultado_texto="La guardia de élite de Marcus blindó la corona (+20 Ejército, +5 Fe).",
                impactos_recursos=[ImpactoRecursoSchema(recurso="ejercito", delta=20), ImpactoRecursoSchema(recurso="fe", delta=5)],
                impactos_afinidad=[]
            ),
            "cierre_frontera_marcus": NodoNarrativoSchema(
                id="cierre_frontera_marcus",
                hablante_id="narrador",
                texto="Las murallas del norte se alzan nuevas. Los invasores retroceden y el pueblo duerme tranquilo.",
                es_final=True,
                resultado_texto="Las defensas reforzadas pacificaron la frontera (+15 Ejército, +10 Pueblo).",
                impactos_recursos=[ImpactoRecursoSchema(recurso="ejercito", delta=15), ImpactoRecursoSchema(recurso="pueblo", delta=10)],
                impactos_afinidad=[]
            )
        }
    )

    esp_traicion_marcus = EventoEspecialV2GrafoSchema(
        _id="esp_traicion_marcus",
        universo_id="corte_medieval",
        personaje_id="pj_comandante_marcus",
        direccion=DireccionEventoEspecialEnum.TRAICION,
        titulo="El Motín del Capitán",
        imagen="/assets/narrative/eventos/default.webp",
        nodo_raiz="motin_marcus",
        nodos={
            "motin_marcus": NodoNarrativoSchema(
                id="motin_marcus",
                hablante_id="narrador",
                texto="Marcus, desencantado con vuestro gobierno, ha acuartelado a la guardia y exige vuestra abdicación desde la muralla este. La corte contiene el aliento.",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(id="opt_negociar", texto="Enviar a Elena a negociar la rendición del capitán", siguiente_nodo="cierre_negociacion_marcus"),
                    OpcionNodoSchema(id="opt_asalto", texto="Asaltar la muralla con las tropas leales", siguiente_nodo="cierre_asalto_marcus")
                ]
            ),
            "cierre_negociacion_marcus": NodoNarrativoSchema(
                id="cierre_negociacion_marcus",
                hablante_id="narrador",
                texto="Elena convence a los cabos de que el motín solo lleva a la horca. Marcus se entrega, amargado.",
                es_final=True,
                resultado_texto="La sangre no llegó al río, pero el ejército quedó dividido (-10 Ejército, +5 Pueblo).",
                impactos_recursos=[ImpactoRecursoSchema(recurso="ejercito", delta=-10), ImpactoRecursoSchema(recurso="pueblo", delta=5)],
                impactos_afinidad=[ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=-10)]
            ),
            "cierre_asalto_marcus": NodoNarrativoSchema(
                id="cierre_asalto_marcus",
                hablante_id="narrador",
                texto="El asalto es cruento. Marcus cae defendiendo su estandarte y la guarnición queda diezmada.",
                es_final=True,
                resultado_texto="La lealtad se impuso por la fuerza, a un precio terrible (-15 Ejército, -15 Pueblo).",
                impactos_recursos=[ImpactoRecursoSchema(recurso="ejercito", delta=-15), ImpactoRecursoSchema(recurso="pueblo", delta=-15)],
                impactos_afinidad=[ImpactoAfinidadSchema(personaje_id="pj_comandante_marcus", delta=-20)]
            )
        }
    )

    esp_lealtad_tomas = EventoEspecialV2GrafoSchema(
        _id="esp_lealtad_tomas",
        universo_id="corte_medieval",
        personaje_id="pj_obispo_tomas",
        direccion=DireccionEventoEspecialEnum.LEALTAD,
        titulo="La Bendición del Obispo",
        imagen="/assets/narrative/eventos/default.webp",
        nodo_raiz="bendicion_tomas",
        nodos={
            "bendicion_tomas": NodoNarrativoSchema(
                id="bendicion_tomas",
                hablante_id="pj_obispo_tomas",
                texto="Majestad, vuestro reinado es grato a los cielos. El clero os respalda y bendice vuestra casa. ¿Cómo deseáis honrar esta alianza santa?",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(id="opt_capilla", texto="Consagrar una capilla real en vuestro nombre", siguiente_nodo="cierre_capilla_tomas"),
                    OpcionNodoSchema(id="opt_diezmo", texto="Invertir en hospitales y obras de caridad", siguiente_nodo="cierre_caridad_tomas")
                ]
            ),
            "cierre_capilla_tomas": NodoNarrativoSchema(
                id="cierre_capilla_tomas",
                hablante_id="narrador",
                texto="Las campanas bendicen la alianza entre el trono y el altar. La fe del reino se enciende.",
                es_final=True,
                resultado_texto="La capilla real elevó el fervor popular (+20 Fe, +5 Pueblo).",
                impactos_recursos=[ImpactoRecursoSchema(recurso="fe", delta=20), ImpactoRecursoSchema(recurso="pueblo", delta=5)],
                impactos_afinidad=[]
            ),
            "cierre_caridad_tomas": NodoNarrativoSchema(
                id="cierre_caridad_tomas",
                hablante_id="narrador",
                texto="Los hospitales de Tomás socorren a los desvalidos. El pueblo bendice al rey misericordioso.",
                es_final=True,
                resultado_texto="La caridad unió a pobres y devotos (+15 Pueblo, +10 Fe).",
                impactos_recursos=[ImpactoRecursoSchema(recurso="pueblo", delta=15), ImpactoRecursoSchema(recurso="fe", delta=10)],
                impactos_afinidad=[]
            )
        }
    )

    esp_traicion_tomas = EventoEspecialV2GrafoSchema(
        _id="esp_traicion_tomas",
        universo_id="corte_medieval",
        personaje_id="pj_obispo_tomas",
        direccion=DireccionEventoEspecialEnum.TRAICION,
        titulo="La Excomunión del Obispo",
        imagen="/assets/narrative/eventos/default.webp",
        nodo_raiz="excomunion_tomas",
        nodos={
            "excomunion_tomas": NodoNarrativoSchema(
                id="excomunion_tomas",
                hablante_id="narrador",
                texto="El Hermano Tomás, indignado con la corona, ha denunciado vuestro nombre desde el púlpito y amenaza con excomulgar al trono. Los fieles se agitan en las plazas.",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(id="opt_reconciliar", texto="Buscar la reconciliación con gestos de humildad", siguiente_nodo="cierre_reconciliacion_tomas"),
                    OpcionNodoSchema(id="opt_desafiar", texto="Desafiar al clero y confiscar tierras de la catedral", siguiente_nodo="cierre_confiscacion_tomas")
                ]
            ),
            "cierre_reconciliacion_tomas": NodoNarrativoSchema(
                id="cierre_reconciliacion_tomas",
                hablante_id="narrador",
                texto="El rey camina descalzo hasta la catedral y Tomás retira la amenaza, conmovido ante el pueblo.",
                es_final=True,
                resultado_texto="La humildad real desactivó el cisma (+5 Fe, +5 Pueblo, -10 Oro).",
                impactos_recursos=[ImpactoRecursoSchema(recurso="fe", delta=5), ImpactoRecursoSchema(recurso="pueblo", delta=5), ImpactoRecursoSchema(recurso="oro", delta=-10)],
                impactos_afinidad=[ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=-5)]
            ),
            "cierre_confiscacion_tomas": NodoNarrativoSchema(
                id="cierre_confiscacion_tomas",
                hablante_id="narrador",
                texto="Las tierras de la catedral pasan a la corona y Tomás es desterrado. El clero entero hierve de rabia.",
                es_final=True,
                resultado_texto="El desafío llenó el tesoro pero encendió la ira de la fe (+20 Oro, -25 Fe).",
                impactos_recursos=[ImpactoRecursoSchema(recurso="oro", delta=20), ImpactoRecursoSchema(recurso="fe", delta=-25)],
                impactos_afinidad=[ImpactoAfinidadSchema(personaje_id="pj_obispo_tomas", delta=-20)]
            )
        }
    )

    esp_lealtad_vera = EventoEspecialV2GrafoSchema(
        _id="esp_lealtad_vera",
        universo_id="corte_medieval",
        personaje_id="pj_alquimista_vera",
        direccion=DireccionEventoEspecialEnum.LEALTAD,
        titulo="La Alquimia al Servicio del Trono",
        imagen="/assets/narrative/eventos/default.webp",
        nodo_raiz="alquimia_vera",
        nodos={
            "alquimia_vera": NodoNarrativoSchema(
                id="alquimia_vera",
                hablante_id="pj_alquimista_vera",
                texto="Majestad, mis secretos alquímicos os pertenecen. Con vuestro respaldo puedo obrar maravillas que asombrarán al reino. ¿Qué priorizamos?",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(id="opt_remedios", texto="Producir remedios gratuitos para todo el pueblo", siguiente_nodo="cierre_remedios_vera"),
                    OpcionNodoSchema(id="opt_metalurgia", texto="Perfeccionar la forja de acero valyrio", siguiente_nodo="cierre_metalurgia_vera")
                ]
            ),
            "cierre_remedios_vera": NodoNarrativoSchema(
                id="cierre_remedios_vera",
                hablante_id="narrador",
                texto="Los tónicos de Vera curan plagas y devuelven la salud a las aldeas. El pueblo la aclama como salvadora.",
                es_final=True,
                resultado_texto="Los remedios de Vera sanaron al reino (+20 Pueblo, +5 Fe).",
                impactos_recursos=[ImpactoRecursoSchema(recurso="pueblo", delta=20), ImpactoRecursoSchema(recurso="fe", delta=5)],
                impactos_afinidad=[]
            ),
            "cierre_metalurgia_vera": NodoNarrativoSchema(
                id="cierre_metalurgia_vera",
                hablante_id="narrador",
                texto="El acero templado con técnicas alquímicas blinda a la guardia real.",
                es_final=True,
                resultado_texto="La forja alquímica reforzó el ejército (+20 Ejército, +5 Oro).",
                impactos_recursos=[ImpactoRecursoSchema(recurso="ejercito", delta=20), ImpactoRecursoSchema(recurso="oro", delta=5)],
                impactos_afinidad=[]
            )
        }
    )

    esp_traicion_vera = EventoEspecialV2GrafoSchema(
        _id="esp_traicion_vera",
        universo_id="corte_medieval",
        personaje_id="pj_alquimista_vera",
        direccion=DireccionEventoEspecialEnum.TRAICION,
        titulo="El Veneno de la Erudita",
        imagen="/assets/narrative/eventos/default.webp",
        nodo_raiz="veneno_vera",
        nodos={
            "veneno_vera": NodoNarrativoSchema(
                id="veneno_vera",
                hablante_id="narrador",
                texto="Un catador real agoniza tras probar vuestro vino. Vera, humillada por la corona, es señalada como autora del veneno. El laboratorio arde en rumores.",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(id="opt_investigar", texto="Investigar antes de juzgar: separar la verdad del chisme", siguiente_nodo="cierre_investigacion_vera"),
                    OpcionNodoSchema(id="opt_encerrar", texto="Encerrar a Vera en las mazmorras sin más trámite", siguiente_nodo="cierre_mazmorra_vera")
                ]
            ),
            "cierre_investigacion_vera": NodoNarrativoSchema(
                id="cierre_investigacion_vera",
                hablante_id="narrador",
                texto="La pesquisa descubre que el veneno vino de un rival noble. Vera queda libre, pero su confianza en el trono se quebró.",
                es_final=True,
                resultado_texto="La prudencia evitó una injusticia, aunque el laboratorio sufrió (-10 Fe, -5 Pueblo).",
                impactos_recursos=[ImpactoRecursoSchema(recurso="fe", delta=-10), ImpactoRecursoSchema(recurso="pueblo", delta=-5)],
                impactos_afinidad=[ImpactoAfinidadSchema(personaje_id="pj_alquimista_vera", delta=-5)]
            ),
            "cierre_mazmorra_vera": NodoNarrativoSchema(
                id="cierre_mazmorra_vera",
                hablante_id="narrador",
                texto="Vera es arrastrada a las mazmorras. Sin sus remedios, las aldeas enfermas quedan desatendidas.",
                es_final=True,
                resultado_texto="El castigo expeditivo calmó a la corte pero desangró al pueblo (-15 Pueblo, -10 Fe).",
                impactos_recursos=[ImpactoRecursoSchema(recurso="pueblo", delta=-15), ImpactoRecursoSchema(recurso="fe", delta=-10)],
                impactos_afinidad=[ImpactoAfinidadSchema(personaje_id="pj_alquimista_vera", delta=-20)]
            )
        }
    )

    esp_lealtad_sylvia = EventoEspecialV2GrafoSchema(
        _id="esp_lealtad_sylvia",
        universo_id="corte_medieval",
        personaje_id="pj_ladrona_sylvia",
        direccion=DireccionEventoEspecialEnum.LEALTAD,
        titulo="El Gremio de las Sombras",
        imagen="/assets/narrative/eventos/default.webp",
        nodo_raiz="gremio_sylvia",
        nodos={
            "gremio_sylvia": NodoNarrativoSchema(
                id="gremio_sylvia",
                hablante_id="pj_ladrona_sylvia",
                texto="Majestad, mi red de sombras os jura fidelidad. Nada se moverá en el reino sin que lo sepáis antes que nadie. ¿Dónde pongo mis ojos primero?",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(id="opt_nobles", texto="Vigilar a los nobles desafectos de la corte", siguiente_nodo="cierre_nobles_sylvia"),
                    OpcionNodoSchema(id="opt_frontera", texto="Vigilar las fronteras y puertos del reino", siguiente_nodo="cierre_frontera_sylvia")
                ]
            ),
            "cierre_nobles_sylvia": NodoNarrativoSchema(
                id="cierre_nobles_sylvia",
                hablante_id="narrador",
                texto="Los espías destapan dos conspiraciones antes de que cuajen. La corte aprende a temer la sombra del trono.",
                es_final=True,
                resultado_texto="La red de Sylvia desactivó traiciones palaciegas (+10 Oro, +10 Pueblo).",
                impactos_recursos=[ImpactoRecursoSchema(recurso="oro", delta=10), ImpactoRecursoSchema(recurso="pueblo", delta=10)],
                impactos_afinidad=[]
            ),
            "cierre_frontera_sylvia": NodoNarrativoSchema(
                id="cierre_frontera_sylvia",
                hablante_id="narrador",
                texto="Informes puntuales anticipan incursiones enemigas. Las defensas se adelantan a cada golpe.",
                es_final=True,
                resultado_texto="La inteligencia de Sylvia blindó las fronteras (+15 Ejército, +5 Oro).",
                impactos_recursos=[ImpactoRecursoSchema(recurso="ejercito", delta=15), ImpactoRecursoSchema(recurso="oro", delta=5)],
                impactos_afinidad=[]
            )
        }
    )

    esp_traicion_sylvia = EventoEspecialV2GrafoSchema(
        _id="esp_traicion_sylvia",
        universo_id="corte_medieval",
        personaje_id="pj_ladrona_sylvia",
        direccion=DireccionEventoEspecialEnum.TRAICION,
        titulo="La Traición de las Sombras",
        imagen="/assets/narrative/eventos/default.webp",
        nodo_raiz="traicion_sylvia",
        nodos={
            "traicion_sylvia": NodoNarrativoSchema(
                id="traicion_sylvia",
                hablante_id="narrador",
                texto="Se descubre que Sylvia ha vendido los secretos de la corte a un reino rival. Los calabozos están vacíos y sus espías han desaparecido. ¿Cómo actuáis?",
                es_final=False,
                opciones=[
                    OpcionNodoSchema(id="opt_cazar", texto="Lanzar una cacería por cada taberna y puerto", siguiente_nodo="cierre_caza_sylvia"),
                    OpcionNodoSchema(id="opt_contrainteligencia", texto="Usar la red corrupta para filtrar información falsa", siguiente_nodo="cierre_falsos_sylvia")
                ]
            ),
            "cierre_caza_sylvia": NodoNarrativoSchema(
                id="cierre_caza_sylvia",
                hablante_id="narrador",
                texto="La red es desmantelada a golpe de cadalso. Los secretos vendidos, sin embargo, ya cruzaron la frontera.",
                es_final=True,
                resultado_texto="La purga restauró el control a un alto costo (-15 Oro, -10 Ejército).",
                impactos_recursos=[ImpactoRecursoSchema(recurso="oro", delta=-15), ImpactoRecursoSchema(recurso="ejercito", delta=-10)],
                impactos_afinidad=[ImpactoAfinidadSchema(personaje_id="pj_ladrona_sylvia", delta=-20)]
            ),
            "cierre_falsos_sylvia": NodoNarrativoSchema(
                id="cierre_falsos_sylvia",
                hablante_id="narrador",
                texto="El rival recibe planos falsos y tropieza en su propia trampa. La sombra de Sylvia queda rota, pero su utilidad sobrevive.",
                es_final=True,
                resultado_texto="La contra-inteligencia volvió la traición a favor (+10 Ejército, -10 Oro).",
                impactos_recursos=[ImpactoRecursoSchema(recurso="ejercito", delta=10), ImpactoRecursoSchema(recurso="oro", delta=-10)],
                impactos_afinidad=[ImpactoAfinidadSchema(personaje_id="pj_ladrona_sylvia", delta=-10)]
            )
        }
    )

    # ========================================================================
    # INSERTAR EN BASE DE DATOS (UPSERT)
    # ========================================================================
    col_events = db[COLL_V2_EVENTS]
    col_convs = db[COLL_V2_CONVERSATIONS]
    col_especiales = db[COLL_V2_EVENTOS_ESPECIALES]

    eventos_todos = [
        evento_cometa,
        evento_secta,
        evento_peste,
        evento_embargo,
        evento_motin,
        evento_sequia,
        evento_pretendiente
    ]
    for ev in eventos_todos:
        doc = ev.model_dump(by_alias=True)
        await col_events.update_one({"_id": doc["_id"]}, {"$setOnInsert": doc}, upsert=True)
        logger.info(f"[NARRATIVE V2 SEED] Evento V2 '{doc['_id']}' asegurado (sin pisar ediciones).")

    conversaciones_todas = [
        conv_presupuesto,
        conv_herejia,
        conv_tregua,
        conv_diezmo,
        conv_botica,
        conv_conspiracion
    ]
    for conv in conversaciones_todas:
        doc = conv.model_dump(by_alias=True)
        await col_convs.update_one({"_id": doc["_id"]}, {"$setOnInsert": doc}, upsert=True)
        logger.info(f"[NARRATIVE V2 SEED] Conversación V2 '{doc['_id']}' asegurada (sin pisar ediciones).")

    especiales_todos = [
        esp_lealtad_elena,
        esp_traicion_elena,
        esp_lealtad_marcus,
        esp_traicion_marcus,
        esp_lealtad_tomas,
        esp_traicion_tomas,
        esp_lealtad_vera,
        esp_traicion_vera,
        esp_lealtad_sylvia,
        esp_traicion_sylvia
    ]
    for esp in especiales_todos:
        doc = esp.model_dump(by_alias=True)
        await col_especiales.update_one({"_id": doc["_id"]}, {"$setOnInsert": doc}, upsert=True)
        logger.info(f"[NARRATIVE V2 SEED] Evento especial '{doc['_id']}' asegurado (sin pisar ediciones).")

    logger.info("[NARRATIVE V2 SEED] ¡Siembra de grafos V2 completada exitosamente!")

if __name__ == "__main__":
    async def main():
        await connect_to_mongo()
        await seed_v2_graphs()
    asyncio.run(main())
