"""Paso 6: escenarios, simulación en segundo plano y resultados (RF07, RF08, RF10)."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable

import numpy as np
import numpy.typing as npt
from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from rutasegura.application.errors import UserFacingError
from rutasegura.application.simulation_service import (
    BASE_SCENARIO,
    SimulationRun,
    SimulationService,
)
from rutasegura.domain.plan import FloorPlan
from rutasegura.domain.scenario import Scenario
from rutasegura.presentation.qt_support import BackgroundJob
from rutasegura.presentation.scenario_dialogs import ComparisonDialog, ScenarioDialog
from rutasegura.presentation.simulation_viewer import SimulationViewer, format_time
from rutasegura.resources.texts import TEXTS, ScenarioTexts, SimulationTexts

Image = npt.NDArray[np.uint8]


def _bold(label: QLabel, extra: int = 0) -> QLabel:
    font = QFont(label.font())
    font.setBold(True)
    font.setPointSize(font.pointSize() + extra)
    label.setFont(font)
    return label


class SimulationPage(QWidget):
    """Botón de simular, progreso/cancelar, visor y panel de resultados."""

    error = Signal(str)
    run_finished = Signal(object)  # SimulationRun
    scenario_changed = Signal(object)  # Scenario

    def __init__(
        self,
        simulations: SimulationService,
        texts: SimulationTexts = TEXTS.simulation,
        scenario_texts: ScenarioTexts = TEXTS.scenarios,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._simulations = simulations
        self._texts = texts
        self._stexts = scenario_texts
        self._project_id: int | None = None
        self._floors: list[tuple[FloorPlan, Image | None]] = []
        self._scenario = Scenario(BASE_SCENARIO, 0)  # escenario base (lo edita el paso 4)
        self._variants: list[Scenario] = []
        self._current = BASE_SCENARIO
        self._run: SimulationRun | None = None
        self.job: BackgroundJob | None = None

        st = scenario_texts
        self.scenario_combo = QComboBox()
        self.scenario_combo.currentTextChanged.connect(self._on_scenario_selected)
        self.new_button = QPushButton(st.new)
        self.new_button.clicked.connect(self.ask_new_variant)
        self.edit_button = QPushButton(st.edit)
        self.edit_button.clicked.connect(self.ask_edit_variant)
        self.delete_button = QPushButton(st.delete)
        self.delete_button.clicked.connect(self.ask_delete_variant)
        self.compare_button = QPushButton(st.compare)
        self.compare_button.clicked.connect(self.open_comparison)

        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 2_000_000_000)
        self.seed_spin.valueChanged.connect(self._on_seed)
        self.run_button = QPushButton(texts.run)
        self.run_button.clicked.connect(self.start_simulation)
        self.cancel_button = QPushButton(texts.cancel)
        self.cancel_button.clicked.connect(self.cancel_simulation)
        self.cancel_button.setEnabled(False)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        self.status_label = QLabel()

        self.viewer = SimulationViewer(texts)
        self.summary_label = QLabel(texts.no_run)
        self.summary_label.setWordWrap(True)
        self.bottleneck_list = QListWidget()
        self.bottleneck_list.setWordWrap(True)
        provisional = QLabel(texts.provisional)
        provisional.setWordWrap(True)
        provisional.setStyleSheet("color: #7f8c8d;")

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.addWidget(_bold(QLabel(texts.results_title), 2))
        panel_layout.addWidget(self.summary_label)
        panel_layout.addWidget(_bold(QLabel(texts.bottlenecks_title)))
        panel_layout.addWidget(self.bottleneck_list, stretch=1)
        panel_layout.addWidget(provisional)
        splitter = QSplitter()
        splitter.addWidget(self.viewer)
        splitter.addWidget(panel)
        splitter.setSizes([800, 340])

        scenario_row = QHBoxLayout()
        scenario_row.addWidget(QLabel(st.label))
        scenario_row.addWidget(self.scenario_combo, stretch=1)
        for button in (self.new_button, self.edit_button, self.delete_button, self.compare_button):
            scenario_row.addWidget(button)
        row = QHBoxLayout()
        row.addWidget(QLabel(texts.seed))
        row.addWidget(self.seed_spin)
        row.addWidget(self.run_button)
        row.addWidget(self.cancel_button)
        row.addWidget(self.progress, stretch=1)
        row.addWidget(self.status_label)
        help_label = QLabel(texts.help)
        help_label.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(_bold(QLabel(texts.title), 5))
        layout.addWidget(help_label)
        layout.addLayout(scenario_row)
        layout.addLayout(row)
        layout.addWidget(splitter, stretch=1)

    # ------------------------------------------------------------------ contenido
    @property
    def current_run(self) -> SimulationRun | None:
        """Corrida mostrada."""
        return self._run

    @property
    def current_scenario(self) -> Scenario:
        """Escenario seleccionado (el base o una variante)."""
        if self._current == BASE_SCENARIO:
            return self._scenario
        return next((v for v in self._variants if v.name == self._current), self._scenario)

    @property
    def scenario_names(self) -> list[str]:
        """Nombres en el selector."""
        return [self.scenario_combo.itemText(i) for i in range(self.scenario_combo.count())]

    def set_content(
        self,
        project_id: int,
        floors: list[tuple[FloorPlan, Image | None]],
        scenario: Scenario,
    ) -> None:
        """Pisos (plano e imagen), escenario base (en memoria) y variantes guardadas."""
        if self._project_id != project_id:
            self._current = BASE_SCENARIO
        self._project_id = project_id
        self._floors = sorted(floors, key=lambda f: f[0].level)
        self._scenario = scenario
        self.viewer.set_floors(self._floors)
        self._reload_variants()

    @property
    def plans(self) -> list[FloorPlan]:
        """Planos de todos los pisos, del más bajo al más alto."""
        return [plan for plan, _ in self._floors]

    def _reload_variants(self) -> None:
        if self._project_id is None:
            return
        self._variants = self._simulations.list_scenarios(self._project_id)[1:]
        names = [BASE_SCENARIO, *(v.name for v in self._variants)]
        if self._current not in names:
            self._current = BASE_SCENARIO
        self.scenario_combo.blockSignals(True)
        self.scenario_combo.clear()
        self.scenario_combo.addItems(names)
        self.scenario_combo.setCurrentText(self._current)
        self.scenario_combo.blockSignals(False)
        self._select(self._current)

    def _on_scenario_selected(self, name: str) -> None:
        if name and name != self._current:
            self._select(name)

    def _select(self, name: str) -> None:
        self._current = name
        is_base = name == BASE_SCENARIO
        self.edit_button.setEnabled(not is_base)
        self.delete_button.setEnabled(not is_base)
        self.seed_spin.blockSignals(True)
        self.seed_spin.setValue(self.current_scenario.seed)
        self.seed_spin.blockSignals(False)
        if self._project_id is not None:
            self.set_run(self._simulations.last_run(self._project_id, name))

    def select_scenario(self, name: str) -> None:
        """Selecciona un escenario por nombre."""
        self.scenario_combo.setCurrentText(name)

    # ------------------------------------------------------------------ variantes
    def _exit_names(self) -> list[str]:
        return [e.name for plan in self.plans for e in plan.exits if e.confirmed]

    def create_variant(self, name: str, percent: int, blocked: frozenset[str]) -> bool:
        """Crea un escenario «qué pasa si» y lo selecciona."""
        return self._save_variant(name, percent, blocked, previous=None)

    def update_current_variant(self, name: str, percent: int, blocked: frozenset[str]) -> bool:
        """Actualiza el escenario seleccionado (no el base)."""
        if self._current == BASE_SCENARIO:
            return False
        return self._save_variant(name, percent, blocked, previous=self._current)

    def _save_variant(
        self, name: str, percent: int, blocked: frozenset[str], previous: str | None
    ) -> bool:
        if self._project_id is None:
            return False
        try:
            variant = self._simulations.save_variant(
                self._project_id, name, self._scenario, percent, blocked, previous_name=previous
            )
        except UserFacingError as exc:
            self.error.emit(exc.message)
            return False
        self._current = variant.name
        self._reload_variants()
        return True

    def delete_current_variant(self) -> None:
        """Elimina el escenario seleccionado (no el base)."""
        if self._project_id is None or self._current == BASE_SCENARIO:
            return
        self._simulations.delete_scenario(self._project_id, self._current)
        self._current = BASE_SCENARIO
        self._reload_variants()

    def ask_new_variant(self) -> None:
        """Diálogo de escenario nuevo."""
        dialog = ScenarioDialog(
            self._exit_names(), self._scenario.total_occupants, texts=self._stexts, parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.create_variant(*dialog.values())

    def ask_edit_variant(self) -> None:
        """Diálogo para editar el escenario seleccionado."""
        variant = self.current_scenario
        if variant.name == BASE_SCENARIO:
            return
        base_total = self._scenario.total_occupants
        percent = round(100 * variant.total_occupants / base_total) if base_total else 100
        dialog = ScenarioDialog(
            self._exit_names(),
            base_total,
            name=variant.name,
            percent=max(10, percent),
            blocked=variant.blocked_exits,
            editing=True,
            texts=self._stexts,
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.update_current_variant(*dialog.values())

    def ask_delete_variant(self) -> None:
        """Pide confirmación y elimina el escenario seleccionado."""
        if self._current == BASE_SCENARIO:
            return
        answer = QMessageBox.question(
            self, self._stexts.delete, self._stexts.confirm_delete.format(name=self._current)
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.delete_current_variant()

    def comparison_dialog(self) -> ComparisonDialog | None:
        """Crea el comparador (o ``None`` sin proyecto)."""
        if self._project_id is None:
            return None
        project_id = self._project_id
        return ComparisonDialog(
            [self._scenario, *self._variants],
            lambda name: self._simulations.last_run(project_id, name),
            self._floors,
            texts=self._stexts,
            sim_texts=self._texts,
            parent=self,
        )

    def open_comparison(self) -> None:
        """Abre el comparador lado a lado."""
        dialog = self.comparison_dialog()
        if dialog is not None:
            dialog.exec()

    def set_run(self, run: SimulationRun | None) -> None:
        """Muestra una corrida (o ninguna)."""
        self._run = run
        self._show_run(run)

    # ------------------------------------------------------------------ ejecución
    def start_simulation(self) -> None:
        """Lanza la simulación en otro hilo."""
        if self._project_id is None or (self.job is not None and self.job.running):
            return
        project_id, plan, scenario = self._project_id, self.plans, self.current_scenario
        simulations = self._simulations

        def work(report: Callable[[float], None], should_cancel: Callable[[], bool]) -> object:
            return simulations.run(
                project_id, plan, scenario, progress=report, should_cancel=should_cancel
            )

        self.job = BackgroundJob(work, self)
        self.job.progress.connect(self._on_progress)
        self.job.done.connect(self._on_done)
        self.job.failed.connect(self._on_failed)
        self.job.cancelled.connect(self._on_cancelled)
        self._set_running(True)
        self.job.start()

    def cancel_simulation(self) -> None:
        """Pide cancelar la simulación en curso."""
        if self.job is not None:
            self.job.cancel()

    def _on_progress(self, fraction: float) -> None:
        percent = 100 * fraction
        self.progress.setValue(round(percent))
        self.status_label.setText(self._texts.running.format(percent=percent))

    def _on_done(self, run: object) -> None:
        self._set_running(False)
        self.status_label.setText("")
        if isinstance(run, SimulationRun):
            self.set_run(run)
            self.viewer.play()
            self.run_finished.emit(run)

    def _on_failed(self, message: str) -> None:
        self._set_running(False)
        self.status_label.setText("")
        self.error.emit(message)

    def _on_cancelled(self) -> None:
        self._set_running(False)
        self.status_label.setText(self._texts.cancelled)

    def _set_running(self, running: bool) -> None:
        self.run_button.setEnabled(not running)
        self.seed_spin.setEnabled(not running)
        self.scenario_combo.setEnabled(not running)
        for button in (self.new_button, self.compare_button):
            button.setEnabled(not running)
        is_base = self._current == BASE_SCENARIO
        self.edit_button.setEnabled(not running and not is_base)
        self.delete_button.setEnabled(not running and not is_base)
        self.cancel_button.setEnabled(running)
        self.progress.setVisible(running)
        self.progress.setValue(0)

    def _on_seed(self, value: int) -> None:
        if self._current == BASE_SCENARIO:
            self._scenario = dataclasses.replace(self._scenario, seed=value)
            self.scenario_changed.emit(self._scenario)
            return
        variant = dataclasses.replace(self.current_scenario, seed=value)
        self._variants = [variant if v.name == variant.name else v for v in self._variants]
        if self._project_id is not None:
            try:
                self._simulations.save_scenario(self._project_id, variant)
            except UserFacingError as exc:
                self.error.emit(exc.message)

    # ------------------------------------------------------------------ resultados
    def _show_run(self, run: SimulationRun | None) -> None:
        self.bottleneck_list.clear()
        if run is None:
            self.viewer.set_run(None, None, 1.0)
            self.summary_label.setText(self._texts.no_run)
            return
        t = self._texts
        result = run.result
        self.viewer.set_run(run.trajectories, result, run.scale_m_per_px)
        lines = [t.total_time.format(time=format_time(result.total_time_s))]
        lines += [t.per_exit.format(name=n, time=format_time(s)) for n, s in result.time_per_exit_s]
        if not result.completed:
            lines.append(
                t.incomplete.format(
                    time=format_time(result.total_time_s),
                    left=result.agents_total - result.agents_evacuated,
                )
            )
        self.summary_label.setText("\n".join(lines))
        if not run.observations:
            self.bottleneck_list.addItem(t.no_bottlenecks)
        for rank, observation in enumerate(run.observations, start=1):
            item = QListWidgetItem(f"{rank}. {observation.description}")
            item.setToolTip(observation.recommendation)
            self.bottleneck_list.addItem(item)
