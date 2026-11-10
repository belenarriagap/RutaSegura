"""Prueba de humo de la ventana principal."""

from __future__ import annotations

from PySide6.QtWidgets import QListWidget
from pytestqt.qtbot import QtBot

from rutasegura.presentation.main_window import MainWindow
from rutasegura.resources.texts import TEXTS


def test_main_window_opens(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    assert window.isVisible()
    assert window.windowTitle() == TEXTS.window_title
    steps = window.findChild(QListWidget, "wizardSteps")
    assert steps is not None
    assert [steps.item(i).text() for i in range(steps.count())] == list(TEXTS.wizard_steps)


def test_menus_are_in_spanish(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    titles = [action.text() for action in window.menuBar().actions()]
    assert titles == [TEXTS.menu_file, TEXTS.menu_help]
