"""Paso 5: aforo por ambiente y observaciones normativas (RF06)."""

from __future__ import annotations

import dataclasses

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rutasegura.application.errors import UserFacingError
from rutasegura.application.norms_service import NormsService
from rutasegura.domain.norms import NormEvaluation
from rutasegura.domain.plan import FloorPlan
from rutasegura.domain.scenario import Scenario
from rutasegura.resources.texts import TEXTS, NormsTexts

COL_NAME, COL_CATEGORY, COL_AREA, COL_CAPACITY, COL_OCCUPANTS, COL_STATUS = range(6)
EXCEEDED_COLOR = QColor("#fadbd8")


class NormsPage(QWidget):
    """Tabla de aforo con categoría editable y lista de observaciones."""

    plan_changed = Signal(object)  # FloorPlan
    error = Signal(str)

    def __init__(
        self, norms: NormsService, texts: NormsTexts = TEXTS.norms, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._norms = norms
        self._texts = texts
        self._plan = FloorPlan()
        self._scenario: Scenario | None = None
        self.evaluation: NormEvaluation | None = None

        title = QLabel(texts.title)
        font = QFont(title.font())
        font.setPointSize(font.pointSize() + 5)
        font.setBold(True)
        title.setFont(font)
        help_label = QLabel(texts.help)
        help_label.setWordWrap(True)
        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet(
            "background: #fdebd0; border: 1px solid #e67e22; padding: 6px;"
        )
        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.total_label = QLabel()
        bold = QFont(self.total_label.font())
        bold.setBold(True)
        self.total_label.setFont(bold)
        self.observations = QListWidget()
        self.observations.setWordWrap(True)
        observations_title = QLabel(texts.observations_title)
        observations_title.setFont(bold)

        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(self.table)
        top_layout.addWidget(self.total_label)
        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addWidget(observations_title)
        bottom_layout.addWidget(self.observations)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(top)
        splitter.addWidget(bottom)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(help_label)
        layout.addWidget(self.warning_label)
        layout.addWidget(splitter, stretch=1)

    @property
    def plan(self) -> FloorPlan:
        """Plano con las categorías actuales."""
        return self._plan

    def set_content(self, plan: FloorPlan, scenario: Scenario | None) -> None:
        """Evalúa y muestra el plano con la ocupación del escenario."""
        self._plan = plan
        self._scenario = scenario
        self._refresh()

    def set_category(self, row: int, category: str) -> None:
        """Cambia la categoría de un ambiente y vuelve a evaluar."""
        rooms = list(self._plan.rooms)
        if not 0 <= row < len(rooms) or rooms[row].category == category:
            return
        rooms[row] = dataclasses.replace(rooms[row], category=category)
        self._plan = dataclasses.replace(self._plan, rooms=tuple(rooms))
        self.plan_changed.emit(self._plan)
        self._refresh()

    def _refresh(self) -> None:
        t = self._texts
        self.table.clear()
        self.observations.clear()
        self.evaluation = None
        try:
            evaluation = self._norms.evaluate(self._plan, self._scenario)
        except UserFacingError as exc:
            self.table.setRowCount(0)
            self.total_label.setText("")
            self.warning_label.setText(exc.message)
            self.warning_label.setVisible(True)
            return
        self.evaluation = evaluation
        headers = [
            t.column_name,
            t.column_category,
            t.column_area,
            t.column_capacity,
            t.column_occupants,
            t.column_status,
        ]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(evaluation.capacities))
        for row, (room, cap) in enumerate(
            zip(self._plan.rooms, evaluation.capacities, strict=True)
        ):
            combo = QComboBox()
            for category_id, label in self._norms.categories(room.use):
                combo.addItem(label, category_id)
            combo.setCurrentIndex(max(0, combo.findData(cap.category)))
            combo.currentIndexChanged.connect(
                lambda _i, r=row, c=combo: self.set_category(r, str(c.currentData()))
            )
            self.table.setCellWidget(row, COL_CATEGORY, combo)
            if cap.capacity is None:
                status = t.status_no_capacity
            else:
                status = t.status_exceeded if cap.exceeded else t.status_ok
            values = {
                COL_NAME: cap.room_name,
                COL_AREA: f"{cap.area_m2:.1f}",
                COL_CAPACITY: "—" if cap.capacity is None else str(cap.capacity),
                COL_OCCUPANTS: str(cap.occupants),
                COL_STATUS: status,
            }
            for col, text in values.items():
                item = QTableWidgetItem(text)
                if cap.exceeded:
                    item.setBackground(EXCEEDED_COLOR)
                self.table.setItem(row, col, item)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.total_label.setText(
            t.total.format(capacity=evaluation.total_capacity, occupants=evaluation.total_occupants)
        )
        unverified = len(evaluation.unverified_rules)
        self.warning_label.setText(t.unverified_warning.format(count=unverified))
        self.warning_label.setVisible(unverified > 0)
        if not evaluation.observations:
            self.observations.addItem(t.no_observations)
        for i, obs in enumerate(evaluation.observations, start=1):
            citation = f"{obs.norm}, {obs.article}" + ("" if obs.verified else t.unverified_tag)
            entry = QListWidgetItem(
                f"{i}. " + t.observation.format(description=obs.description, citation=citation)
            )
            entry.setToolTip(obs.recommendation)
            self.observations.addItem(entry)
