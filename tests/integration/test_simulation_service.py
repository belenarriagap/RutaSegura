"""Servicio de simulación: validaciones, ejecución, guardado y recuperación de la corrida."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import pytest

from rutasegura.application.errors import OperationCancelled, UserFacingError
from rutasegura.application.services import AppServices
from rutasegura.application.simulation_service import BASE_SCENARIO, describe_place
from rutasegura.data.trajectories import load_run
from rutasegura.domain.enums import ObservationType, UseType
from rutasegura.domain.geometry import Point
from rutasegura.domain.people import Occupancy
from rutasegura.domain.plan import Exit, FloorPlan
from tests.fixtures.simple_plans import SCALE, single_room, two_rooms


def _project(services: AppServices, plan: FloorPlan) -> int:
    project_id = services.projects.create_project("Colegio", UseType.EDUCATION)
    services.projects.save_floor(project_id, plan)
    return project_id


def test_full_run_is_saved_and_reloaded(services: AppServices) -> None:
    plan = two_rooms()
    project_id = _project(services, plan)
    scenario = dataclasses.replace(
        services.simulations.load_scenario(project_id),
        occupancies=(Occupancy("Aula 1", "niño", 30), Occupancy("Aula 2", "adulto", 20)),
    )
    assert scenario.name == BASE_SCENARIO
    progress: list[float] = []
    run = services.simulations.run(project_id, plan, scenario, progress=progress.append)
    assert run.result.completed
    assert run.result.agents_evacuated == 50
    assert progress[-1] == 1.0
    assert run.result.trajectories_path is not None
    assert Path(run.result.trajectories_path).exists()
    assert all(o.kind is ObservationType.CONGESTION for o in run.observations)

    stored = load_run(Path(run.result.trajectories_path))
    assert np.array_equal(stored.trajectories.positions, run.trajectories.positions)
    assert stored.bottlenecks == run.result.bottlenecks

    again = services.simulations.last_run(project_id)
    assert again is not None
    assert again.simulation_id == run.simulation_id
    assert again.result.total_time_s == run.result.total_time_s
    assert np.array_equal(again.result.density_map, run.result.density_map)
    assert again.observations == run.observations
    assert services.simulations.load_scenario(project_id) == scenario


@pytest.mark.parametrize(
    ("plan", "occupants", "message"),
    [
        (dataclasses.replace(single_room(), scale_m_per_px=None), 1, "escala"),
        (single_room(confirmed=False), 1, "ninguna salida confirmada"),
        (dataclasses.replace(single_room(), exits=()), 1, "ninguna salida"),
        (dataclasses.replace(single_room(), rooms=()), 1, "ambientes"),
        (single_room(), 0, "cuántas personas"),
    ],
)
def test_validation_messages(
    services: AppServices, plan: FloorPlan, occupants: int, message: str
) -> None:
    project_id = services.projects.create_project("Local", UseType.OFFICE)
    scenario = dataclasses.replace(
        services.simulations.load_scenario(project_id),
        occupancies=(Occupancy("Aula 1", "adulto", occupants),) if occupants else (),
    )
    with pytest.raises(UserFacingError, match=message):
        services.simulations.run(project_id, plan, scenario)


def test_cancel(services: AppServices) -> None:
    plan = single_room()
    project_id = _project(services, plan)
    scenario = dataclasses.replace(
        services.simulations.load_scenario(project_id),
        occupancies=(Occupancy("Aula 1", "adulto", 10),),
    )
    with pytest.raises(OperationCancelled):
        services.simulations.run(project_id, plan, scenario, should_cancel=lambda: True)
    assert services.simulations.last_run(project_id) is None


def test_describe_place() -> None:
    plan = single_room()
    assert describe_place(plan, SCALE, Point(9.6, 3.0)) == "junto a «Salida 1» de «Aula 1»"
    assert describe_place(plan, SCALE, Point(2.0, 2.0)) == "en «Aula 1»"
    assert describe_place(plan, SCALE, Point(50.0, 50.0)) == "en un pasillo o zona de circulación"


def test_room_detection_service(services: AppServices) -> None:
    plan = dataclasses.replace(two_rooms(), rooms=())
    detected = services.plans.detect_rooms(plan, UseType.EDUCATION, "Ambiente {number}")
    assert [r.name for r in detected.rooms] == ["Ambiente 1", "Ambiente 2"]
    # volver a detectar no duplica ambientes existentes
    again = services.plans.detect_rooms(detected, UseType.EDUCATION, "Ambiente {number}")
    assert len(again.rooms) == 2
    with pytest.raises(UserFacingError, match="escala"):
        services.plans.detect_rooms(
            dataclasses.replace(plan, scale_m_per_px=None), UseType.OFFICE, "A{number}"
        )


def test_unconfirmed_proposals_do_not_block(services: AppServices) -> None:
    """Una salida propuesta sin confirmar se ignora; basta con una confirmada."""
    plan = single_room(second_exit=True)
    proposed = dataclasses.replace(plan.exits[1], confirmed=False)
    plan = dataclasses.replace(plan, exits=(plan.exits[0], proposed))
    project_id = _project(services, plan)
    scenario = dataclasses.replace(
        services.simulations.load_scenario(project_id),
        occupancies=(Occupancy("Aula 1", "adulto", 10),),
    )
    run = services.simulations.run(project_id, plan, scenario)
    assert run.result.completed
    assert {name for name, _ in run.result.time_per_exit_s} == {"Salida 1"}


def test_detection_keeps_confirmed_exits(services: AppServices) -> None:
    from tests.fixtures.synthetic_plans import generate_plan

    synthetic = generate_plan(1)
    manual = Exit(synthetic.exits[0], "Puerta principal")  # dibujada a mano sobre una salida real
    plan = FloorPlan(scale_m_per_px=synthetic.scale_m_per_px, exits=(manual,))
    detected = services.plans.detect(synthetic.image, plan)
    assert detected.exits[0] == manual
    proposals = detected.exits[1:]
    assert all(not e.confirmed for e in proposals)
    # la propuesta que coincidía con la salida manual se descartó
    assert len(proposals) == len(synthetic.exits) - 1
    assert len({e.name for e in detected.exits}) == len(detected.exits)
