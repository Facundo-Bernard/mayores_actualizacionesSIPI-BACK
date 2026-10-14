"""
seed_sudoku.py
Script de siembra inicial de desafíos diarios de Sudoku para la plataforma Mente Activa.
Genera y sincroniza de forma idempotente los meses de Agosto a Diciembre de 2026.
"""

import logging
from app.features.daily_challenges.service import generate_and_save_sudoku_month

logger = logging.getLogger(__name__)

async def seed_sudoku_challenges():
    """Siembra los desafíos de Sudoku para 2026 (Agosto a Diciembre)."""
    logger.info("[SUDOKU SEED] Verificando y sembrando desafíos de Sudoku...")
    total_generated = 0

    # Meses a sembrar inicialmente: Agosto (8) a Diciembre (12) de 2026
    meses_2026 = [8, 9, 10, 11, 12]

    for m in meses_2026:
        res = await generate_and_save_sudoku_month(year=2026, month=m)
        total_generated += res.get("generated_count", 0)

    logger.info(f"[SUDOKU SEED] Sincronización completa: {total_generated} desafíos asegurados en MongoDB.")
