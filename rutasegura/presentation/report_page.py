"""Paso 7: generar el informe PDF (RF09)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QStandardPaths, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from rutasegura.application.report_service import ReportService
from rutasegura.presentation.qt_support import BackgroundJob
from rutasegura.resources.texts import TEXTS, ReportTexts


class ReportPage(QWidget):
    """Botón para generar el informe y acceso al archivo generado."""

    error = Signal(str)
    report_ready = Signal(object)  # Path

    def __init__(
        self,
        reports: ReportService,
        texts: ReportTexts = TEXTS.report,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._reports = reports
        self._texts = texts
        self._project_id: int | None = None
        self._project_name = ""
        self.last_path: Path | None = None
        self.job: BackgroundJob | None = None

        title = QLabel(texts.title)
        font = QFont(title.font())
        font.setPointSize(font.pointSize() + 5)
        font.setBold(True)
        title.setFont(font)
        help_label = QLabel(texts.help)
        help_label.setWordWrap(True)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.result_label = QLabel()
        self.result_label.setWordWrap(True)
        self.generate_button = QPushButton(texts.generate)
        self.generate_button.clicked.connect(self.ask_and_generate)
        self.open_button = QPushButton(texts.open)
        self.open_button.clicked.connect(self.open_report)
        self.open_button.setEnabled(False)
        buttons = QHBoxLayout()
        buttons.addWidget(self.generate_button)
        buttons.addWidget(self.open_button)
        buttons.addStretch(1)
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(help_label)
        layout.addWidget(self.status_label)
        layout.addLayout(buttons)
        layout.addWidget(self.result_label)
        layout.addStretch(1)

    def set_content(self, project_id: int, project_name: str, has_run: bool) -> None:
        """Proyecto a informar y si ya tiene simulación."""
        self._project_id = project_id
        self._project_name = project_name
        self.status_label.setText(self._texts.ready if has_run else self._texts.no_run)

    def ask_and_generate(self) -> None:
        """Pide dónde guardar y genera el informe."""
        folder = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        safe_name = "".join(c for c in self._project_name if c not in '\\/:*?"<>|').strip()
        suggested = str(Path(folder) / self._texts.default_name.format(name=safe_name or "local"))
        filename, _ = QFileDialog.getSaveFileName(
            self, self._texts.save_title, suggested, self._texts.save_filter
        )
        if filename:
            self.generate_to(Path(filename))

    def generate_to(self, path: Path) -> None:
        """Genera el informe en ``path`` sin bloquear la interfaz."""
        if self._project_id is None or (self.job is not None and self.job.running):
            return
        project_id, reports = self._project_id, self._reports

        def work(_report: Callable[[float], None], _cancel: Callable[[], bool]) -> object:
            return reports.generate(project_id, path)

        self.job = BackgroundJob(work, self)
        self.job.done.connect(self._on_done)
        self.job.failed.connect(self._on_failed)
        self.generate_button.setEnabled(False)
        self.result_label.setText(self._texts.generating)
        self.job.start()

    def open_report(self) -> None:
        """Abre el último informe con el visor de PDF del sistema."""
        if self.last_path is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_path)))

    def _on_done(self, path: object) -> None:
        self.generate_button.setEnabled(True)
        if isinstance(path, Path):
            self.last_path = path
            self.open_button.setEnabled(True)
            self.result_label.setText(self._texts.saved.format(path=path))
            self.report_ready.emit(path)

    def _on_failed(self, message: str) -> None:
        self.generate_button.setEnabled(True)
        self.result_label.setText("")
        self.error.emit(message)
