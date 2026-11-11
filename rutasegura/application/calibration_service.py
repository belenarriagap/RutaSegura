"""Registro de simulacros reales y calibración del modelo (RF11)."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Sequence

from rutasegura.application.errors import OperationCancelled, UserFacingError
from rutasegura.application.simulation_service import SimulationService, scale_occupancies
from rutasegura.data.database import Database
from rutasegura.domain.calibration import CalibrationResult
from rutasegura.domain.plan import FloorPlan
from rutasegura.domain.scenario import RealDrill, Scenario
from rutasegura.engines.calibration.grid_search import (
    DEFAULT_REACTION_FACTORS,
    DEFAULT_SPEED_FACTORS,
    CalibrationCancelled,
    Outcome,
    grid_search,
    scale_profiles,
)


class CalibrationService:
    """Compara la simulación con un simulacro real y ajusta los perfiles."""

    def __init__(self, db: Database, simulations: SimulationService) -> None:
        self._db = db
        self._simulations = simulations

    def drills(self, project_id: int) -> list[RealDrill]:
        """Simulacros registrados del proyecto, por fecha."""
        with self._db.unit_of_work() as uow:
            return [d for _, d in uow.drills.list_all(project_id)]

    def calibrate(
        self,
        project_id: int,
        plan: FloorPlan | Sequence[FloorPlan],
        scenario: Scenario,
        drill: RealDrill,
        *,
        reaction_factors: Sequence[float] = DEFAULT_REACTION_FACTORS,
        speed_factors: Sequence[float] = DEFAULT_SPEED_FACTORS,
        progress: Callable[[float], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> CalibrationResult:
        """Registra el simulacro y busca los factores que mejor lo reproducen.

        La ocupación del escenario se reparte proporcionalmente para que el total sea igual a
        los participantes del simulacro.
        """
        if scenario.total_occupants == 0:
            raise UserFacingError(
                "Primero indique cómo se reparten las personas en los ambientes (paso 4)."
            )
        drill_scenario = dataclasses.replace(
            scenario, occupancies=scale_occupancies(scenario.occupancies, drill.participants)
        )
        base_profiles = self._simulations.profiles()
        combos = len({*reaction_factors, 1.0}) * len({*speed_factors, 1.0})
        done = 0

        def evaluate(reaction: float, speed: float) -> Outcome:
            nonlocal done
            profiles = scale_profiles(base_profiles, reaction, speed)

            def inner(fraction: float) -> None:
                if progress is not None:
                    progress(min(1.0, (done + fraction) / combos))

            output = self._simulations.simulate(
                plan, drill_scenario, profiles, progress=inner, should_cancel=should_cancel
            )
            done += 1
            return Outcome(output.result.total_time_s, dict(output.result.time_per_exit_s))

        try:
            result = grid_search(
                evaluate,
                drill,
                reaction_factors,
                speed_factors,
                should_cancel=should_cancel,
            )
        except CalibrationCancelled as exc:
            raise OperationCancelled from exc
        with self._db.unit_of_work() as uow:
            uow.drills.add(project_id, drill)
        return result

    def apply(self, result: CalibrationResult) -> None:
        """Multiplica reacción y velocidad de todos los perfiles por los factores calibrados."""
        best = result.best
        with self._db.unit_of_work() as uow:
            for profile in scale_profiles(
                uow.profiles.list_all(), best.reaction_factor, best.speed_factor
            ):
                uow.profiles.save(profile)
