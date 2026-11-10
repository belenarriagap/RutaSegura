"""Pruebas de las estructuras de dominio."""

from __future__ import annotations

import dataclasses
from datetime import date

import numpy as np
import pytest

from rutasegura.domain import (
    AgentArrays,
    AgentStatus,
    Door,
    FloorPlan,
    Observation,
    ObservationType,
    Occupancy,
    PersonProfile,
    Point,
    Polygon,
    RealDrill,
    Room,
    Scenario,
    Segment,
    SimulationResult,
    UseType,
    Wall,
)


def _square(side: float) -> Polygon:
    return Polygon((Point(0, 0), Point(side, 0), Point(side, side), Point(0, side)))


class TestGeometry:
    def test_segment_length_and_midpoint(self) -> None:
        seg = Segment(Point(0, 0), Point(3, 4))
        assert seg.length == pytest.approx(5.0)
        assert seg.midpoint == Point(1.5, 2.0)

    def test_polygon_area_is_positive_in_both_orientations(self) -> None:
        square = _square(10)
        reversed_square = Polygon(tuple(reversed(square.vertices)))
        assert square.area == pytest.approx(100.0)
        assert reversed_square.area == pytest.approx(100.0)
        assert square.centroid == Point(5, 5)

    def test_polygon_needs_three_vertices(self) -> None:
        with pytest.raises(ValueError, match="al menos 3"):
            Polygon((Point(0, 0), Point(1, 1)))


class TestFloorPlan:
    def test_conversion_to_meters(self) -> None:
        plan = FloorPlan(scale_m_per_px=0.05)
        assert plan.is_scaled
        assert plan.to_meters(20) == pytest.approx(1.0)
        assert plan.area_m2(_square(100)) == pytest.approx(25.0)

    def test_unscaled_plan_refuses_conversion(self) -> None:
        plan = FloorPlan()
        assert not plan.is_scaled
        with pytest.raises(ValueError, match="escala"):
            plan.to_meters(10)
        with pytest.raises(ValueError, match="escala"):
            plan.area_m2(_square(1))

    def test_invalid_scale(self) -> None:
        with pytest.raises(ValueError, match="escala"):
            FloorPlan(scale_m_per_px=0)

    def test_plan_is_immutable_and_replaceable(self) -> None:
        wall = Wall(Segment(Point(0, 0), Point(100, 0)))
        plan = FloorPlan(walls=(wall,))
        with pytest.raises(dataclasses.FrozenInstanceError):
            plan.level = 2  # type: ignore[misc]
        edited = dataclasses.replace(plan, rooms=(Room("Aula 1", UseType.EDUCATION, _square(5)),))
        assert edited.walls == plan.walls
        assert len(edited.rooms) == 1
        assert len(plan.rooms) == 0

    @pytest.mark.parametrize("confidence", [-0.1, 1.5])
    def test_confidence_range(self, confidence: float) -> None:
        with pytest.raises(ValueError, match="confianza"):
            Door(Segment(Point(0, 0), Point(1, 0)), confidence=confidence)


class TestPeopleAndScenario:
    def test_profile_validation(self) -> None:
        with pytest.raises(ValueError, match="velocidad"):
            PersonProfile("x", max_speed_mps=0, reaction_mean_s=1, reaction_std_s=0, radius_m=0.2)
        with pytest.raises(ValueError, match="reacción"):
            PersonProfile("x", max_speed_mps=1, reaction_mean_s=-1, reaction_std_s=0, radius_m=0.2)
        with pytest.raises(ValueError, match="radio"):
            PersonProfile("x", max_speed_mps=1, reaction_mean_s=1, reaction_std_s=0, radius_m=0)

    def test_occupancy_cannot_be_negative(self) -> None:
        with pytest.raises(ValueError, match="negativa"):
            Occupancy("Aula 1", "adulto", -1)

    def test_scenario_total_and_seed(self) -> None:
        scenario = Scenario(
            "Base",
            seed=42,
            occupancies=(Occupancy("Aula 1", "niño", 30), Occupancy("Aula 1", "adulto", 1)),
            blocked_exits=frozenset({"Salida 2"}),
        )
        assert scenario.total_occupants == 31
        with pytest.raises(ValueError, match="semilla"):
            Scenario("Mala", seed=-1)

    def test_real_drill_validation(self) -> None:
        RealDrill(date(2026, 5, 31), participants=200, total_time_s=180.0)
        with pytest.raises(ValueError, match="participante"):
            RealDrill(date(2026, 5, 31), participants=0, total_time_s=180.0)
        with pytest.raises(ValueError, match="tiempo total"):
            RealDrill(date(2026, 5, 31), participants=10, total_time_s=0)


class TestAgentArrays:
    def test_empty_has_consistent_shapes(self) -> None:
        agents = AgentArrays.empty(5)
        assert len(agents) == 5
        assert agents.position.shape == (5, 2)
        assert agents.evacuated_count == 0
        agents.status[:2] = AgentStatus.EVACUATED
        assert agents.evacuated_count == 2

    def test_inconsistent_shapes_are_rejected(self) -> None:
        agents = AgentArrays.empty(3)
        with pytest.raises(ValueError, match="radius"):
            dataclasses.replace(agents, radius=np.zeros(4))
        with pytest.raises(ValueError, match="position y velocity"):
            dataclasses.replace(agents, velocity=np.zeros((3, 3)))


class TestResults:
    def test_norm_observation_must_cite_article(self) -> None:
        with pytest.raises(ValueError, match="artículo"):
            Observation(ObservationType.NORM, "Puerta angosta", "Ensanchar la puerta")
        obs = Observation(
            ObservationType.NORM,
            "Puerta angosta",
            "Ensanchar la puerta",
            norm="RNE A.130",
            article="Art. X",
            verified=False,
        )
        assert not obs.verified

    def test_congestion_observation_without_article(self) -> None:
        obs = Observation(ObservationType.CONGESTION, "Congestión", "Abrir segunda salida")
        assert obs.article is None

    def test_result_curve_shapes_must_match(self) -> None:
        with pytest.raises(ValueError, match="curva"):
            SimulationResult(
                seed=1,
                total_time_s=10.0,
                time_per_exit_s=(),
                curve_times_s=np.zeros(3),
                curve_evacuated=np.zeros(2, dtype=np.int32),
                density_map=np.zeros((2, 2)),
            )
