"""Varios pisos a través de la ventana: selector, agregar/eliminar, simular y ver cada piso."""

from __future__ import annotations

import numpy as np
import pytest
from pytestqt.qtbot import QtBot

from rutasegura.application.services import AppServices
from rutasegura.domain.enums import ElementType, UseType
from rutasegura.presentation.editor.editor_widget import PlanEditor, next_stair_name
from rutasegura.presentation.main_window import STEP_ROOMS, STEP_SIMULATE, MainWindow
from tests.fixtures.simple_plans import rect, two_floor_building


@pytest.fixture
def window(qtbot: QtBot, services: AppServices, monkeypatch: pytest.MonkeyPatch) -> MainWindow:
    project_id = services.projects.create_project("Colegio de dos pisos", UseType.EDUCATION)
    ground, upper = two_floor_building()
    image = np.full((320, 520, 3), 250, np.uint8)
    services.projects.save_floor(project_id, ground, image)
    services.projects.save_floor(project_id, upper, image)
    win = MainWindow(services)
    qtbot.addWidget(win)
    errors: list[str] = []
    monkeypatch.setattr(win, "show_error", errors.append)
    win.errors = errors  # type: ignore[attr-defined]
    win.open_project(project_id)
    return win


def _errors(window: MainWindow) -> list[str]:
    return list(getattr(window, "errors"))  # noqa: B009


def test_floor_bar_and_switching(window: MainWindow) -> None:
    assert not window.floor_bar.isHidden()
    assert [window.floor_combo.itemText(i) for i in range(window.floor_combo.count())] == [
        "Piso 1",
        "Piso 2",
    ]
    assert window.level == 0
    assert not window.delete_floor_button.isEnabled()  # el piso 1 no se elimina
    assert window.switch_floor(1)
    assert window.level == 1
    assert window.plan.rooms[0].name == "Aula 201"
    assert window.editor_page.editor.plan().level == 1
    assert window.delete_floor_button.isEnabled()
    window.floor_combo.setCurrentIndex(0)  # también desde el selector
    assert window.level == 0


def test_occupants_per_floor_and_simulation(window: MainWindow, qtbot: QtBot) -> None:
    window.go_to_step(STEP_ROOMS)
    window.rooms_page.set_occupants("Hall", "adulto", 5)
    window.switch_floor(1)
    assert window.current_step() == STEP_ROOMS
    window.rooms_page.set_occupants("Aula 201", "niño", 20)
    scenario = window.scenario
    assert scenario is not None
    assert {(o.room_name, o.level) for o in scenario.occupancies} == {("Hall", 0), ("Aula 201", 1)}

    window.go_to_step(STEP_SIMULATE)
    page = window.simulation_page
    assert [p.level for p in page.plans] == [0, 1]
    with qtbot.waitSignal(page.run_finished, timeout=120_000):
        page.start_simulation()
    run = page.current_run
    assert run is not None
    assert run.result.agents_total == 25
    assert [m.level for m in run.result.floor_maps] == [0, 1]
    viewer = page.viewer
    assert not viewer.floor_combo.isHidden()
    viewer.pause()
    viewer.set_time(0.0)
    viewer.show_floor(1)
    assert viewer.agents.visible_count == 20  # al inicio, los 20 niños están arriba
    viewer.show_floor(0)
    assert viewer.agents.visible_count == 5
    assert _errors(window) == []


def test_add_and_delete_floors(window: MainWindow) -> None:
    assert window.add_floor()
    assert window.level == 2
    assert window.floor_combo.count() == 3
    window.go_to_step(STEP_ROOMS)
    assert window.delete_current_floor()
    assert window.level == 1
    assert window.floor_combo.count() == 2
    window.switch_floor(0)
    assert not window.delete_current_floor()  # nunca el piso 1
    assert any("más alto" in e for e in _errors(window))
    assert window.add_floor()
    assert window.add_floor()
    assert window.floor_combo.count() == 4
    assert not window.add_floor()
    assert any("hasta 4 pisos" in e for e in _errors(window))
    assert not window.add_floor_button.isEnabled()


def test_stairs_are_named_in_order(qtbot: QtBot) -> None:
    editor = PlanEditor()
    qtbot.addWidget(editor)
    editor.add_area(ElementType.STAIR, rect(0, 0, 1, 2))
    editor.add_area(ElementType.STAIR, rect(5, 0, 1, 2))
    assert [s.name for s in editor.plan().stairs] == ["Escalera A", "Escalera B"]
    assert next_stair_name(editor.plan(), "Escalera {letter}") == "Escalera C"
