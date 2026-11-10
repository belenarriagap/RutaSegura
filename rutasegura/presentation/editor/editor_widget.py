"""Editor de planos con deshacer/rehacer (RF03, RNF03).

El documento es un ``FloorPlan`` inmutable: cada edición crea un plano nuevo y se registra en
un ``QUndoStack`` como «reemplazar plano anterior por nuevo». Deshacer restaura el anterior.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable
from typing import Any

import numpy as np
import numpy.typing as npt
import shiboken6
from PySide6.QtCore import QPointF, QRectF, Signal
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QUndoCommand, QUndoStack
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from rutasegura.domain.enums import ElementType
from rutasegura.domain.geometry import Point, Polygon, Segment
from rutasegura.domain.plan import Door, Exit, FloorPlan, Obstacle, SafeZone, Stair, Wall
from rutasegura.presentation.editor.scene import ElementRef, PlanScene
from rutasegura.presentation.editor.view import PlanView, Tool
from rutasegura.resources.texts import TEXTS, EditorTexts

TOOL_KIND = {
    Tool.WALL: ElementType.WALL,
    Tool.DOOR: ElementType.DOOR,
    Tool.EXIT: ElementType.EXIT,
    Tool.STAIR: ElementType.STAIR,
    Tool.OBSTACLE: ElementType.OBSTACLE,
    Tool.SAFE_ZONE: ElementType.SAFE_ZONE,
}

_FIELD = {
    ElementType.WALL: "walls",
    ElementType.DOOR: "doors",
    ElementType.EXIT: "exits",
    ElementType.STAIR: "stairs",
    ElementType.OBSTACLE: "obstacles",
    ElementType.SAFE_ZONE: "safe_zones",
}


class _ReplacePlan(QUndoCommand):
    """Comando de deshacer: cambia el plano completo."""

    def __init__(self, editor: PlanEditor, before: FloorPlan, after: FloorPlan, text: str) -> None:
        super().__init__(text)
        self._editor = editor
        self._before = before
        self._after = after

    def redo(self) -> None:
        self._editor._show(self._after)

    def undo(self) -> None:
        self._editor._show(self._before)


def next_exit_name(plan: FloorPlan, template: str) -> str:
    """Primer nombre «Salida N» que no esté usado."""
    used = {e.name for e in plan.exits}
    number = 1
    while template.format(number=number) in used:
        number += 1
    return template.format(number=number)


class PlanEditor(QWidget):
    """Editor: herramientas, capas visibles y edición con deshacer."""

    plan_changed = Signal(object)  # FloorPlan

    def __init__(self, texts: EditorTexts = TEXTS.editor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._texts = texts
        self._plan = FloorPlan()
        self.undo_stack = QUndoStack(self)
        self.scene = PlanScene(self)
        self.view = PlanView(self.scene)
        self.view.segment_drawn.connect(self._on_segment)
        self.view.area_drawn.connect(self._on_area)
        self.view.delete_requested.connect(self.delete_selected)
        self.scene.selectionChanged.connect(self._update_actions)
        self._build_ui()
        self.set_tool(Tool.SELECT)

    # ----------------------------------------------------------------- interfaz
    def _build_ui(self) -> None:
        t = self._texts
        self.toolbar = QToolBar()
        self.tool_actions: dict[Tool, QAction] = {}
        group = QActionGroup(self)
        group.setExclusive(True)
        for tool, label in (
            (Tool.SELECT, t.tool_select),
            (Tool.WALL, t.tool_wall),
            (Tool.DOOR, t.tool_door),
            (Tool.EXIT, t.tool_exit),
            (Tool.STAIR, t.tool_stair),
            (Tool.OBSTACLE, t.tool_obstacle),
            (Tool.SAFE_ZONE, t.tool_safe_zone),
        ):
            action = QAction(label, self)
            action.setCheckable(True)
            action.triggered.connect(lambda _=False, tl=tool: self.set_tool(tl))
            group.addAction(action)
            self.toolbar.addAction(action)
            self.tool_actions[tool] = action
        self.toolbar.addSeparator()
        self.delete_action = QAction(t.delete, self)
        self.delete_action.triggered.connect(self.delete_selected)
        self.confirm_action = QAction(t.confirm_exit, self)
        self.confirm_action.triggered.connect(self.confirm_selected_exits)
        self.undo_action = self.undo_stack.createUndoAction(self, t.undo)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.redo_action = self.undo_stack.createRedoAction(self, t.redo)
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        fit_action = QAction(t.fit, self)
        fit_action.triggered.connect(self.view.fit_all)
        for action in (
            self.delete_action,
            self.confirm_action,
            self.undo_action,
            self.redo_action,
            fit_action,
        ):
            self.toolbar.addAction(action)

        layers = QGroupBox(t.layers)
        layers_layout = QVBoxLayout(layers)
        self.layer_boxes: dict[ElementType | None, QCheckBox] = {}
        for kind, label in (
            (None, t.layer_background),
            (ElementType.WALL, t.layer_walls),
            (ElementType.DOOR, t.layer_doors),
            (ElementType.EXIT, t.layer_exits),
            (ElementType.STAIR, t.layer_stairs),
            (ElementType.OBSTACLE, t.layer_obstacles),
            (ElementType.SAFE_ZONE, t.layer_safe_zones),
        ):
            box = QCheckBox(label)
            box.setChecked(True)
            box.toggled.connect(lambda checked, k=kind: self.scene.set_layer_visible(k, checked))
            layers_layout.addWidget(box)
            self.layer_boxes[kind] = box
        layers_layout.addStretch(1)

        self.hint_label = QLabel()
        self.hint_label.setWordWrap(True)
        self.pending_label = QLabel()
        self.pending_label.setWordWrap(True)
        self.pending_label.setStyleSheet("color: #c0392b; font-weight: bold;")
        side = QVBoxLayout()
        side.addWidget(layers)
        side.addWidget(self.pending_label)
        side.addWidget(self.hint_label)
        side.addStretch(1)
        side_widget = QWidget()
        side_widget.setLayout(side)
        side_widget.setMaximumWidth(230)

        body = QHBoxLayout()
        body.addWidget(self.view, stretch=1)
        body.addWidget(side_widget)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.toolbar)
        root.addLayout(body)

    def set_tool(self, tool: Tool) -> None:
        """Activa una herramienta."""
        self.view.set_tool(tool)
        if tool in self.tool_actions:
            self.tool_actions[tool].setChecked(True)
        t = self._texts
        if tool is Tool.SELECT:
            hint = t.hint_select
        elif tool in (Tool.STAIR, Tool.OBSTACLE, Tool.SAFE_ZONE):
            hint = t.hint_area
        else:
            hint = t.hint_segment
        self.hint_label.setText(f"{hint}\n\n{t.hint_zoom}")

    def _update_actions(self) -> None:
        if not shiboken6.isValid(self.scene):  # la escena emite señales mientras se destruye
            return
        refs = self.scene.selected_refs()
        self.delete_action.setEnabled(bool(refs))
        self.confirm_action.setEnabled(
            any(
                kind is ElementType.EXIT and not self._plan.exits[i].confirmed
                for kind, i in refs
                if kind is ElementType.EXIT and i < len(self._plan.exits)
            )
        )

    # ----------------------------------------------------------------- documento
    def plan(self) -> FloorPlan:
        """Plano actual."""
        return self._plan

    def set_plan(self, plan: FloorPlan, image: npt.NDArray[np.uint8] | None) -> None:
        """Carga un plano nuevo (borra el historial de deshacer)."""
        self.undo_stack.clear()
        self.scene.set_image(image)
        self._show(plan)
        self.view.fit_all()

    def apply(self, new_plan: FloorPlan, text: str) -> None:
        """Aplica un cambio como paso que se puede deshacer."""
        if new_plan != self._plan:
            self.undo_stack.push(_ReplacePlan(self, self._plan, new_plan, text))

    def _show(self, plan: FloorPlan) -> None:
        self._plan = plan
        self.scene.render_plan(plan)
        pending = sum(1 for e in plan.exits if not e.confirmed)
        self.pending_label.setText(
            self._texts.pending_exits.format(count=pending) if pending else ""
        )
        self._update_actions()
        self.plan_changed.emit(plan)

    # ----------------------------------------------------------------- ediciones
    def add_segment(self, kind: ElementType, segment: Segment) -> None:
        """Agrega un muro, puerta o salida dibujados por el usuario (confianza total)."""
        plan = self._plan
        t = self._texts
        if kind is ElementType.WALL:
            new = dataclasses.replace(plan, walls=(*plan.walls, Wall(segment)))
            what = t.tool_wall
        elif kind is ElementType.DOOR:
            new = dataclasses.replace(plan, doors=(*plan.doors, Door(segment)))
            what = t.tool_door
        elif kind is ElementType.EXIT:
            name = next_exit_name(plan, t.exit_name)
            new = dataclasses.replace(plan, exits=(*plan.exits, Exit(segment, name)))
            what = t.tool_exit
        else:
            raise ValueError(f"{kind} no se dibuja como segmento.")
        self.apply(new, t.cmd_add.format(what=what.lower()))

    def add_area(self, kind: ElementType, area: Polygon) -> None:
        """Agrega una escalera, obstáculo o zona segura."""
        plan = self._plan
        t = self._texts
        if kind is ElementType.STAIR:
            new = dataclasses.replace(plan, stairs=(*plan.stairs, Stair(area)))
            what = t.tool_stair
        elif kind is ElementType.OBSTACLE:
            new = dataclasses.replace(plan, obstacles=(*plan.obstacles, Obstacle(area)))
            what = t.tool_obstacle
        elif kind is ElementType.SAFE_ZONE:
            new = dataclasses.replace(plan, safe_zones=(*plan.safe_zones, SafeZone(area)))
            what = t.tool_safe_zone
        else:
            raise ValueError(f"{kind} no se dibuja como área.")
        self.apply(new, t.cmd_add.format(what=what.lower()))

    def delete(self, refs: Iterable[ElementRef]) -> None:
        """Borra los elementos indicados."""
        to_delete: dict[ElementType, set[int]] = {}
        for kind, index in refs:
            to_delete.setdefault(kind, set()).add(index)
        if not to_delete:
            return
        changes: dict[str, Any] = {
            _FIELD[kind]: tuple(
                el for i, el in enumerate(getattr(self._plan, _FIELD[kind])) if i not in indices
            )
            for kind, indices in to_delete.items()
        }
        count = sum(len(v) for v in to_delete.values())
        self.apply(
            dataclasses.replace(self._plan, **changes), self._texts.cmd_delete.format(count=count)
        )

    def delete_selected(self) -> None:
        """Borra lo seleccionado."""
        self.delete(self.scene.selected_refs())

    def confirm_exits(self, indices: Iterable[int]) -> None:
        """Marca como confirmadas las salidas propuestas indicadas."""
        wanted = {i for i in indices if 0 <= i < len(self._plan.exits)}
        pending = {i for i in wanted if not self._plan.exits[i].confirmed}
        if not pending:
            return
        exits = tuple(
            dataclasses.replace(e, confirmed=True) if i in pending else e
            for i, e in enumerate(self._plan.exits)
        )
        self.apply(
            dataclasses.replace(self._plan, exits=exits),
            self._texts.cmd_confirm.format(count=len(pending)),
        )

    def confirm_selected_exits(self) -> None:
        """Confirma las salidas propuestas seleccionadas."""
        self.confirm_exits(i for kind, i in self.scene.selected_refs() if kind is ElementType.EXIT)

    # ----------------------------------------------------------------- señales de la vista
    def _on_segment(self, tool: Tool, start: QPointF, end: QPointF) -> None:
        kind = TOOL_KIND.get(tool)
        if kind is not None:
            self.add_segment(kind, Segment(Point(start.x(), start.y()), Point(end.x(), end.y())))

    def _on_area(self, tool: Tool, rect: QRectF) -> None:
        kind = TOOL_KIND.get(tool)
        if kind is not None:
            area = Polygon(
                (
                    Point(rect.left(), rect.top()),
                    Point(rect.right(), rect.top()),
                    Point(rect.right(), rect.bottom()),
                    Point(rect.left(), rect.bottom()),
                )
            )
            self.add_area(kind, area)
