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
import atexit
import random
import logging
import threading
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
_CACHE_LOCK = threading.RLock()

# Caché negativa: evita repetir palabras que ya fallaron (429 o sin acepción) durante un TTL.
_NEGATIVE_CACHE: Dict[str, float] = {}
_NEGATIVE_LOCK = threading.Lock()

# Espaciado global entre llamadas HTTP: los pools concurrentes no saturan la cuota de la RAE.
_CALL_GATE = threading.Lock()
_NEXT_CALL_AT = 0.0

# Persistencia diferida: varias definiciones seguidas generan una sola escritura atómica.
_FLUSH_LOCK = threading.Lock()
_FLUSH_TIMER: Optional[threading.Timer] = None
_DIRTY = False
_LAST_FLUSH = 0.0

def _load_definitions_cache() -> Dict[str, str]:
    """Carga la caché local de definiciones desde el archivo JSON en disco."""
    global _DEFINICIONES_CACHE
    if _DEFINICIONES_CACHE:
        return _DEFINICIONES_CACHE

    with _CACHE_LOCK:
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

def _write_definitions_cache() -> None:
    """Escritura atómica: el archivo final nunca queda a medio escribir."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with _CACHE_LOCK:
            payload = dict(_DEFINICIONES_CACHE)
        tmp_path = f"{CACHE_PATH}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, CACHE_PATH)
    except Exception as e:
        logger.warning(f"[RAE] Error al persistir caché de definiciones: {e}")


def _flush_definitions_cache() -> None:
    global _DIRTY, _LAST_FLUSH
    with _FLUSH_LOCK:
        if not _DIRTY:
            return
        _DIRTY = False
        _LAST_FLUSH = time.monotonic()
        _write_definitions_cache()


def _save_definitions_cache() -> None:
    """Marca la caché como sucia y la persiste como máximo cada RAE_CACHE_FLUSH_SECONDS."""
    global _DIRTY, _FLUSH_TIMER
    interval = max(0.0, float(settings.RAE_CACHE_FLUSH_SECONDS))
    with _FLUSH_LOCK:
        _DIRTY = True
        if interval == 0:
            _DIRTY = False
            _LAST_FLUSH = time.monotonic()
            _write_definitions_cache()
            return
        if _FLUSH_TIMER is None or not _FLUSH_TIMER.is_alive():
            espera = max(0.0, interval - (time.monotonic() - _LAST_FLUSH))
            _FLUSH_TIMER = threading.Timer(espera, _flush_definitions_cache)
            _FLUSH_TIMER.daemon = True
            _FLUSH_TIMER.start()


atexit.register(_flush_definitions_cache)

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

def _negative_key(word: str) -> str:
    return word.upper().strip()


def _is_negative(word: str) -> bool:
    key = _negative_key(word)
    with _NEGATIVE_LOCK:
        expiry = _NEGATIVE_CACHE.get(key)
        if expiry is None:
            return False
        if expiry <= time.monotonic():
            _NEGATIVE_CACHE.pop(key, None)
            return False
        return True


def _mark_negative(word: str) -> None:
    ttl = max(0.0, float(settings.RAE_NEGATIVE_CACHE_TTL_SECONDS))
    if ttl == 0:
        return
    with _NEGATIVE_LOCK:
        _NEGATIVE_CACHE[_negative_key(word)] = time.monotonic() + ttl


def _wait_for_call_slot() -> None:
    """Espacia las llamadas HTTP a nivel global, aunque haya varios hilos consultando."""
    global _NEXT_CALL_AT
    interval = max(0.0, float(settings.RAE_MIN_INTERVAL_MS) / 1000.0)
    if interval == 0:
        return
    with _CALL_GATE:
        now = time.monotonic()
        wait = _NEXT_CALL_AT - now
        if wait < 0:
            wait = 0.0
        _NEXT_CALL_AT = max(now, _NEXT_CALL_AT) + interval
    if wait > 0:
        time.sleep(wait)


def _backoff_delay(attempt: int) -> float:
    base = max(0.0, float(settings.RAE_RETRY_BASE_SECONDS))
    delay = base * (2 ** attempt) + random.uniform(0.0, 0.3)
    max_backoff = max(0.0, float(settings.RAE_MAX_BACKOFF_SECONDS))
    return max(0.0, min(delay, max_backoff))


def _retry_delay(error: urllib.error.HTTPError, attempt: int) -> float:
    retry_after: Optional[float] = None
    try:
        raw = error.headers.get("Retry-After") if error.headers else None
        if raw is not None:
            retry_after = float(raw)
    except (TypeError, ValueError):
        retry_after = None

    if retry_after is None:
        return _backoff_delay(attempt)
    max_backoff = max(0.0, float(settings.RAE_MAX_BACKOFF_SECONDS))
    return max(0.0, min(retry_after, max_backoff))


def fetch_rae_definition(word: str, mask_spoiler: bool = True) -> Optional[str]:
    """
    Consulta la definición de una palabra en la RAE.
    1. Revisa primero la caché local (0 ms) y la caché negativa (fallos recientes).
    2. Prueba forma canónica con tilde (si aplica), forma minúscula directa y lemas singulares.
    3. Espacia las llamadas y reintenta 429/5xx respetando Retry-After.
    4. Persiste los aciertos en caché de forma atómica y diferida.
    """
    cache = _load_definitions_cache()
    word_upper = word.upper().strip()

    # Si la solicitud es con máscara y ya está en caché, devolver de inmediato
    if mask_spoiler and word_upper in cache:
        return cache[word_upper]
    if _is_negative(word_upper):
        return None

    acentos_map = _load_acentos_map()

    # Generar candidatos de búsqueda ordenados por probabilidad de éxito en la RAE
    candidates: List[str] = []
    if word_upper in acentos_map:
        candidates.append(acentos_map[word_upper])
    candidates.append(word_upper.lower())

    # Si es plural, probar el lema en singular (ej: MESES -> mes, HIJOS -> hijo)
    if word_upper.endswith("ES") and len(word_upper) >= 5:
        candidates.append(word_upper[:-2].lower())
    elif word_upper.endswith("S") and len(word_upper) >= 4:
        candidates.append(word_upper[:-1].lower())
    candidates = list(dict.fromkeys(candidates))

    # Obtener API Key desde settings o variables de entorno
    api_key = (settings.RAE_API_KEY or os.environ.get("RAE_API_KEY", "")).strip()

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    if api_key:
        headers["X-API-Key"] = api_key

    max_retries = max(0, int(settings.RAE_MAX_RETRIES))

    for term in candidates:
        url = f"https://rae-api.com/api/words/{urllib.parse.quote(term)}"
        req = urllib.request.Request(url, headers=headers)

        attempt = 0
        while attempt <= max_retries:
            _wait_for_call_slot()
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
                            with _CACHE_LOCK:
                                cache[word_upper] = best_cleaned
                            _save_definitions_cache()
                        return best_cleaned
                break
            except urllib.error.HTTPError as he:
                if he.code == 429:
                    if attempt >= max_retries:
                        _mark_negative(word_upper)
                        return None
                    delay = _retry_delay(he, attempt)
                    logger.warning(
                        f"[RAE] Límite de tasa (429) para '{term}'. Reintentando en {delay:.2f}s "
                        f"({attempt + 1}/{max_retries})."
                    )
                    time.sleep(delay)
                    attempt += 1
                    continue
                if he.code in (500, 502, 503, 504) and attempt < max_retries:
                    delay = _retry_delay(he, attempt)
                    logger.warning(f"[RAE] Error {he.code} para '{term}'. Reintentando en {delay:.2f}s.")
                    time.sleep(delay)
                    attempt += 1
                    continue
                break
            except (urllib.error.URLError, TimeoutError):
                if attempt < max_retries:
                    delay = _backoff_delay(attempt)
                    logger.warning(f"[RAE] Error de red para '{term}'. Reintentando en {delay:.2f}s.")
                    time.sleep(delay)
                    attempt += 1
                    continue
                break
            except Exception as e:
                logger.debug(f"[RAE] Error consultando candidato '{term}': {e}")
                break

    _mark_negative(word_upper)
    return None

def get_masked_definition(word: str) -> Optional[str]:
    """Obtiene la definición de la RAE con la palabra tapada mediante '___' (ideal para juegos y desafíos)."""
    return fetch_rae_definition(word, mask_spoiler=True)

def get_definition(word: str) -> Optional[str]:
    """Obtiene la definición de la RAE limpia en texto claro (ideal para glosarios y diccionarios educativos)."""
    return fetch_rae_definition(word, mask_spoiler=False)
