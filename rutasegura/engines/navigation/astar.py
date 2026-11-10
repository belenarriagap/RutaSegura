"""A* sobre la grilla, para agentes con destino propio (p. ej. un docente que va por su grupo)."""

from __future__ import annotations

import heapq
import itertools
import math

import numpy as np
import numpy.typing as npt

from rutasegura.engines.navigation.fields import NEIGHBORS

Cell = tuple[int, int]


def _octile(a: Cell, b: Cell) -> float:
    dr, dc = abs(a[0] - b[0]), abs(a[1] - b[1])
    return max(dr, dc) + (math.sqrt(2) - 1) * min(dr, dc)


def astar(walkable: npt.NDArray[np.bool_], start: Cell, goal: Cell) -> list[Cell] | None:
    """Camino más corto de ``start`` a ``goal`` (lista de celdas, inclusive), o ``None``.

    Misma vecindad y costos que el campo de distancia; heurística octil (admisible).
    """
    rows, cols = walkable.shape
    walk = walkable.tolist()

    def ok(cell: Cell) -> bool:
        r, c = cell
        return 0 <= r < rows and 0 <= c < cols and bool(walk[r][c])

    if not ok(start) or not ok(goal):
        return None
    g: dict[Cell, float] = {start: 0.0}
    parent: dict[Cell, Cell] = {}
    heap: list[tuple[float, float, Cell]] = [(_octile(start, goal), 0.0, start)]
    closed: set[Cell] = set()
    while heap:
        _, cost, cell = heapq.heappop(heap)
        if cell == goal:
            path = [cell]
            while cell in parent:
                cell = parent[cell]
                path.append(cell)
            return path[::-1]
        if cell in closed:
            continue
        closed.add(cell)
        r, c = cell
        for dr, dc, step in NEIGHBORS:
            nxt = (r + dr, c + dc)
            if not ok(nxt) or nxt in closed:
                continue
            if dr and dc and not (walk[r + dr][c] and walk[r][c + dc]):
                continue
            new_cost = cost + step
            if new_cost < g.get(nxt, math.inf):
                g[nxt] = new_cost
                parent[nxt] = cell
                heapq.heappush(heap, (new_cost + _octile(nxt, goal), new_cost, nxt))
    return None


def path_length(path: list[Cell], cell_size: float) -> float:
    """Longitud del camino en metros."""
    total = 0.0
    for a, b in itertools.pairwise(path):
        total += math.hypot(a[0] - b[0], a[1] - b[1]) * cell_size
    return total
