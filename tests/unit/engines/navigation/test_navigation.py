"""Grilla, campo de distancia, campo de direcciones, A* y detección de ambientes."""

from __future__ import annotations

import dataclasses
import math

import numpy as np
import pytest

from rutasegura.domain.enums import CellType
from rutasegura.domain.plan import FloorPlan
from rutasegura.engines.navigation.astar import astar, path_length
from rutasegura.engines.navigation.fields import direction_field, distance_field, wall_distance
from rutasegura.engines.navigation.grid import build_grid
from rutasegura.engines.navigation.rooms import detect_rooms
from tests.fixtures.simple_plans import room_with_patio, single_room, two_rooms


class TestGrid:
    def test_room_is_enclosed_and_exit_is_target(self) -> None:
        grid = build_grid(single_room())
        assert grid.target_names == ("Salida 1",)
        assert grid.targets.sum() >= 2  # 1.2 m de salida ≈ 3 celdas
        inside = grid.to_cell(np.array([[5.0, 3.0]]))
        assert grid.cells[inside][0] == CellType.FREE
        outside = grid.to_cell(np.array([[-0.8, -0.8]]))
        assert grid.cells[outside][0] == CellType.OUTSIDE
        assert grid.cells[0, 0] == CellType.OUTSIDE

    def test_blocked_and_unconfirmed_exits_are_sealed(self) -> None:
        blocked = build_grid(single_room(), blocked_exits={"Salida 1"})
        assert blocked.target_names == ()
        assert not blocked.targets.any()
        # sin salida activa el interior queda cerrado (no se convierte en exterior)
        inside = blocked.to_cell(np.array([[5.0, 3.0]]))
        assert blocked.cells[inside][0] == CellType.FREE
        unconfirmed = build_grid(single_room(confirmed=False))
        assert not unconfirmed.targets.any()

    def test_interior_safe_zone_is_a_target(self) -> None:
        grid = build_grid(room_with_patio())
        assert grid.target_names == ("Patio",)
        cell = grid.to_cell(np.array([[8.0, 2.0]]))
        assert grid.cells[cell][0] == CellType.SAFE_ZONE
        assert grid.target_ids[cell][0] == 0

    def test_requires_scale_and_content(self) -> None:
        with pytest.raises(ValueError, match="escala"):
            build_grid(dataclasses.replace(single_room(), scale_m_per_px=None))
        with pytest.raises(ValueError, match="vacío"):
            build_grid(FloorPlan(scale_m_per_px=0.02))

    def test_polygon_mask_and_cell_centers(self) -> None:
        grid = build_grid(two_rooms())
        room = two_rooms().rooms[0]
        from rutasegura.engines.navigation.grid import polygon_to_m

        mask = grid.polygon_mask(polygon_to_m(room.area, 0.02))
        area = mask.sum() * grid.cell_size**2
        assert area == pytest.approx(36.0, rel=0.15)
        r, c = grid.to_cell(np.array([[1.0, 1.0]]))
        center = grid.cell_centers(r, c)[0]
        assert abs(center[0] - 1.0) <= grid.cell_size / 2 + 1e-9


class TestFields:
    def test_distance_in_open_space(self) -> None:
        walkable = np.ones((5, 10), bool)
        targets = np.zeros((5, 10), bool)
        targets[:, 9] = True
        dist = distance_field(walkable, targets, 0.4)
        assert dist[2, 0] == pytest.approx(9 * 0.4)
        assert dist[2, 9] == 0.0

    def test_diagonal_cost_and_no_corner_cutting(self) -> None:
        walkable = np.ones((3, 3), bool)
        targets = np.zeros((3, 3), bool)
        targets[0, 0] = True
        assert distance_field(walkable, targets, 1.0)[1, 1] == pytest.approx(math.sqrt(2))
        walkable[0, 1] = False  # bloquea una de las celdas ortogonales
        assert distance_field(walkable, targets, 1.0)[1, 1] == pytest.approx(2.0)

    def test_unreachable_is_infinite(self) -> None:
        walkable = np.ones((3, 5), bool)
        walkable[:, 2] = False
        targets = np.zeros((3, 5), bool)
        targets[1, 0] = True
        dist = distance_field(walkable, targets, 1.0)
        assert np.isinf(dist[1, 4])

    def test_directions_point_to_exit(self) -> None:
        grid = build_grid(single_room())
        dist = distance_field(grid.walkable, grid.targets, grid.cell_size)
        directions = direction_field(dist, grid.walkable)
        r, c = grid.to_cell(np.array([[2.0, 3.0]]))
        dx, dy = directions[r[0], c[0]]
        assert dx > 0.9  # la salida está a la derecha
        assert abs(math.hypot(dx, dy) - 1.0) < 1e-6
        # todo el interior alcanza la salida
        inside = grid.walkable & ~grid.targets
        assert np.isfinite(dist[inside]).all()

    def test_wall_distance(self) -> None:
        walkable = np.ones((7, 7), bool)
        walkable[:, 0] = False
        dist, grad = wall_distance(walkable, 0.4)
        assert dist[3, 1] < dist[3, 5]
        assert grad[3, 3, 0] > 0.9  # se aleja del muro izquierdo


class TestAStar:
    def test_matches_distance_field(self) -> None:
        grid = build_grid(two_rooms())
        dist = distance_field(grid.walkable, grid.targets, grid.cell_size)
        start = tuple(int(v[0]) for v in grid.to_cell(np.array([[1.0, 1.0]])))
        goal_cells = np.argwhere(grid.targets)
        goal = (int(goal_cells[0][0]), int(goal_cells[0][1]))
        path = astar(grid.walkable, (start[0], start[1]), goal)
        assert path is not None
        assert path[0] == (start[0], start[1])
        assert path[-1] == goal
        # A* a una salida concreta no puede ser más corto que el campo multiorigen
        assert path_length(path, grid.cell_size) >= dist[start[0], start[1]] - 1e-6

    def test_no_path_and_trivial_cases(self) -> None:
        walkable = np.ones((3, 5), bool)
        walkable[:, 2] = False
        assert astar(walkable, (1, 0), (1, 4)) is None
        assert astar(walkable, (1, 0), (1, 0)) == [(1, 0)]
        assert astar(walkable, (1, 2), (1, 0)) is None


class TestRooms:
    def test_two_rooms_are_found(self) -> None:
        plan = two_rooms()
        rooms = detect_rooms(plan)
        assert len(rooms) == 2
        areas = sorted(plan.area_m2(r) for r in rooms)
        assert areas[0] == pytest.approx(36.0, rel=0.1)
        assert areas[1] == pytest.approx(36.0, rel=0.1)
        assert rooms[0].centroid.x < rooms[1].centroid.x

    def test_requires_scale_and_handles_empty_plan(self) -> None:
        with pytest.raises(ValueError, match="escala"):
            detect_rooms(FloorPlan())
        assert detect_rooms(FloorPlan(scale_m_per_px=0.02)) == []
