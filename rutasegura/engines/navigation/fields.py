"""Campo de distancia a los objetivos (Dijkstra multiorigen) y campos derivados.

* 8-vecindad, costo diagonal √2 × tamaño de celda.
* No se permite "cortar esquinas": un paso diagonal exige que las dos celdas ortogonales
  intermedias sean transitables (evita atravesar muros en diagonal).
"""

from __future__ import annotations

import heapq
import math

import cv2
import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]
BoolArray = npt.NDArray[np.bool_]

NEIGHBORS = (
    (-1, 0, 1.0),
    (1, 0, 1.0),
    (0, -1, 1.0),
    (0, 1, 1.0),
    (-1, -1, math.sqrt(2)),
    (-1, 1, math.sqrt(2)),
    (1, -1, math.sqrt(2)),
    (1, 1, math.sqrt(2)),
)


def distance_field(walkable: BoolArray, targets: BoolArray, cell_size: float) -> FloatArray:
    """Distancia caminable (m) de cada celda al objetivo más cercano (``inf`` si no hay camino)."""
    rows, cols = walkable.shape
    dist = np.full((rows, cols), np.inf)
    walk = walkable.tolist()
    heap: list[tuple[float, int, int]] = []
    for r, c in zip(*np.nonzero(targets & walkable), strict=True):
        dist[r, c] = 0.0
        heap.append((0.0, int(r), int(c)))
    heapq.heapify(heap)
    d = dist.tolist()
    while heap:
        current, r, c = heapq.heappop(heap)
        if current > d[r][c]:
            continue
        for dr, dc, cost in NEIGHBORS:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < rows and 0 <= nc < cols) or not walk[nr][nc]:
                continue
            if dr and dc and not (walk[r + dr][c] and walk[r][c + dc]):
                continue
            candidate = current + cost * cell_size
            if candidate < d[nr][nc]:
                d[nr][nc] = candidate
                heapq.heappush(heap, (candidate, nr, nc))
    return np.array(d, dtype=np.float64)


def direction_field(dist: FloatArray, walkable: BoolArray) -> FloatArray:
    """Dirección unitaria (filas, columnas, 2) = (dx, dy) hacia donde baja la distancia.

    Se toma el vecino de menor distancia (descenso más pronunciado, sin cortar esquinas) y luego
    se suaviza promediando con los vecinos para que las trayectorias no sean en zigzag.
    """
    rows, cols = dist.shape
    padded = np.pad(dist, 1, constant_values=np.inf)
    walk_pad = np.pad(walkable, 1, constant_values=False)
    finite = np.isfinite(dist) & walkable
    best_slope = np.zeros((rows, cols))  # distancia ganada por metro recorrido
    vec = np.zeros((rows, cols, 2))
    for dr, dc, cost in NEIGHBORS:
        neighbor = padded[1 + dr : 1 + dr + rows, 1 + dc : 1 + dc + cols]
        allowed = walk_pad[1 + dr : 1 + dr + rows, 1 + dc : 1 + dc + cols]
        if dr and dc:
            allowed = (
                allowed
                & walk_pad[1 + dr : 1 + dr + rows, 1 : 1 + cols]
                & walk_pad[1 : 1 + rows, 1 + dc : 1 + dc + cols]
            )
        with np.errstate(invalid="ignore"):
            slope = np.where(
                allowed & finite & np.isfinite(neighbor), (dist - neighbor) / cost, 0.0
            )
        take = slope > best_slope + 1e-12
        best_slope = np.where(take, slope, best_slope)
        vec[take] = np.array([dc, dr], dtype=np.float64) / cost
    smoothed = cv2.blur(vec, (3, 3), borderType=cv2.BORDER_CONSTANT)
    smoothed[~walkable] = 0.0
    norm = np.linalg.norm(smoothed, axis=2, keepdims=True)
    result = np.where(norm > 1e-9, smoothed / np.maximum(norm, 1e-12), vec)
    return np.asarray(result, dtype=np.float64)


def wall_distance(walkable: BoolArray, cell_size: float) -> tuple[FloatArray, FloatArray]:
    """Distancia (m) de cada celda al obstáculo más cercano y su gradiente (alejándose del muro)."""
    dist = cv2.distanceTransform(walkable.astype(np.uint8), cv2.DIST_L2, 5).astype(np.float64)
    dist *= cell_size
    gy, gx = np.gradient(dist)
    grad = np.stack([gx, gy], axis=2)
    norm = np.linalg.norm(grad, axis=2, keepdims=True)
    grad = np.where(norm > 1e-9, grad / np.maximum(norm, 1e-12), 0.0)
    return dist, np.asarray(grad, dtype=np.float64)
