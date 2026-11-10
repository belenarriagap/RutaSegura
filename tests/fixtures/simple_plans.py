"""Planos simples hechos a mano (50 px = 1 m) para probar navegación y simulación."""

from __future__ import annotations

from rutasegura.domain.enums import UseType
from rutasegura.domain.geometry import Point, Polygon, Segment
from rutasegura.domain.plan import Door, Exit, FloorPlan, Room, SafeZone, Wall

PX_PER_M = 50.0
SCALE = 1.0 / PX_PER_M


def _p(x_m: float, y_m: float) -> Point:
    return Point(x_m * PX_PER_M, y_m * PX_PER_M)


def _seg(x1: float, y1: float, x2: float, y2: float) -> Segment:
    return Segment(_p(x1, y1), _p(x2, y2))


def rect(x: float, y: float, w: float, h: float) -> Polygon:
    """Rectángulo en metros convertido a píxeles."""
    return Polygon((_p(x, y), _p(x + w, y), _p(x + w, y + h), _p(x, y + h)))


def single_room(
    width: float = 10.0,
    height: float = 6.0,
    exit_width: float = 1.2,
    *,
    second_exit: bool = False,
    confirmed: bool = True,
) -> FloorPlan:
    """Un ambiente rectangular con una salida centrada en el muro derecho (y opcional otra
    en el muro izquierdo)."""
    y0 = height / 2 - exit_width / 2
    y1 = height / 2 + exit_width / 2
    walls = [
        _seg(0, 0, width, 0),
        _seg(0, height, width, height),
        _seg(width, 0, width, y0),
        _seg(width, y1, width, height),
    ]
    exits = [Exit(_seg(width, y0, width, y1), "Salida 1", confirmed)]
    if second_exit:
        walls += [_seg(0, 0, 0, y0), _seg(0, y1, 0, height)]
        exits.append(Exit(_seg(0, y0, 0, y1), "Salida 2", confirmed))
    else:
        walls.append(_seg(0, 0, 0, height))
    return FloorPlan(
        scale_m_per_px=SCALE,
        walls=tuple(Wall(w) for w in walls),
        exits=tuple(exits),
        rooms=(Room("Aula 1", UseType.EDUCATION, rect(0, 0, width, height)),),
    )


def two_rooms() -> FloorPlan:
    """Dos ambientes de 6×6 m unidos por una puerta de 0.9 m; salida de 1.2 m en el segundo."""
    walls = [
        _seg(0, 0, 12, 0),
        _seg(0, 6, 12, 6),
        _seg(0, 0, 0, 6),
        _seg(12, 0, 12, 2.4),
        _seg(12, 3.6, 12, 6),
        _seg(6, 0, 6, 2.55),
        _seg(6, 3.45, 6, 6),
    ]
    return FloorPlan(
        scale_m_per_px=SCALE,
        walls=tuple(Wall(w) for w in walls),
        doors=(Door(_seg(6, 2.55, 6, 3.45)),),
        exits=(Exit(_seg(12, 2.4, 12, 3.6), "Salida principal"),),
        rooms=(
            Room("Aula 1", UseType.EDUCATION, rect(0, 0, 6, 6)),
            Room("Aula 2", UseType.EDUCATION, rect(6, 0, 6, 6)),
        ),
    )


def room_with_patio() -> FloorPlan:
    """Ambiente cerrado (sin salida al exterior) con una zona segura interior."""
    plan = single_room()
    walls = [w for w in plan.walls] + [Wall(_seg(10, 2.4, 10, 3.6))]
    return FloorPlan(
        scale_m_per_px=SCALE,
        walls=tuple(walls),
        safe_zones=(SafeZone(rect(7, 1, 2, 2), "Patio"),),
        rooms=plan.rooms,
    )
