"""Calibración por búsqueda en rejilla (CLAUDE.md §5.5).

Se ajustan dos factores globales: uno multiplica el tiempo de reacción de todos los perfiles y otro
su velocidad máxima. Así se conservan las diferencias entre perfiles (adulto, niño, movilidad
reducida). El error es el RMSE de los errores relativos del tiempo total y de los tiempos por
salida registrados en el simulacro.

El motor recibe una función ``evaluate(factor_reacción, factor_velocidad) → Outcome``; así no
depende de cómo se arma la simulación y se prueba con funciones simples.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from rutasegura.domain.calibration import CalibrationPoint, CalibrationResult
from rutasegura.domain.people import PersonProfile
from rutasegura.domain.scenario import RealDrill

DEFAULT_REACTION_FACTORS = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0)
DEFAULT_SPEED_FACTORS = (0.7, 0.8, 0.9, 1.0, 1.1, 1.2)


class CalibrationCancelled(Exception):  # noqa: N818 - nombre de dominio
    """El usuario canceló la calibración."""


@dataclass(frozen=True)
class Outcome:
    """Lo que se compara con el simulacro: tiempo total y tiempo de cada salida."""

    total_time_s: float
    per_exit_s: Mapping[str, float] = field(default_factory=dict)


Evaluate = Callable[[float, float], Outcome]


def relative_errors(outcome: Outcome, drill: RealDrill) -> list[float]:
    """Errores relativos (simulado − observado) / observado del total y de cada salida medida."""
    errors = [(outcome.total_time_s - drill.total_time_s) / drill.total_time_s]
    for name, observed in drill.time_per_exit_s:
        if observed > 0 and name in outcome.per_exit_s:
            errors.append((outcome.per_exit_s[name] - observed) / observed)
    return errors


def calibration_error(outcome: Outcome, drill: RealDrill) -> float:
    """RMSE de los errores relativos."""
    errors = relative_errors(outcome, drill)
    return math.sqrt(sum(e * e for e in errors) / len(errors))


def scale_profiles(
    profiles: Sequence[PersonProfile], reaction_factor: float, speed_factor: float
) -> list[PersonProfile]:
    """Perfiles con reacción (media y desviación) y velocidad multiplicadas."""
    if reaction_factor <= 0 or speed_factor <= 0:
        raise ValueError("Los factores de calibración deben ser positivos.")
    return [
        PersonProfile(
            name=p.name,
            max_speed_mps=p.max_speed_mps * speed_factor,
            reaction_mean_s=p.reaction_mean_s * reaction_factor,
            reaction_std_s=p.reaction_std_s * reaction_factor,
            radius_m=p.radius_m,
        )
        for p in profiles
    ]


def grid_search(
    evaluate: Evaluate,
    drill: RealDrill,
    reaction_factors: Sequence[float] = DEFAULT_REACTION_FACTORS,
    speed_factors: Sequence[float] = DEFAULT_SPEED_FACTORS,
    *,
    progress: Callable[[float], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> CalibrationResult:
    """Evalúa todas las combinaciones y elige la de menor error.

    La rejilla siempre incluye el punto (1, 1) para medir el error antes de calibrar. A igual
    error gana la combinación más cercana a (1, 1) (cambia menos el modelo).
    """
    reactions = sorted({*reaction_factors, 1.0})
    speeds = sorted({*speed_factors, 1.0})
    if any(f <= 0 for f in (*reactions, *speeds)):
        raise ValueError("Los factores de calibración deben ser positivos.")
    combos = [(r, s) for r in reactions for s in speeds]
    points: list[CalibrationPoint] = []
    for i, (r, s) in enumerate(combos):
        if should_cancel is not None and should_cancel():
            raise CalibrationCancelled
        outcome = evaluate(r, s)
        points.append(
            CalibrationPoint(r, s, outcome.total_time_s, calibration_error(outcome, drill))
        )
        if progress is not None:
            progress((i + 1) / len(combos))
    baseline = next(p for p in points if p.reaction_factor == 1.0 and p.speed_factor == 1.0)
    best = min(
        points,
        key=lambda p: (
            round(p.error, 9),
            abs(math.log(p.reaction_factor)) + abs(math.log(p.speed_factor)),
        ),
    )
    return CalibrationResult(drill.total_time_s, baseline, best, tuple(points))
