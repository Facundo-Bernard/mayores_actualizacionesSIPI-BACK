"""
challenge_service.py
Generación procedimental de desafíos diarios para el juego narrativo (daily_challenges)
y sembrado automatizado de finalizaciones/derrotas para cada recurso del universo.
"""

import random
import calendar
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List
from fastapi import HTTPException

from app.core.database import get_database
from app.features.narrative.constants import (
    COLL_SETTINGS,
    COLL_CHARACTERS,
    COLL_CARDS,
    COLL_EVENTS,
    COLL_CONVERSATIONS,
    COLL_ENDINGS,
    COLL_CHALLENGES
)
from app.features.narrative.enums import TipoFinalizacionEnum
from app.features.narrative.schemas.catalog_schemas import FinalizacionResponse
from app.features.narrative.admin.crud_service import obtener_finalizaciones

logger = logging.getLogger(__name__)

async def sembrar_finalizaciones_para_universo(universo_id: str) -> List[FinalizacionResponse]:
    """
    Genera automáticamente las finalizaciones de derrota base (<= 0) para cada recurso
    definido en el universo indicado, garantizando aislamiento estricto de textos e ilustraciones.
    """
    db = get_database()
    universo = await db[COLL_SETTINGS].find_one({"_id": universo_id})
    if not universo:
        raise HTTPException(status_code=404, detail=f"Universo '{universo_id}' no encontrado.")

    if universo_id == "corte_medieval":
        default_endings = [
            {
                "_id": "fin_corte_oro_cero",
                "universo_id": "corte_medieval",
                "recurso_clave": "oro",
                "tipo": TipoFinalizacionEnum.DERROTA_RECURSO.value,
                "titulo": "Bancarrota de la Corona",
                "texto": "Las arcas del reino quedaron completamente vacías. La guardia real desertó por falta de paga y los acreedores extranjeros confiscaron los castillos.",
                "imagen": "/assets/narrative/finalizaciones/default.webp",
                "rango": "F"
            },
            {
                "_id": "fin_corte_pueblo_cero",
                "universo_id": "corte_medieval",
                "recurso_clave": "pueblo",
                "tipo": TipoFinalizacionEnum.DERROTA_RECURSO.value,
                "titulo": "Revolución Popular",
                "texto": "El pueblo hambriento y descontento derribó los portones del palacio. La muchedumbre desconoció las leyes de la corona y la corte debió huir al exilio.",
                "imagen": "/assets/narrative/finalizaciones/default.webp",
                "rango": "F"
            },
            {
                "_id": "fin_corte_nobleza_cero",
                "universo_id": "corte_medieval",
                "recurso_clave": "nobleza",
                "tipo": TipoFinalizacionEnum.DERROTA_RECURSO.value,
                "titulo": "Golpe de Estado Feudal",
                "texto": "Los señores feudales y nobles terratenientes desconocieron tu linaje. Formaron un concejo militar conjunto y fuiste depuesto sin derramamiento de sangre.",
                "imagen": "/assets/narrative/finalizaciones/default.webp",
                "rango": "F"
            },
            {
                "_id": "fin_corte_fe_cero",
                "universo_id": "corte_medieval",
                "recurso_clave": "fe",
                "tipo": TipoFinalizacionEnum.DERROTA_RECURSO.value,
                "titulo": "Excomunión Papal",
                "texto": "El clero te declaró en apostasía y herejía. Sin la bendición de la Iglesia, los súbditos fueron liberados de sus votos de lealtad y el reino cayó en cisma.",
                "imagen": "/assets/narrative/finalizaciones/default.webp",
                "rango": "F"
            },
            {
                "_id": "fin_corte_ejercito_cero",
                "universo_id": "corte_medieval",
                "recurso_clave": "ejercito",
                "tipo": TipoFinalizacionEnum.DERROTA_RECURSO.value,
                "titulo": "Invasión Bárbara",
                "texto": "Sin un ejército disciplinado que vigile las fronteras, hordas invasoras saquearon las ciudades indefensas y redujeron el reino a cenizas.",
                "imagen": "/assets/narrative/finalizaciones/default.webp",
                "rango": "F"
            }
        ]
        for end_data in default_endings:
            await db[COLL_ENDINGS].replace_one({"_id": end_data["_id"]}, end_data, upsert=True)
    else:
        for rec in universo.get("recursos", []):
            clave = rec["clave"]
            nombre = rec["nombre"]
            ending_id = f"fin_{universo_id}_{clave}_cero"
            ending_doc = {
                "_id": ending_id,
                "universo_id": universo_id,
                "recurso_clave": clave,
                "tipo": TipoFinalizacionEnum.DERROTA_RECURSO.value,
                "titulo": f"Colapso de {nombre}",
                "texto": f"El reino sucumbió al agotarse completamente el recurso vital '{nombre}'. La administración se derrumbó y el mandato concluyó en ruina.",
                "imagen": "/assets/narrative/finalizaciones/default.webp",
                "rango": "F"
            }
            await db[COLL_ENDINGS].replace_one({"_id": ending_id}, ending_doc, upsert=True)

    return await obtener_finalizaciones(universo_id=universo_id)

