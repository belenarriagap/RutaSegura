"""Vista del plano: zoom, desplazamiento y herramientas de dibujo."""

from __future__ import annotations

import math
from enum import Enum, auto

from PySide6.QtCore import QLineF, QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QWidget,
)


class Tool(Enum):
    """Herramienta activa en la vista."""

    SELECT = auto()
    WALL = auto()
    DOOR = auto()
    EXIT = auto()
    STAIR = auto()
    OBSTACLE = auto()
    SAFE_ZONE = auto()
    MEASURE = auto()  # línea de referencia para la escala
    POINTS = auto()  # marcar puntos sueltos (esquinas para enderezar)
    NONE = auto()  # solo mirar


SEGMENT_TOOLS = frozenset({Tool.WALL, Tool.DOOR, Tool.EXIT, Tool.MEASURE})
AREA_TOOLS = frozenset({Tool.STAIR, Tool.OBSTACLE, Tool.SAFE_ZONE})
MIN_ZOOM, MAX_ZOOM = 0.02, 40.0


def snap_to_angle(start: QPointF, end: QPointF, step_deg: float = 45.0) -> QPointF:
    """Ajusta ``end`` para que la línea quede a un múltiplo de ``step_deg`` grados."""
    dx, dy = end.x() - start.x(), end.y() - start.y()
    length = math.hypot(dx, dy)
    if length == 0:
        return QPointF(end)
    angle = round(math.degrees(math.atan2(dy, dx)) / step_deg) * step_deg
    rad = math.radians(angle)
    return QPointF(start.x() + length * math.cos(rad), start.y() + length * math.sin(rad))


class PlanView(QGraphicsView):
    """Vista con zoom (rueda), desplazamiento (botón central) y dibujo según la herramienta."""

    segment_drawn = Signal(object, QPointF, QPointF)  # (Tool, inicio, fin) en coordenadas de escena
    area_drawn = Signal(object, QRectF)  # (Tool, rectángulo)
    point_picked = Signal(QPointF)
    delete_requested = Signal()

    def __init__(self, scene: QGraphicsScene, parent: QWidget | None = None) -> None:
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QColor("#f4f4f4"))
        self._tool = Tool.NONE
        self._start: QPointF | None = None
        self._preview: QGraphicsLineItem | QGraphicsRectItem | None = None
        self._pan_from: QPoint | None = None
        self.set_tool(Tool.NONE)

    @property
    def tool(self) -> Tool:
        """Herramienta activa."""
        return self._tool

    def set_tool(self, tool: Tool) -> None:
        """Cambia la herramienta (cancela un dibujo en curso)."""
        self._cancel_drawing()
        self._tool = tool
        if tool is Tool.SELECT:
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            cursor = Qt.CursorShape.ArrowCursor if tool is Tool.NONE else Qt.CursorShape.CrossCursor
            self.viewport().setCursor(cursor)

    def zoom_factor(self) -> float:
        """Escala actual de la vista."""
        return float(self.transform().m11())

    def zoom_by(self, factor: float) -> None:
        """Acerca (>1) o aleja (<1) respetando los límites."""
        current = self.zoom_factor()
        target = min(MAX_ZOOM, max(MIN_ZOOM, current * factor))
        if current > 0:
            self.scale(target / current, target / current)

    def fit_all(self) -> None:
        """Muestra todo el plano."""
        rect = self.sceneRect()
        if not rect.isEmpty():
            self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    # ----------------------------------------------------------------- eventos
    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - API de Qt
        steps = event.angleDelta().y() / 120.0
        if steps:
            self.zoom_by(1.25**steps)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_from = event.position().toPoint()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            pos = self.mapToScene(event.position().toPoint())
            if self._tool is Tool.POINTS:
                self.point_picked.emit(pos)
                event.accept()
                return
            if self._tool in SEGMENT_TOOLS or self._tool in AREA_TOOLS:
                self._start = pos
                pen = QPen(QColor("#d35400"), 2, Qt.PenStyle.DashLine)
                pen.setCosmetic(True)
                if self._tool in SEGMENT_TOOLS:
                    self._preview = QGraphicsLineItem(QLineF(pos, pos))
                else:
                    self._preview = QGraphicsRectItem(QRectF(pos, pos))
                self._preview.setPen(pen)
                self._preview.setZValue(1000)
                self.scene().addItem(self._preview)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._pan_from is not None:
            delta = event.position().toPoint() - self._pan_from
            self._pan_from = event.position().toPoint()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        if self._start is not None and self._preview is not None:
            end = self._end_point(event)
            if isinstance(self._preview, QGraphicsLineItem):
                self._preview.setLine(QLineF(self._start, end))
            else:
                self._preview.setRect(QRectF(self._start, end).normalized())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.MiddleButton and self._pan_from is not None:
            self._pan_from = None
            self.set_tool(self._tool)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and self._start is not None:
            start, end = self._start, self._end_point(event)
            tool = self._tool
            self._cancel_drawing()
            if tool in SEGMENT_TOOLS and QLineF(start, end).length() >= 3:
                self.segment_drawn.emit(tool, start, end)
            elif tool in AREA_TOOLS:
                rect = QRectF(start, end).normalized()
                if rect.width() >= 3 and rect.height() >= 3:
                    self.area_drawn.emit(tool, rect)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_requested.emit()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self._cancel_drawing()
            event.accept()
            return
        super().keyPressEvent(event)

    def _end_point(self, event: QMouseEvent) -> QPointF:
        end = self.mapToScene(event.position().toPoint())
        snap = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if snap and self._start is not None and self._tool in SEGMENT_TOOLS:
            return snap_to_angle(self._start, end)
        return end

    def _cancel_drawing(self) -> None:
        if self._preview is not None and self._preview.scene() is not None:
            self.scene().removeItem(self._preview)
        self._preview = None
        self._start = None
