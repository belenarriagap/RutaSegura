"""Detección automática de ambientes: espacios cerrados por muros, puertas y salidas.

Las puertas se tratan como cerradas para separar ambientes vecinos. Devuelve polígonos en
píxeles del plano, ordenados de arriba a abajo y de izquierda a derecha.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

from rutasegura.domain.geometry import Point, Polygon
from rutasegura.domain.plan import FloorPlan

RESOLUTION_M = 0.1
MIN_AREA_M2 = 2.0


def detect_rooms(
    plan: FloorPlan, *, resolution_m: float = RESOLUTION_M, min_area_m2: float = MIN_AREA_M2
) -> list[Polygon]:
    """Polígonos (en píxeles) de los espacios cerrados del plano."""
    if plan.scale_m_per_px is None:
        raise ValueError("El plano no tiene escala; defínala en el paso 2.")
    segments = [w.segment for w in plan.walls] + [d.segment for d in plan.doors]
    segments += [e.segment for e in plan.exits]
    if not segments:
        return []
    cell_px = max(1.0, resolution_m / plan.scale_m_per_px)
    xs = [p.x for s in segments for p in (s.start, s.end)]
    ys = [p.y for s in segments for p in (s.start, s.end)]
    x0, y0 = min(xs) - 3 * cell_px, min(ys) - 3 * cell_px
    cols = math.ceil((max(xs) - x0) / cell_px) + 4
    rows = math.ceil((max(ys) - y0) / cell_px) + 4
    barrier = np.zeros((rows, cols), np.uint8)

    def cv_point(p: Point) -> tuple[int, int]:
        return round((p.x - x0) / cell_px * 16), round((p.y - y0) / cell_px * 16)

    for seg in segments:
        cv2.line(barrier, cv_point(seg.start), cv_point(seg.end), 1, 2, cv2.LINE_8, 4)

    free = (barrier == 0).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(free, connectivity=4)
    border = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]])))
    min_cells = min_area_m2 / (resolution_m * resolution_m)
    polygons: list[tuple[float, float, Polygon]] = []
    for label in range(1, count):
        if label in border or stats[label, cv2.CC_STAT_AREA] < min_cells:
            continue
        region = (labels == label).astype(np.uint8)
        # cerrar la franja de la barrera para que el contorno siga el eje del muro
        region = cv2.dilate(region, np.ones((3, 3), np.uint8))
        contours, _ = cv2.findContours(region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contour = max(contours, key=cv2.contourArea)
        approx = cv2.approxPolyDP(contour, 1.5, True).reshape(-1, 2)
        if len(approx) < 3:
            continue
        vertices = tuple(Point(x0 + float(x) * cell_px, y0 + float(y) * cell_px) for x, y in approx)
        poly = Polygon(vertices)
        polygons.append((round(poly.centroid.y / (2 / plan.scale_m_per_px)), poly.centroid.x, poly))
    polygons.sort(key=lambda item: (item[0], item[1]))
    return [poly for _, _, poly in polygons]
