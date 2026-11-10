"""Ventana principal: asistente paso a paso (pasos 1–3 activos desde el Hito 2)."""

from __future__ import annotations

import dataclasses

import numpy as np
import numpy.typing as npt
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QFont, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

import rutasegura
from rutasegura.application.errors import UserFacingError
from rutasegura.application.services import AppServices
from rutasegura.domain.enums import UseType
from rutasegura.domain.plan import FloorPlan
from rutasegura.presentation.project_dialogs import NewProjectDialog, OpenProjectDialog
from rutasegura.presentation.wizard_pages import EditorPage, LoadPlanPage, ScalePage
from rutasegura.resources.texts import TEXTS, UiTexts

Image = npt.NDArray[np.uint8]

STEP_LOAD, STEP_SCALE, STEP_EDIT = 0, 1, 2
ACTIVE_STEPS = (STEP_LOAD, STEP_SCALE, STEP_EDIT)


class MainWindow(QMainWindow):
    """Ventana principal de RutaSegura."""

    def __init__(
        self, services: AppServices, texts: UiTexts = TEXTS, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._services = services
        self._texts = texts
        self.project_id: int | None = None
        self._plan = FloorPlan()
        self._image: Image | None = None
        self._image_dirty = False
        self._dirty = False

        self.setWindowTitle(texts.window_title)
        self.resize(1200, 780)
        self._build_pages()
        self._build_menu()
        self._build_central()
        self.statusBar().showMessage(texts.status_ready)
        self._update_steps()

    # ----------------------------------------------------------------- construcción
    def _build_menu(self) -> None:
        t, p = self._texts, self._texts.project
        file_menu = self.menuBar().addMenu(t.menu_file)
        self.new_action = QAction(p.menu_new, self)
        self.new_action.setShortcut(QKeySequence.StandardKey.New)
        self.new_action.triggered.connect(self.ask_new_project)
        self.open_action = QAction(p.menu_open, self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.triggered.connect(self.ask_open_project)
        self.save_action = QAction(p.menu_save, self)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_action.triggered.connect(self.save)
        quit_action = QAction(t.action_quit, self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        for action in (self.new_action, self.open_action, self.save_action):
            file_menu.addAction(action)
        file_menu.addSeparator()
        file_menu.addAction(quit_action)

        edit_menu = self.menuBar().addMenu(t.menu_edit)
        edit_menu.addAction(self.editor_page.editor.undo_action)
        edit_menu.addAction(self.editor_page.editor.redo_action)

        help_menu = self.menuBar().addMenu(t.menu_help)
        about_action = QAction(t.action_about, self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _build_pages(self) -> None:
        plans = self._services.plans
        self.load_page = LoadPlanPage(plans, self._texts.wizard)
        self.scale_page = ScalePage(plans, self._texts.wizard)
        self.editor_page = EditorPage(plans, self._texts.wizard, self._texts.editor)
        self.load_page.image_loaded.connect(self._on_image_loaded)
        self.load_page.next_requested.connect(lambda: self.go_to_step(STEP_SCALE))
        self.scale_page.scale_changed.connect(self._on_scale_changed)
        self.scale_page.next_requested.connect(lambda: self.go_to_step(STEP_EDIT))
        self.editor_page.editor.plan_changed.connect(self._on_plan_edited)
        for page in (self.load_page, self.scale_page, self.editor_page):
            page.error.connect(self.show_error)

    def _build_central(self) -> None:
        t = self._texts
        self.steps_list = QListWidget()
        self.steps_list.setObjectName("wizardSteps")
        self.steps_list.setMaximumWidth(240)
        for step in t.wizard_steps:
            self.steps_list.addItem(QListWidgetItem(step))
        self.steps_list.currentRowChanged.connect(self._on_step_selected)

        self.stack = QStackedWidget()
        self.welcome_page = self._build_welcome()
        self.pending_page = QLabel(t.wizard.step_not_ready)
        self.pending_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for page in (
            self.welcome_page,
            self.load_page,
            self.scale_page,
            self.editor_page,
            self.pending_page,
        ):
            self.stack.addWidget(page)

        layout = QHBoxLayout()
        layout.addWidget(self.steps_list)
        layout.addWidget(self.stack, stretch=1)
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

    def _build_welcome(self) -> QWidget:
        t = self._texts
        title = QLabel(t.welcome_title)
        title.setObjectName("welcomeTitle")
        font = QFont(title.font())
        font.setPointSize(font.pointSize() + 8)
        font.setBold(True)
        title.setFont(font)
        body = QLabel(t.welcome_body)
        body.setWordWrap(True)
        new_button = QPushButton(t.project.welcome_new)
        new_button.clicked.connect(self.ask_new_project)
        open_button = QPushButton(t.project.welcome_open)
        open_button.clicked.connect(self.ask_open_project)
        buttons = QHBoxLayout()
        buttons.addWidget(new_button)
        buttons.addWidget(open_button)
        buttons.addStretch(1)
        layout = QVBoxLayout()
        layout.addStretch(1)
        layout.addWidget(title)
        layout.addWidget(body)
        layout.addLayout(buttons)
        layout.addStretch(2)
        page = QWidget()
        page.setLayout(layout)
        return page

    # ----------------------------------------------------------------- proyectos
    def ask_new_project(self) -> None:
        """Diálogo de proyecto nuevo."""
        dialog = NewProjectDialog(self._texts.project, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.create_project(*dialog.values())

    def ask_open_project(self) -> None:
        """Diálogo para abrir un proyecto."""
        dialog = OpenProjectDialog(
            self._services.projects.list_projects(), self._texts.project, self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            project_id = dialog.selected_id()
            if project_id is not None:
                self.open_project(project_id)

    def create_project(self, name: str, use: UseType, address: str = "") -> int | None:
        """Crea y abre un proyecto. Devuelve su id (o ``None`` si hubo error)."""
        if not self._save_if_dirty():
            return None
        try:
            project_id = self._services.projects.create_project(name, use, address)
        except UserFacingError as exc:
            self.show_error(exc.message)
            return None
        self.open_project(project_id)
        return project_id

    def open_project(self, project_id: int) -> None:
        """Abre un proyecto y muestra el paso que corresponda."""
        if not self._save_if_dirty():
            return
        try:
            project = self._services.projects.get_project(project_id)
        except UserFacingError as exc:
            self.show_error(exc.message)
            return
        plan = self._services.projects.load_floor(project_id) or FloorPlan()
        image = self._services.projects.load_floor_image(plan)
        self.project_id = project_id
        self._plan, self._image = plan, image
        self._image_dirty = self._dirty = False
        self.load_page.set_image(image)
        self.scale_page.set_content(image, plan.scale_m_per_px)
        self.editor_page.set_content(plan, image)
        self.setWindowTitle(f"{project.name} — {self._texts.window_title}")
        self.statusBar().showMessage(self._texts.project.opened.format(name=project.name))
        self._update_steps()
        has_elements = bool(plan.walls or plan.doors or plan.exits)
        self.go_to_step(STEP_EDIT if has_elements else STEP_LOAD)

    def save(self) -> bool:
        """Guarda el plano actual. Devuelve ``False`` si no se pudo."""
        if self.project_id is None:
            return True
        try:
            self._plan = self._services.projects.save_floor(
                self.project_id, self._plan, self._image if self._image_dirty else None
            )
        except UserFacingError as exc:
            self.show_error(exc.message)
            return False
        self._image_dirty = self._dirty = False
        self.statusBar().showMessage(self._texts.project.saved, 4000)
        return True

    def _save_if_dirty(self) -> bool:
        return self.save() if self._dirty else True

    @property
    def plan(self) -> FloorPlan:
        """Plano en edición."""
        return self._plan

    @property
    def is_dirty(self) -> bool:
        """Hay cambios sin guardar."""
        return self._dirty

    # ----------------------------------------------------------------- pasos
    def go_to_step(self, step: int) -> None:
        """Muestra un paso del asistente (guarda los cambios pendientes)."""
        if self.project_id is None:
            self.stack.setCurrentWidget(self.welcome_page)
            return
        self._save_if_dirty()
        self.steps_list.blockSignals(True)
        self.steps_list.setCurrentRow(step)
        self.steps_list.blockSignals(False)
        if step == STEP_LOAD:
            self.stack.setCurrentWidget(self.load_page)
        elif step == STEP_SCALE:
            self.scale_page.set_content(self._image, self._plan.scale_m_per_px)
            self.stack.setCurrentWidget(self.scale_page)
        elif step == STEP_EDIT:
            if self.editor_page.editor.plan() != self._plan:
                self.editor_page.set_content(self._plan, self._image)
            self.stack.setCurrentWidget(self.editor_page)
            if self.editor_page.needs_detection():
                self.editor_page.detect()
        else:
            self.stack.setCurrentWidget(self.pending_page)

    def current_step(self) -> int:
        """Paso seleccionado."""
        return self.steps_list.currentRow()

    def _on_step_selected(self, row: int) -> None:
        if row >= 0:
            self.go_to_step(row)

    def _update_steps(self) -> None:
        for row in range(self.steps_list.count()):
            item = self.steps_list.item(row)
            enabled = self.project_id is not None and row in ACTIVE_STEPS
            flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            item.setFlags(flags if enabled else Qt.ItemFlag.NoItemFlags)
            if row not in ACTIVE_STEPS:
                item.setToolTip(self._texts.wizard.step_not_ready)
        self.save_action.setEnabled(self.project_id is not None)
        if self.project_id is None:
            self.stack.setCurrentWidget(self.welcome_page)

    # ----------------------------------------------------------------- cambios en los pasos
    def _on_image_loaded(self, image: Image) -> None:
        # Imagen nueva: la geometría anterior y la escala ya no corresponden a estos píxeles.
        self._image = image
        self._image_dirty = True
        self._plan = FloorPlan(level=self._plan.level)
        self._dirty = True
        self.editor_page.set_content(self._plan, image)

    def _on_scale_changed(self, scale: float) -> None:
        # El editor se recarga con la nueva escala al entrar al paso 3 (go_to_step).
        self._plan = dataclasses.replace(self._plan, scale_m_per_px=scale)
        self._dirty = True

    def _on_plan_edited(self, plan: FloorPlan) -> None:
        if plan != self._plan:
            self._plan = plan
            self._dirty = True

    # ----------------------------------------------------------------- varios
    def show_error(self, message: str) -> None:
        """Muestra un mensaje de error comprensible."""
        QMessageBox.warning(self, self._texts.project.error_title, message)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - API de Qt
        """Guarda automáticamente al cerrar."""
        self._save_if_dirty()
        super().closeEvent(event)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            self._texts.about_title,
            self._texts.about_body.format(version=rutasegura.__version__),
        )
