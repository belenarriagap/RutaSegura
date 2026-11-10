"""Piezas del detector: preprocesamiento, agrupación de colineales, esquinas y puertas."""

from __future__ import annotations

import math

import cv2
import numpy as np
import pytest

from rutasegura.domain.geometry import Point, Segment
from rutasegura.engines.vision.doors import arc_score, building_outline, is_on_outline
from rutasegura.engines.vision.preprocess import (
    binarize,
    estimate_wall_thickness,
    remove_small_components,
    thin,
)
from rutasegura.engines.vision.walls import (
    LineGroup,
    group_collinear,
    longest_empty_run,
    merge_intervals,
    merge_parallel_groups,
    occupancy,
    segment_coverage,
    snap_endpoints,
    wall_mask,
)


def _bar_mask(thickness: int) -> np.ndarray:
    mask = np.zeros((80, 200), dtype=bool)
    mask[40 - thickness // 2 : 40 - thickness // 2 + thickness, 20:180] = True
    return mask


class TestPreprocess:
    def test_binarize_marks_ink(self) -> None:
        gray = np.full((100, 100), 230, np.uint8)
        gray[40:50, 10:90] = 20
        mask = binarize(gray)
        assert mask[45, 50]
        assert not mask[10, 10]

    def test_small_components_are_removed(self) -> None:
        mask = np.zeros((50, 50), bool)
        mask[5, 5] = True
        mask[20:30, 20:30] = True
        cleaned = remove_small_components(mask, 10)
        assert not cleaned[5, 5]
        assert cleaned[25, 25]

    def test_thin_produces_one_pixel_centerline(self) -> None:
        skeleton = thin(_bar_mask(11))
        columns = skeleton[:, 50:150]
        assert (columns.sum(axis=0) == 1).all()
        rows = np.nonzero(columns)[0]
        assert abs(rows.mean() - 40) <= 1

    @pytest.mark.parametrize("thickness", [6, 10, 16])
    def test_wall_thickness_estimate(self, thickness: int) -> None:
        mask = _bar_mask(thickness)
        mask[60:61, 20:180] = True  # línea fina que no debe influir
        assert estimate_wall_thickness(mask) == pytest.approx(thickness, abs=2.5)

    def test_wall_mask_drops_thin_lines(self) -> None:
        mask = _bar_mask(10)
        mask[70, :] = True
        walls = wall_mask(mask, 10)
        assert walls[40, 100]
        assert not walls[70, 100]


class TestLineGrouping:
    def test_collinear_pieces_share_a_group_and_parallels_do_not(self) -> None:
        segments = np.array(
            [
                [0, 100, 200, 101],
                [260, 102, 500, 104],  # misma recta, levemente inclinada
                [0, 140, 500, 140],  # paralela a 40 px
            ],
            dtype=float,
        )
        groups = group_collinear(segments, angle_tol_deg=3, dist_tol=6)
        assert sorted(len(g.members) for g in groups) == [1, 2]

    def test_merge_parallel_groups_and_refit(self) -> None:
        a = LineGroup(0.0, 100.0, 200.0, [np.array([0, 100, 200, 100], float)])
        b = LineGroup(0.0, 103.0, 100.0, [np.array([300, 103, 400, 103], float)])
        merged = merge_parallel_groups([a, b], angle_tol_deg=3, dist_tol=6)
        assert len(merged) == 1
        # la recta reajustada pasa entre ambos tramos en toda su extensión
        for x in (0.0, 200.0, 400.0):
            line = merged[0]
            nx, ny = line.normal
            y = (line.rho - nx * x) / ny
            assert 99.0 <= y <= 104.0

    def test_nearly_horizontal_lines_across_zero_angle(self) -> None:
        segments = np.array([[0, 50, 300, 52], [320, 52.2, 600, 50]], dtype=float)
        groups = group_collinear(segments, angle_tol_deg=3, dist_tol=6)
        assert len(groups) == 1

    def test_merge_intervals(self) -> None:
        assert merge_intervals([(0, 10), (12, 20), (40, 50)], gap_tol=3) == [(0, 20), (40, 50)]

    def test_occupancy_and_longest_empty_run(self) -> None:
        mask = np.zeros((40, 200), bool)
        mask[18:23, 0:60] = True
        mask[18:23, 110:200] = True
        group = LineGroup(0.0, 20.0, 1.0)
        ts, occ = occupancy(mask, group, 0, 199, half_width=2)
        run = longest_empty_run(ts, occ)
        assert run is not None
        assert run[0] == pytest.approx(60, abs=1)
        assert run[1] == pytest.approx(109, abs=1)

    def test_snap_endpoints_closes_corner(self) -> None:
        horizontal = Segment(Point(5, 0), Point(100, 0))
        vertical = Segment(Point(0, 6), Point(0, 100))
        snapped, joined = snap_endpoints([horizontal, vertical], tol=10)
        assert snapped[0].start == Point(0, 0)
        assert snapped[1].start == Point(0, 0)
        assert joined == [(True, False), (True, False)]

    def test_segment_coverage(self) -> None:
        mask = np.zeros((20, 100), bool)
        mask[10, :50] = True
        assert segment_coverage(mask, Segment(Point(0, 10), Point(99, 10))) == pytest.approx(
            0.5, abs=0.05
        )


class TestDoors:
    def test_arc_increases_score(self) -> None:
        residual = np.zeros((200, 200), bool)
        gap = Segment(Point(50, 100), Point(100, 100))
        assert arc_score(residual, gap) == 0.0
        canvas = np.zeros((200, 200), np.uint8)
        cv2.ellipse(canvas, (50, 100), (50, 50), 0, 0, -90, 255, 1)
        assert arc_score(canvas > 0, gap) > 0.8

    def test_outline_and_points_on_it(self) -> None:
        mask = np.zeros((200, 300), bool)
        mask[40:50, 40:260] = True
        mask[150:160, 40:260] = True
        mask[40:160, 40:50] = True
        mask[40:160, 250:260] = True
        mask[150:160, 120:170] = False  # salida
        outline = building_outline(mask, close_px=70)
        assert outline is not None
        assert is_on_outline(outline, Point(145, 155), tol=15)
        assert not is_on_outline(outline, Point(150, 100), tol=15)
        assert building_outline(np.zeros((10, 10), bool), 5) is None


def test_angle_helpers_are_consistent() -> None:
    group = LineGroup(math.pi / 2, -30.0, 1.0)  # recta vertical x = 30
    p = group.point_at(10)
    assert p.x == pytest.approx(30)
    assert p.y == pytest.approx(10)
