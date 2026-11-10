"""Ventana principal: arranque, menús y habilitación de pasos."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget
from pytestqt.qtbot import QtBot

from rutasegura.application.services import AppServices
from rutasegura.domain.enums import UseType
from rutasegura.presentation.main_window import MainWindow
from rutasegura.resources.texts import TEXTS


def _window(qtbot: QtBot, services: AppServices) -> MainWindow:
    window = MainWindow(services)
    qtbot.addWidget(window)
    return window


def test_main_window_opens(qtbot: QtBot, services: AppServices) -> None:
    window = _window(qtbot, services)
    window.show()
    qtbot.waitExposed(window)
    assert window.isVisible()
    assert window.windowTitle() == TEXTS.window_title
    steps = window.findChild(QListWidget, "wizardSteps")
    assert steps is not None
    assert [steps.item(i).text() for i in range(steps.count())] == list(TEXTS.wizard_steps)
    assert window.stack.currentWidget() is window.welcome_page


def test_menus_are_in_spanish(qtbot: QtBot, services: AppServices) -> None:
    window = _window(qtbot, services)
    titles = [action.text() for action in window.menuBar().actions()]
    assert titles == [TEXTS.menu_file, TEXTS.menu_edit, TEXTS.menu_help]


def test_steps_enable_after_creating_project(qtbot: QtBot, services: AppServices) -> None:
    window = _window(qtbot, services)

    def enabled(row: int) -> bool:
        return bool(window.steps_list.item(row).flags() & Qt.ItemFlag.ItemIsEnabled)

    assert not any(enabled(r) for r in range(7))
    assert not window.save_action.isEnabled()
    project_id = window.create_project("Colegio Prueba", UseType.EDUCATION)
    assert project_id is not None
    assert [enabled(r) for r in range(7)] == [True, True, True, False, False, False, False]
    assert window.stack.currentWidget() is window.load_page
    assert "Colegio Prueba" in window.windowTitle()


def test_invalid_project_name_shows_error(
    qtbot: QtBot, services: AppServices, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _window(qtbot, services)
    errors: list[str] = []
    monkeypatch.setattr(window, "show_error", errors.append)
    assert window.create_project("   ", UseType.OFFICE) is None
    assert errors == ["El proyecto necesita un nombre."]
