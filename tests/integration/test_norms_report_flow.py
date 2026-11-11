"""Pasos 5 (revisar norma) y 7 (informe) a través de la ventana."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QComboBox
from pytestqt.qtbot import QtBot

from rutasegura.application.services import AppServices
from rutasegura.domain.enums import UseType
from rutasegura.presentation.main_window import (
    STEP_NORMS,
    STEP_REPORT,
    STEP_ROOMS,
    STEP_SIMULATE,
    MainWindow,
)
from rutasegura.presentation.norms_page import COL_CATEGORY, COL_STATUS
from tests.fixtures.simple_plans import two_rooms


@pytest.fixture
def window(qtbot: QtBot, services: AppServices, monkeypatch: pytest.MonkeyPatch) -> MainWindow:
    project_id = services.projects.create_project("Colegio Norma", UseType.EDUCATION)
    services.projects.save_floor(project_id, two_rooms(), np.full((300, 600, 3), 250, np.uint8))
    win = MainWindow(services)
    qtbot.addWidget(win)
    monkeypatch.setattr(win, "show_error", lambda message: pytest.fail(message))
    win.open_project(project_id)
    win.go_to_step(STEP_ROOMS)
    win.rooms_page.set_occupants("Aula 1", "niño", 30)  # 36 m² de aula → aforo 24
    return win


def _status(window: MainWindow, row: int) -> str:
    item = window.norms_page.table.item(row, COL_STATUS)
    assert item is not None
    return item.text()


def test_norms_step_shows_capacity_and_category_changes(window: MainWindow) -> None:
    window.go_to_step(STEP_NORMS)
    page = window.norms_page
    assert window.stack.currentWidget() is page
    evaluation = page.evaluation
    assert evaluation is not None
    assert evaluation.capacities[0].capacity == 24
    assert _status(window, 0) == "Excede el aforo"
    assert not page.warning_label.isHidden()
    assert "no fueron verificadas" in page.warning_label.text()
    assert any(
        "aforo es 24" in page.observations.item(i).text() for i in range(page.observations.count())
    )
    combo = page.table.cellWidget(0, COL_CATEGORY)
    assert isinstance(combo, QComboBox)
    combo.setCurrentIndex(combo.findData("sum"))  # sala de uso múltiple: 1 m²/persona → 36
    assert _status(window, 0) == "Correcto"
    assert window.plan.rooms[0].category == "sum"
    assert window.is_dirty


def test_report_step_generates_pdf(window: MainWindow, qtbot: QtBot, tmp_path: Path) -> None:
    window.go_to_step(STEP_SIMULATE)
    with qtbot.waitSignal(window.simulation_page.run_finished, timeout=120_000):
        window.simulation_page.start_simulation()
    window.go_to_step(STEP_REPORT)
    page = window.report_page
    assert window.stack.currentWidget() is page
    assert "última simulación" in page.status_label.text()
    with qtbot.waitSignal(page.report_ready, timeout=120_000) as blocker:
        page.generate_to(tmp_path / "informe")
    path = blocker.args[0]
    assert isinstance(path, Path)
    assert path.exists()
    assert path.suffix == ".pdf"
    assert page.open_button.isEnabled()
    assert str(path) in page.result_label.text()


def test_report_without_simulation_is_announced(window: MainWindow) -> None:
    window.go_to_step(STEP_REPORT)
    assert "Todavía no simuló" in window.report_page.status_label.text()
