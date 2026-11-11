"""Vista del plano: zoom, desplazamiento y herramientas de dibujo."""

from __future__ import annotations

import math
from enum import Enum, auto

from PySide6.QtCore import QLineF, QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QContextMenuEvent,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QResizeEvent,
    QShowEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QGraphicsLineItem,
    QGraphicsPathItem,
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
    POLYGON = auto()  # clic en cada vértice; doble clic, Enter o clic derecho para cerrar
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
    polygon_drawn = Signal(list)  # list[QPointF] (3 o más vértices)
    delete_requested = Signal()
    context_menu_requested = Signal(QPoint, QPointF)  # (posición global, punto de la escena)
    double_clicked = Signal(QPointF)  # punto de la escena (herramienta Seleccionar)

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
        self._vertices: list[QPointF] = []
        self._fit_pending = False
        self._polygon_preview: QGraphicsPathItem | None = None
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
        """Muestra todo el plano (si la vista aún no es visible, lo hace al mostrarse)."""
        rect = self.sceneRect()
        if rect.isEmpty():
            return
        if not self.isVisible():
            self._fit_pending = True
            return
        self._fit_pending = False
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 - API de Qt
        super().showEvent(event)
        if self._fit_pending:
            self.fit_all()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 - API de Qt
        super().resizeEvent(event)
        if self._fit_pending:
            self.fit_all()

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
        if self._tool is Tool.POLYGON and event.button() == Qt.MouseButton.RightButton:
            self.finish_polygon()
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            pos = self.mapToScene(event.position().toPoint())
            if self._tool is Tool.POLYGON:
                self.add_polygon_vertex(pos)
                event.accept()
                return
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
        if self._tool is Tool.POLYGON and self._vertices:
            self._update_polygon_preview(self.mapToScene(event.position().toPoint()))
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

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._tool is Tool.POLYGON:
            self.finish_polygon()
            event.accept()
            return
        if self._tool is Tool.SELECT and event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:  # noqa: N802
        if self._tool is Tool.POLYGON or self._start is not None:
            event.accept()  # el clic derecho cierra el polígono; no hay menú
            return
        self.context_menu_requested.emit(event.globalPos(), self.mapToScene(event.pos()))
        event.accept()

    def scene_tolerance(self, pixels: float = 6.0) -> float:
        """Distancia en unidades de la escena equivalente a ``pixels`` en pantalla."""
        zoom = self.zoom_factor()
        return pixels / zoom if zoom > 0 else pixels

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if self._tool is Tool.POLYGON and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.finish_polygon()
            event.accept()
            return
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

    # ----------------------------------------------------------------- polígonos
    def add_polygon_vertex(self, point: QPointF) -> None:
        """Agrega un vértice al polígono en curso (ignora clics repetidos en el mismo lugar)."""
        if self._vertices and QLineF(self._vertices[-1], point).length() < 2:
            return
        self._vertices.append(QPointF(point))
        self._update_polygon_preview(point)

    def finish_polygon(self) -> None:
        """Cierra el polígono en curso y lo emite si tiene al menos 3 vértices."""
        vertices = list(self._vertices)
        self._cancel_drawing()
        if len(vertices) >= 3:
            self.polygon_drawn.emit(vertices)

    def _update_polygon_preview(self, cursor: QPointF) -> None:
        path = QPainterPath(self._vertices[0])
        for vertex in self._vertices[1:]:
            path.lineTo(vertex)
        path.lineTo(cursor)
        if self._polygon_preview is None:
            pen = QPen(QColor("#d35400"), 2, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            self._polygon_preview = QGraphicsPathItem()
            self._polygon_preview.setPen(pen)
            self._polygon_preview.setZValue(1000)
            self.scene().addItem(self._polygon_preview)
        self._polygon_preview.setPath(path)

    def _cancel_drawing(self) -> None:
        if self._preview is not None and self._preview.scene() is not None:
            self.scene().removeItem(self._preview)
        if self._polygon_preview is not None and self._polygon_preview.scene() is not None:
            self.scene().removeItem(self._polygon_preview)
        self._preview = None
        self._polygon_preview = None
        self._vertices = []
        self._start = None
