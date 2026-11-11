"""Pasos 1 a 3 del asistente: cargar plano, escala y corregir plano."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import numpy.typing as npt
from PySide6.QtCore import QLineF, QPointF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPen
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from rutasegura.application.errors import UserFacingError
from rutasegura.application.plan_import import PlanImportService
from rutasegura.domain.geometry import Point
from rutasegura.domain.plan import FloorPlan
from rutasegura.presentation.editor.editor_widget import PlanEditor
from rutasegura.presentation.editor.scene import PlanScene
from rutasegura.presentation.editor.view import PlanView, Tool
from rutasegura.presentation.qt_support import run_in_background
from rutasegura.resources.texts import TEXTS, EditorTexts, WizardTexts

Image = npt.NDArray[np.uint8]


def _title(text: str) -> QLabel:
    label = QLabel(text)
    font = QFont(label.font())
    font.setPointSize(font.pointSize() + 5)
    font.setBold(True)
    label.setFont(font)
    return label


def _help(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    return label


def _marker(point: QPointF, color: str) -> QGraphicsEllipseItem:
    item = QGraphicsEllipseItem(-6, -6, 12, 12)
    item.setPos(point)
    item.setBrush(QBrush(QColor(color)))
    pen = QPen(QColor("white"), 2)
    pen.setCosmetic(True)
    item.setPen(pen)
    item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
    item.setZValue(500)
    return item


# --------------------------------------------------------------------------- paso 1


class LoadPlanPage(QWidget):
    """Paso 1: elegir el archivo, la página del PDF y, si hace falta, enderezar la foto."""

    image_loaded = Signal(object)  # imagen nueva (array RGB)
    error = Signal(str)
    next_requested = Signal()

    def __init__(
        self,
        plans: PlanImportService,
        texts: WizardTexts = TEXTS.wizard,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._plans = plans
        self._texts = texts
        self._path: Path | None = None
        self._image: Image | None = None
        self._original: Image | None = None
        self._corners: list[QPointF] = []
        self._markers: list[QGraphicsEllipseItem] = []

        self.choose_button = QPushButton(texts.choose_file)
        self.choose_button.clicked.connect(self.choose_file)
        self.file_label = QLabel(texts.no_file)
        self.page_label = QLabel(texts.page_label)
        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.valueChanged.connect(self._on_page_changed)
        self.straighten_button = QPushButton(texts.straighten)
        self.straighten_button.setCheckable(True)
        self.straighten_button.toggled.connect(self._on_straighten_toggled)
        self.undo_straighten_button = QPushButton(texts.straighten_undo)
        self.undo_straighten_button.clicked.connect(self.undo_straighten)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.next_button = QPushButton(texts.next)
        self.next_button.clicked.connect(self.next_requested)

        self.scene = PlanScene(self)
        self.view = PlanView(self.scene)
        self.view.point_picked.connect(self.add_corner)

        row = QHBoxLayout()
        row.addWidget(self.choose_button)
        row.addWidget(self.file_label)
        row.addStretch(1)
        right: tuple[QWidget, ...] = (
            self.page_label,
            self.page_spin,
            self.straighten_button,
            self.undo_straighten_button,
        )
        for widget in right:
            row.addWidget(widget)
        bottom = QHBoxLayout()
        bottom.addWidget(self.status_label, stretch=1)
        bottom.addWidget(self.next_button)
        layout = QVBoxLayout(self)
        layout.addWidget(_title(texts.load_title))
        layout.addWidget(_help(texts.load_help))
        layout.addLayout(row)
        layout.addWidget(self.view, stretch=1)
        layout.addLayout(bottom)
        self._refresh()

    @property
    def image(self) -> Image | None:
        """Imagen actual (ya enderezada, si corresponde)."""
        return self._image

    def set_image(self, image: Image | None) -> None:
        """Muestra la imagen de un proyecto abierto (sin emitir ``image_loaded``)."""
        self._path = None
        self._original = None
        self._image = image
        self.scene.set_image(image)
        self.file_label.setText("" if image is not None else self._texts.no_file)
        self._refresh()
        self.view.fit_all()

    def choose_file(self) -> None:
        """Abre el diálogo para elegir el plano."""
        patterns = " ".join(f"*{s}" for s in self._plans.supported_suffixes())
        filename, _ = QFileDialog.getOpenFileName(
            self,
            self._texts.file_dialog_title,
            "",
            self._texts.file_filter.format(patterns=patterns),
        )
        if filename:
            self.open_file(Path(filename))

    def open_file(self, path: Path, page: int = 0) -> None:
        """Carga un archivo (imagen o PDF)."""
        try:
            pages = self._plans.page_count(path)
            image = self._plans.load(path, page)
        except UserFacingError as exc:
            self.error.emit(exc.message)
            return
        self._path = path
        self.page_spin.blockSignals(True)
        self.page_spin.setMaximum(pages)
        self.page_spin.setValue(page + 1)
        self.page_spin.blockSignals(False)
        self.file_label.setText(path.name)
        self._original = image
        self._set_new_image(image)

    def _on_page_changed(self, value: int) -> None:
        if self._path is not None:
            self.open_file(self._path, value - 1)

    def _set_new_image(self, image: Image) -> None:
        self._image = image
        self.scene.set_image(image)
        self.straighten_button.setChecked(False)
        self._clear_corners()
        self._refresh()
        self.view.fit_all()
        self.image_loaded.emit(image)

    # ----------------------------------------------------------------- enderezar
    def _on_straighten_toggled(self, checked: bool) -> None:
        self._clear_corners()
        self.view.set_tool(Tool.POINTS if checked else Tool.NONE)
        self._refresh()

    def add_corner(self, point: QPointF) -> None:
        """Registra una esquina; con la cuarta, endereza la imagen."""
        if not self.straighten_button.isChecked() or self._image is None:
            return
        self._corners.append(point)
        marker = _marker(point, "#e74c3c")
        self.scene.addItem(marker)
        self._markers.append(marker)
        if len(self._corners) == 4:
            corners = [Point(p.x(), p.y()) for p in self._corners]
            try:
                straight = self._plans.straighten(self._image, corners)
            except UserFacingError as exc:
                self._clear_corners()
                self.error.emit(exc.message)
                return
            if self._original is None:
                self._original = self._image
            self._set_new_image(straight)
            return
        self._refresh()

    def undo_straighten(self) -> None:
        """Vuelve a la imagen sin enderezar."""
        if self._original is not None and self._original is not self._image:
            self._set_new_image(self._original)

    def _clear_corners(self) -> None:
        for marker in self._markers:
            self.scene.removeItem(marker)
        self._markers.clear()
        self._corners.clear()

    def _refresh(self) -> None:
        has_image = self._image is not None
        multi_page = self.page_spin.maximum() > 1 and self._path is not None
        self.page_label.setVisible(multi_page)
        self.page_spin.setVisible(multi_page)
        self.straighten_button.setEnabled(has_image)
        self.undo_straighten_button.setVisible(
            self._original is not None and self._original is not self._image
        )
        self.next_button.setEnabled(has_image)
        if self.straighten_button.isChecked():
            self.status_label.setText(self._texts.straighten_help.format(count=len(self._corners)))
        else:
            self.status_label.setText("")


# --------------------------------------------------------------------------- paso 2


class ScalePage(QWidget):
    """Paso 2: el usuario dibuja una medida conocida y escribe cuántos metros mide (RF04)."""

    scale_changed = Signal(float)
    error = Signal(str)
    next_requested = Signal()

    def __init__(
        self,
        plans: PlanImportService,
        texts: WizardTexts = TEXTS.wizard,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._plans = plans
        self._texts = texts
        self._reference: tuple[Point, Point] | None = None
        self._line: QGraphicsLineItem | None = None
        self._scale: float | None = None

        self.scene = PlanScene(self)
        self.view = PlanView(self.scene)
        self.view.set_tool(Tool.MEASURE)
        self.view.segment_drawn.connect(
            lambda _tool, a, b: self.set_reference(Point(a.x(), a.y()), Point(b.x(), b.y()))
        )
        self.meters_spin = QDoubleSpinBox()
        self.meters_spin.setRange(0.01, 1000.0)
        self.meters_spin.setDecimals(2)
        self.meters_spin.setSingleStep(0.1)
        self.meters_spin.setValue(1.0)
        self.meters_spin.setSuffix(" m")
        self.apply_button = QPushButton(texts.scale_apply)
        self.apply_button.clicked.connect(self.apply_scale)
        self.result_label = QLabel()
        self.result_label.setWordWrap(True)
        self.next_button = QPushButton(texts.next)
        self.next_button.clicked.connect(self.next_requested)

        row = QHBoxLayout()
        row.addWidget(QLabel(texts.scale_meters))
        row.addWidget(self.meters_spin)
        row.addWidget(self.apply_button)
        row.addStretch(1)
        bottom = QHBoxLayout()
        bottom.addWidget(self.result_label, stretch=1)
        bottom.addWidget(self.next_button)
        layout = QVBoxLayout(self)
        layout.addWidget(_title(texts.scale_title))
        layout.addWidget(_help(texts.scale_help))
        layout.addLayout(row)
        layout.addWidget(self.view, stretch=1)
        layout.addLayout(bottom)
        self._show_scale()

    @property
    def scale(self) -> float | None:
        """Metros por píxel definidos (o ``None``)."""
        return self._scale

    def set_content(self, image: Image | None, scale: float | None) -> None:
        """Muestra la imagen y la escala actual."""
        self.scene.set_image(image)
        self._clear_reference()
        self._scale = scale
        self._show_scale()
        self.view.fit_all()

    def set_reference(self, p1: Point, p2: Point) -> None:
        """Línea de referencia dibujada por el usuario."""
        self._clear_reference()
        self._reference = (p1, p2)
        pen = QPen(QColor("#d35400"), 3)
        pen.setCosmetic(True)
        self._line = QGraphicsLineItem(QLineF(p1.x, p1.y, p2.x, p2.y))
        self._line.setPen(pen)
        self._line.setZValue(400)
        self.scene.addItem(self._line)

    def apply_scale(self) -> None:
        """Calcula la escala con la línea dibujada y los metros indicados."""
        if self._reference is None:
            self.error.emit(self._texts.scale_draw_first)
            return
        try:
            scale = self._plans.scale_from_reference(*self._reference, self.meters_spin.value())
        except UserFacingError as exc:
            self.error.emit(exc.message)
            return
        self._scale = scale
        self._show_scale()
        self.scale_changed.emit(scale)

    def _clear_reference(self) -> None:
        if self._line is not None:
            self.scene.removeItem(self._line)
        self._line = None
        self._reference = None

    def _show_scale(self) -> None:
        if self._scale:
            self.result_label.setText(self._texts.scale_result.format(px_per_m=1.0 / self._scale))
            self.result_label.setStyleSheet("color: #1e8449;")
        else:
            self.result_label.setText(self._texts.scale_missing)
            self.result_label.setStyleSheet("color: #b9770e;")


# --------------------------------------------------------------------------- paso 3


class EditorPage(QWidget):
    """Paso 3: detección automática + corrección manual."""

    error = Signal(str)
    detection_finished = Signal()

    def __init__(
        self,
        plans: PlanImportService,
        texts: WizardTexts = TEXTS.wizard,
        editor_texts: EditorTexts = TEXTS.editor,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._plans = plans
        self._texts = texts
        self._editor_texts = editor_texts
        self._image: Image | None = None
        self.editor = PlanEditor(editor_texts)
        self.detect_button = QPushButton(texts.detect)
        self.detect_button.clicked.connect(self.detect)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        row = QHBoxLayout()
        row.addWidget(self.detect_button)
        row.addWidget(self.status_label, stretch=1)
        layout = QVBoxLayout(self)
        layout.addWidget(_title(texts.editor_title))
        layout.addWidget(_help(texts.editor_help))
        layout.addLayout(row)
        layout.addWidget(self.editor, stretch=1)

    def set_content(self, plan: FloorPlan, image: Image | None) -> None:
        """Carga el plano y su imagen en el editor."""
        self._image = image
        self.editor.set_plan(plan, image)
        self.detect_button.setEnabled(image is not None)
        self.status_label.setText("" if image is not None else self._texts.no_image)

    def needs_detection(self) -> bool:
        """Hay imagen pero ningún muro, puerta ni salida todavía."""
        plan = self.editor.plan()
        return self._image is not None and not (plan.walls or plan.doors or plan.exits)

    def detect(self) -> None:
        """Ejecuta la detección automática en segundo plano."""
        if self._image is None:
            self.error.emit(self._texts.no_image)
            return
        image, plan = self._image, self.editor.plan()
        self.detect_button.setEnabled(False)
        self.editor.setEnabled(False)  # evita perder lo que se dibuje mientras se detecta
        self.status_label.setText(self._texts.detecting)
        self.setCursor(Qt.CursorShape.BusyCursor)
        run_in_background(
            lambda: self._plans.detect(image, plan), self._on_detected, self._on_failed
        )

    def _on_detected(self, result: object) -> None:
        self.unsetCursor()
        self.detect_button.setEnabled(True)
        self.editor.setEnabled(True)
        if isinstance(result, FloorPlan):
            self.editor.apply(result, self._editor_texts.cmd_detect)
            self.status_label.setText(
                self._texts.detect_done.format(
                    walls=len(result.walls), doors=len(result.doors), exits=len(result.exits)
                )
            )
        self.detection_finished.emit()

    def _on_failed(self, message: str) -> None:
        self.unsetCursor()
        self.detect_button.setEnabled(True)
        self.editor.setEnabled(True)
        self.status_label.setText("")
        self.error.emit(message)
        self.detection_finished.emit()
