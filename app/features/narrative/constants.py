"""
Constantes de nombres de colecciones en MongoDB para el motor narrativo.
"""

COLL_SETTINGS = "narrative_settings"
COLL_CHARACTERS = "narrative_characters"
COLL_CARDS = "narrative_cards"
COLL_RESULTS = "narrative_results"
COLL_EVENTS = "narrative_events"
COLL_CONVERSATIONS = "narrative_conversations"
COLL_ENDINGS = "narrative_endings"
COLL_RUNS = "narrative_runs"
COLL_RUNS_ARCHIVE = "narrative_runs_archive"
COLL_ACTIONS = "narrative_actions"
COLL_FREQUENCIES = "narrative_frequencies"
COLL_CHALLENGES = "daily_challenges"
COLL_USER_ATTEMPTS = "user_attempts"

# Colecciones V2 dedicadas para grafos de decisión
COLL_V2_EVENTS = "narrative_v2_events"
COLL_V2_CONVERSATIONS = "narrative_v2_conversations"
COLL_V2_EVENTOS_ESPECIALES = "narrative_v2_eventos_especiales"

# Umbrales de afinidad para disparar eventos especiales de lealtad / traición
AFINIDAD_UMBRAL_LEALTAD = 95
AFINIDAD_UMBRAL_TRAICION = 15

# Marca de protocolo de comandos (recibos + obligación económica embebidos).
# Las rutas legacy no pueden mutar runs con esta marca.
PROTOCOLO_V3 = "v3"
