"""
generator.py
Orquestador del Crucigrama con dos dificultades:

- facil: tablero 7x7 con plantillas simétricas + backtracking CSP, pistas
  curadas pedagógicas (CURATED_CLUES) y definiciones RAE como respaldo.
- dificil: tablero 11x11 generado por crecimiento (growth.py) con definiciones
  formales de la RAE.

La salida de ambas es el mismo contrato: {theme, grid_size, cells, words,
total_words, date}. `cells` describe la grilla con bloques/números/punteros,
igual que el formato previo, solo que `grid_size` varía (7 u 11).
"""

import concurrent.futures
import logging
import random
import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from app.core.config import settings
from app.core.rae_client import fetch_rae_definition
from app.features.daily_challenges.crucigrama.clues import CURATED_CLUES
from app.features.daily_challenges.crucigrama.growth import generate_growth_board
from app.features.daily_challenges.crucigrama.solver import (
    _parse_template_slots,
    _solve_crucigrama_backtracking,
    normalize_word,
)
from app.features.daily_challenges.crucigrama.templates_facil import CRUCIGRAMA_TEMPLATES

logger = logging.getLogger(__name__)

DIFF_FACIL = "facil"
DIFF_DIFICIL = "dificil"
DIFICIL_SIZE = 11


def _parse_and_build_challenge(
    theme: str,
    grid_raw: List[str],
    prefer_curated: bool = True,
    clue_overrides: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Analiza una grilla resuelta, asigna números en orden occidental, construye
    la matriz de celdas con bloques/punteros y enriquece las pistas con la RAE.

    prefer_curated=True (facil): pistas curadas primero, RAE como respaldo.
    prefer_curated=False (dificil): definiciones formales de la RAE.
    clue_overrides permite fijar pistas propias por palabra (palabra -> pista).
    """
    R = len(grid_raw)
    C = len(grid_raw[0]) if R else 0
    grid_raw = [row.ljust(C, "#")[:C] for row in grid_raw]

    num = 1
    across_words = []
    down_words = []
    cell_numbers = [[None for _ in range(C)] for _ in range(R)]
    cell_across = [[None for _ in range(C)] for _ in range(R)]
    cell_down = [[None for _ in range(C)] for _ in range(R)]

    for r in range(R):
        for c in range(C):
            ch = grid_raw[r][c]
            if ch == "#":
                continue

            is_a_start = (c == 0 or grid_raw[r][c - 1] == "#") and (c + 1 < C and grid_raw[r][c + 1] != "#")
            is_d_start = (r == 0 or grid_raw[r - 1][c] == "#") and (r + 1 < R and grid_raw[r + 1][c] != "#")

            assigned_num = None
            if is_a_start or is_d_start:
                assigned_num = num
                cell_numbers[r][c] = num
                num += 1

            if is_a_start:
                w_chars = []
                coords = []
                cc = c
                while cc < C and grid_raw[r][cc] != "#":
                    w_chars.append(grid_raw[r][cc])
                    coords.append([r, cc])
                    cell_across[r][cc] = assigned_num
                    cc += 1
                word_str = "".join(w_chars)
                across_words.append({
                    "id": f"H{assigned_num}",
                    "number": assigned_num,
                    "direction": "horizontal",
                    "word": word_str,
                    "length": len(word_str),
                    "row": r,
                    "col": c,
                    "coords": coords,
                    "clue": CURATED_CLUES.get(word_str, f"Palabra de {len(word_str)} letras."),
                })

            if is_d_start:
                w_chars = []
                coords = []
                rr = r
                while rr < R and grid_raw[rr][c] != "#":
                    w_chars.append(grid_raw[rr][c])
                    coords.append([rr, c])
                    cell_down[rr][c] = assigned_num
                    rr += 1
                word_str = "".join(w_chars)
                down_words.append({
                    "id": f"V{assigned_num}",
                    "number": assigned_num,
                    "direction": "vertical",
                    "word": word_str,
                    "length": len(word_str),
                    "row": r,
                    "col": c,
                    "coords": coords,
                    "clue": CURATED_CLUES.get(word_str, f"Palabra de {len(word_str)} letras."),
                })

    # Enriquecer pistas con la RAE y limpiar prefijos.
    # Las consultas RAE son independientes por palabra: se paralelizan para no
    # demorar la generación (cada palabra suele tardar ~0.8s en red).
    all_words = across_words + down_words
    overrides = {
        str(k).strip().upper(): str(v).strip()
        for k, v in (clue_overrides or {}).items()
        if str(v or "").strip()
    }

    def _resolve_clue(item: Dict[str, Any]) -> str:
        w = item["word"]
        if w in overrides:
            return overrides[w]
        if prefer_curated and w in CURATED_CLUES:
            return CURATED_CLUES[w]
        rae_def = fetch_rae_definition(w)
        if rae_def:
            return rae_def
        return f"Palabra de {len(w)} letras que comienza con '{w[0]}' y termina en '{w[-1]}'."

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=max(1, min(settings.RAE_MAX_CONCURRENCY, len(all_words) or 1))
    ) as executor:
        raw_clues = list(executor.map(_resolve_clue, all_words))

    for item, raw_clue in zip(all_words, raw_clues):
        clean_clue = re.sub(r"^definici[oó]n\s*[:\-]?\s*", "", raw_clue, flags=re.IGNORECASE).strip()
        item["clue"] = clean_clue

    # Construir matriz de celdas serializable
    cells = []
    for r in range(R):
        row_cells = []
        for c in range(C):
            ch = grid_raw[r][c]
            is_block = (ch == "#")
            row_cells.append({
                "row": r,
                "col": c,
                "is_block": is_block,
                "letter": "" if is_block else ch,
                "number": cell_numbers[r][c],
                "across_num": cell_across[r][c],
                "down_num": cell_down[r][c],
            })
        cells.append(row_cells)

    return {
        "theme": theme,
        "grid_size": R,
        "cells": cells,
        "words": all_words,
        "total_words": len(all_words),
    }


def build_challenge_from_solution(
    theme: str,
    solution_grid: List[str],
    prefer_curated: bool = False,
    clue_overrides: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Construye el contrato completo del desafío a partir de una grilla resuelta
    (por ejemplo, la solución de una máscara diseñada en el panel admin).
    """
    return _parse_and_build_challenge(
        theme,
        solution_grid,
        prefer_curated=prefer_curated,
        clue_overrides=clue_overrides,
    )


def _generate_facil(
    date_str: str, rng: random.Random, banned: Set[str] = frozenset()
) -> Tuple[str, List[str]]:
    seed_val = int(date_str.replace("-", ""))
    tmpl_data = CRUCIGRAMA_TEMPLATES[seed_val % len(CRUCIGRAMA_TEMPLATES)]
    theme = tmpl_data.get("theme", "Palabras Cruzadas")
    pattern = tmpl_data["pattern"]

    slots, intersections = _parse_template_slots(pattern)
    solution = _solve_crucigrama_backtracking(
        slots, intersections, rng, prefer_curated=True, banned_words=banned
    )

    if solution:
        R = len(pattern)
        C = len(pattern[0]) if R else 0
        grid_letters = [["#" if pattern[r][c] == "#" else "" for c in range(C)] for r in range(R)]
        for s in slots:
            word = solution[s["id"]]
            for (r, c), ch in zip(s["coords"], word):
                grid_letters[r][c] = ch
        final_grid = ["".join(row) for row in grid_letters]
    else:
        logger.warning(f"[CRUCIGRAMA] Backtracking sin solución para {date_str} (facil). Usando tablero curado de respaldo.")
        final_grid = tmpl_data["fallback_grid"]

    return theme, final_grid


def _generate_dificil(
    date_str: str, rng: random.Random, banned: Set[str] = frozenset()
) -> Tuple[str, List[str]]:
    result = generate_growth_board(
        DIFICIL_SIZE, rng, min_words=15, max_words=28, banned_words=banned
    )
    if result is None:
        raise RuntimeError("No se pudo generar el crucigrama difícil (índice de palabras vacío).")
    final_grid, words = result
    if len(words) < 15:
        logger.warning(f"[CRUCIGRAMA] Difícil {date_str}: solo {len(words)} palabras (objetivo 15).")
    return "Palabras Cruzadas", final_grid


def generate_crucigrama_challenge_for_date(
    date_str: str, difficulty: str = DIFF_FACIL, banned_words: Optional[Iterable[str]] = None
) -> Dict[str, Any]:
    """
    Genera la configuración completa del desafío de Crucigrama para una fecha.

    Determinista: misma fecha + dificultad produce el mismo tablero en cualquier
    servidor (todo el azar sale de un `random.Random` sembrado por fecha y nivel).
    `banned_words` (vetos globales) se excluye del pool de candidatos.
    """
    diff = (difficulty or DIFF_FACIL).lower().strip()
    rng = random.Random(f"crucigrama_{date_str}_{diff}")
    banned: Set[str] = {
        normalize_word(word) for word in (banned_words or ()) if normalize_word(word)
    }

    if diff == DIFF_DIFICIL:
        theme, final_grid = _generate_dificil(date_str, rng, banned)
        challenge = _parse_and_build_challenge(theme, final_grid, prefer_curated=False)
    else:
        theme, final_grid = _generate_facil(date_str, rng, banned)
        challenge = _parse_and_build_challenge(theme, final_grid, prefer_curated=True)

    infractoras = sorted({w["word"] for w in challenge.get("words", [])} & banned)
    if infractoras:
        logger.warning(
            f"[CRUCIGRAMA] {date_str} ({diff}): tablero de respaldo con palabras vetadas: "
            f"{', '.join(infractoras)}."
        )

    challenge["date"] = date_str
    return challenge
