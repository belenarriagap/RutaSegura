"""Ventana principal: asistente de 7 pasos, del plano al informe."""

from __future__ import annotations

import dataclasses

import numpy as np
import numpy.typing as npt
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QFont, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
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
from rutasegura.domain.scenario import Scenario
from rutasegura.presentation.calibration_dialog import CalibrationDialog
from rutasegura.presentation.norms_page import NormsPage
from rutasegura.presentation.project_dialogs import NewProjectDialog, OpenProjectDialog
from rutasegura.presentation.report_page import ReportPage
from rutasegura.presentation.rooms_page import RoomsPage
from rutasegura.presentation.simulation_page import SimulationPage
from rutasegura.presentation.wizard_pages import EditorPage, LoadPlanPage, ScalePage
from rutasegura.resources.texts import TEXTS, UiTexts

Image = npt.NDArray[np.uint8]

STEP_LOAD, STEP_SCALE, STEP_EDIT, STEP_ROOMS, STEP_NORMS, STEP_SIMULATE, STEP_REPORT = range(7)
MAX_FLOORS = 4
ACTIVE_STEPS = (
    STEP_LOAD,
    STEP_SCALE,
    STEP_EDIT,
    STEP_ROOMS,
    STEP_NORMS,
    STEP_SIMULATE,
    STEP_REPORT,
)


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
        self._scenario: Scenario | None = None
        self._scenario_dirty = False
        self._project_use = UseType.EDUCATION
        # Pisos que no se están editando (ya guardados): nivel → (plano, imagen).
        self._other_floors: dict[int, tuple[FloorPlan, Image | None]] = {}
        self._project_name = ""

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

        tools_menu = self.menuBar().addMenu(t.calibration.menu_tools)
        self.calibrate_action = QAction(t.calibration.menu_calibrate, self)
        self.calibrate_action.triggered.connect(self.open_calibration)
        tools_menu.addAction(self.calibrate_action)

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
        self.rooms_page = RoomsPage(plans, self._texts.rooms, self._texts.project)
        self.rooms_page.plan_changed.connect(self._on_plan_edited)
        self.rooms_page.scenario_changed.connect(self._on_scenario_changed)
        self.simulation_page = SimulationPage(
            self._services.simulations, self._texts.simulation, self._texts.scenarios
        )
        self.simulation_page.scenario_changed.connect(self._on_scenario_changed)
        self.norms_page = NormsPage(self._services.norms, self._texts.norms)
        self.norms_page.plan_changed.connect(self._on_plan_edited)
        self.report_page = ReportPage(self._services.reports, self._texts.report)
        for page in (
            self.load_page,
            self.scale_page,
            self.editor_page,
            self.rooms_page,
            self.norms_page,
            self.simulation_page,
            self.report_page,
        ):
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
            self.rooms_page,
            self.norms_page,
            self.simulation_page,
            self.report_page,
            self.pending_page,
        ):
            self.stack.addWidget(page)

        ft = t.floors
        self.floor_combo = QComboBox()
        self.floor_combo.currentIndexChanged.connect(self._on_floor_selected)
        self.add_floor_button = QPushButton(ft.add)
        self.add_floor_button.clicked.connect(self.add_floor)
        self.delete_floor_button = QPushButton(ft.delete)
        self.delete_floor_button.clicked.connect(self.ask_delete_floor)
        floor_bar = QHBoxLayout()
        floor_bar.addWidget(QLabel(ft.label))
        floor_bar.addWidget(self.floor_combo)
        floor_bar.addWidget(self.add_floor_button)
        floor_bar.addWidget(self.delete_floor_button)
        floor_bar.addStretch(1)
        self.floor_bar = QWidget()
        self.floor_bar.setLayout(floor_bar)
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.addWidget(self.floor_bar)
        right.addWidget(self.stack, stretch=1)

        layout = QHBoxLayout()
        layout.addWidget(self.steps_list)
        layout.addLayout(right, stretch=1)
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
        floors = self._services.projects.load_floors(project_id) or [FloorPlan()]
        images = [self._services.projects.load_floor_image(f) for f in floors]
        plan, image = floors[0], images[0]
        self._other_floors = {
            f.level: (f, img) for f, img in zip(floors[1:], images[1:], strict=True)
        }
        self.project_id = project_id
        self._project_use = project.use
        self._project_name = project.name
        self._plan, self._image = plan, image
        self._image_dirty = self._dirty = self._scenario_dirty = False
        self._scenario = self._services.simulations.load_scenario(project_id)
        self.simulation_page.set_run(self._services.simulations.last_run(project_id))
        self.load_page.set_image(image)
        self.scale_page.set_content(image, plan.scale_m_per_px)
        self.editor_page.set_content(plan, image)
        self.setWindowTitle(f"{project.name} — {self._texts.window_title}")
        self.statusBar().showMessage(self._texts.project.opened.format(name=project.name))
        self._refresh_floor_bar()
        self._update_steps()
        has_elements = bool(plan.walls or plan.doors or plan.exits)
        self.go_to_step(STEP_EDIT if has_elements else STEP_LOAD)

    def save(self) -> bool:
        """Guarda el plano y el escenario. Devuelve ``False`` si no se pudo."""
        if self.project_id is None:
            return True
        try:
            self._plan = self._services.projects.save_floor(
                self.project_id, self._plan, self._image if self._image_dirty else None
            )
            self._image_dirty = self._dirty = False
            # el escenario referencia ambientes por nombre: se guarda después del plano
            if self._scenario is not None and self._scenario_dirty:
                self._services.simulations.save_scenario(self.project_id, self._scenario)
                self._scenario_dirty = False
        except UserFacingError as exc:
            self.show_error(exc.message)
            return False
        self.statusBar().showMessage(self._texts.project.saved, 4000)
        return True

    def _save_if_dirty(self) -> bool:
        return self.save() if self.is_dirty else True

    @property
    def plan(self) -> FloorPlan:
        """Plano en edición (piso actual)."""
        return self._plan

    @property
    def level(self) -> int:
        """Piso en edición (0 = piso 1)."""
        return self._plan.level

    def all_floors(self) -> list[tuple[FloorPlan, Image | None]]:
        """Todos los pisos (plano, imagen), del más bajo al más alto."""
        floors = {**self._other_floors, self._plan.level: (self._plan, self._image)}
        return [floors[level] for level in sorted(floors)]

    # ----------------------------------------------------------------- pisos
    def switch_floor(self, level: int) -> bool:
        """Pasa a editar otro piso (guarda el actual)."""
        if level == self._plan.level or level not in self._other_floors:
            return level == self._plan.level
        if not self.save():
            return False
        self._other_floors[self._plan.level] = (self._plan, self._image)
        self._load_current(*self._other_floors.pop(level))
        step = self.current_step()
        self.go_to_step(step if step in ACTIVE_STEPS else STEP_LOAD)
        return True

    def add_floor(self) -> bool:
        """Agrega un piso encima del más alto (hasta 4) y lo abre en el paso 1."""
        ft = self._texts.floors
        levels = [plan.level for plan, _ in self.all_floors()]
        if len(levels) >= MAX_FLOORS:
            self.show_error(ft.max_floors)
            return False
        if not self.save():
            return False
        self._other_floors[self._plan.level] = (self._plan, self._image)
        new_level = max(levels) + 1
        self._load_current(FloorPlan(level=new_level), None)
        self._dirty = True
        self.save()
        self.statusBar().showMessage(
            ft.added.format(name=ft.name.format(number=new_level + 1)), 8000
        )
        self.go_to_step(STEP_LOAD)
        return True

    def ask_delete_floor(self) -> None:
        """Pide confirmación y elimina el piso actual."""
        ft = self._texts.floors
        name = ft.name.format(number=self._plan.level + 1)
        answer = QMessageBox.question(self, ft.delete, ft.confirm_delete.format(name=name))
        if answer == QMessageBox.StandardButton.Yes:
            self.delete_current_floor()

    def delete_current_floor(self) -> bool:
        """Elimina el piso actual (solo el más alto, y nunca el piso 1)."""
        levels = [plan.level for plan, _ in self.all_floors()]
        level = self._plan.level
        if self.project_id is None or level == min(levels) or level != max(levels):
            self.show_error(self._texts.floors.cannot_delete)
            return False
        if self._scenario is not None:
            self._scenario = dataclasses.replace(
                self._scenario,
                occupancies=tuple(o for o in self._scenario.occupancies if o.level != level),
            )
            self._scenario_dirty = True
        self._services.projects.delete_floor(self.project_id, level)
        self._dirty = self._image_dirty = False
        below = max(self._other_floors)
        self._load_current(*self._other_floors.pop(below))
        self.save()
        self.go_to_step(
            STEP_LOAD if self.current_step() not in ACTIVE_STEPS else self.current_step()
        )
        return True

    def _load_current(self, plan: FloorPlan, image: Image | None) -> None:
        self._plan, self._image = plan, image
        self._dirty = self._image_dirty = False
        self.load_page.set_image(image)
        self.scale_page.set_content(image, plan.scale_m_per_px)
        self.editor_page.set_content(plan, image)
        self._refresh_floor_bar()

    def _refresh_floor_bar(self) -> None:
        ft = self._texts.floors
        levels = [plan.level for plan, _ in self.all_floors()]
        self.floor_combo.blockSignals(True)
        self.floor_combo.clear()
        for level in levels:
            self.floor_combo.addItem(ft.name.format(number=level + 1), level)
        self.floor_combo.setCurrentIndex(self.floor_combo.findData(self._plan.level))
        self.floor_combo.blockSignals(False)
        self.add_floor_button.setEnabled(len(levels) < MAX_FLOORS)
        self.delete_floor_button.setEnabled(
            self._plan.level == max(levels) and self._plan.level != min(levels)
        )

    def _on_floor_selected(self, index: int) -> None:
        level = self.floor_combo.itemData(index)
        if level is not None and not self.switch_floor(int(level)):
            self._refresh_floor_bar()

    @property
    def scenario(self) -> Scenario | None:
        """Escenario en edición."""
        return self._scenario

    @property
    def is_dirty(self) -> bool:
        """Hay cambios sin guardar."""
        return self._dirty or self._scenario_dirty

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
        elif step == STEP_ROOMS and self._scenario is not None:
            self.rooms_page.set_content(
                self._plan,
                self._image,
                self._scenario,
                self._services.simulations.profiles(),
                self._project_use,
            )
            self.stack.setCurrentWidget(self.rooms_page)
        elif step == STEP_NORMS:
            self.norms_page.set_content(self._plan, self._scenario)
            self.stack.setCurrentWidget(self.norms_page)
        elif step == STEP_REPORT:
            self.report_page.set_content(
                self.project_id,
                self._project_name,
                self.simulation_page.current_run is not None,
            )
            self.stack.setCurrentWidget(self.report_page)
        elif step == STEP_SIMULATE and self._scenario is not None:
            self.simulation_page.set_content(self.project_id, self.all_floors(), self._scenario)
            self.stack.setCurrentWidget(self.simulation_page)
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
        self.calibrate_action.setEnabled(self.project_id is not None)
        self.floor_bar.setVisible(self.project_id is not None)
        if self.project_id is None:
            self.stack.setCurrentWidget(self.welcome_page)

    # ----------------------------------------------------------------- cambios en los pasos
    def _on_image_loaded(self, image: Image) -> None:
        # Imagen nueva: la geometría anterior y la escala ya no corresponden a estos píxeles.
        self._image = image
        self._image_dirty = True
        self._plan = FloorPlan(level=self._plan.level)
        self._dirty = True
        level = self._plan.level
        if self._scenario is not None and any(o.level == level for o in self._scenario.occupancies):
            kept = tuple(o for o in self._scenario.occupancies if o.level != level)
            self._scenario = dataclasses.replace(self._scenario, occupancies=kept)
            self._scenario_dirty = True
        self.editor_page.set_content(self._plan, image)

    def _on_scale_changed(self, scale: float) -> None:
        # El editor se recarga con la nueva escala al entrar al paso 3 (go_to_step).
        self._plan = dataclasses.replace(self._plan, scale_m_per_px=scale)
        self._dirty = True

    def _on_plan_edited(self, plan: FloorPlan) -> None:
        if plan != self._plan:
            self._plan = plan
            self._dirty = True

    def _on_scenario_changed(self, scenario: Scenario) -> None:
        if scenario != self._scenario:
            self._scenario = scenario
            self._scenario_dirty = True

    # ----------------------------------------------------------------- calibración
    def calibration_dialog(self) -> CalibrationDialog | None:
        """Diálogo de calibración con el plano y el escenario base actuales (guarda antes)."""
        if self.project_id is None or self._scenario is None or not self.save():
            self.show_error(self._texts.calibration.no_project)
            return None
        dialog = CalibrationDialog(
            self._services.calibration,
            self.project_id,
            [plan for plan, _ in self.all_floors()],
            self._scenario,
            texts=self._texts.calibration,
            parent=self,
        )
        dialog.applied.connect(
            lambda: self.statusBar().showMessage(self._texts.calibration.applied, 6000)
        )
        return dialog

    def open_calibration(self) -> None:
        """Abre el diálogo de calibración."""
        dialog = self.calibration_dialog()
        if dialog is not None:
            dialog.exec()

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
