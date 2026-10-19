"""
Módulo de Lógica de Juego Narrativo (Fases 0 a 4, ciclo mensual, modales y routers de jugador).
"""

from app.features.narrative.game.router import router, router_v2
from app.features.narrative.game.setup_service import (
    _RECURSOS_MAPA_CACHE,
    invalidar_cache_recursos_universo,
    _obtener_mapa_recursos_universo,
    obtener_setup_desafio,
    reiniciar_partida,
    iniciar_partida_v2,
)
from app.features.narrative.game.turn_service import (
    elegir_carta_mes_v2,
    decidir_evento_v2,
    responder_conversacion_v2,
)
from app.features.narrative.game.transition_service import (
    avanzar_mes_v2,
)
from app.features.narrative.game.endings_service import (
    verificar_colapso_recursos,
    calcular_finalizacion_victoria,
    sincronizar_intento_usuario,
)
from app.features.narrative.game.modals_service import (
    obtener_historial_partida,
    obtener_inventario_partida,
    obtener_corte_partida,
    obtener_finalizacion_partida,
    obtener_turno_actual,
    obtener_evento_actual_partida,
    obtener_conversacion_actual_partida,
    obtener_resultado_actual_partida,
    obtener_draft_actual_partida,
)

__all__ = [
    # Routers
    "router",
    "router_v2",
    # Setup
    "_RECURSOS_MAPA_CACHE",
    "invalidar_cache_recursos_universo",
    "_obtener_mapa_recursos_universo",
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
