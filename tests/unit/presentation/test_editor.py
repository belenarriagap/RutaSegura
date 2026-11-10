"""Editor de planos: herramientas, deshacer/rehacer, capas y confirmación de salidas."""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from rutasegura.domain.enums import ElementType
from rutasegura.domain.geometry import Point, Polygon, Segment
from rutasegura.domain.plan import Exit, FloorPlan, Wall
from rutasegura.presentation.editor.editor_widget import PlanEditor, next_exit_name
from rutasegura.presentation.editor.view import PlanView, Tool, snap_to_angle


def _seg(x1: float, y1: float, x2: float, y2: float) -> Segment:
    return Segment(Point(x1, y1), Point(x2, y2))


def _square(x: float, y: float, s: float) -> Polygon:
    return Polygon((Point(x, y), Point(x + s, y), Point(x + s, y + s), Point(x, y + s)))


@pytest.fixture
def editor(qtbot: QtBot) -> PlanEditor:
    widget = PlanEditor()
    qtbot.addWidget(widget)
    widget.resize(900, 600)
    widget.set_plan(FloorPlan(), np.full((400, 600, 3), 255, np.uint8))
    return widget


def _send(view: PlanView, kind: QEvent.Type, pos: QPoint, buttons: Qt.MouseButton) -> None:
    button = Qt.MouseButton.LeftButton if kind != QEvent.Type.MouseMove else Qt.MouseButton.NoButton
    event = QMouseEvent(
        kind,
        QPointF(pos),
        QPointF(view.viewport().mapToGlobal(pos)),
        button,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(view.viewport(), event)


def _drag(view: PlanView, start: QPoint, end: QPoint) -> None:
    left = Qt.MouseButton.LeftButton
    _send(view, QEvent.Type.MouseButtonPress, start, left)
    _send(view, QEvent.Type.MouseMove, end, left)
    _send(view, QEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton)


class TestEditing:
    def test_add_undo_redo(self, editor: PlanEditor) -> None:
        editor.add_segment(ElementType.WALL, _seg(0, 0, 100, 0))
        editor.add_segment(ElementType.DOOR, _seg(20, 0, 60, 0))
        assert len(editor.plan().walls) == 1
        assert len(editor.plan().doors) == 1
        editor.undo_stack.undo()
        assert editor.plan().doors == ()
        editor.undo_stack.undo()
        assert editor.plan().walls == ()
        editor.undo_stack.redo()
        assert editor.plan().walls == (Wall(_seg(0, 0, 100, 0)),)
        assert editor.undo_stack.undoText() == "Agregar muro"

    def test_areas_and_delete(self, editor: PlanEditor) -> None:
        editor.add_area(ElementType.STAIR, _square(0, 0, 10))
        editor.add_area(ElementType.OBSTACLE, _square(20, 20, 5))
        editor.add_area(ElementType.SAFE_ZONE, _square(50, 50, 30))
        editor.add_segment(ElementType.WALL, _seg(0, 0, 1, 1))
        assert len(editor.scene.all_element_items()) == 4
        editor.delete([(ElementType.OBSTACLE, 0), (ElementType.WALL, 0)])
        plan = editor.plan()
        assert (len(plan.stairs), len(plan.obstacles), len(plan.safe_zones), len(plan.walls)) == (
            1,
            0,
            1,
            0,
        )
        editor.undo_stack.undo()
        assert len(editor.plan().obstacles) == 1

    def test_delete_selected_items(self, editor: PlanEditor) -> None:
        editor.add_segment(ElementType.WALL, _seg(0, 0, 100, 0))
        editor.add_segment(ElementType.WALL, _seg(0, 50, 100, 50))
        editor.scene.items_of(ElementType.WALL)[1].setSelected(True)
        assert editor.delete_action.isEnabled()
        editor.delete_selected()
        assert editor.plan().walls == (Wall(_seg(0, 0, 100, 0)),)

    def test_exit_names_are_unique(self, editor: PlanEditor) -> None:
        editor.add_segment(ElementType.EXIT, _seg(0, 0, 50, 0))
        editor.add_segment(ElementType.EXIT, _seg(0, 100, 50, 100))
        assert [e.name for e in editor.plan().exits] == ["Salida 1", "Salida 2"]
        plan = FloorPlan(exits=(Exit(_seg(0, 0, 1, 0), "Salida 2"),))
        assert next_exit_name(plan, "Salida {number}") == "Salida 1"

    def test_confirm_proposed_exits(self, editor: PlanEditor) -> None:
        proposed = FloorPlan(
            exits=(
                Exit(_seg(0, 0, 50, 0), "Salida 1", confirmed=False),
                Exit(_seg(0, 90, 50, 90), "Salida 2", confirmed=False),
            )
        )
        editor.set_plan(proposed, None)
        assert "2 salida(s)" in editor.pending_label.text()
        editor.scene.items_of(ElementType.EXIT)[0].setSelected(True)
        assert editor.confirm_action.isEnabled()
        editor.confirm_selected_exits()
        assert [e.confirmed for e in editor.plan().exits] == [True, False]
        assert "1 salida(s)" in editor.pending_label.text()
        editor.undo_stack.undo()
        assert [e.confirmed for e in editor.plan().exits] == [False, False]

    def test_set_plan_clears_history(self, editor: PlanEditor) -> None:
        editor.add_segment(ElementType.WALL, _seg(0, 0, 10, 0))
        editor.set_plan(FloorPlan(), None)
        assert not editor.undo_stack.canUndo()

    def test_plan_changed_signal(self, editor: PlanEditor, qtbot: QtBot) -> None:
        with qtbot.waitSignal(editor.plan_changed) as blocker:
            editor.add_segment(ElementType.WALL, _seg(0, 0, 10, 0))
        assert isinstance(blocker.args[0], FloorPlan)


class TestLayersAndView:
    def test_layer_visibility(self, editor: PlanEditor) -> None:
        editor.add_segment(ElementType.WALL, _seg(0, 0, 100, 0))
        editor.add_segment(ElementType.DOOR, _seg(10, 0, 50, 0))
        editor.layer_boxes[ElementType.WALL].setChecked(False)
        assert not editor.scene.items_of(ElementType.WALL)[0].isVisible()
        assert editor.scene.items_of(ElementType.DOOR)[0].isVisible()
        # al redibujar (nueva edición) la capa sigue oculta
        editor.add_segment(ElementType.WALL, _seg(0, 10, 100, 10))
        assert not any(i.isVisible() for i in editor.scene.items_of(ElementType.WALL))
        editor.layer_boxes[None].setChecked(False)
        assert not editor.scene.is_layer_visible(None)

    def test_low_confidence_items_are_dashed(self, editor: PlanEditor) -> None:
        editor.set_plan(FloorPlan(walls=(Wall(_seg(0, 0, 9, 0), confidence=0.3),)), None)
        item = editor.scene.items_of(ElementType.WALL)[0]
        assert item.pen().style() == Qt.PenStyle.DashLine  # type: ignore[attr-defined]

    def test_drawing_with_the_mouse(self, editor: PlanEditor, qtbot: QtBot) -> None:
        editor.show()
        qtbot.waitExposed(editor)
        editor.set_tool(Tool.WALL)
        _drag(editor.view, QPoint(100, 100), QPoint(300, 100))
        assert len(editor.plan().walls) == 1
        wall = editor.plan().walls[0].segment
        assert wall.length > 50
        editor.set_tool(Tool.OBSTACLE)
        _drag(editor.view, QPoint(120, 150), QPoint(200, 230))
        assert len(editor.plan().obstacles) == 1
        editor.undo_action.trigger()
        assert editor.plan().obstacles == ()

    def test_tiny_drags_are_ignored(self, editor: PlanEditor, qtbot: QtBot) -> None:
        editor.show()
        qtbot.waitExposed(editor)
        editor.set_tool(Tool.DOOR)
        _drag(editor.view, QPoint(100, 100), QPoint(100, 100))
        assert editor.plan().doors == ()

    def test_zoom_limits(self, editor: PlanEditor) -> None:
        for _ in range(100):
            editor.view.zoom_by(2.0)
        assert editor.view.zoom_factor() == pytest.approx(40.0)
        for _ in range(100):
            editor.view.zoom_by(0.5)
        assert editor.view.zoom_factor() == pytest.approx(0.02)

    def test_snap_to_angle(self) -> None:
        end = snap_to_angle(QPointF(0, 0), QPointF(100, 7))
        assert end.y() == pytest.approx(0, abs=1e-9)
        assert end.x() == pytest.approx(100.24, abs=0.01)
        diag = snap_to_angle(QPointF(0, 0), QPointF(50, 46))
        assert diag.x() == pytest.approx(diag.y())
