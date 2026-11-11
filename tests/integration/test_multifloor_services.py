"""Servicios con un edificio de dos pisos: simular, guardar, recuperar, normas e informe."""

from __future__ import annotations

import dataclasses
from datetime import date
from pathlib import Path

import numpy as np
import pymupdf
import pytest

from rutasegura.application.errors import UserFacingError
from rutasegura.application.services import AppServices
from rutasegura.domain.enums import UseType
from rutasegura.domain.people import Occupancy
from rutasegura.domain.scenario import RealDrill, Scenario
from tests.fixtures.simple_plans import two_floor_building


@pytest.fixture
def building(services: AppServices) -> tuple[int, Scenario]:
    project_id = services.projects.create_project("Colegio de dos pisos", UseType.EDUCATION)
    ground, upper = two_floor_building()
    image = np.full((320, 520, 3), 250, np.uint8)
    services.projects.save_floor(project_id, ground, image)
    services.projects.save_floor(project_id, upper, image)
    scenario = dataclasses.replace(
        services.simulations.load_scenario(project_id),
        occupancies=(Occupancy("Hall", "adulto", 10), Occupancy("Aula 201", "niño", 25, level=1)),
    )
    services.simulations.save_scenario(project_id, scenario)
    return project_id, scenario


def test_run_store_and_reload(services: AppServices, building: tuple[int, Scenario]) -> None:
    project_id, scenario = building
    floors = services.projects.load_floors(project_id)
    assert [f.level for f in floors] == [0, 1]
    assert floors[1].stairs[0].name == "Escalera A"  # el nombre se guarda
    run = services.simulations.run(project_id, floors, scenario)
    assert run.result.completed
    assert run.result.agents_total == 35
    assert [m.level for m in run.result.floor_maps] == [0, 1]
    assert run.scale_of(1) == pytest.approx(0.02)

    again = services.simulations.last_run(project_id)
    assert again is not None
    assert [m.level for m in again.result.floor_maps] == [0, 1]
    assert again.trajectories.level is not None
    assert again.floor_scales == ((0, 0.02), (1, 0.02))
    assert again.result.total_time_s == run.result.total_time_s


def test_building_norms(services: AppServices, building: tuple[int, Scenario]) -> None:
    project_id, scenario = building
    floors = services.projects.load_floors(project_id)
    crowded = dataclasses.replace(
        scenario, occupancies=(Occupancy("Aula 201", "niño", 300, level=1),)
    )
    evaluation = services.norms.evaluate_building(floors, crowded)
    texts = [o.description for o in evaluation.observations]
    # el piso 1 debe dar salida a todo el edificio (300 personas × 0.005 m > 1.2 m)
    assert any(t.startswith("Piso 1: Las salidas confirmadas suman 1.20 m") for t in texts)
    # el piso 2 no se evalúa por salidas: se baja por la escalera
    assert not any(t.startswith("Piso 2: Las salidas confirmadas") for t in texts)
    assert any(t.startswith("Piso 2: «Aula 201» tiene 300 personas") for t in texts)
    assert {c.level for c in evaluation.capacities} == {0, 1}


def test_report_has_one_heatmap_per_floor(
    services: AppServices, building: tuple[int, Scenario], tmp_path: Path
) -> None:
    project_id, scenario = building
    services.simulations.run(project_id, services.projects.load_floors(project_id), scenario)
    path = services.reports.generate(project_id, tmp_path / "edificio.pdf")
    with pymupdf.open(path) as doc:
        text = " ".join(" ".join(page.get_text() for page in doc).split())
    assert "Mapa de calor de congestión — Piso 1" in text
    assert "Mapa de calor de congestión — Piso 2" in text


def test_validation_and_calibration(services: AppServices, building: tuple[int, Scenario]) -> None:
    project_id, scenario = building
    ground, upper = services.projects.load_floors(project_id)
    without_stair = dataclasses.replace(ground, stairs=())
    with pytest.raises(UserFacingError, match="no tiene una escalera correspondiente en el piso 1"):
        services.simulations.simulate([without_stair, upper], scenario)
    with pytest.raises(UserFacingError, match="El piso 2 no tiene escala"):
        services.simulations.simulate(
            [ground, dataclasses.replace(upper, scale_m_per_px=None)], scenario
        )
    drill = RealDrill(date(2026, 10, 8), 35, 90.0)
    result = services.calibration.calibrate(
        project_id,
        [ground, upper],
        scenario,
        drill,
        reaction_factors=(1.0,),
        speed_factors=(1.0,),
    )
    assert result.best.reaction_factor == 1.0
