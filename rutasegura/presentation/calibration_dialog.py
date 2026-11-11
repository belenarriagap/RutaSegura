"""Registro de un simulacro real y calibración del modelo (RF11)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from PySide6.QtCore import QDate, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from rutasegura.application.calibration_service import CalibrationService
from rutasegura.domain.calibration import CalibrationResult
from rutasegura.domain.plan import FloorPlan
from rutasegura.domain.scenario import RealDrill, Scenario
from rutasegura.presentation.qt_support import BackgroundJob
from rutasegura.presentation.simulation_viewer import format_time
from rutasegura.resources.texts import TEXTS, CalibrationTexts


class CalibrationDialog(QDialog):
    """Datos del simulacro → búsqueda de factores → aplicar a los perfiles."""

    calibrated = Signal(object)  # CalibrationResult
    failed = Signal(str)
    applied = Signal()

    def __init__(
        self,
        calibration: CalibrationService,
        project_id: int,
        plan: FloorPlan,
        scenario: Scenario,
        *,
        grid: tuple[Sequence[float], Sequence[float]] | None = None,
        texts: CalibrationTexts = TEXTS.calibration,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._calibration = calibration
        self._project_id = project_id
        self._plan = plan
        self._scenario = scenario
        self._grid = grid
        self._texts = texts
        self.calibration_result: CalibrationResult | None = None
        self.job: BackgroundJob | None = None
        self.setWindowTitle(texts.title)
        self.resize(560, 520)

        help_label = QLabel(texts.help)
        help_label.setWordWrap(True)
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.participants_spin = QSpinBox()
        self.participants_spin.setRange(1, 20_000)
        self.participants_spin.setValue(max(1, scenario.total_occupants))
        self.minutes_spin = QSpinBox()
        self.minutes_spin.setRange(0, 120)
        self.minutes_spin.setSuffix(texts.minutes)
        self.seconds_spin = QSpinBox()
        self.seconds_spin.setRange(0, 59)
        self.seconds_spin.setSuffix(texts.seconds)
        time_row = QHBoxLayout()
        time_row.addWidget(self.minutes_spin)
        time_row.addWidget(self.seconds_spin)
        time_row.addStretch(1)
        form = QFormLayout()
        form.addRow(texts.date, self.date_edit)
        form.addRow(texts.participants, self.participants_spin)
        form.addRow(texts.total_time, time_row)
        self.exit_spins: dict[str, QSpinBox] = {}
        exits_form = QFormLayout()
        for exit_ in plan.exits:
            if not exit_.confirmed:
                continue
            spin = QSpinBox()
            spin.setRange(0, 7200)
            spin.setSuffix(texts.seconds)
            self.exit_spins[exit_.name] = spin
            exits_form.addRow(f"{exit_.name}:", spin)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        self.status_label = QLabel()
        self.result_label = QLabel()
        self.result_label.setWordWrap(True)
        bold = QFont(self.result_label.font())
        bold.setBold(True)
        self.result_label.setFont(bold)
        self.run_button = QPushButton(texts.run)
        self.run_button.clicked.connect(self.start)
        self.cancel_button = QPushButton(texts.cancel)
        self.cancel_button.clicked.connect(self.cancel)
        self.cancel_button.setEnabled(False)
        self.apply_button = QPushButton(texts.apply)
        self.apply_button.clicked.connect(self.apply)
        self.apply_button.setEnabled(False)
        close_button = QPushButton(texts.close)
        close_button.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        for button in (self.run_button, self.cancel_button, self.apply_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(help_label)
        layout.addLayout(form)
        if self.exit_spins:
            per_exit = QLabel(texts.per_exit)
            per_exit.setWordWrap(True)
            layout.addWidget(per_exit)
            layout.addLayout(exits_form)
        layout.addLayout(buttons)
        layout.addWidget(self.progress)
        layout.addWidget(self.status_label)
        layout.addWidget(self.result_label)
        layout.addStretch(1)

    def set_drill(self, drill: RealDrill) -> None:
        """Rellena el formulario con un simulacro (útil para pruebas y reintentos)."""
        d = drill.drill_date
        self.date_edit.setDate(QDate(d.year, d.month, d.day))
        self.participants_spin.setValue(drill.participants)
        minutes, seconds = divmod(round(drill.total_time_s), 60)
        self.minutes_spin.setValue(minutes)
        self.seconds_spin.setValue(seconds)
        times = dict(drill.time_per_exit_s)
        for name, spin in self.exit_spins.items():
            spin.setValue(round(times.get(name, 0)))

    def drill(self) -> RealDrill:
        """Simulacro con los datos del formulario."""
        total = self.minutes_spin.value() * 60 + self.seconds_spin.value()
        per_exit = tuple(
            (name, float(spin.value()))
            for name, spin in self.exit_spins.items()
            if spin.value() > 0
        )
        return RealDrill(
            drill_date=self.date_edit.date().toPython(),  # type: ignore[arg-type]
            participants=self.participants_spin.value(),
            total_time_s=float(max(total, 1)),
            time_per_exit_s=per_exit,
        )

    def start(self) -> None:
        """Calibra en segundo plano."""
        if self.job is not None and self.job.running:
            return
        if self.minutes_spin.value() * 60 + self.seconds_spin.value() == 0:
            self.status_label.setText(self._texts.missing_time)
            self.failed.emit(self._texts.missing_time)
            return
        drill = self.drill()
        service, project_id, plan, scenario = (
            self._calibration,
            self._project_id,
            self._plan,
            self._scenario,
        )
        extra: dict[str, Any] = {}
        if self._grid is not None:
            extra = {"reaction_factors": self._grid[0], "speed_factors": self._grid[1]}

        def work(report: Callable[[float], None], should_cancel: Callable[[], bool]) -> object:
            return service.calibrate(
                project_id,
                plan,
                scenario,
                drill,
                progress=report,
                should_cancel=should_cancel,
                **extra,
            )

        self.job = BackgroundJob(work, self)
        self.job.progress.connect(self._on_progress)
        self.job.done.connect(self._on_done)
        self.job.failed.connect(self._on_failed)
        self.job.cancelled.connect(self._on_cancelled)
        self.calibration_result = None
        self.result_label.setText("")
        self.apply_button.setEnabled(False)
        self._set_running(True)
        self.job.start()

    def cancel(self) -> None:
        """Pide cancelar."""
        if self.job is not None:
            self.job.cancel()

    def apply(self) -> None:
        """Aplica los factores calibrados a los perfiles."""
        if self.calibration_result is None:
            return
        self._calibration.apply(self.calibration_result)
        self.apply_button.setEnabled(False)
        self.status_label.setText(self._texts.applied)
        self.applied.emit()

    def _on_progress(self, fraction: float) -> None:
        self.progress.setValue(round(100 * fraction))
        self.status_label.setText(self._texts.running.format(percent=100 * fraction))

    def _on_done(self, result: object) -> None:
        self._set_running(False)
        if not isinstance(result, CalibrationResult):
            return
        self.calibration_result = result
        t = self._texts
        text = t.result.format(
            before=result.total_error_before,
            after=result.total_error_after,
            reaction=result.best.reaction_factor,
            speed=result.best.speed_factor,
            simulated=format_time(result.best.total_time_s),
            observed=format_time(result.observed_total_s),
        )
        verdict = t.target_met if result.meets_target else t.target_missed
        self.result_label.setText(f"{text}\n{verdict}")
        self.status_label.setText("")
        self.apply_button.setEnabled(True)
        self.calibrated.emit(result)

    def _on_failed(self, message: str) -> None:
        self._set_running(False)
        self.status_label.setText(message)
        self.failed.emit(message)

    def _on_cancelled(self) -> None:
        self._set_running(False)
        self.status_label.setText(self._texts.cancelled)

    def _set_running(self, running: bool) -> None:
        self.run_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)
        self.progress.setVisible(running)
        self.progress.setValue(0)
