"""Escena del plano: imagen de fondo y elementos dibujados por capas."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
from PySide6.QtCore import QObject, QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPen, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPixmapItem,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
)

from rutasegura.domain.enums import ElementType
from rutasegura.domain.geometry import Polygon, Segment
from rutasegura.domain.plan import FloorPlan
from rutasegura.presentation.qt_support import to_pixmap

KIND_KEY = 0
INDEX_KEY = 1
LOW_CONFIDENCE = 0.7

WALL_COLOR = QColor("#1f3a93")
LOW_CONF_COLOR = QColor("#e67e22")
DOOR_COLOR = QColor("#27ae60")
EXIT_COLOR = QColor("#c0392b")
STAIR_COLOR = QColor("#8e44ad")
OBSTACLE_COLOR = QColor("#7f8c8d")
SAFE_ZONE_COLOR = QColor("#2ecc71")

ElementRef = tuple[ElementType, int]


def _pen(color: QColor, width: float, dashed: bool = False) -> QPen:
    pen = QPen(color, width)
    pen.setCosmetic(True)  # mismo grosor en pantalla con cualquier zoom
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    if dashed:
        pen.setStyle(Qt.PenStyle.DashLine)
    return pen


def _qpolygon(polygon: Polygon) -> QPolygonF:
    return QPolygonF([QPointF(p.x, p.y) for p in polygon.vertices])


class PlanScene(QGraphicsScene):
    """Dibuja un ``FloorPlan``. Cada elemento guarda su tipo e índice para editarlo."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._background: QGraphicsPixmapItem | None = None
        self._items: dict[ElementType, list[QGraphicsItem]] = {k: [] for k in ElementType}
        self._labels: list[QGraphicsItem] = []
        self._visible: dict[ElementType | None, bool] = {k: True for k in ElementType}
        self._visible[None] = True  # None = fondo

    # ----------------------------------------------------------------- fondo
    def set_image(self, image: npt.NDArray[np.uint8] | None) -> None:
        """Pone (o quita) la imagen del plano como fondo."""
        if self._background is not None:
            self.removeItem(self._background)
            self._background = None
        if image is not None:
            self._background = self.addPixmap(to_pixmap(image))
            self._background.setZValue(-100)
            self._background.setVisible(self._visible[None])
            self.setSceneRect(self._background.boundingRect())

    @property
    def has_image(self) -> bool:
        """Indica si hay imagen de fondo."""
        return self._background is not None

    # ----------------------------------------------------------------- elementos
    def render_plan(self, plan: FloorPlan) -> None:
        """Vuelve a dibujar todos los elementos del plano."""
        selected = {self.ref(item) for item in self.selectedItems()}
        for items in self._items.values():
            for item in items:
                self.removeItem(item)
            items.clear()
        for label in self._labels:
            self.removeItem(label)
        self._labels.clear()

        for i, wall in enumerate(plan.walls):
            low = wall.confidence < LOW_CONFIDENCE
            pen = _pen(LOW_CONF_COLOR if low else WALL_COLOR, 4, dashed=low)
            self._add_line(ElementType.WALL, i, wall.segment, pen, z=1)
        for i, door in enumerate(plan.doors):
            low = door.confidence < LOW_CONFIDENCE
            pen = _pen(LOW_CONF_COLOR if low else DOOR_COLOR, 6, dashed=low)
            self._add_line(ElementType.DOOR, i, door.segment, pen, z=2)
        for i, exit_ in enumerate(plan.exits):
            pen = _pen(EXIT_COLOR, 7, dashed=not exit_.confirmed)
            self._add_line(ElementType.EXIT, i, exit_.segment, pen, z=3)
            label = QGraphicsSimpleTextItem(exit_.name + ("" if exit_.confirmed else " ?"))
            label.setBrush(QBrush(EXIT_COLOR))
            label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            mid = exit_.segment.midpoint
            label.setPos(mid.x + 6, mid.y + 6)
            label.setZValue(4)
            label.setVisible(self._visible[ElementType.EXIT])
            self.addItem(label)
            self._labels.append(label)
        for i, stair in enumerate(plan.stairs):
            brush = QBrush(STAIR_COLOR, Qt.BrushStyle.BDiagPattern)
            pen = _pen(STAIR_COLOR, 2, dashed=not stair.confirmed)
            self._add_polygon(ElementType.STAIR, i, stair.area, pen, brush)
        for i, obstacle in enumerate(plan.obstacles):
            color = QColor(OBSTACLE_COLOR)
            color.setAlpha(140)
            self._add_polygon(
                ElementType.OBSTACLE, i, obstacle.area, _pen(OBSTACLE_COLOR, 2), QBrush(color)
            )
        for i, zone in enumerate(plan.safe_zones):
            color = QColor(SAFE_ZONE_COLOR)
            color.setAlpha(70)
            self._add_polygon(
                ElementType.SAFE_ZONE, i, zone.area, _pen(SAFE_ZONE_COLOR, 2), QBrush(color)
            )
        for item in self.all_element_items():
            if self.ref(item) in selected:
                item.setSelected(True)

    def _tag(self, item: QGraphicsItem, kind: ElementType, index: int, z: float) -> None:
        item.setData(KIND_KEY, kind.value)
        item.setData(INDEX_KEY, index)
        item.setZValue(z)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        item.setVisible(self._visible[kind])
        self.addItem(item)
        self._items[kind].append(item)

    def _add_line(self, kind: ElementType, index: int, seg: Segment, pen: QPen, z: float) -> None:
        item = QGraphicsLineItem(seg.start.x, seg.start.y, seg.end.x, seg.end.y)
        item.setPen(pen)
        self._tag(item, kind, index, z)

    def _add_polygon(
        self, kind: ElementType, index: int, polygon: Polygon, pen: QPen, brush: QBrush
    ) -> None:
        item = QGraphicsPolygonItem(_qpolygon(polygon))
        item.setPen(pen)
        item.setBrush(brush)
        self._tag(item, kind, index, z=0)

    # ----------------------------------------------------------------- consultas y capas
    @staticmethod
    def ref(item: QGraphicsItem) -> ElementRef | None:
        """(tipo, índice) del elemento que representa ``item``, o ``None``."""
        kind = item.data(KIND_KEY)
        index = item.data(INDEX_KEY)
        if kind is None or index is None:
            return None
        return ElementType(kind), int(index)

    def items_of(self, kind: ElementType) -> list[QGraphicsItem]:
        """Ítems gráficos de un tipo de elemento."""
        return list(self._items[kind])

    def all_element_items(self) -> list[QGraphicsItem]:
        """Todos los ítems de elementos (sin fondo ni etiquetas)."""
        return [item for items in self._items.values() for item in items]

    def selected_refs(self) -> list[ElementRef]:
        """Elementos seleccionados."""
        refs = (self.ref(item) for item in self.selectedItems())
        return [r for r in refs if r is not None]

    def set_layer_visible(self, kind: ElementType | None, visible: bool) -> None:
        """Muestra u oculta una capa (``None`` = imagen de fondo)."""
        self._visible[kind] = visible
        if kind is None:
            if self._background is not None:
                self._background.setVisible(visible)
            return
        for item in self._items[kind]:
            item.setVisible(visible)
            if not visible:
                item.setSelected(False)
        if kind is ElementType.EXIT:
            for label in self._labels:
                label.setVisible(visible)

    def is_layer_visible(self, kind: ElementType | None) -> bool:
        """Estado de una capa."""
        return self._visible[kind]
