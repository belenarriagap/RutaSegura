"""Interfaz amigable: tema, franjas de mensaje, guía de pasos, tarjetas y proyectos recientes."""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication, QPushButton
from pytestqt.qtbot import QtBot

from rutasegura.application.progress import StepState
from rutasegura.application.services import AppServices
from rutasegura.domain.enums import ElementType, UseType
from rutasegura.domain.geometry import Point, Segment
from rutasegura.domain.plan import Exit, FloorPlan, SafeZone
from rutasegura.presentation.editor.editor_widget import PlanEditor
from rutasegura.presentation.icons import element_icon, select_icon, step_icon
from rutasegura.presentation.main_window import STEP_EDIT, STEP_LOAD, STEP_SCALE, MainWindow
from rutasegura.presentation.theme import PRIMARY, STYLESHEET, apply_theme, set_primary
from rutasegura.presentation.widgets import Banner, MetricCard
from rutasegura.resources.texts import TEXTS
from tests.fixtures.simple_plans import rect


def _seg(x1: float, y1: float, x2: float, y2: float) -> Segment:
    return Segment(Point(x1, y1), Point(x2, y2))


class TestThemeAndWidgets:
    def test_theme_applies(self, qtbot: QtBot) -> None:
        app = QApplication.instance()
        assert isinstance(app, QApplication)
        sheet, font, palette, style = (
            app.styleSheet(),
            app.font(),
            app.palette(),
            app.style().name(),
        )
        try:
            apply_theme(app)
            assert app.styleSheet() == STYLESHEET
            assert app.palette().color(app.palette().ColorRole.Highlight).name() == PRIMARY
        finally:  # no afecta a las demás pruebas
            app.setStyleSheet(sheet)
            app.setFont(font)
            app.setPalette(palette)
            app.setStyle(style)
        button = set_primary(QPushButton("Simular"))
        qtbot.addWidget(button)
        assert button.property("primary") is True

    def test_icons_are_drawn(self, qtbot: QtBot) -> None:
        for kind in (None, *ElementType):
            assert not element_icon(kind).isNull()
        assert not select_icon().isNull()
        for state in StepState:
            assert not step_icon(state, 3).isNull()

    def test_banner(self, qtbot: QtBot) -> None:
        banner = Banner()
        qtbot.addWidget(banner)
        assert banner.isHidden()
        clicks: list[int] = []
        banner.show_message(
            "Falta la escala", "warning", action_text="Ir", action=lambda: clicks.append(1)
        )
        assert not banner.isHidden()
        assert banner.kind == "warning"
        assert banner.text == "Falta la escala"
        banner.action_button.click()
        assert clicks == [1]
        with qtbot.waitSignal(banner.closed):
            banner.close_button.click()
        assert banner.isHidden()
        with pytest.raises(ValueError, match="desconocido"):
            banner.show_message("x", "rosado")

    def test_banner_hides_itself(self, qtbot: QtBot) -> None:
        banner = Banner()
        qtbot.addWidget(banner)
        banner.show_message("Guardado", "success", timeout_ms=10)
        qtbot.waitUntil(banner.isHidden, timeout=2000)

    def test_metric_card(self, qtbot: QtBot) -> None:
        card = MetricCard("Tiempo total")
        qtbot.addWidget(card)
        card.set_value("1 min 30 s", "Salieron todos", "success")
        assert card.value_label.text() == "1 min 30 s"
        assert card.kind == "success"
        assert not card.note_label.isHidden()


