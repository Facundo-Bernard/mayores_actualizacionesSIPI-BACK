"""Configuración global de economía (lectura, actualización y defaults)."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.core.database import get_database
from app.features.economy.schemas import (
    DEFAULT_ESCALAS_TIEMPO,
    EconomyConfigResponse,
    EconomyConfigUpdateRequest,
    EscalaCalificacionTiempo,
)

logger = logging.getLogger("EconomyService")

COLL_CONFIG = "configuracion_economia"

DEFAULT_ECONOMY_CONFIG: Dict[str, Any] = {
    "_id": "global_economy",
    "vidas_iniciales": 5,
    "costo_desbloqueo_dia_puntos": 100,
    "costo_pista_puntos": 20,
    "puntos_por_calificacion": {
        "S": 100,
        "A": 90,
        "B": 75,
        "C": 50,
        "F": 0,
    },
    "guest_migration_max_points": 1000,
    "escalas_tiempo_por_juego": DEFAULT_ESCALAS_TIEMPO,
    "paquetes_tienda": [
        {"id": "pack_1", "vidas": 1, "puntos": 50, "popular": False, "badge": None, "descuento": None},
        {"id": "pack_3", "vidas": 3, "puntos": 120, "popular": True, "badge": "Popular", "descuento": "Ahorrá 30 pts"},
        {"id": "pack_5", "vidas": 5, "puntos": 180, "popular": False, "badge": "Mejor valor", "descuento": "Ahorrá 70 pts"},
    ],
    "puntos_por_juego": {
        "wordle": 50,
        "sopa_letras": 50,
        "sudoku": 60,
        "crucigrama": 70,
        "narrativo": 80,
    },
    "updated_at": datetime.now(timezone.utc).isoformat(),
}


async def get_economy_config() -> EconomyConfigResponse:
    """
    Obtiene la configuración económica global de la base de datos.
    Si no existe, la siembra automáticamente con valores predeterminados seguros.
    """
    db = get_database()
    doc = await db[COLL_CONFIG].find_one({"_id": "global_economy"})
    if not doc:
        now_str = datetime.now(timezone.utc).isoformat()
        initial = dict(DEFAULT_ECONOMY_CONFIG)
        initial["updated_at"] = now_str
        await db[COLL_CONFIG].update_one(
            {"_id": "global_economy"},
            {"$setOnInsert": initial},
            upsert=True,
        )
        doc = await db[COLL_CONFIG].find_one({"_id": "global_economy"}) or initial

    raw_escalas = doc.get("escalas_tiempo_por_juego") or DEFAULT_ESCALAS_TIEMPO
    escalas_map: Dict[str, List[EscalaCalificacionTiempo]] = {}
    for gid, items in raw_escalas.items():
        escalas_map[gid] = [EscalaCalificacionTiempo(**item) for item in items]

    return EconomyConfigResponse(
        vidas_iniciales=int(doc.get("vidas_iniciales", 5)),
        costo_desbloqueo_dia_puntos=int(doc.get("costo_desbloqueo_dia_puntos", 100)),
        costo_pista_puntos=int(doc.get("costo_pista_puntos", 20)),
        puntos_por_calificacion=doc.get("puntos_por_calificacion", DEFAULT_ECONOMY_CONFIG["puntos_por_calificacion"]),
        escalas_tiempo_por_juego=escalas_map,
        puntos_por_juego=doc.get("puntos_por_juego", DEFAULT_ECONOMY_CONFIG["puntos_por_juego"]),
        guest_migration_max_points=int(
            doc.get("guest_migration_max_points", DEFAULT_ECONOMY_CONFIG["guest_migration_max_points"])
        ),
        updated_at=str(doc.get("updated_at", "")),
    )


async def update_economy_config(req: EconomyConfigUpdateRequest) -> EconomyConfigResponse:
    """
    Actualiza la configuración económica desde la Torre de Control (Panel Administrador).
    """
    db = get_database()
    update_fields: Dict[str, Any] = {}

    if req.vidas_iniciales is not None:
        update_fields["vidas_iniciales"] = max(1, req.vidas_iniciales)
    if req.costo_desbloqueo_dia_puntos is not None:
        update_fields["costo_desbloqueo_dia_puntos"] = max(0, req.costo_desbloqueo_dia_puntos)
    if req.costo_pista_puntos is not None:
        update_fields["costo_pista_puntos"] = max(0, req.costo_pista_puntos)
    if req.puntos_por_calificacion is not None:
        update_fields["puntos_por_calificacion"] = req.puntos_por_calificacion
    if req.escalas_tiempo_por_juego is not None:
        update_fields["escalas_tiempo_por_juego"] = {
            gid: [item.model_dump() for item in items]
            for gid, items in req.escalas_tiempo_por_juego.items()
        }
    if req.puntos_por_juego is not None:
        update_fields["puntos_por_juego"] = req.puntos_por_juego
    if req.guest_migration_max_points is not None:
        update_fields["guest_migration_max_points"] = max(0, req.guest_migration_max_points)

    update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db[COLL_CONFIG].update_one(
        {"_id": "global_economy"},
        {"$set": update_fields},
        upsert=True,
    )
    logger.info(f"[ECONOMIA] Configuración actualizada: {list(update_fields.keys())}")
    return await get_economy_config()
