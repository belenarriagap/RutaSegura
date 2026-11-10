"""Paso 6: ejecutar la simulación en segundo plano y revisar resultados (RF07, RF08)."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable

import numpy as np
import numpy.typing as npt
from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from rutasegura.application.simulation_service import SimulationRun, SimulationService
from rutasegura.domain.plan import FloorPlan
from rutasegura.domain.scenario import Scenario
from rutasegura.presentation.qt_support import BackgroundJob
from rutasegura.presentation.simulation_viewer import SimulationViewer, format_time
from rutasegura.resources.texts import TEXTS, SimulationTexts

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
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._simulations = simulations
        self._texts = texts
        self._project_id: int | None = None
        self._plan = FloorPlan()
        self._scenario = Scenario("", 0)
        self._run: SimulationRun | None = None
        self.job: BackgroundJob | None = None

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
        layout.addLayout(row)
        layout.addWidget(splitter, stretch=1)

    # ------------------------------------------------------------------ contenido
    @property
    def current_run(self) -> SimulationRun | None:
        """Corrida mostrada."""
        return self._run

    def set_content(
        self, project_id: int, plan: FloorPlan, image: Image | None, scenario: Scenario
    ) -> None:
        """Plano y escenario a simular."""
        self._project_id = project_id
        self._plan = plan
        self._scenario = scenario
        self.seed_spin.blockSignals(True)
        self.seed_spin.setValue(scenario.seed)
        self.seed_spin.blockSignals(False)
        self.viewer.set_plan(plan, image)
        if self._run is not None:
            self._show_run(self._run)

    def set_run(self, run: SimulationRun | None) -> None:
        """Muestra una corrida (o ninguna)."""
        self._run = run
        self._show_run(run)

    # ------------------------------------------------------------------ ejecución
    def start_simulation(self) -> None:
        """Lanza la simulación en otro hilo."""
        if self._project_id is None or (self.job is not None and self.job.running):
            return
        project_id, plan, scenario = self._project_id, self._plan, self._scenario
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
        self.cancel_button.setEnabled(running)
        self.progress.setVisible(running)
        self.progress.setValue(0)

    def _on_seed(self, value: int) -> None:
        self._scenario = dataclasses.replace(self._scenario, seed=value)
        self.scenario_changed.emit(self._scenario)

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
