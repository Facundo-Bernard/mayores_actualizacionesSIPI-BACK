"""
rae_client.py
Cliente centralizado y reutilizable para la API no oficial de la RAE (rae-api.com).

Características:
- Autenticación transparente mediante cabecera X-API-Key (usando settings.RAE_API_KEY).
- Caché local persistente en JSON (0ms para palabras previamente consultadas).
- Mapeo fonético y ortográfico de acentos (8.500+ palabras con tilde).
- Búsqueda resiliente por lemas singulares para palabras en plural (ej: 'meses' -> 'mes').
- Selección inteligente de acepciones pedagógicas (evita referencias circulares).
- Máscara de spoilers opcional ('___') para su uso en desafíos y juegos.
"""

import os
import re
import time
import json
import logging
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, Any, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Rutas de datos y caché persistente
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CACHE_PATH = os.path.join(DATA_DIR, "definiciones_cache.json")
ACENTOS_PATH = os.path.join(DATA_DIR, "acentos_todas_palabras.json")

_DEFINICIONES_CACHE: Dict[str, str] = {}
_ACENTOS_MAP: Dict[str, str] = {}

def _load_definitions_cache() -> Dict[str, str]:
    """Carga la caché local de definiciones desde el archivo JSON en disco."""
    global _DEFINICIONES_CACHE
    if _DEFINICIONES_CACHE:
        return _DEFINICIONES_CACHE

    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                _DEFINICIONES_CACHE = json.load(f)
        except Exception as e:
            logger.warning(f"[RAE] Error al leer caché de definiciones: {e}")
            _DEFINICIONES_CACHE = {}

    return _DEFINICIONES_CACHE

def _save_definitions_cache():
    """Persiste en disco la caché local de definiciones en formato JSON."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(_DEFINICIONES_CACHE, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"[RAE] Error al persistir caché de definiciones: {e}")

def _load_acentos_map() -> Dict[str, str]:
    """Carga el diccionario completo de palabras normalizadas a sus formas oficiales con tilde."""
    global _ACENTOS_MAP
    if _ACENTOS_MAP:
        return _ACENTOS_MAP

    if os.path.exists(ACENTOS_PATH):
        try:
            with open(ACENTOS_PATH, "r", encoding="utf-8") as f:
                _ACENTOS_MAP = json.load(f)
        except Exception as e:
            logger.warning(f"[RAE] Error cargando mapa de acentos: {e}")
            _ACENTOS_MAP = {}
    return _ACENTOS_MAP

def clean_and_mask_definition(raw_text: str, word: str, mask_spoiler: bool = True) -> Optional[str]:
    """
    Limpia etiquetas gramaticales técnicas de la RAE y opcionalmente
    tapa la palabra con '___' para evitar spoilers en juegos didácticos.
    """
    if not raw_text:
        return None

    # Reemplazar símbolos técnicos de la RAE
    text = raw_text.replace("\u2016", " - ").replace("~", "___" if mask_spoiler else word.lower())

    # Quitar número inicial de acepción (ej: "1. ")
    text = re.sub(r"^\s*\d+\.\s*", "", text)

    # Quitar abreviaturas gramaticales al inicio (f., m., adj., tr., intr., etc.)
    text = re.sub(r"^(?:[a-záéíóúñ]+\.\s*)+", "", text, flags=re.IGNORECASE)

    # Quitar sección de sinónimos/antónimos al final
    text = re.sub(r"\s*(?:Sin\.:|Ant\.:|V\.:|Comp\.:|U\. t\. c\.).*$", "", text, flags=re.IGNORECASE)
    text = text.lstrip(":.,; ").strip()

    if not text or len(text) < 6:
        return None

    # Si se requiere enmascarar, tapar menciones de la palabra raíz
    if mask_spoiler:
        root_word = word.lower()
        if len(root_word) >= 4:
            pattern = re.compile(rf"\b{re.escape(root_word)}\w*\b", re.IGNORECASE)
            text = pattern.sub("___", text)

    if not text.endswith("."):
        text += "."

    # Capitalizar la primera letra
    text = text[0].upper() + text[1:]
    return text

def fetch_rae_definition(word: str, mask_spoiler: bool = True) -> Optional[str]:
    """
    Consulta la definición de una palabra en la RAE.
    1. Revisa primero en la caché local (0 ms).
    2. Prueba forma canónica con tilde (si aplica), forma minúscula directa y lemas singulares.
    3. Maneja autenticación con X-API-Key y control de límites de tasa (HTTP 429).
    4. Guarda el resultado en caché para no volver a consultar a internet.
    """
    cache = _load_definitions_cache()
    word_upper = word.upper().strip()

    # Si la solicitud es con máscara y ya está en caché, devolver de inmediato
    if mask_spoiler and word_upper in cache:
        return cache[word_upper]

    acentos_map = _load_acentos_map()

    # Generar candidatos de búsqueda ordenados por probabilidad de éxito en la RAE
    candidates = []
    if word_upper in acentos_map:
        candidates.append(acentos_map[word_upper])
    candidates.append(word_upper.lower())

    # Si es plural, probar el lema en singular (ej: MESES -> mes, HIJOS -> hijo)
    if word_upper.endswith("ES") and len(word_upper) >= 5:
        candidates.append(word_upper[:-2].lower())
    elif word_upper.endswith("S") and len(word_upper) >= 4:
        candidates.append(word_upper[:-1].lower())

    # Obtener API Key desde settings o variables de entorno
    api_key = (settings.RAE_API_KEY or os.environ.get("RAE_API_KEY", "")).strip()

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    if api_key:
        headers["X-API-Key"] = api_key

    for term in candidates:
        url = f"https://rae-api.com/api/words/{urllib.parse.quote(term)}"
        req = urllib.request.Request(url, headers=headers)

        for attempt in range(2):
            try:
                with urllib.request.urlopen(req, timeout=3.5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    meanings = data.get("data", {}).get("meanings", [])
                    senses = meanings[0].get("senses", []) if meanings else []
                    best_cleaned = None
                    for s in senses:
                        raw_def = s.get("raw", "")
                        cleaned = clean_and_mask_definition(raw_def, word_upper, mask_spoiler=mask_spoiler)
                        if cleaned:
                            words_count = len(cleaned.split())
                            # Preferir acepciones ricas y descriptivas (> 3 palabras)
                            if words_count >= 4 and not cleaned.startswith("___"):
                                best_cleaned = cleaned
                                break
                            elif not best_cleaned:
                                best_cleaned = cleaned

                    if best_cleaned:
                        if mask_spoiler:
                            cache[word_upper] = best_cleaned
                            _save_definitions_cache()
                        return best_cleaned
                break
            except urllib.error.HTTPError as he:
                if he.code == 429 and attempt == 0:
                    logger.warning(f"[RAE] Límite de tasa (429) para '{term}'. Esperando 1.2s antes de reintentar...")
                    time.sleep(1.2)
                    continue
                break
            except Exception as e:
                logger.debug(f"[RAE] Error consultando candidato '{term}': {e}")
                break

    return None

def get_masked_definition(word: str) -> Optional[str]:
    """Obtiene la definición de la RAE con la palabra tapada mediante '___' (ideal para juegos y desafíos)."""
    return fetch_rae_definition(word, mask_spoiler=True)

def get_definition(word: str) -> Optional[str]:
    """Obtiene la definición de la RAE limpia en texto claro (ideal para glosarios y diccionarios educativos)."""
    return fetch_rae_definition(word, mask_spoiler=False)
