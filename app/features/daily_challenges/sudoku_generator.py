"""
sudoku_generator.py
Generador determinista de tableros de Sudoku con garantía matemática de solución única.

Características:
1. Semilla determinista: Utiliza `random.Random(f"sudoku_{date_str}")`.
   Dos llamadas con la misma fecha en cualquier servidor generan exactamente el mismo tablero.
2. Solución única garantizada: Mediante algoritmo de backtracking y verificación de unicidad.
3. 3 niveles de dificultad equilibrados:
   - Nivel 1 (Fácil / Bajo): ~43 pistas iniciales.
   - Nivel 2 (Medio): ~35 pistas iniciales.
   - Nivel 3 (Alto / Avanzado): ~27 pistas iniciales.
   Todos los niveles comparten la misma solución matemática.
"""

import random
from typing import List, Tuple, Dict, Any

SudokuGrid = List[List[int]]

def _is_valid(grid: SudokuGrid, r: int, c: int, val: int) -> bool:
    """Verifica si `val` no colisiona en la fila `r`, columna `c` o su caja 3x3."""
    for i in range(9):
        if grid[r][i] == val or grid[i][c] == val:
            return False
    br, bc = (r // 3) * 3, (c // 3) * 3
    for i in range(3):
        for j in range(3):
            if grid[br + i][bc + j] == val:
                return False
    return True

def _count_solutions(grid: SudokuGrid, count: int = 0) -> int:
    """
    Cuenta la cantidad de soluciones de un tablero de Sudoku con poda temprana (MRV).
    Retorna 0 (sin solución), 1 (solución única) o 2 (más de una solución).
    """
    min_poss = 10
    best_cell = None

    for r in range(9):
        for c in range(9):
            if grid[r][c] == 0:
                poss = [v for v in range(1, 10) if _is_valid(grid, r, c, v)]
                if len(poss) < min_poss:
                    min_poss = len(poss)
                    best_cell = (r, c, poss)
                    if min_poss <= 1:
                        break
        if best_cell and min_poss <= 1:
            break

    if not best_cell:
        return count + 1  # Tablero completamente lleno y válido

    r, c, poss = best_cell
    for val in poss:
        grid[r][c] = val
        count = _count_solutions(grid, count)
        grid[r][c] = 0
        if count >= 2:
            return count

    return count

def _fill_solution(grid: SudokuGrid, rng: random.Random) -> bool:
    """Rellena un tablero vacío 9x9 con una solución matemática completa y válida."""
    for r in range(9):
        for c in range(9):
            if grid[r][c] == 0:
                digits = list(range(1, 10))
                rng.shuffle(digits)
                for val in digits:
                    if _is_valid(grid, r, c, val):
                        grid[r][c] = val
                        if _fill_solution(grid, rng):
                            return True
                        grid[r][c] = 0
                return False
    return True

def generate_sudoku_for_date(date_str: str) -> Dict[str, Any]:
    """
    Genera el puzzle diario de Sudoku para una fecha determinada en formato YYYY-MM-DD.
    Garantiza reproducibilidad determinista gracias a la semilla de fecha.
    """
    rng = random.Random(f"sudoku_{date_str}")

    # 1. Generar la solución completa 9x9
    solution: SudokuGrid = [[0] * 9 for _ in range(9)]
    _fill_solution(solution, rng)

    # 2. Partir de la solución y remover celdas preservando unicidad para Nivel 3 (Alto)
    puzzle = [row[:] for row in solution]
    all_cells: List[Tuple[int, int]] = [(r, c) for r in range(9) for c in range(9)]
    rng.shuffle(all_cells)

    removed = 0
    for r, c in all_cells:
        temp = puzzle[r][c]
        puzzle[r][c] = 0

        # Clonar para probar si sigue teniendo solución única
        grid_copy = [row[:] for row in puzzle]
        if _count_solutions(grid_copy) != 1:
            # Si generó múltiples soluciones, reponer número
            puzzle[r][c] = temp
        else:
            removed += 1
            # Para Nivel 3 (Alto), buscar ~27 pistas (~54 celdas removidas)
            if 81 - removed <= 27:
                break

    board_lvl3 = [row[:] for row in puzzle]

    # 3. Para Nivel 2 y Nivel 1, revelar pistas adicionales de la solución
    empty_cells = [(r, c) for r in range(9) for c in range(9) if board_lvl3[r][c] == 0]
    rng.shuffle(empty_cells)

    # Nivel 2 (Medio): revelar 8 pistas adicionales (~35 pistas en total)
    board_lvl2 = [row[:] for row in board_lvl3]
    for r, c in empty_cells[:8]:
        board_lvl2[r][c] = solution[r][c]

    # Nivel 1 (Fácil): revelar 16 pistas adicionales (~43 pistas en total)
    board_lvl1 = [row[:] for row in board_lvl3]
    for r, c in empty_cells[:16]:
        board_lvl1[r][c] = solution[r][c]

    clues_lvl1 = 81 - sum(row.count(0) for row in board_lvl1)
    clues_lvl2 = 81 - sum(row.count(0) for row in board_lvl2)
    clues_lvl3 = 81 - sum(row.count(0) for row in board_lvl3)

    return {
        "solution": solution,
        "boards": {
            "1": board_lvl1,
            "2": board_lvl2,
            "3": board_lvl3,
        },
        "clues": {
            "1": clues_lvl1,
            "2": clues_lvl2,
            "3": clues_lvl3,
        }
    }
