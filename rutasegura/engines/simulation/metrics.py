"""Cuellos de botella: zonas con densidad alta sostenida, ordenadas por severidad (RF08)."""

from __future__ import annotations

import cv2
import numpy as np
import numpy.typing as npt

from rutasegura.domain.geometry import Point
from rutasegura.domain.results import Bottleneck
from rutasegura.engines.navigation.grid import NavGrid

FloatArray = npt.NDArray[np.float64]


def find_bottlenecks(
    grid: NavGrid,
    time_above: FloatArray,
    density_when_above: FloatArray,
    *,
    min_duration_s: float,
    limit: int = 10,
) -> tuple[Bottleneck, ...]:
    """Agrupa celdas con densidad alta durante al menos ``min_duration_s``.

    * ``time_above``: segundos que cada celda estuvo por encima del umbral de congestión.
    * ``density_when_above``: suma de densidad·dt mientras estuvo por encima.

    Severidad = duración × densidad media (personas·s/m²): mayor es peor.
    """
    mask = (time_above >= min_duration_s).astype(np.uint8)
    count, labels = cv2.connectedComponents(mask, connectivity=8)
    found: list[Bottleneck] = []
    for label in range(1, count):
        rows, cols = np.nonzero(labels == label)
        times = time_above[rows, cols]
        total_time = float(times.sum())
        mean_density = float(density_when_above[rows, cols].sum() / max(total_time, 1e-9))
        duration = float(times.max())
        weights = times / max(total_time, 1e-9)
        center = grid.cell_centers(rows, cols)
        location = Point(float(center[:, 0] @ weights), float(center[:, 1] @ weights))
        found.append(
            Bottleneck(
                location=location,
                mean_density=round(mean_density, 3),
                duration_s=round(duration, 2),
                severity=round(duration * mean_density, 2),
            )
        )
    found.sort(key=lambda b: (-b.severity, b.location.x, b.location.y))
    return tuple(found[:limit])
