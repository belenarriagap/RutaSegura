"""Escenarios, comparador y calibración a través de la interfaz (RF10, RF11)."""

from __future__ import annotations

import dataclasses
from datetime import date

import numpy as np
import pytest
from PySide6.QtWidgets import QTableWidget
from pytestqt.qtbot import QtBot

from rutasegura.application.services import AppServices
from rutasegura.application.simulation_service import BASE_SCENARIO, scale_occupancies
from rutasegura.domain.calibration import CalibrationResult
from rutasegura.domain.enums import UseType
from rutasegura.domain.scenario import RealDrill
from rutasegura.engines.calibration.grid_search import scale_profiles
from rutasegura.presentation.calibration_dialog import CalibrationDialog
from rutasegura.presentation.main_window import STEP_ROOMS, STEP_SIMULATE, MainWindow
from rutasegura.presentation.scenario_dialogs import ScenarioDialog
from tests.fixtures.simple_plans import single_room

PLAN = single_room(exit_width=0.9, second_exit=True)


@pytest.fixture
def window(qtbot: QtBot, services: AppServices, monkeypatch: pytest.MonkeyPatch) -> MainWindow:
    project_id = services.projects.create_project("Colegio", UseType.EDUCATION)
    services.projects.save_floor(project_id, PLAN, np.full((320, 520, 3), 250, np.uint8))
    win = MainWindow(services)
    qtbot.addWidget(win)
    errors: list[str] = []
    monkeypatch.setattr(win, "show_error", errors.append)
    win.errors = errors  # type: ignore[attr-defined]
    win.open_project(project_id)
    win.go_to_step(STEP_ROOMS)
    win.rooms_page.set_occupants("Aula 1", "adulto", 150)  # suficiente para formar fila
    win.go_to_step(STEP_SIMULATE)
    return win


def _cell(table: QTableWidget, row: int, col: int) -> str:
    item = table.item(row, col)
    assert item is not None
    return item.text()


def _run(window: MainWindow, qtbot: QtBot, name: str) -> None:
    page = window.simulation_page
    page.select_scenario(name)
    with qtbot.waitSignal(page.run_finished, timeout=120_000):
        page.start_simulation()


def test_variants_compare_and_delete(window: MainWindow, qtbot: QtBot) -> None:
    page = window.simulation_page
    assert page.scenario_names == [BASE_SCENARIO]
    assert not page.edit_button.isEnabled()
    assert page.create_variant("Sin salida 2", 100, frozenset({"Salida 2"}))
    assert page.scenario_names == [BASE_SCENARIO, "Sin salida 2"]
    assert page.current_scenario.blocked_exits == frozenset({"Salida 2"})
    assert page.edit_button.isEnabled()
    assert page.current_run is None

    _run(window, qtbot, BASE_SCENARIO)
    _run(window, qtbot, "Sin salida 2")
    assert page.current_run is not None
    blocked_time = page.current_run.result.total_time_s
    page.select_scenario(BASE_SCENARIO)
    assert page.current_run is not None
    assert page.current_run.result.total_time_s < blocked_time

    dialog = page.comparison_dialog()
    assert dialog is not None
    qtbot.addWidget(dialog)
    assert dialog.available == [BASE_SCENARIO, "Sin salida 2"]
    cells = {
        _cell(dialog.table, r, 0): _cell(dialog.table, r, 3) for r in range(dialog.table.rowCount())
    }
    assert cells["Tiempo para evacuar al 90 %"].startswith("+")
    assert "Tiempo por «Salida 2»" in cells
    dialog.play_both()
    assert all(v.is_playing for v in dialog.viewers)

    page.select_scenario("Sin salida 2")
    assert page.update_current_variant("Doble aforo", 200, frozenset())
    assert page.scenario_names == [BASE_SCENARIO, "Doble aforo"]
    assert page.current_scenario.total_occupants == 300
    page.seed_spin.setValue(99)  # la semilla de una variante se guarda directamente
    assert getattr(window, "errors") == []  # noqa: B009
    page.delete_current_variant()
    assert page.scenario_names == [BASE_SCENARIO]


def test_invalid_variant_reports_error(window: MainWindow) -> None:
    assert not window.simulation_page.create_variant(BASE_SCENARIO, 100, frozenset())
    assert getattr(window, "errors")  # noqa: B009


def test_comparison_needs_two_runs(window: MainWindow, qtbot: QtBot) -> None:
    dialog = window.simulation_page.comparison_dialog()
    assert dialog is not None
    qtbot.addWidget(dialog)
    assert dialog.available == []
    assert "al menos dos" in dialog.message.text()
    assert not dialog.play_button.isEnabled()


def test_scenario_dialog_values(qtbot: QtBot) -> None:
    dialog = ScenarioDialog(
        ["Salida 1", "Salida 2"], 40, name="X", percent=150, blocked=frozenset({"Salida 1"})
    )
    qtbot.addWidget(dialog)
    assert dialog.values() == ("X", 150, frozenset({"Salida 1"}))
    assert "60 personas" in dialog.result_label.text()  # 150 % de 40


def test_calibration_dialog(window: MainWindow, services: AppServices, qtbot: QtBot) -> None:
    empty = window.calibration_dialog()
    assert empty is not None
    qtbot.addWidget(empty)
    with qtbot.waitSignal(empty.failed):
        empty.start()  # sin tiempo total no calibra
    assert "tiempo total" in empty.status_label.text()
    scenario = window.scenario
    assert scenario is not None
    drill_scenario = dataclasses.replace(
        scenario, occupancies=scale_occupancies(scenario.occupancies, 30)
    )
    truth = services.simulations.simulate(
        PLAN, drill_scenario, scale_profiles(services.simulations.profiles(), 1.5, 1.0)
    ).result
    dialog = CalibrationDialog(
        services.calibration,
        window.project_id or 0,
        window.plan,
        scenario,
        grid=((1.0, 1.5), (1.0,)),
    )
    qtbot.addWidget(dialog)
    dialog.set_drill(
        RealDrill(date(2026, 10, 8), 30, round(truth.total_time_s), truth.time_per_exit_s)
    )
    assert dialog.drill().participants == 30
    with qtbot.waitSignal(dialog.calibrated, timeout=120_000) as blocker:
        dialog.start()
    result = blocker.args[0]
    assert isinstance(result, CalibrationResult)
    assert result.best.reaction_factor == 1.5
    assert "Tiempos de reacción × 1.5" in dialog.result_label.text()
    assert dialog.apply_button.isEnabled()
    before = services.simulations.profiles()[0].reaction_mean_s
    with qtbot.waitSignal(dialog.applied):
        dialog.apply()
    assert services.simulations.profiles()[0].reaction_mean_s == pytest.approx(before * 1.5)
    assert not dialog.apply_button.isEnabled()
