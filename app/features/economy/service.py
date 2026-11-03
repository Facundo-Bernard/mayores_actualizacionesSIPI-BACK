"""Fachada del servicio de economía.

La implementación está separada por responsabilidad en módulos internos
(``config``, ``points``, ``lives``, ``hints``, ``unlock``, ``admin``). Este
módulo conserva los imports históricos del router y de otros consumidores.
"""

import logging

from app.features.economy.admin import (  # noqa: F401
    adjust_user_economy,
    change_user_subscription,
    find_user_by_identifier,
)
from app.features.economy.config import (  # noqa: F401
    COLL_CONFIG,
    DEFAULT_ECONOMY_CONFIG,
    get_economy_config,
    update_economy_config,
)
from app.features.economy.hints import (  # noqa: F401
    COLL_HINTS,
    _find_hint_challenge,
    _hint_response_from_record,
    _resolve_hint,
    use_hint,
)
from app.features.economy.lives import (  # noqa: F401
    REFILL_LIVES_COST,
    buy_lives,
    consume_life,
    get_user_economy,
    refill_lives,
)
from app.features.economy.points import migrate_guest_points  # noqa: F401
from app.features.economy.unlock import unlock_historical_day  # noqa: F401

logger = logging.getLogger("EconomyService")
