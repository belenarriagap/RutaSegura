"""Ventana principal (Hito 0: esqueleto con los pasos del asistente aún deshabilitados)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

import rutasegura
from rutasegura.resources.texts import TEXTS, UiTexts


class MainWindow(QMainWindow):
    """Ventana principal de RutaSegura."""

    def __init__(self, texts: UiTexts = TEXTS, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._texts = texts
        self.setWindowTitle(texts.window_title)
        self.resize(1100, 720)
        self._build_menu()
        self._build_central()
        self.statusBar().showMessage(texts.status_ready)

    def _build_menu(self) -> None:
        t = self._texts
        file_menu = self.menuBar().addMenu(t.menu_file)
        quit_action = QAction(t.action_quit, self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        help_menu = self.menuBar().addMenu(t.menu_help)
        about_action = QAction(t.action_about, self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _build_central(self) -> None:
        t = self._texts
        self.steps_list = QListWidget()
        self.steps_list.setObjectName("wizardSteps")
        self.steps_list.setMaximumWidth(240)
        for step in t.wizard_steps:
            item = QListWidgetItem(step)
            item.setFlags(Qt.ItemFlag.NoItemFlags)  # se habilitan en los próximos hitos
            self.steps_list.addItem(item)

        title = QLabel(t.welcome_title)
        title.setObjectName("welcomeTitle")
        font = title.font()
        font.setPointSize(font.pointSize() + 8)
        font.setBold(True)
        title.setFont(font)
        body = QLabel(t.welcome_body)
        body.setWordWrap(True)

        content = QVBoxLayout()
        content.addStretch(1)
        content.addWidget(title)
        content.addWidget(body)
        content.addStretch(2)

        layout = QHBoxLayout()
        layout.addWidget(self.steps_list)
        layout.addLayout(content, stretch=1)
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            self._texts.about_title,
            self._texts.about_body.format(version=rutasegura.__version__),
        )
