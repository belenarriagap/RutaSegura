"""Escenarios «qué pasa si» (RF10) y calibración con un simulacro real (RF11)."""

from __future__ import annotations

import dataclasses
from datetime import date

import pytest

from rutasegura.application.errors import OperationCancelled, UserFacingError
from rutasegura.application.services import AppServices
from rutasegura.application.simulation_service import BASE_SCENARIO, scale_occupancies
from rutasegura.domain.enums import UseType
from rutasegura.domain.people import Occupancy
from rutasegura.domain.scenario import RealDrill, Scenario
from rutasegura.engines.calibration.grid_search import scale_profiles
from tests.fixtures.simple_plans import single_room

PLAN = single_room(exit_width=0.9, second_exit=True)


@pytest.fixture
def project(services: AppServices) -> tuple[int, Scenario]:
    project_id = services.projects.create_project("Colegio", UseType.EDUCATION)
    services.projects.save_floor(project_id, PLAN)
    base = dataclasses.replace(
        services.simulations.load_scenario(project_id),
        occupancies=(Occupancy("Aula 1", "adulto", 30), Occupancy("Aula 1", "niño", 10)),
    )
    services.simulations.save_scenario(project_id, base)
    return project_id, base


def test_scale_occupancies_keeps_exact_total() -> None:
    occ = (Occupancy("A", "adulto", 3), Occupancy("A", "niño", 3), Occupancy("B", "niño", 1))
    scaled = scale_occupancies(occ, 10)
    assert sum(o.count for o in scaled) == 10
    assert [o.count for o in scaled] == [4, 4, 2]
    assert scale_occupancies(occ, 0) == ()
    assert scale_occupancies((), 5) == ()
    assert sum(o.count for o in scale_occupancies(occ, 1)) == 1


class TestScenarios:
    def test_list_create_rename_delete(
        self, services: AppServices, project: tuple[int, Scenario]
    ) -> None:
        project_id, base = project
        assert [s.name for s in services.simulations.list_scenarios(project_id)] == [BASE_SCENARIO]
        variant = services.simulations.save_variant(
            project_id, "Salida 2 bloqueada", base, 150, {"Salida 2"}
        )
        assert variant.total_occupants == 60
        assert variant.blocked_exits == frozenset({"Salida 2"})
        assert variant.seed == base.seed
        names = [s.name for s in services.simulations.list_scenarios(project_id)]
        assert names == [BASE_SCENARIO, "Salida 2 bloqueada"]
        renamed = services.simulations.save_variant(
            project_id, "Sin salida 2", base, 100, {"Salida 2"}, previous_name="Salida 2 bloqueada"
        )
        assert renamed.total_occupants == 40
        names = [s.name for s in services.simulations.list_scenarios(project_id)]
        assert names == [BASE_SCENARIO, "Sin salida 2"]
        assert services.simulations.load_scenario(project_id, "Sin salida 2") == renamed
        services.simulations.delete_scenario(project_id, "Sin salida 2")
        services.simulations.delete_scenario(project_id, "No existe")  # no falla
        assert len(services.simulations.list_scenarios(project_id)) == 1

    @pytest.mark.parametrize(
        ("name", "percent", "message"),
        [
            ("", 100, "nombre"),
            (BASE_SCENARIO, 100, "paso 4"),
            ("Otro", 0, "mayor que cero"),
        ],
    )
    def test_variant_validation(
        self,
        services: AppServices,
        project: tuple[int, Scenario],
        name: str,
        percent: float,
        message: str,
    ) -> None:
        project_id, base = project
        with pytest.raises(UserFacingError, match=message):
            services.simulations.save_variant(project_id, name, base, percent, set())

    def test_duplicate_and_protected_names(
        self, services: AppServices, project: tuple[int, Scenario]
    ) -> None:
        project_id, base = project
        services.simulations.save_variant(project_id, "A", base, 100, set())
        with pytest.raises(UserFacingError, match="Ya existe"):
            services.simulations.save_variant(project_id, "A", base, 100, set())
        with pytest.raises(UserFacingError, match="no se puede eliminar"):
            services.simulations.delete_scenario(project_id, BASE_SCENARIO)
        with pytest.raises(UserFacingError, match="No existe"):
            services.simulations.load_scenario(project_id, "Z")

    def test_blocking_an_exit_takes_longer(
        self, services: AppServices, project: tuple[int, Scenario]
    ) -> None:
        project_id, base = project
        variant = services.simulations.save_variant(
            project_id, "Bloqueada", base, 100, {"Salida 2"}
        )
        base_run = services.simulations.run(project_id, PLAN, base)
        variant_run = services.simulations.run(project_id, PLAN, variant)
        assert variant_run.result.total_time_s > base_run.result.total_time_s
        assert {n for n, _ in variant_run.result.time_per_exit_s} == {"Salida 1"}
        last_base = services.simulations.last_run(project_id)
        last_variant = services.simulations.last_run(project_id, "Bloqueada")
        assert last_base is not None
        assert last_variant is not None
        assert last_base.simulation_id == base_run.simulation_id
        assert last_variant.simulation_id == variant_run.simulation_id


class TestCalibration:
    def test_recovers_known_factors_and_applies_them(
        self, services: AppServices, project: tuple[int, Scenario]
    ) -> None:
        project_id, base = project
        # "Simulacro" fabricado con reacción ×1.5 y velocidad ×0.8, con 30 participantes.
        participants = 30
        drill_scenario = dataclasses.replace(
            base, occupancies=scale_occupancies(base.occupancies, participants)
        )
        true_profiles = scale_profiles(services.simulations.profiles(), 1.5, 0.8)
        truth = services.simulations.simulate(PLAN, drill_scenario, true_profiles).result
        drill = RealDrill(
            date(2026, 10, 8), participants, truth.total_time_s, truth.time_per_exit_s
        )
        progress: list[float] = []
        result = services.calibration.calibrate(
            project_id,
            PLAN,
            base,
            drill,
            reaction_factors=(1.0, 1.5),
            speed_factors=(0.8, 1.0),
            progress=progress.append,
        )
        assert (result.best.reaction_factor, result.best.speed_factor) == (1.5, 0.8)
        assert result.best.error == pytest.approx(0.0)
        assert result.total_error_before > result.total_error_after
        assert result.meets_target
        assert progress == sorted(progress)
        assert progress[-1] == pytest.approx(1.0)
        assert services.calibration.drills(project_id) == [drill]

        before = {p.name: p for p in services.simulations.profiles()}
        services.calibration.apply(result)
        after = {p.name: p for p in services.simulations.profiles()}
        for name, profile in before.items():
            assert after[name].reaction_mean_s == pytest.approx(profile.reaction_mean_s * 1.5)
            assert after[name].max_speed_mps == pytest.approx(profile.max_speed_mps * 0.8)

    def test_cancel_and_empty_scenario(
        self, services: AppServices, project: tuple[int, Scenario]
    ) -> None:
        project_id, base = project
        drill = RealDrill(date(2026, 10, 8), 20, 60.0)
        with pytest.raises(OperationCancelled):
            services.calibration.calibrate(
                project_id, PLAN, base, drill, should_cancel=lambda: True
            )
        assert services.calibration.drills(project_id) == []
        empty = dataclasses.replace(base, occupancies=())
        with pytest.raises(UserFacingError, match="paso 4"):
            services.calibration.calibrate(project_id, PLAN, empty, drill)
