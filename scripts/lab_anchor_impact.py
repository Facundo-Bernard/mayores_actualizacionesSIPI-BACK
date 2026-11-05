"""
lab_anchor_impact.py
Mide el impacto de prefijar 1 o 2 palabras ("anclas") al resolver máscaras 11x11.

Condiciones:
  base      - sin anclas
  sol1/sol2 - 1 o 2 anclas tomadas de la solución original del tablero growth
              (compatibles por construcción; mide reducción de búsqueda)
  com1/com2 - 1 o 2 anclas elegidas por el "operador" entre palabras con
              definición conocida (curadas/caché RAE); pueden sobre-restringir
              (mide riesgo de publicación)

Métrica principal: éxito en un intento de 150k nodos (primer presupuesto del
validador) y éxito implícito con 6 reintentos: 1 - (1-p)^6.
"""
import json
import random
import statistics
import sys
import time
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

sys.path.insert(0, ".")

from app.core.rae_client import _load_definitions_cache
from app.features.daily_challenges.crucigrama.clues import CURATED_CLUES
from app.features.daily_challenges.crucigrama import solver as S
from app.features.daily_challenges.crucigrama.growth import generate_growth_board
from app.features.daily_challenges.crucigrama.solver import _parse_template_slots

N = 11
N_MASKS = 16
SEEDS = 6
BUDGET = 150_000
OUT = "scripts/anchor_lab_results.json"


def solve_with_anchors(
    slots: List[Dict],
    intersections: Dict[str, List[Tuple[int, str, int]]],
    rng: random.Random,
    preassigned: Dict[str, str],
    max_nodes: Optional[int] = None,
    max_candidates: int = 150,
) -> Tuple[Optional[Dict[str, str]], int]:
    S._init_word_index()
    if not S._WORDS_BY_LEN:
        return None, 0

    by_id = {s["id"]: s for s in slots}
    assignment: Dict[str, str] = {}
    used: Set[str] = set()

    for sid, word in preassigned.items():
        slot = by_id[sid]
        if len(word) != slot["len"]:
            return None, 0
        assignment[sid] = word
        used.add(word)

    # Verificar coherencia de anclas en sus cruces mutuos
    for sid, word in preassigned.items():
        for my_pos, other_id, other_pos in intersections[sid]:
            if other_id in preassigned and preassigned[other_id][other_pos] != word[my_pos]:
                return None, 0

    cached_defs = _load_definitions_cache()
    sorted_slots = sorted(slots, key=lambda s: len(intersections[s["id"]]), reverse=True)
    nodes = [0]

    def backtrack(idx: int) -> Optional[Dict[str, str]]:
        if max_nodes is not None and nodes[0] >= max_nodes:
            return None
        nodes[0] += 1

        if idx == len(sorted_slots):
            return assignment

        slot = sorted_slots[idx]
        s_id = slot["id"]
        if s_id in assignment:
            return backtrack(idx + 1)

        s_len = slot["len"]
        constraints = []
        for my_pos, other_id, other_pos in intersections[s_id]:
            if other_id in assignment:
                constraints.append((my_pos, assignment[other_id][other_pos]))

        if constraints:
            cands = None
            for pos, ch in constraints:
                s_set = S._LETTER_POS_INDEX.get((s_len, pos, ch), set())
                cands = s_set if cands is None else cands & s_set
            cand_list = [w for w in (cands or []) if w not in used]
        else:
            cand_list = [w for w in S._WORDS_BY_LEN.get(s_len, []) if w not in used]

        cand_list.sort()
        if not cand_list:
            return None

        for w in S._order_candidates(cand_list, cached_defs, rng, prefer_curated=False)[:max_candidates]:
            assignment[s_id] = w
            used.add(w)
            res = backtrack(idx + 1)
            if res is not None:
                return res
            del assignment[s_id]
            used.remove(w)

        return None

    if len(assignment) == len(slots):
        return dict(assignment), 0
    return backtrack(0), nodes[0]


def build_masks() -> List[Dict]:
    masks = []
    seen = set()
    for i in range(60):
        if len(masks) >= N_MASKS:
            break
        rng = random.Random(f"anchor-base-{i}")
        board = generate_growth_board(N, rng, min_words=15, max_words=28)
        if not board:
            continue
        rows, words = board
        pattern = ["".join("." if ch != "#" else "#" for ch in row) for row in rows]
        key = tuple(pattern)
        if key in seen:
            continue
        seen.add(key)
        slots, inter = _parse_template_slots(pattern)
        by_id = {s["id"]: s for s in slots}
        solution = {}
        for w in words:
            sid = f"{w['dir']}_{w['row']}_{w['col']}"
            if sid in by_id and by_id[sid]["len"] == len(w["word"]):
                solution[sid] = w["word"]
        # La solución de growth debe cubrir todos los slots
        if len(solution) != len(slots):
            continue
        masks.append({
            "id": i,
            "pattern": pattern,
            "slots": slots,
            "inter": inter,
            "solution": solution,
        })
    return masks