async def sembrar_finalizaciones_default():
    """Siembra los finales por defecto de los universos activos al arrancar el backend."""
    try:
        db = get_database()
        total_endings = await db[COLL_ENDINGS].count_documents({})
        if total_endings == 0:
            universos = await db[COLL_SETTINGS].find().to_list(length=100)
            for u in universos:
                await sembrar_finalizaciones_para_universo(u["_id"])
    except Exception as e:
        logger.warning(f"Aviso al sembrar finalizaciones por defecto: {e}")

async def generar_mes_narrativo(year: int, month: int, universo_id: str) -> Dict[str, Any]:
    """Genera proceduralmente los desafíos diarios del mes para el juego narrativo."""
    db = get_database()
    universo = await db[COLL_SETTINGS].find_one({"_id": universo_id})
    if not universo:
        raise HTTPException(status_code=404, detail=f"Universo '{universo_id}' no encontrado.")

    pjs = await db[COLL_CHARACTERS].find({"universo_id": universo_id}).to_list(None)
    cartas = await db[COLL_CARDS].find({"universo_id": universo_id}).to_list(None)
    eventos = await db[COLL_EVENTS].find({"universo_id": universo_id}).to_list(None)
    convs = await db[COLL_CONVERSATIONS].find({"universo_id": universo_id}).to_list(None)

    if len(pjs) < 5:
        raise HTTPException(status_code=400, detail=f"Se requieren al menos 5 personajes en el universo '{universo_id}' (hay {len(pjs)}).")
    if len(cartas) < 5:
        raise HTTPException(status_code=400, detail=f"Se requieren al menos 5 cartas en el universo '{universo_id}' (hay {len(cartas)}).")

    pj_ids = [p["_id"] for p in pjs]
    carta_ids = [c["_id"] for c in cartas]
    evento_ids = [e["_id"] for e in eventos]
    conv_ids = [c["_id"] for c in convs]

    num_days = calendar.monthrange(year, month)[1]
    created = 0
    updated = 0

    recursos_iniciales = {r["clave"]: r.get("inicial", 50) for r in universo.get("recursos", [])}

    for day in range(1, num_days + 1):
        date_str = f"{year:04d}-{month:02d}-{day:02d}"
        seed_str = f"narrativo_{universo_id}_{date_str}"
        rng = random.Random(seed_str)

        setup_corte = rng.sample(pj_ids, 5)
        setup_cartas = rng.sample(carta_ids, 5)

        cartas_mensuales_pool = [c for c in carta_ids if c not in setup_cartas]
        if len(cartas_mensuales_pool) < 6:
            cartas_mensuales_pool = carta_ids

        challenge_doc = {
            "game_id": "narrativo",
            "date": date_str,
            "difficulty": "normal",
            "universo_id": universo_id,
            "title": f"Desafío Real - {date_str}",
            "description": f"Goberná el reino de {universo.get('nombre', universo_id)} durante 12 meses.",
            "config": {
                "universo_id": universo_id,
                "atributos_iniciales": recursos_iniciales,
                "setup_corte_ofrecidos_ids": setup_corte,
                "setup_cartas_ofrecidas_ids": setup_cartas,
                "pool_cartas_mensuales_ids": cartas_mensuales_pool,
                "pool_eventos_disponibles_ids": evento_ids,
                "pool_conversaciones_ids": conv_ids
            },
            "created_at": datetime.now(timezone.utc)
        }

        res = await db[COLL_CHALLENGES].replace_one(
            {"game_id": "narrativo", "date": date_str, "difficulty": "normal"},
            challenge_doc,
            upsert=True
        )
        if res.upserted_id:
            created += 1
        else:
            updated += 1

    return {
        "success": True,
        "year": year,
        "month": month,
        "universo_id": universo_id,
        "dias_procesados": num_days,
        "desafios_creados": created + updated,
        "creados": created,
        "actualizados": updated
    }
