"""Edición asistida del plano: encajar puertas y salidas en el muro donde se dibujan.

Cuando el usuario dibuja una puerta o salida cerca de un muro, se ubica exactamente sobre el eje
de ese muro y se le abre el hueco (el muro se parte en dos). Así el paso queda abierto en la
simulación aunque el trazo no haya caído justo encima del muro.
"""

from __future__ import annotations

import dataclasses
import math

from rutasegura.domain.geometry import Point, Segment
from rutasegura.domain.plan import FloorPlan, Wall

SNAP_DISTANCE_M = 0.8  # distancia máxima del trazo al muro para encajarlo
SNAP_DISTANCE_PX = 30.0  # si el plano aún no tiene escala
MAX_ANGLE_DEG = 25.0
MIN_LENGTH_PX = 3.0


@dataclasses.dataclass(frozen=True)
class SnapResult:
    """Vano ubicado sobre un muro y muros resultantes (con el hueco abierto)."""

    opening: Segment
    walls: tuple[Wall, ...]
    snapped: bool


def _angle(seg: Segment) -> float:
    return math.atan2(seg.end.y - seg.start.y, seg.end.x - seg.start.x)


def _angle_diff(a: Segment, b: Segment) -> float:
    diff = abs(_angle(a) - _angle(b)) % math.pi
    return min(diff, math.pi - diff)


def _param(wall: Segment, p: Point) -> float:
    dx, dy = wall.end.x - wall.start.x, wall.end.y - wall.start.y
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return 0.0
    return ((p.x - wall.start.x) * dx + (p.y - wall.start.y) * dy) / length2


def _at(wall: Segment, t: float) -> Point:
    return Point(
        wall.start.x + t * (wall.end.x - wall.start.x),
        wall.start.y + t * (wall.end.y - wall.start.y),
    )


def _distance_to_line(wall: Segment, p: Point) -> float:
    q = _at(wall, _param(wall, p))
    return p.distance_to(q)


def snap_opening(plan: FloorPlan, drawn: Segment) -> SnapResult:
    """Encaja un vano dibujado en el muro más cercano y abre el hueco.

    Si no hay un muro cercano y casi paralelo, devuelve el trazo tal cual (``snapped=False``):
    puede ser un vano dibujado en un hueco que ya existe.
    """
    tolerance = SNAP_DISTANCE_M / plan.scale_m_per_px if plan.scale_m_per_px else SNAP_DISTANCE_PX
    best: tuple[float, int, float, float] | None = None
    for index, wall in enumerate(plan.walls):
        seg = wall.segment
        if seg.length < MIN_LENGTH_PX or _angle_diff(seg, drawn) > math.radians(MAX_ANGLE_DEG):
            continue
        t0 = _param(seg, drawn.start)
        t1 = _param(seg, drawn.end)
        lo, hi = max(0.0, min(t0, t1)), min(1.0, max(t0, t1))
        if (hi - lo) * seg.length < MIN_LENGTH_PX:
            continue
        distance = _distance_to_line(seg, drawn.midpoint)
        if distance <= tolerance and (best is None or distance < best[0]):
            best = (distance, index, lo, hi)
    if best is None:
        return SnapResult(drawn, plan.walls, snapped=False)
    _, index, lo, hi = best
    wall = plan.walls[index]
    seg = wall.segment
    opening = Segment(_at(seg, lo), _at(seg, hi))
    pieces = [
        Wall(Segment(_at(seg, a), _at(seg, b)), wall.confidence)
        for a, b in ((0.0, lo), (hi, 1.0))
        if (b - a) * seg.length >= MIN_LENGTH_PX
    ]
    walls = (*plan.walls[:index], *pieces, *plan.walls[index + 1 :])
    return SnapResult(opening, walls, snapped=True)