def common_pool() -> Dict[int, List[str]]:
    words = set(CURATED_CLUES) | set(_load_definitions_cache())
    pool: Dict[int, List[str]] = defaultdict(list)
    for w in words:
        w = w.upper()
        if w.isalpha() and S.MIN_WORD_LEN <= len(w) <= S.MAX_WORD_LEN:
            pool[len(w)].append(w)
    for length in pool:
        pool[length].sort()
    return pool


def pick_solution_anchors(
    mask: Dict, count: int, rng: random.Random, strategy: str = "random"
) -> Optional[Dict[str, str]]:
    candidates = [s for s in mask["slots"] if len(mask["solution"][s["id"]]) >= 4]
    if len(candidates) < count:
        return None
    if strategy == "degree":
        ordered = sorted(
            candidates, key=lambda s: (-len(mask["inter"][s["id"]]), s["id"])
        )
        chosen = ordered[:count]
    else:
        chosen = rng.sample(sorted(candidates, key=lambda s: s["id"]), count)
    return {s["id"]: mask["solution"][s["id"]] for s in chosen}


def pick_common_anchors(
    mask: Dict, count: int, pool: Dict[int, List[str]], rng: random.Random
) -> Optional[Dict[str, str]]:
    slots = [s for s in mask["slots"] if s["len"] >= 4]
    if len(slots) < count:
        return None
    for _ in range(200):
        chosen = rng.sample(slots, count)
        anchors = {}
        ok = True
        for s in chosen:
            options = pool.get(s["len"], [])
            if not options:
                ok = False
                break
            anchors[s["id"]] = options[rng.randrange(len(options))]
        if not ok:
            continue
        for sid, word in anchors.items():
            for my_pos, other_id, other_pos in mask["inter"][sid]:
                if other_id in anchors and anchors[other_id][other_pos] != word[my_pos]:
                    ok = False
                    break
            if not ok:
                break
        if ok:
            return anchors
    return None


def run_condition(masks, condition, picker, seeds=SEEDS):
    runs = []
    for mask in masks:
        for seed in range(seeds):
            rng_pick = random.Random(f"{condition}-pick-{mask['id']}-{seed}")
            anchors = picker(mask, rng_pick) if picker else {}
            if anchors is None:
                continue
            rng = random.Random(f"{condition}-solve-{mask['id']}-{seed}")
            t0 = time.perf_counter()
            solution, nodes = solve_with_anchors(
                mask["slots"], mask["inter"], rng, anchors, max_nodes=BUDGET
            )
            elapsed = (time.perf_counter() - t0) * 1000
            runs.append({
                "mask": mask["id"],
                "seed": seed,
                "anchors": anchors,
                "success": solution is not None,
                "nodes": nodes,
                "ms": round(elapsed, 1),
            })
    return runs


def summarize(condition, runs):
    ok = [r for r in runs if r["success"]]
    p = len(ok) / len(runs) if runs else 0.0
    per_mask = defaultdict(list)
    for r in runs:
        per_mask[r["mask"]].append(r["success"])
    implied = statistics.mean(
        1 - (1 - sum(v) / len(v)) ** 6 for v in per_mask.values() if v
    ) if per_mask else 0.0
    return {
        "condition": condition,
        "runs": len(runs),
        "success": len(ok),
        "p": round(p, 4),
        "implied_6_attempts": round(implied, 4),
        "median_nodes_ok": int(statistics.median(r["nodes"] for r in ok)) if ok else None,
        "mean_ms_ok": round(statistics.mean(r["ms"] for r in ok), 1) if ok else None,
        "median_ms_all": round(statistics.median(r["ms"] for r in runs), 1) if runs else None,
    }


def main():
    masks = build_masks()
    print(f"máscaras: {len(masks)}", flush=True)
    pool = common_pool()

    conditions = [
        ("base", None),
        ("sol1_rand", lambda m, r: pick_solution_anchors(m, 1, r, "random")),
        ("sol2_rand", lambda m, r: pick_solution_anchors(m, 2, r, "random")),
        ("sol1_deg", lambda m, r: pick_solution_anchors(m, 1, r, "degree")),
        ("sol2_deg", lambda m, r: pick_solution_anchors(m, 2, r, "degree")),
        ("sol3_deg", lambda m, r: pick_solution_anchors(m, 3, r, "degree")),
        ("com1", lambda m, r: pick_common_anchors(m, 1, pool, r)),
        ("com2", lambda m, r: pick_common_anchors(m, 2, pool, r)),
    ]

    results = {}
    for name, picker in conditions:
        t0 = time.time()
        runs = run_condition(masks, name, picker)
        summary = summarize(name, runs)
        results[name] = {"summary": summary, "runs": runs}
        print(
            f"[{name}] n={summary['runs']} p={summary['p']:.3f} "
            f"impl6={summary['implied_6_attempts']:.3f} "
            f"nodos_ok={summary['median_nodes_ok']} ms_ok={summary['mean_ms_ok']} "
            f"({time.time()-t0:.0f}s)",
            flush=True,
        )

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("resultados:", OUT)


if __name__ == "__main__":
    main()
