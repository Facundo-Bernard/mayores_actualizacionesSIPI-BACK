"""
wordle_generator.py
Módulo para la selección y generación de desafíos diarios de Wordle (Palabra del Día).
Utiliza el banco ordenado de frecuencia real 'palabras_wordle_5_letras.txt'
e integra consultas a la API de la RAE con caché local y máscara de spoilers.
"""

import os
import re
import time
import json
import logging
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, Any, Set, List, Optional

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DATA_PATH = os.path.join(DATA_DIR, "palabras_wordle_5_letras.txt")
CACHE_PATH = os.path.join(DATA_DIR, "definiciones_cache.json")
ACENTOS_PATH = os.path.join(DATA_DIR, "acentos_todas_palabras.json")

_WORD_POOL: List[str] = []
_DEFINICIONES_CACHE: Dict[str, str] = {}
_ACENTOS_MAP: Dict[str, str] = {}

def _load_acentos_map() -> Dict[str, str]:
    """Carga el mapa de palabras normalizadas a sus formas originales con tilde."""
    global _ACENTOS_MAP
    if _ACENTOS_MAP:
        return _ACENTOS_MAP

    if os.path.exists(ACENTOS_PATH):
        try:
            with open(ACENTOS_PATH, "r", encoding="utf-8") as f:
                _ACENTOS_MAP = json.load(f)
        except Exception as e:
            logger.warning(f"Error cargando mapa de acentos: {e}")
            _ACENTOS_MAP = {}
    return _ACENTOS_MAP

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

def _load_definitions_cache() -> Dict[str, str]:
    """Carga la caché local de definiciones de la RAE desde el archivo JSON."""
    global _DEFINICIONES_CACHE
    if _DEFINICIONES_CACHE:
        return _DEFINICIONES_CACHE

    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                _DEFINICIONES_CACHE = json.load(f)
        except Exception as e:
            logger.warning(f"Error al leer caché de definiciones: {e}")
            _DEFINICIONES_CACHE = {}

    return _DEFINICIONES_CACHE

def _save_definitions_cache():
    """Guarda en disco la caché local de definiciones en JSON."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(_DEFINICIONES_CACHE, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Error al persistir caché de definiciones: {e}")

def clean_and_mask_definition(raw_text: str, word: str) -> Optional[str]:
    """
    Limpia etiquetas gramaticales técnicas de la RAE y tapa la palabra
    con '___' para evitar spoilers en el juego.
    """
    if not raw_text:
        return None

    # Reemplazar símbolos especiales
    text = raw_text.replace("\u2016", " - ").replace("~", "___")

    # Quitar número inicial (ej: "1. ")
    text = re.sub(r"^\s*\d+\.\s*", "", text)

    # Quitar abreviaturas gramaticales al inicio (f., m., adj., tr., intr., etc.)
    text = re.sub(r"^(?:[a-záéíóúñ]+\.\s*)+", "", text, flags=re.IGNORECASE)

    # Quitar sección de sinónimos/antónimos al final
    text = re.sub(r"\s*(?:Sin\.:|Ant\.:|V\.:|Comp\.:|U\. t\. c\.).*$", "", text, flags=re.IGNORECASE)
    text = text.strip()

    if not text or len(text) < 6:
        return None

    # Tapar cualquier mención de la palabra raíz para evitar spoilers (ej: 'playa', 'amigo')
    root_word = word.lower()
    if len(root_word) >= 4:
        # Detectar la palabra o su plural/variación
        pattern = re.compile(rf"\b{re.escape(root_word)}\w*\b", re.IGNORECASE)
        text = pattern.sub("___", text)

    if not text.endswith("."):
        text += "."

    # Capitalizar la primera letra
    text = text[0].upper() + text[1:]
    return text

def fetch_rae_definition(word: str) -> Optional[str]:
    """
    Consulta la definición de una palabra en la RAE.
    1. Revisa primero en la caché local (0 ms).
    2. Prueba forma canónica con tilde (si aplica), forma minúscula directa y lemas singulares.
    3. Maneja rate-limiting (HTTP 429) con reintento automático tras pausa de cortesía.
    4. Guarda el resultado en caché para no volver a consultar a internet.
    """
    cache = _load_definitions_cache()
    word_upper = word.upper().strip()

    if word_upper in cache:
        return cache[word_upper]

    acentos_map = _load_acentos_map()

    # Generar candidatos de búsqueda ordenados por probabilidad de coincidencia en la RAE
    candidates = []
    if word_upper in acentos_map:
        candidates.append(acentos_map[word_upper])
    candidates.append(word_upper.lower())

    # Si es plural, probar el lema en singular (ej: MESES -> mes, HIJOS -> hijo)
    if word_upper.endswith("ES") and len(word_upper) == 5:
        candidates.append(word_upper[:-2].lower())
    elif word_upper.endswith("S") and len(word_upper) == 5:
        candidates.append(word_upper[:-1].lower())

    api_key = os.environ.get("RAE_API_KEY", "")
    if not api_key:
        try:
            from app.core.config import settings
            api_key = settings.RAE_API_KEY or ""
        except Exception:
            api_key = ""

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    if api_key:
        headers["X-API-Key"] = api_key.strip()

    for term in candidates:
        url = f"https://rae-api.com/api/words/{urllib.parse.quote(term)}"
        req = urllib.request.Request(
            url,
            headers=headers
        )

        for attempt in range(2):
            try:
                with urllib.request.urlopen(req, timeout=3.5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    meanings = data.get("data", {}).get("meanings", [])
                    senses = meanings[0].get("senses", []) if meanings else []
                    best_cleaned = None
                    for s in senses:
                        raw_def = s.get("raw", "")
                        cleaned = clean_and_mask_definition(raw_def, word_upper)
                        if cleaned:
                            # Preferir acepciones explicativas completas (más de 3 palabras y no spoiler vacío)
                            words_count = len(cleaned.split())
                            if words_count >= 4 and not cleaned.startswith("___"):
                                best_cleaned = cleaned
                                break
                            elif not best_cleaned:
                                best_cleaned = cleaned

                    if best_cleaned:
                        cache[word_upper] = best_cleaned
                        _save_definitions_cache()
                        return best_cleaned
                break
            except urllib.error.HTTPError as he:
                if he.code == 429 and attempt == 0:
                    logger.warning(f"Límite de tasa RAE (429) para '{term}'. Esperando 1.2s antes de reintentar...")
                    time.sleep(1.2)
                    continue
                break
            except Exception as e:
                logger.debug(f"Error consultando RAE para candidato '{term}': {e}")
                break

    return None

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
