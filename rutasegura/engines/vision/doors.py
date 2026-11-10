"""Puertas (huecos en muros + arco de apertura) y propuesta de salidas."""

from __future__ import annotations

import math
from collections.abc import Sequence

import cv2
import numpy as np
import numpy.typing as npt

from rutasegura.domain.geometry import Point, Segment
from rutasegura.engines.vision.images import Mask


def arc_score(residual: Mask, gap: Segment, samples: int = 24, radius_px: int = 2) -> float:
    """Evidencia de arco de apertura (0–1) junto a un hueco.

    Prueba las 4 combinaciones (bisagra en cada extremo × lado del muro) y se queda con la mejor:
    fracción de puntos del cuarto de círculo de radio = ancho del hueco que tienen trazo fino cerca.
    """
    if gap.length < 2:
        return 0.0
    near = cv2.dilate(residual.astype(np.uint8), np.ones((2 * radius_px + 1,) * 2, np.uint8)) > 0
    h, w = near.shape
    ux = (gap.end.x - gap.start.x) / gap.length
    uy = (gap.end.y - gap.start.y) / gap.length
    phis = np.linspace(0.15, math.pi / 2 - 0.15, samples)
    best = 0.0
    for hinge, sign_u in ((gap.start, 1.0), (gap.end, -1.0)):
        for side in (1.0, -1.0):
            nx, ny = -uy * side, ux * side
            xs = hinge.x + gap.length * (np.cos(phis) * ux * sign_u + np.sin(phis) * nx)
            ys = hinge.y + gap.length * (np.cos(phis) * uy * sign_u + np.sin(phis) * ny)
            xi, yi = xs.round().astype(int), ys.round().astype(int)
            ok = (xi >= 0) & (xi < w) & (yi >= 0) & (yi < h)
            if ok.any():
                best = max(best, float(near[yi[ok], xi[ok]].sum()) / samples)
    return best


def door_confidence(residual: Mask, gap: Segment) -> float:
    """Confianza de una puerta: base por el hueco + extra si hay arco de apertura."""
    return min(1.0, 0.45 + 0.55 * arc_score(residual, gap))


def building_outline(wall_mask: Mask, close_px: int) -> npt.NDArray[np.int32] | None:
    """Contorno exterior del edificio: cierra los huecos de puertas y toma la mancha mayor."""
    if not wall_mask.any():
        return None
    k = max(3, close_px | 1)
    pad = k + 2  # margen para que el cierre no se pegue al borde de la imagen
    padded = np.pad(wall_mask.astype(np.uint8), pad)
    closed = cv2.morphologyEx(
        padded, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
    )
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    return np.asarray(max(contours, key=cv2.contourArea), dtype=np.int32) - pad


def is_on_outline(outline: npt.NDArray[np.int32], point: Point, tol: float) -> bool:
    """Indica si el punto está a menos de ``tol`` px del contorno exterior."""
    dist = cv2.pointPolygonTest(outline, (float(point.x), float(point.y)), True)
    return abs(float(dist)) <= tol


def corner_gaps(
    walls: Sequence[Segment],
    free_ends: Sequence[tuple[int, int]],
    wall_mask: Mask,
    *,
    thickness: float,
    min_px: float,
    max_px: float,
) -> list[Segment]:
    """Huecos entre el extremo libre de un muro y un muro perpendicular (puerta junto a esquina)."""
    gaps: list[Segment] = []
    for idx, end in free_ends:
        wall = walls[idx]
        tip, base = (wall.start, wall.end) if end == 0 else (wall.end, wall.start)
        if wall.length < 1:
            continue
        ux, uy = (tip.x - base.x) / wall.length, (tip.y - base.y) / wall.length
        best: Segment | None = None
        best_s = max_px * 1.1
        for j, other in enumerate(walls):
            if j == idx:
                continue
            ox, oy = other.end.x - other.start.x, other.end.y - other.start.y
            olen = math.hypot(ox, oy)
            if olen < 1 or abs(ux * ox / olen + uy * oy / olen) > math.cos(math.radians(60)):
                continue
            den = ux * oy - uy * ox
            if abs(den) < 1e-9:
                continue
            # tip + s·u = other.start + r·o
            s = ((other.start.x - tip.x) * oy - (other.start.y - tip.y) * ox) / den
            r = ((other.start.x - tip.x) * uy - (other.start.y - tip.y) * ux) / den
            margin = thickness / olen
            if not -margin <= r <= 1 + margin:
                continue
            face = s - thickness / 2
            if min_px * 0.75 <= face <= best_s:
                end_pt = Point(tip.x + ux * face, tip.y + uy * face)
                candidate = Segment(tip, end_pt)
                # el hueco debe estar vacío de muro
                n = max(2, int(face / 2))
                xs = np.linspace(tip.x + ux * thickness, end_pt.x, n).round().astype(int)
                ys = np.linspace(tip.y + uy * thickness, end_pt.y, n).round().astype(int)
                h, w = wall_mask.shape
                ok = (xs >= 0) & (xs < w) & (ys >= 0) & (ys < h)
                if ok.any() and wall_mask[ys[ok], xs[ok]].mean() < 0.2:
                    best, best_s = candidate, face
        if best is not None:
            gaps.append(best)
    return gaps
