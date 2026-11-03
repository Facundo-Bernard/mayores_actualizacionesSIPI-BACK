"""
Módulo de Lógica de Juego Narrativo.
- motor_v1: superficie legacy (/api/narrative/partida).
- motor_v2: ciclo mensual nativo y motor de grafos (/api/narrative/v2/partida).
- compartido: identidad de invitados, persistencia de runs y recursos de universo.
"""

from app.features.narrative.game.router import router, router_v2
from app.features.narrative.game.universe_resources import (
    _RECURSOS_MAPA_CACHE,
    invalidar_cache_recursos_universo,
    obtener_mapa_recursos_universo,
)
from app.features.narrative.game.motor_v1.setup_service import (
    obtener_setup_desafio,
    reiniciar_partida,
)
from app.features.narrative.game.motor_v2.setup_service import iniciar_partida_v2
from app.features.narrative.game.motor_v2.turn_service import (
    elegir_carta_mes_v2,
    decidir_evento_v2,
    responder_conversacion_v2,
)
from app.features.narrative.game.motor_v2.transition_service import avanzar_mes_v2
from app.features.narrative.game.motor_v2.endings_service import (
    verificar_colapso_recursos,
    calcular_finalizacion_victoria,
    sincronizar_intento_usuario,
)
from app.features.narrative.game.motor_v1.modals_service import (
    obtener_historial_partida,
    obtener_inventario_partida,
    obtener_corte_partida,
    obtener_finalizacion_partida,
    obtener_evento_actual_partida,
    obtener_conversacion_actual_partida,
    obtener_resultado_actual_partida,
    obtener_draft_actual_partida,
)
from app.features.narrative.game.motor_v2.modals import obtener_turno_actual

__all__ = [
    # Routers
    "router",
    "router_v2",
    # Recursos de universo
    "_RECURSOS_MAPA_CACHE",
    "invalidar_cache_recursos_universo",
    "obtener_mapa_recursos_universo",
    # Setup
    "obtener_setup_desafio",
    "reiniciar_partida",
    "iniciar_partida_v2",
    # Turn Loop
    "elegir_carta_mes_v2",
    "decidir_evento_v2",
    "responder_conversacion_v2",
    # Transition
    "avanzar_mes_v2",
    # Endings & Sync
    "verificar_colapso_recursos",
    "calcular_finalizacion_victoria",
    "sincronizar_intento_usuario",
    # Modals & Reactive Queries
    "obtener_historial_partida",
    "obtener_inventario_partida",
    "obtener_corte_partida",
    "obtener_finalizacion_partida",
    "obtener_turno_actual",
    "obtener_evento_actual_partida",
    "obtener_conversacion_actual_partida",
    "obtener_resultado_actual_partida",
    "obtener_draft_actual_partida",
]
