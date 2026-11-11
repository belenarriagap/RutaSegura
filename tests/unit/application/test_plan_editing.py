"""Puertas y salidas dibujadas a mano: se encajan en el muro y le abren el hueco."""

from __future__ import annotations

import dataclasses

import pytest

from rutasegura.application.plan_editing import snap_opening
from rutasegura.domain.geometry import Point, Segment
from rutasegura.domain.people import Occupancy
from rutasegura.domain.plan import Exit, FloorPlan, Wall
from tests.fixtures.simple_plans import _seg, single_room
from tests.unit.engines.simulation.helpers import make_simulation


def _closed_room() -> FloorPlan:
    """Aula de 10 × 6 m totalmente cerrada (sin salida)."""
    base = single_room()
    return dataclasses.replace(base, walls=(*base.walls, Wall(_seg(10, 2.4, 10, 3.6))), exits=())


def test_opening_is_moved_onto_the_wall_and_cuts_it() -> None:
    plan = FloorPlan(scale_m_per_px=0.02, walls=(Wall(_seg(0, 0, 10, 0)),))
    drawn = _seg(3, 0.4, 4.2, 0.45)  # 40 cm al costado del muro y un poco torcido
    snap = snap_opening(plan, drawn)
    assert snap.snapped
    assert snap.opening.start.y == pytest.approx(0)
    assert snap.opening.end.y == pytest.approx(0)
    assert snap.opening.length == pytest.approx(1.2 * 50, abs=1)
    assert [w.segment for w in snap.walls] == [
        Segment(Point(0, 0), snap.opening.start),
        Segment(snap.opening.end, Point(500, 0)),
    ]


def test_far_or_perpendicular_strokes_are_left_alone() -> None:
    plan = FloorPlan(scale_m_per_px=0.02, walls=(Wall(_seg(0, 0, 10, 0)),))
    far = _seg(3, 2, 4, 2)  # a 2 m
    assert not snap_opening(plan, far).snapped
    across = _seg(3, -1, 3, 1)  # perpendicular
    assert not snap_opening(plan, across).snapped
    assert snap_opening(plan, far).walls == plan.walls


def test_opening_at_the_end_of_a_wall_keeps_one_piece() -> None:
    plan = FloorPlan(scale_m_per_px=0.02, walls=(Wall(_seg(0, 0, 10, 0)),))
    snap = snap_opening(plan, _seg(9, 0.1, 11, 0.1))  # sobresale del muro
    assert snap.opening.end == Point(500, 0)
    assert len(snap.walls) == 1


def test_manually_drawn_exit_off_the_wall_now_works() -> None:
    """Antes: una salida dibujada a 0.6 m del muro dejaba a todos sin salida."""
    plan = _closed_room()
    drawn = _seg(10.6, 2.4, 10.6, 3.6)
    snap = snap_opening(plan, drawn)
    assert snap.snapped
    fixed = dataclasses.replace(plan, walls=snap.walls, exits=(Exit(snap.opening, "Salida 1"),))
    result = make_simulation(fixed, [Occupancy("Aula 1", "adulto", 10)]).run().result
    assert result.completed
