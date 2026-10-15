"""
wordle_generator.py
Módulo para la selección y generación de desafíos diarios de Wordle (Palabra del Día).
Utiliza el banco ordenado de frecuencia real 'palabras_wordle_5_letras.txt'
e integra consultas a la API de la RAE con caché local y máscara de spoilers.
"""

import os
import logging
from typing import Dict, Any, Set, List, Optional

from app.core.rae_client import (
    fetch_rae_definition,
    clean_and_mask_definition,
    get_masked_definition,
    get_definition,
)

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DATA_PATH = os.path.join(DATA_DIR, "palabras_wordle_5_letras.txt")

_WORD_POOL: List[str] = []

def _load_word_pool() -> List[str]:
    """Carga en memoria la lista de palabras limpias de 5 letras ordenadas por frecuencia."""
    global _WORD_POOL
    if _WORD_POOL:
        return _WORD_POOL

    if not os.path.exists(DATA_PATH):
        logger.warning(f"No se encontró el archivo de palabras en {DATA_PATH}.")
        return []

    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            _WORD_POOL = [line.strip().upper() for line in f if len(line.strip()) == 5]
    except Exception as e:
        logger.error(f"Error cargando palabras de Wordle: {e}")
        _WORD_POOL = []

    return _WORD_POOL

def generate_wordle_hints(word: str) -> List[str]:
    """
    Genera pistas pedagógicas y claras para personas mayores.
    Prioriza la definición real de la RAE con máscara '___' y fallback a vocales.
    """
    rae_def = fetch_rae_definition(word)

    if rae_def:
        pista_1 = f"Definición: {rae_def}"
    else:
        # Fallback si no hay conexión o no se encontró definición
        vocales = sorted(list(set(c for c in word if c in "AEIOU")))
        vocales_str = ", ".join(vocales) if vocales else "ninguna vocal común"
        pista_1 = f"Contiene las vocales ({vocales_str}) y termina con la letra '{word[-1]}'."

    pista_2 = f"La primera letra de la palabra es la '{word[0]}'."
    return [pista_1, pista_2]

def pick_wordle_word(used_words: Set[str], fallback_index: int = 0) -> str:
    """
    Selecciona la siguiente palabra de mayor frecuencia en español que no haya sido jugada todavía.
    """
    pool = _load_word_pool()
    if not pool:
        return "PLAYA"

    for w in pool:
        if w not in used_words:
            return w

    return pool[fallback_index % len(pool)]

def generate_wordle_challenge(date_str: str, used_words: Set[str], index: int = 0) -> Dict[str, Any]:
    """Genera la configuración completa del desafío de Wordle para una fecha específica."""
    word = pick_wordle_word(used_words, fallback_index=index)
    hints = generate_wordle_hints(word)

    return {
        "solution": word,
        "word_length": 5,
        "max_attempts": 6,
        "hints": hints
    }
