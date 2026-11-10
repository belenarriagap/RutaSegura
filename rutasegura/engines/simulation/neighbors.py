"""Búsqueda de vecinos con hash espacial por celdas (sin comparar todos con todos)."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

IntArray = npt.NDArray[np.int64]


def neighbor_pairs(positions: npt.NDArray[np.float64], cutoff: float) -> tuple[IntArray, IntArray]:
    """Pares ordenados (i, j), i ≠ j, de agentes en celdas vecinas de lado ``cutoff``.

    Incluye todos los pares a distancia < ``cutoff`` (y algunos más lejanos, que el llamador
    filtra). Cada par aparece en ambos sentidos. Completamente vectorizado.
    """
    n = len(positions)
    if n < 2:
        empty = np.zeros(0, dtype=np.int64)
        return empty, empty
    cells = np.floor(positions / cutoff).astype(np.int64)
    cells -= cells.min(axis=0) - 1  # deja margen para el desplazamiento −1
    width = int(cells[:, 1].max()) + 2
    keys = cells[:, 0] * width + cells[:, 1]
    order = np.argsort(keys, kind="stable")
    unique, starts, counts = np.unique(keys[order], return_index=True, return_counts=True)
    agents = np.arange(n, dtype=np.int64)
    firsts: list[IntArray] = []
    seconds: list[IntArray] = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            target = (cells[:, 0] + dx) * width + (cells[:, 1] + dy)
            pos = np.searchsorted(unique, target)
            pos_clipped = np.minimum(pos, len(unique) - 1)
            found = unique[pos_clipped] == target
            cnt = np.where(found, counts[pos_clipped], 0)
            total = int(cnt.sum())
            if total == 0:
                continue
            first = np.repeat(agents, cnt)
            begin = np.repeat(np.where(found, starts[pos_clipped], 0), cnt)
            offsets = np.arange(total) - np.repeat(np.cumsum(cnt) - cnt, cnt)
            second = order[begin + offsets]
            firsts.append(first)
            seconds.append(second)
    if not firsts:
        empty = np.zeros(0, dtype=np.int64)
        return empty, empty
    i = np.concatenate(firsts)
    j = np.concatenate(seconds)
    keep = i != j
    return i[keep], j[keep]
