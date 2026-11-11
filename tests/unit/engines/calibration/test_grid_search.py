"""Calibración por búsqueda en rejilla con un modelo de evacuación de juguete."""

from __future__ import annotations

from datetime import date

import pytest

from rutasegura.domain.calibration import CalibrationPoint, CalibrationResult
from rutasegura.domain.people import PersonProfile
from rutasegura.domain.scenario import RealDrill
from rutasegura.engines.calibration.grid_search import (
    CalibrationCancelled,
    Outcome,
    calibration_error,
    grid_search,
    relative_errors,
    scale_profiles,
)


def toy_model(reaction_factor: float, speed_factor: float) -> Outcome:
    """Tiempo = reacción + recorrido / velocidad (40 s y 60 s con factores 1)."""
    total = 40 * reaction_factor + 60 / speed_factor
    return Outcome(total, {"Salida 1": total, "Salida 2": 0.8 * total})


DRILL = RealDrill(date(2026, 10, 8), participants=120, total_time_s=40 * 1.5 + 60 / 0.8)


def test_errors() -> None:
    outcome = Outcome(110.0, {"Salida 1": 110.0})
    drill = RealDrill(date(2026, 1, 1), 10, 100.0, (("Salida 1", 100.0), ("Salida 9", 50.0)))
    assert relative_errors(outcome, drill) == pytest.approx([0.1, 0.1])  # Salida 9 no se simuló
    assert calibration_error(outcome, drill) == pytest.approx(0.1)
    assert calibration_error(Outcome(100.0), RealDrill(date(2026, 1, 1), 10, 100.0)) == 0.0


def test_grid_search_recovers_the_true_factors() -> None:
    progress: list[float] = []
    result = grid_search(toy_model, DRILL, progress=progress.append)
    assert result.best.reaction_factor == 1.5
    assert result.best.speed_factor == 0.8
    assert result.best.error == pytest.approx(0.0)
    assert result.baseline.reaction_factor == 1.0
    assert result.baseline.speed_factor == 1.0
    assert result.total_error_before > 0.2
    assert result.total_error_after == pytest.approx(0.0)
    assert result.meets_target
    assert len(result.points) == 36
    assert progress[-1] == 1.0


def test_baseline_is_always_evaluated() -> None:
    result = grid_search(toy_model, DRILL, reaction_factors=(2.0,), speed_factors=(0.5,))
    assert {(p.reaction_factor, p.speed_factor) for p in result.points} == {
        (1.0, 0.5),
        (1.0, 1.0),
        (2.0, 0.5),
        (2.0, 1.0),
    }


def test_ties_prefer_the_smallest_change() -> None:
    flat = grid_search(lambda r, s: Outcome(DRILL.total_time_s), DRILL)
    assert (flat.best.reaction_factor, flat.best.speed_factor) == (1.0, 1.0)


def test_cancel_and_invalid_factors() -> None:
    with pytest.raises(CalibrationCancelled):
        grid_search(toy_model, DRILL, should_cancel=lambda: True)
    with pytest.raises(ValueError, match="positivos"):
        grid_search(toy_model, DRILL, reaction_factors=(0.0,))
    with pytest.raises(ValueError, match="positivos"):
        scale_profiles([], 0.0, 1.0)


def test_scale_profiles_keeps_differences() -> None:
    profiles = [
        PersonProfile("adulto", 1.3, 30, 10, 0.25),
        PersonProfile("niño", 1.0, 20, 8, 0.2),
    ]
    scaled = scale_profiles(profiles, 1.5, 0.8)
    assert scaled[0].reaction_mean_s == pytest.approx(45)
    assert scaled[0].reaction_std_s == pytest.approx(15)
    assert scaled[1].max_speed_mps == pytest.approx(0.8)
    assert scaled[1].radius_m == 0.2
    assert scaled[0].max_speed_mps / scaled[1].max_speed_mps == pytest.approx(1.3)


def test_result_properties() -> None:
    base = CalibrationPoint(1.0, 1.0, 150.0, 0.5)
    best = CalibrationPoint(0.8, 1.1, 105.0, 0.05)
    result = CalibrationResult(100.0, base, best, (base, best))
    assert result.total_error_before == pytest.approx(0.5)
    assert result.total_error_after == pytest.approx(0.05)
    assert result.meets_target
