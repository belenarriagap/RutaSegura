"""Paso 4: ambientes y ocupantes por perfil (RF05)."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence

import numpy as np
import numpy.typing as npt
from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPen, QPolygonF
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGraphicsItem,
    QGraphicsPolygonItem,
    QGraphicsSimpleTextItem,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rutasegura.application.errors import UserFacingError
from rutasegura.application.plan_import import PlanImportService
from rutasegura.domain.enums import UseType
from rutasegura.domain.geometry import Point, Polygon
from rutasegura.domain.people import Occupancy, PersonProfile
from rutasegura.domain.plan import FloorPlan, Room
from rutasegura.domain.scenario import Scenario
from rutasegura.presentation.editor.scene import PlanScene
from rutasegura.presentation.editor.view import PlanView, Tool
from rutasegura.resources.texts import TEXTS, ProjectTexts, RoomsTexts

Image = npt.NDArray[np.uint8]
ROOM_COLOR = QColor("#2980b9")
SELECTED_COLOR = QColor("#e67e22")
COL_NAME, COL_USE, COL_AREA, FIRST_PROFILE_COL = 0, 1, 2, 3


class RoomsPage(QWidget):
    """Ambientes (polígonos con nombre y uso) y cantidad de personas por perfil."""

    plan_changed = Signal(object)  # FloorPlan
    scenario_changed = Signal(object)  # Scenario
    error = Signal(str)

    def __init__(
        self,
        plans: PlanImportService,
        texts: RoomsTexts = TEXTS.rooms,
        project_texts: ProjectTexts = TEXTS.project,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._plans = plans
        self._texts = texts
        self._use_labels = dict(project_texts.use_labels)
        self._plan = FloorPlan()
        self._scenario = Scenario("", 0)
        self._profiles: list[PersonProfile] = []
        self._default_use = UseType.EDUCATION
        self._room_items: list[QGraphicsPolygonItem] = []
        self._label_items: list[QGraphicsItem] = []
        self._updating = False

        self.scene = PlanScene(self)
        self.view = PlanView(self.scene)
        self.view.polygon_drawn.connect(self._on_polygon)
        self.detect_button = QPushButton(texts.detect)
        self.detect_button.clicked.connect(self.detect_rooms)
        self.draw_button = QPushButton(texts.draw)
        self.draw_button.setCheckable(True)
        self.draw_button.toggled.connect(
            lambda on: self.view.set_tool(Tool.POLYGON if on else Tool.NONE)
        )
        self.delete_button = QPushButton(texts.delete)
        self.delete_button.clicked.connect(self.delete_selected_room)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.total_label = QLabel()
        bold = QFont(self.total_label.font())
        bold.setBold(True)
        self.total_label.setFont(bold)
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.itemSelectionChanged.connect(self._highlight_selection)

        buttons = QHBoxLayout()
        for button in (self.detect_button, self.draw_button, self.delete_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.table, stretch=1)
        right_layout.addWidget(self.total_label)
        splitter = QSplitter()
        splitter.addWidget(self.view)
        splitter.addWidget(right)
        splitter.setSizes([600, 500])

        title = QLabel(texts.title)
        font = QFont(title.font())
        font.setPointSize(font.pointSize() + 5)
        font.setBold(True)
        title.setFont(font)
        help_label = QLabel(texts.help)
        help_label.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(help_label)
        layout.addLayout(buttons)
        layout.addWidget(self.status_label)
        layout.addWidget(splitter, stretch=1)

    # ------------------------------------------------------------------ contenido
    @property
    def plan(self) -> FloorPlan:
        """Plano con los ambientes actuales."""
        return self._plan

    @property
    def scenario(self) -> Scenario:
        """Escenario con las ocupaciones actuales."""
        return self._scenario

    def set_content(
        self,
        plan: FloorPlan,
        image: Image | None,
        scenario: Scenario,
        profiles: Sequence[PersonProfile],
        default_use: UseType,
    ) -> None:
        """Carga plano, escenario y perfiles."""
        self._plan = plan
        self._scenario = scenario
        self._profiles = list(profiles)
        self._default_use = default_use
        self.scene.set_image(image)
        self.scene.render_plan(plan)
        for kind_items in (self.scene.all_element_items(),):
            for item in kind_items:
                item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self._refresh()
        self.view.fit_all()
        self.status_label.setText("" if plan.is_scaled else self._texts.no_scale)

    # ------------------------------------------------------------------ acciones
    def detect_rooms(self) -> None:
        """Agrega automáticamente los ambientes cerrados."""
        try:
            new_plan = self._plans.detect_rooms(
                self._plan, self._default_use, self._texts.name_template
            )
        except UserFacingError as exc:
            self.error.emit(exc.message)
            return
        added = len(new_plan.rooms) - len(self._plan.rooms)
        self.status_label.setText(
            self._texts.detected.format(count=added) if added else self._texts.nothing_detected
        )
        if added:
            self._set_plan(new_plan)

    def add_room(self, polygon: Polygon, name: str | None = None) -> None:
        """Agrega un ambiente dibujado a mano."""
        used = {r.name for r in self._plan.rooms}
        if name is None:
            number = 1
            while self._texts.name_template.format(number=number) in used:
                number += 1
            name = self._texts.name_template.format(number=number)
        room = Room(name, self._default_use, polygon)
        self._set_plan(dataclasses.replace(self._plan, rooms=(*self._plan.rooms, room)))

    def delete_room(self, index: int) -> None:
        """Borra un ambiente y sus ocupantes."""
        if not 0 <= index < len(self._plan.rooms):
            return
        removed = self._plan.rooms[index]
        rooms = tuple(r for i, r in enumerate(self._plan.rooms) if i != index)
        occupancies = tuple(
            o
            for o in self._scenario.occupancies
            if not (o.room_name == removed.name and o.level == self._plan.level)
        )
        self._set_scenario(dataclasses.replace(self._scenario, occupancies=occupancies))
        self._set_plan(dataclasses.replace(self._plan, rooms=rooms))

    def delete_selected_room(self) -> None:
        """Borra el ambiente seleccionado en la tabla."""
        self.delete_room(self.table.currentRow())

    def set_occupants(self, room_name: str, profile_name: str, count: int) -> None:
        """Fija cuántas personas de un perfil hay en un ambiente."""
        level = self._plan.level
        others = [
            o
            for o in self._scenario.occupancies
            if not (
                o.room_name == room_name and o.profile_name == profile_name and o.level == level
            )
        ]
        if count > 0:
            others.append(Occupancy(room_name, profile_name, count, level))
        order = {r.name: i for i, r in enumerate(self._plan.rooms)}
        profile_order = {p.name: i for i, p in enumerate(self._profiles)}
        others.sort(
            key=lambda o: (order.get(o.room_name, 999), profile_order.get(o.profile_name, 999))
        )
        self._set_scenario(dataclasses.replace(self._scenario, occupancies=tuple(others)))
        self._sync_spin(room_name, profile_name, count)
        self._update_total()

    def _sync_spin(self, room_name: str, profile_name: str, count: int) -> None:
        """Refleja en la tabla un cambio hecho por código."""
        rows = [i for i, r in enumerate(self._plan.rooms) if r.name == room_name]
        cols = [k for k, p in enumerate(self._profiles) if p.name == profile_name]
        if not rows or not cols:
            return
        spin = self.table.cellWidget(rows[0], FIRST_PROFILE_COL + cols[0])
        if isinstance(spin, QSpinBox) and spin.value() != count:
            spin.blockSignals(True)
            spin.setValue(count)
            spin.blockSignals(False)

    def rename_room(self, index: int, new_name: str) -> None:
        """Cambia el nombre de un ambiente (y de sus ocupaciones)."""
        new_name = new_name.strip()
        old = self._plan.rooms[index]
        if not new_name or new_name == old.name:
            self._refresh()
            return
        if any(r.name == new_name for r in self._plan.rooms):
            self.error.emit(f"Ya existe un ambiente llamado «{new_name}».")
            self._refresh()
            return
        rooms = list(self._plan.rooms)
        rooms[index] = dataclasses.replace(old, name=new_name)
        occupancies = tuple(
            dataclasses.replace(o, room_name=new_name) if o.room_name == old.name else o
            for o in self._scenario.occupancies
        )
        self._set_scenario(dataclasses.replace(self._scenario, occupancies=occupancies))
        self._set_plan(dataclasses.replace(self._plan, rooms=tuple(rooms)))

    def set_room_use(self, index: int, use: UseType) -> None:
        """Cambia el uso de un ambiente."""
        rooms = list(self._plan.rooms)
        rooms[index] = dataclasses.replace(rooms[index], use=use)
        self._set_plan(dataclasses.replace(self._plan, rooms=tuple(rooms)), refresh=False)

    # ------------------------------------------------------------------ interno
    def _set_plan(self, plan: FloorPlan, *, refresh: bool = True) -> None:
        self._plan = plan
        if refresh:
            self._refresh()
        self.plan_changed.emit(plan)

    def _set_scenario(self, scenario: Scenario) -> None:
        self._scenario = scenario
        self.scenario_changed.emit(scenario)

    def _on_polygon(self, points: list[QPointF]) -> None:
        self.add_room(Polygon(tuple(Point(p.x(), p.y()) for p in points)))

    def _count(self, room: str, profile: str) -> int:
        for o in self._scenario.occupancies:
            if o.room_name == room and o.profile_name == profile and o.level == self._plan.level:
                return o.count
        return 0

    def _refresh(self) -> None:
        self._draw_rooms()
        self._updating = True
        t = self._texts
        headers = [t.column_name, t.column_use, t.column_area, *(p.name for p in self._profiles)]
        self.table.clear()
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(self._plan.rooms))
        for row, room in enumerate(self._plan.rooms):
            self.table.setItem(row, COL_NAME, QTableWidgetItem(room.name))
            combo = QComboBox()
            for value, label in self._use_labels.items():
                combo.addItem(label, value)
            combo.setCurrentIndex(max(0, combo.findData(room.use.value)))
            combo.currentIndexChanged.connect(
                lambda _i, r=row, c=combo: self.set_room_use(r, UseType(c.currentData()))
            )
            self.table.setCellWidget(row, COL_USE, combo)
            area = f"{self._plan.area_m2(room.area):.1f}" if self._plan.is_scaled else "—"
            area_item = QTableWidgetItem(area)
            area_item.setFlags(area_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, COL_AREA, area_item)
            for k, profile in enumerate(self._profiles):
                spin = QSpinBox()
                spin.setRange(0, 5000)
                spin.setValue(self._count(room.name, profile.name))
                spin.valueChanged.connect(
                    lambda value, rn=room.name, pn=profile.name: self.set_occupants(rn, pn, value)
                )
                self.table.setCellWidget(row, FIRST_PROFILE_COL + k, spin)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setMinimumSectionSize(70)
        self._updating = False
        self.delete_button.setEnabled(bool(self._plan.rooms))
        self._update_total()

    def _update_total(self) -> None:
        self.total_label.setText(self._texts.total.format(count=self._scenario.total_occupants))

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating or item.column() != COL_NAME:
            return
        self.rename_room(item.row(), item.text())

    def _draw_rooms(self) -> None:
        for item in self._room_items + self._label_items:
            self.scene.removeItem(item)
        self._room_items.clear()
        self._label_items.clear()
        for room in self._plan.rooms:
            fill = QColor(ROOM_COLOR)
            fill.setAlpha(45)
            pen = QPen(ROOM_COLOR, 2)
            pen.setCosmetic(True)
            item = QGraphicsPolygonItem(QPolygonF([QPointF(p.x, p.y) for p in room.area.vertices]))
            item.setPen(pen)
            item.setBrush(QBrush(fill))
            item.setZValue(5)
            self.scene.addItem(item)
            self._room_items.append(item)
            label = QGraphicsSimpleTextItem(room.name)
            label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            center = room.area.centroid
            label.setPos(center.x, center.y)
            label.setZValue(6)
            self.scene.addItem(label)
            self._label_items.append(label)
        self._highlight_selection()

    def _highlight_selection(self) -> None:
        selected = self.table.currentRow()
        for i, item in enumerate(self._room_items):
            color = SELECTED_COLOR if i == selected else ROOM_COLOR
            pen = QPen(color, 3 if i == selected else 2)
            pen.setCosmetic(True)
            item.setPen(pen)
