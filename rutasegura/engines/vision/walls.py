"""Detección de muros: máscara de trazos gruesos, esqueleto, Hough y fusión de colineales.

Representación de una recta: ángulo ``theta`` en [0, π), dirección ``d = (cos θ, sin θ)`` y
normal ``n = (-sin θ, cos θ)``. Un punto ``p`` está en la recta si ``n·p = rho``; su posición a lo
largo de ella es ``t = d·p``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

import cv2
import numpy as np
import numpy.typing as npt

from rutasegura.domain.geometry import Point, Segment
from rutasegura.engines.vision.images import Mask
from rutasegura.engines.vision.preprocess import remove_small_components, thin

SegmentArray = npt.NDArray[np.float64]  # (n, 4): x1, y1, x2, y2


def wall_mask(binary: Mask, thickness: float) -> Mask:
    """Conserva solo los trazos gruesos (muros); elimina texto, cotas, arcos y mobiliario fino."""
    k = max(3, round(0.6 * thickness))
    closed = cv2.morphologyEx(binary.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
    return remove_small_components(opened > 0, int(max(20.0, 3.0 * thickness * thickness)))


def hough_segments(mask: Mask, *, min_length: float, max_gap: float) -> SegmentArray:
    """Segmentos rectos sobre el esqueleto de la máscara de muros."""
    skeleton = thin(mask).astype(np.uint8) * 255
    lines = cv2.HoughLinesP(
        skeleton,
        rho=1,
        theta=np.pi / 720,
        threshold=max(8, int(min_length * 0.5)),
        minLineLength=min_length,
        maxLineGap=max_gap,
    )
    if lines is None:
        return np.zeros((0, 4), dtype=np.float64)
    return np.asarray(lines, dtype=np.float64).reshape(-1, 4)


def _line_params(seg: npt.NDArray[np.float64]) -> tuple[float, float]:
    x1, y1, x2, y2 = (float(v) for v in seg)
    theta = math.atan2(y2 - y1, x2 - x1) % math.pi
    rho = -math.sin(theta) * x1 + math.cos(theta) * y1
    return theta, rho


@dataclass(slots=True)
class LineGroup:
    """Segmentos casi colineales que comparten una recta."""

    theta: float
    rho: float
    weight: float
    members: list[npt.NDArray[np.float64]] = field(default_factory=list)

    @property
    def direction(self) -> tuple[float, float]:
        return math.cos(self.theta), math.sin(self.theta)

    @property
    def normal(self) -> tuple[float, float]:
        return -math.sin(self.theta), math.cos(self.theta)

    def project(self, x: float, y: float) -> float:
        dx, dy = self.direction
        return dx * x + dy * y

    def point_at(self, t: float) -> Point:
        dx, dy = self.direction
        nx, ny = self.normal
        return Point(t * dx + self.rho * nx, t * dy + self.rho * ny)

    def refit(self) -> None:
        """Ajusta la recta a los puntos de sus miembros (mínimos cuadrados totales)."""
        samples = []
        for x1, y1, x2, y2 in self.members:
            n = max(2, int(math.hypot(x2 - x1, y2 - y1) / 4))
            t = np.linspace(0.0, 1.0, n)
            samples.append(np.column_stack([x1 + t * (x2 - x1), y1 + t * (y2 - y1)]))
        pts = np.vstack(samples)
        center = pts.mean(axis=0)
        _, _, vt = np.linalg.svd(pts - center, full_matrices=False)
        dx, dy = float(vt[0, 0]), float(vt[0, 1])
        self.theta = math.atan2(dy, dx) % math.pi
        self.rho = -math.sin(self.theta) * float(center[0]) + math.cos(self.theta) * float(
            center[1]
        )

    def intervals(self) -> list[tuple[float, float]]:
        """Intervalos [t0, t1] de cada miembro proyectados sobre la recta del grupo."""
        result = []
        for x1, y1, x2, y2 in self.members:
            a, b = self.project(float(x1), float(y1)), self.project(float(x2), float(y2))
            result.append((min(a, b), max(a, b)))
        return sorted(result)


def _aligned(theta: float, rho: float, ref_theta: float) -> tuple[float, float]:
    """Expresa (theta, rho) cerca de ``ref_theta`` (las rectas casi horizontales cruzan 0/π)."""
    if theta - ref_theta > math.pi / 2:
        return theta - math.pi, -rho
    if ref_theta - theta > math.pi / 2:
        return theta + math.pi, -rho
    return theta, rho


def group_collinear(
    segments: SegmentArray, *, angle_tol_deg: float, dist_tol: float
) -> list[LineGroup]:
    """Agrupa segmentos con ángulo y distancia a la recta dentro de las tolerancias."""
    angle_tol = math.radians(angle_tol_deg)
    lengths = np.hypot(segments[:, 2] - segments[:, 0], segments[:, 3] - segments[:, 1])
    groups: list[LineGroup] = []
    for idx in np.argsort(-lengths):
        seg = segments[idx]
        length = float(lengths[idx])
        theta, rho = _line_params(seg)
        best: LineGroup | None = None
        best_dist = dist_tol
        for group in groups:
            th, rh = _aligned(theta, rho, group.theta)
            if abs(th - group.theta) > angle_tol:
                continue
            # distancia de los extremos del segmento a la recta del grupo
            nx, ny = group.normal
            d = max(
                abs(nx * seg[0] + ny * seg[1] - group.rho),
                abs(nx * seg[2] + ny * seg[3] - group.rho),
            )
            if d <= best_dist:
                best, best_dist = group, float(d)
        if best is None:
            groups.append(LineGroup(theta, rho, length, [seg]))
            continue
        th, rh = _aligned(theta, rho, best.theta)
        total = best.weight + length
        new_theta = (best.theta * best.weight + th * length) / total
        new_rho = (best.rho * best.weight + rh * length) / total
        if new_theta < 0 or new_theta >= math.pi:
            new_theta, new_rho = new_theta % math.pi, -new_rho
        best.theta, best.rho, best.weight = new_theta, new_rho, total
        best.members.append(seg)
    return groups


def merge_parallel_groups(
    groups: Sequence[LineGroup], *, angle_tol_deg: float, dist_tol: float
) -> list[LineGroup]:
    """Une grupos que describen la misma recta (un muro largo y levemente rotado puede
    partirse en dos grupos casi idénticos)."""
    angle_tol = math.radians(angle_tol_deg)
    for group in groups:
        group.refit()
    pending = sorted(groups, key=lambda g: -g.weight)
    result: list[LineGroup] = []
    for group in pending:
        target = None
        for kept in result:
            th, rh = _aligned(group.theta, group.rho, kept.theta)
            if abs(th - kept.theta) <= angle_tol and abs(rh - kept.rho) <= dist_tol:
                target = kept
                break
        if target is None:
            result.append(LineGroup(group.theta, group.rho, group.weight, list(group.members)))
            continue
        th, rh = _aligned(group.theta, group.rho, target.theta)
        total = target.weight + group.weight
        target.theta = (target.theta * target.weight + th * group.weight) / total
        target.rho = (target.rho * target.weight + rh * group.weight) / total
        if target.theta < 0 or target.theta >= math.pi:
            target.theta, target.rho = target.theta % math.pi, -target.rho
        target.weight = total
        target.members.extend(group.members)
    for group in result:
        group.refit()
    return result


def merge_intervals(
    intervals: Sequence[tuple[float, float]], gap_tol: float
) -> list[tuple[float, float]]:
    """Une intervalos que se solapan o están separados por menos de ``gap_tol``."""
    merged: list[tuple[float, float]] = []
    for a, b in sorted(intervals):
        if merged and a - merged[-1][1] <= gap_tol:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def occupancy(
    mask: Mask, group: LineGroup, t0: float, t1: float, half_width: float
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.bool_]]:
    """Recorre la recta de ``t0`` a ``t1`` (paso 1 px) e indica dónde hay muro.

    Se mira una franja de ±``half_width`` px perpendicular a la recta para tolerar pequeños
    desvíos del eje estimado.
    """
    n = max(2, int(abs(t1 - t0)) + 1)
    ts = np.linspace(t0, t1, n)
    dx, dy = group.direction
    nx, ny = group.normal
    offsets = np.linspace(-half_width, half_width, max(3, int(2 * half_width) + 1))
    xs = ts[:, None] * dx + group.rho * nx + offsets[None, :] * nx
    ys = ts[:, None] * dy + group.rho * ny + offsets[None, :] * ny
    xi, yi = xs.round().astype(int), ys.round().astype(int)
    h, w = mask.shape
    ok = (xi >= 0) & (xi < w) & (yi >= 0) & (yi < h)
    hit = np.zeros(xi.shape, dtype=np.bool_)
    hit[ok] = mask[yi[ok], xi[ok]]
    return ts, np.asarray(hit.any(axis=1), dtype=np.bool_)


def longest_empty_run(
    ts: npt.NDArray[np.float64], occupied: npt.NDArray[np.bool_]
) -> tuple[float, float] | None:
    """Tramo vacío más largo (sin muro) del recorrido, como (t_inicio, t_fin)."""
    best: tuple[float, float] | None = None
    start: int | None = None
    for i, occ in enumerate([*occupied.tolist(), True]):
        if not occ and start is None:
            start = i
        elif occ and start is not None:
            run = (float(ts[start]), float(ts[i - 1]))
            if best is None or abs(run[1] - run[0]) > abs(best[1] - best[0]):
                best = run
            start = None
    return best


def extend_to_mask_end(
    mask: Mask, group: LineGroup, t: float, direction: float, max_dist: float, half_width: float
) -> float:
    """Avanza desde ``t`` en ``direction`` (±1) mientras haya muro, hasta ``max_dist`` px.

    Corrige el acortamiento del esqueleto en los extremos de cada tramo.
    """
    ts, occ = occupancy(mask, group, t, t + direction * max_dist, half_width)
    empty = np.flatnonzero(~occ)
    if empty.size == 0:
        return float(ts[-1])
    return float(ts[max(int(empty[0]) - 1, 0)])


def _line_intersection(s1: Segment, s2: Segment) -> Point | None:
    x1, y1, x2, y2 = s1.start.x, s1.start.y, s1.end.x, s1.end.y
    x3, y3, x4, y4 = s2.start.x, s2.start.y, s2.end.x, s2.end.y
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-9:
        return None
    a = x1 * y2 - y1 * x2
    b = x3 * y4 - y3 * x4
    return Point((a * (x3 - x4) - (x1 - x2) * b) / den, (a * (y3 - y4) - (y1 - y2) * b) / den)


def _angle_between(s1: Segment, s2: Segment) -> float:
    a1 = math.atan2(s1.end.y - s1.start.y, s1.end.x - s1.start.x)
    a2 = math.atan2(s2.end.y - s2.start.y, s2.end.x - s2.start.x)
    diff = abs(a1 - a2) % math.pi
    return min(diff, math.pi - diff)


def _param_on(segment: Segment, point: Point) -> float:
    """Posición de ``point`` proyectado sobre ``segment`` (0 = inicio, 1 = fin)."""
    dx, dy = segment.end.x - segment.start.x, segment.end.y - segment.start.y
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return 0.0
    return ((point.x - segment.start.x) * dx + (point.y - segment.start.y) * dy) / length2


def snap_endpoints(
    segments: Sequence[Segment], tol: float, min_angle_deg: float = 30.0
) -> tuple[list[Segment], list[tuple[bool, bool]]]:
    """Lleva cada extremo a la intersección con un muro no paralelo cercano (esquinas y "T").

    Devuelve los segmentos ajustados y, por cada uno, si su inicio/fin quedó unido a otro muro.
    """
    min_angle = math.radians(min_angle_deg)
    result = list(segments)
    joined: list[tuple[bool, bool]] = []
    for i, seg in enumerate(segments):
        ends = [seg.start, seg.end]
        flags = [False, False]
        for k in (0, 1):
            endpoint = ends[k]
            best: Point | None = None
            best_d = tol
            for j, other in enumerate(segments):
                if i == j or _angle_between(seg, other) < min_angle:
                    continue
                x = _line_intersection(seg, other)
                if x is None:
                    continue
                d = endpoint.distance_to(x)
                if d > best_d:
                    continue
                margin = tol / max(other.length, 1e-9)
                if not -margin <= _param_on(other, x) <= 1 + margin:
                    continue
                best, best_d = x, d
            if best is not None:
                ends[k] = best
                flags[k] = True
        result[i] = Segment(ends[0], ends[1])
        joined.append((flags[0], flags[1]))
    return result, joined


def segment_coverage(mask: Mask, segment: Segment, step: float = 2.0) -> float:
    """Fracción de puntos del segmento que caen sobre la máscara (confianza del muro)."""
    n = max(2, int(segment.length / step))
    xs = np.linspace(segment.start.x, segment.end.x, n).round().astype(int)
    ys = np.linspace(segment.start.y, segment.end.y, n).round().astype(int)
    h, w = mask.shape
    inside = (xs >= 0) & (xs < w) & (ys >= 0) & (ys < h)
    if not inside.any():
        return 0.0
    return float(mask[ys[inside], xs[inside]].mean() * inside.mean())