class TestEditorExtras:
    @pytest.fixture
    def editor(self, qtbot: QtBot) -> PlanEditor:
        widget = PlanEditor()
        qtbot.addWidget(widget)
        widget.resize(900, 600)
        widget.set_plan(FloorPlan(), np.full((400, 600, 3), 255, np.uint8))
        return widget

    def test_tools_have_icons_shortcuts_and_tips(self, editor: PlanEditor) -> None:
        for action in editor.tool_actions.values():
            assert not action.icon().isNull()
            assert not action.shortcut().isEmpty()
            assert "Atajo:" in action.toolTip()

    def test_rename_with_undo_and_validation(self, editor: PlanEditor) -> None:
        editor.add_segment(ElementType.EXIT, _seg(0, 0, 50, 0))
        editor.add_segment(ElementType.EXIT, _seg(0, 100, 50, 100))
        errors: list[str] = []
        editor.error.connect(errors.append)
        assert editor.rename((ElementType.EXIT, 0), "Puerta principal")
        assert editor.plan().exits[0].name == "Puerta principal"
        assert not editor.rename((ElementType.EXIT, 1), "Puerta principal")
        assert not editor.rename((ElementType.EXIT, 1), "   ")
        assert len(errors) == 2
        assert not editor.rename((ElementType.WALL, 0), "Muro")  # los muros no tienen nombre
        editor.undo_stack.undo()
        assert editor.plan().exits[0].name == "Salida 1"
        editor.add_area(ElementType.SAFE_ZONE, rect(1, 1, 2, 2))
        assert editor.rename((ElementType.SAFE_ZONE, 0), "Patio")
        assert editor.plan().safe_zones[0] == SafeZone(rect(1, 1, 2, 2), "Patio")

    def test_context_menu_actions(self, editor: PlanEditor) -> None:
        proposed = FloorPlan(exits=(Exit(_seg(0, 0, 50, 0), "Salida 1", confirmed=False),))
        editor.set_plan(proposed, None)
        menu = editor.context_menu((ElementType.EXIT, 0))
        labels = [a.text() for a in menu.actions() if not a.isSeparator()]
        t = TEXTS.editor
        assert labels == [t.menu_confirm, t.menu_rename, t.menu_delete]
        menu.actions()[0].trigger()
        assert editor.plan().exits[0].confirmed
        menu = editor.context_menu((ElementType.EXIT, 0))
        assert t.menu_confirm not in [a.text() for a in menu.actions()]
        next(a for a in menu.actions() if a.text() == t.menu_delete).trigger()
        assert editor.plan().exits == ()

    def test_double_click_confirms_a_proposed_exit(self, editor: PlanEditor, qtbot: QtBot) -> None:
        editor.show()
        qtbot.waitExposed(editor)
        proposed = FloorPlan(exits=(Exit(_seg(100, 100, 300, 100), "Salida 1", confirmed=False),))
        editor.set_plan(proposed, np.full((400, 600, 3), 255, np.uint8))
        editor.view.fit_all()
        on_exit, empty = QPointF(200, 101), QPointF(50, 300)  # 1 px al costado: hay tolerancia
        assert editor.scene.ref_at(on_exit, editor.view.scene_tolerance()) == (ElementType.EXIT, 0)
        editor.view.double_clicked.emit(on_exit)
        assert editor.plan().exits[0].confirmed
        before = editor.plan()
        editor.view.double_clicked.emit(empty)  # en un lugar vacío no pasa nada
        assert editor.plan() == before


class TestGuide:
    def test_welcome_lists_projects(self, qtbot: QtBot, services: AppServices) -> None:
        window = MainWindow(services)
        qtbot.addWidget(window)
        assert window.recent_list.isHidden()
        assert not window.recent_empty.isHidden()
        project_id = services.projects.create_project("Colegio Los Pinos", UseType.EDUCATION)
        window.refresh_recent_projects()
        assert window.recent_list.count() == 1
        item = window.recent_list.item(0)
        assert "Colegio Los Pinos" in item.text()
        window._on_recent_activated(item)
        assert window.project_id == project_id

    def test_guide_tells_what_is_missing(self, qtbot: QtBot, services: AppServices) -> None:
        window = MainWindow(services)
        qtbot.addWidget(window)
        window.create_project("Tienda", UseType.COMMERCE)
        g = TEXTS.guide
        # paso 1: falta la imagen
        assert window.current_step() == STEP_LOAD
        assert not window.guide_banner.isHidden()
        assert g.issue_text("sin_imagen") in window.guide_banner.text
        assert not window.prev_button.isEnabled()
        # paso 3 sin imagen: avisa que falta el paso 1 y ofrece ir
        window.go_to_step(STEP_EDIT)
        assert window.guide_banner.kind == "warning"
        assert "paso 1" in window.guide_banner.text
        window.guide_banner.action_button.click()
        assert window.current_step() == STEP_LOAD
        # Siguiente y Anterior
        window.next_button.click()
        assert window.current_step() == STEP_SCALE
        assert TEXTS.wizard_steps[STEP_SCALE] in window.nav_label.text()
        window.prev_button.click()
        assert window.current_step() == STEP_LOAD

    def test_errors_show_in_a_banner(self, qtbot: QtBot, services: AppServices) -> None:
        window = MainWindow(services)
        qtbot.addWidget(window)
        window.create_project("Oficina", UseType.OFFICE)
        window.show_error("No se pudo leer el archivo.")
        assert window.message_banner.kind == "error"
        assert window.message_banner.text == "No se pudo leer el archivo."
        window.go_to_step(STEP_SCALE)  # al cambiar de paso se limpia
        assert window.message_banner.isHidden()
