"""Detección completa sobre planos sintéticos (RF02) y métricas de evaluación."""

from __future__ import annotations

import numpy as np
import pytest

from rutasegura.domain.geometry import Point, Segment
from rutasegura.engines.vision.metrics import Score, coverage, opening_score, wall_score
from rutasegura.engines.vision.pipeline import VisionParams, detect_plan
from tests.fixtures.synthetic_plans import SyntheticPlan, generate_plan

SEEDS = range(6)
TARGET = 0.85  # meta del proyecto (CLAUDE.md §5.1)


def _scores(plan: SyntheticPlan, params: VisionParams) -> tuple[Score, Score, Score]:
    result = detect_plan(plan.image, params)
    tol = 0.2 / plan.scale_m_per_px
    walls = wall_score([w.segment for w in result.walls], plan.walls, tol)
    predicted = [d.segment for d in result.doors] + [e.segment for e in result.exits]
    openings = opening_score(predicted, plan.openings, tol)
    exits = opening_score([e.segment for e in result.exits], plan.exits, tol)
    return walls, openings, exits


@pytest.fixture(scope="module")
def plans() -> list[SyntheticPlan]:
    return [generate_plan(seed) for seed in SEEDS]


def test_synthetic_plans_meet_target_with_scale(plans: list[SyntheticPlan]) -> None:
    rows = [_scores(p, VisionParams(scale_m_per_px=p.scale_m_per_px)) for p in plans]
    walls = np.mean([[w.precision, w.recall] for w, _, _ in rows], axis=0)
    openings = np.mean([[o.precision, o.recall] for _, o, _ in rows], axis=0)
    exits = np.mean([[e.precision, e.recall] for _, _, e in rows], axis=0)
    assert (walls >= TARGET).all(), walls
    assert (openings >= TARGET).all(), openings
    assert (exits >= TARGET).all(), exits


def test_detection_without_scale_still_works(plans: list[SyntheticPlan]) -> None:
    rows = [_scores(p, VisionParams()) for p in plans[:3]]
    assert np.mean([w.f1 for w, _, _ in rows]) >= TARGET
    assert np.mean([o.f1 for _, o, _ in rows]) >= TARGET


def test_exits_are_proposals_pending_confirmation(plans: list[SyntheticPlan]) -> None:
    plan = plans[0]
    result = detect_plan(plan.image, VisionParams(scale_m_per_px=plan.scale_m_per_px))
    assert result.exits
    assert all(not e.confirmed for e in result.exits)
    assert [e.name for e in result.exits] == [f"Salida {i + 1}" for i in range(len(result.exits))]
    assert all(0.0 <= d.confidence <= 1.0 for d in result.doors)
    assert all(0.0 <= w.confidence <= 1.0 for w in result.walls)


def test_door_widths_are_accurate(plans: list[SyntheticPlan]) -> None:
    """Los anchos importan para verificar mínimos normativos (RF06)."""
    plan = plans[1]
    result = detect_plan(plan.image, VisionParams(scale_m_per_px=plan.scale_m_per_px))
    for truth in plan.doors:
        nearest = min(result.doors, key=lambda d: d.segment.midpoint.distance_to(truth.midpoint))
        error_m = abs(nearest.segment.length - truth.length) * plan.scale_m_per_px
        assert error_m < 0.1


def test_detection_is_deterministic(plans: list[SyntheticPlan]) -> None:
    plan = plans[2]
    assert detect_plan(plan.image) == detect_plan(plan.image)


def test_blank_image_returns_nothing() -> None:
    result = detect_plan(np.full((300, 400, 3), 255, np.uint8))
    assert result.walls == ()
    assert result.doors == ()


def test_synthetic_generator_is_reproducible() -> None:
    a, b = generate_plan(11), generate_plan(11)
    assert np.array_equal(a.image, b.image)
    assert a.walls == b.walls
    assert not np.array_equal(a.image, generate_plan(12).image)


class TestMetrics:
    def test_perfect_and_shifted_walls(self) -> None:
        truth = [Segment(Point(0, 0), Point(100, 0))]
        assert wall_score(truth, truth, tol=2) == Score(1.0, 1.0)
        shifted = [Segment(Point(0, 10), Point(100, 10))]
        assert wall_score(shifted, truth, tol=2) == Score(0.0, 0.0)

    def test_partial_coverage(self) -> None:
        truth = [Segment(Point(0, 0), Point(100, 0))]
        half = [Segment(Point(0, 0), Point(50, 0))]
        assert coverage(truth, half, tol=1) == pytest.approx(0.5, abs=0.05)
        assert coverage([], [], tol=1) == 1.0

    def test_openings_matched_one_to_one(self) -> None:
        truth = [Segment(Point(0, 0), Point(40, 0)), Segment(Point(200, 0), Point(240, 0))]
        predicted = [Segment(Point(2, 1), Point(41, 1)), Segment(Point(5, 0), Point(38, 0))]
        score = opening_score(predicted, truth, tol=5)
        assert score.precision == 0.5
        assert score.recall == 0.5
        assert score.f1 == pytest.approx(0.5)
        assert opening_score([], [], tol=5) == Score(1.0, 1.0)
