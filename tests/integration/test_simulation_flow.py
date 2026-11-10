"""Pasos 4 y 6 a través de la ventana: ambientes, ocupantes, simular en segundo plano y reabrir."""

from __future__ import annotations

import dataclasses

import pytest
from PySide6.QtWidgets import QSpinBox
from pytestqt.qtbot import QtBot

from rutasegura.application.services import AppServices
from rutasegura.domain.enums import UseType
from rutasegura.presentation.main_window import STEP_ROOMS, STEP_SIMULATE, MainWindow
from rutasegura.presentation.rooms_page import FIRST_PROFILE_COL
from tests.fixtures.simple_plans import two_rooms


@pytest.fixture
def window(qtbot: QtBot, services: AppServices, monkeypatch: pytest.MonkeyPatch) -> MainWindow:
    project_id = services.projects.create_project("Colegio", UseType.EDUCATION)
    services.projects.save_floor(project_id, dataclasses.replace(two_rooms(), rooms=()))
    win = MainWindow(services)
    qtbot.addWidget(win)
    errors: list[str] = []
    monkeypatch.setattr(win, "show_error", errors.append)
    win.errors = errors  # type: ignore[attr-defined]
    win.open_project(project_id)
    return win


def test_rooms_occupants_simulate_and_reopen(
    window: MainWindow, services: AppServices, qtbot: QtBot
) -> None:
    window.go_to_step(STEP_ROOMS)
    rooms = window.rooms_page
    assert window.stack.currentWidget() is rooms
    rooms.detect_rooms()
    profiles = [p.name for p in services.simulations.profiles()]
    child_col = FIRST_PROFILE_COL + profiles.index("niño")
    for row, count in ((0, 20), (1, 15)):
        spin = rooms.table.cellWidget(row, child_col)
        assert isinstance(spin, QSpinBox)
        spin.setValue(count)
    assert window.is_dirty

    window.go_to_step(STEP_SIMULATE)
    assert not window.is_dirty  # se guardó al cambiar de paso
    page = window.simulation_page
    page.seed_spin.setValue(77)
    with qtbot.waitSignal(page.run_finished, timeout=120_000):
        page.start_simulation()
    run = page.current_run
    assert run is not None
    assert run.result.agents_total == 35
    assert run.result.completed
    assert run.result.seed == 77
    assert "Tiempo total" in page.summary_label.text()
    assert page.bottleneck_list.count() >= 1
    assert page.viewer.is_playing
    assert getattr(window, "errors") == []  # noqa: B009

    other = MainWindow(services)
    qtbot.addWidget(other)
    other.open_project(window.project_id or 0)
    assert other.scenario is not None
    assert other.scenario.total_occupants == 35
    assert other.scenario.seed == 77
    restored = other.simulation_page.current_run
    assert restored is not None
    assert restored.result.total_time_s == run.result.total_time_s


def test_cancel_simulation(window: MainWindow, qtbot: QtBot) -> None:
    window.go_to_step(STEP_ROOMS)
    window.rooms_page.detect_rooms()
    window.rooms_page.set_occupants("Ambiente 1", "adulto", 200)
    window.go_to_step(STEP_SIMULATE)
    page = window.simulation_page
    page.start_simulation()
    assert page.job is not None
    with qtbot.waitSignal(page.job.cancelled, timeout=60_000):
        page.cancel_simulation()
    assert page.run_button.isEnabled()
    assert "cancelada" in page.status_label.text()


def test_simulation_errors_are_reported(window: MainWindow, qtbot: QtBot) -> None:
    window.go_to_step(STEP_SIMULATE)  # sin ambientes ni ocupantes
    page = window.simulation_page
    with qtbot.waitSignal(page.error, timeout=30_000) as blocker:
        page.start_simulation()
    assert "ambientes" in blocker.args[0]
