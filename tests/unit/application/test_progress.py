"""Avance del asistente: estados de los pasos y lo que falta."""

from __future__ import annotations

import dataclasses

from rutasegura.application.progress import (
    STEP_EDIT,
    STEP_LOAD,
    STEP_NORMS,
    STEP_REPORT,
    STEP_ROOMS,
    STEP_SCALE,
    STEP_SIMULATE,
    Blocker,
    Issue,
    StepState,
    wizard_progress,
)
from rutasegura.domain.people import Occupancy
from rutasegura.domain.plan import Exit, FloorPlan, Stair
from rutasegura.domain.scenario import Scenario
from tests.fixtures.simple_plans import _seg, rect, single_room

SCENARIO = Scenario("Escenario base", 1, (Occupancy("Aula 1", "adulto", 10),))


def test_empty_project_needs_everything() -> None:
    progress = wizard_progress(FloorPlan(), has_image=False, scenario=None, result=None)
    states = [s.state for s in progress.steps]
    assert states == [StepState.TODO] * 7
    assert progress.steps[STEP_LOAD].issue is Issue.NO_IMAGE
    assert progress.steps[STEP_EDIT].issue is Issue.NO_WALLS
    # el paso 6 dice primero lo que falta antes: la escala
    assert progress.blocker(STEP_SIMULATE) == Blocker(STEP_SCALE, Issue.NO_SCALE)
    assert progress.blocker(STEP_SCALE) == Blocker(STEP_LOAD, Issue.NO_IMAGE)
    assert progress.blocker(STEP_LOAD) is None
    assert progress.blocker(STEP_REPORT) is None


def test_complete_plan_until_simulation() -> None:
    progress = wizard_progress(single_room(), has_image=True, scenario=SCENARIO, result=None)
    states = [s.state for s in progress.steps]
    assert states[:STEP_SIMULATE] == [StepState.DONE] * STEP_SIMULATE
    assert progress.steps[STEP_SIMULATE].issue is Issue.NO_RUN
    assert progress.blocker(STEP_SIMULATE) is None
    assert progress.steps[STEP_NORMS].state is StepState.DONE


def test_exits_pending_and_missing() -> None:
    pending = single_room(confirmed=False)
    progress = wizard_progress(pending, has_image=True, scenario=SCENARIO, result=None)
    assert progress.steps[STEP_EDIT].issue is Issue.NO_EXITS
    assert progress.blocker(STEP_SIMULATE) == Blocker(STEP_EDIT, Issue.NO_EXITS)
    both = dataclasses.replace(
        pending, exits=(*pending.exits, Exit(_seg(0, 2, 0, 3), "Salida 2", confirmed=True))
    )
    progress = wizard_progress(both, has_image=True, scenario=SCENARIO, result=None)
    assert progress.steps[STEP_EDIT].state is StepState.WARNING
    assert progress.steps[STEP_EDIT].issue is Issue.PENDING_EXITS
    assert progress.blocker(STEP_SIMULATE) is None  # una advertencia no bloquea


def test_upper_floor_leaves_by_the_stairs() -> None:
    upper = dataclasses.replace(
        single_room(), level=1, exits=(), stairs=(Stair(rect(1, 1, 2, 2), name="Escalera A"),)
    )
    lowest = wizard_progress(upper, has_image=True, scenario=None, result=None)
    assert lowest.steps[STEP_EDIT].issue is Issue.NO_EXITS
    progress = wizard_progress(
        upper, has_image=True, scenario=None, result=None, is_lowest_floor=False
    )
    assert progress.steps[STEP_EDIT].state is StepState.DONE


def test_rooms_without_occupants() -> None:
    empty = Scenario("Escenario base", 1)
    progress = wizard_progress(single_room(), has_image=True, scenario=empty, result=None)
    assert progress.steps[STEP_ROOMS].issue is Issue.NO_OCCUPANTS
    no_rooms = dataclasses.replace(single_room(), rooms=())
    progress = wizard_progress(no_rooms, has_image=True, scenario=SCENARIO, result=None)
    assert progress.steps[STEP_ROOMS].issue is Issue.NO_ROOMS
    assert progress.blocker(STEP_NORMS) == Blocker(STEP_ROOMS, Issue.NO_ROOMS)
