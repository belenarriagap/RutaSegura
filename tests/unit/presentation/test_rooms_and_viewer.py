"""Paso 4 (ambientes y ocupantes) y visor de simulación."""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QSpinBox
from pytestqt.qtbot import QtBot

from rutasegura.application.plan_import import PlanImportService
from rutasegura.domain.enums import UseType
from rutasegura.domain.people import Occupancy, PersonProfile
from rutasegura.domain.scenario import Scenario
from rutasegura.presentation.editor.view import Tool
from rutasegura.presentation.rooms_page import FIRST_PROFILE_COL, RoomsPage
from rutasegura.presentation.simulation_viewer import (
    SPEEDS,
    SimulationViewer,
    format_time,
    heatmap_rgba,
)
from tests.fixtures.simple_plans import SCALE, two_rooms
from tests.unit.engines.simulation.helpers import make_simulation

PROFILES = [PersonProfile("adulto", 1.3, 5, 2, 0.25), PersonProfile("niño", 1.0, 3, 1, 0.2)]


@pytest.fixture
def page(qtbot: QtBot) -> RoomsPage:
    widget = RoomsPage(PlanImportService())
    qtbot.addWidget(widget)
    plan = dataclasses.replace(two_rooms(), rooms=())
    widget.set_content(plan, None, Scenario("Base", 1), PROFILES, UseType.EDUCATION)
    return widget


class TestRoomsPage:
    def test_detect_and_assign_occupants(self, page: RoomsPage, qtbot: QtBot) -> None:
        with qtbot.waitSignal(page.plan_changed):
            page.detect_rooms()
        assert [r.name for r in page.plan.rooms] == ["Ambiente 1", "Ambiente 2"]
        assert page.table.rowCount() == 2
        area_item = page.table.item(0, 2)
        assert area_item is not None
        assert float(area_item.text()) == pytest.approx(36.0, rel=0.1)
        spin = page.table.cellWidget(0, FIRST_PROFILE_COL + 1)
        assert isinstance(spin, QSpinBox)
        with qtbot.waitSignal(page.scenario_changed):
            spin.setValue(25)
        assert page.scenario.occupancies == (Occupancy("Ambiente 1", "niño", 25),)
        assert "25" in page.total_label.text()
        # detectar otra vez no duplica
        page.detect_rooms()
        assert len(page.plan.rooms) == 2

    def test_rename_updates_occupancies(self, page: RoomsPage) -> None:
        page.detect_rooms()
        page.set_occupants("Ambiente 1", "adulto", 3)
        name_item = page.table.item(0, 0)
        assert name_item is not None
        name_item.setText("Aula 1A")
        assert page.plan.rooms[0].name == "Aula 1A"
        assert page.scenario.occupancies == (Occupancy("Aula 1A", "adulto", 3),)

    def test_duplicate_name_is_rejected(self, page: RoomsPage, qtbot: QtBot) -> None:
        page.detect_rooms()
        with qtbot.waitSignal(page.error) as blocker:
            page.rename_room(1, "Ambiente 1")
        assert "Ya existe" in blocker.args[0]
        assert page.plan.rooms[1].name == "Ambiente 2"

    def test_delete_room_removes_its_occupants(self, page: RoomsPage) -> None:
        page.detect_rooms()
        page.set_occupants("Ambiente 1", "adulto", 3)
        page.set_occupants("Ambiente 2", "niño", 4)
        page.table.selectRow(0)
        page.delete_selected_room()
        assert [r.name for r in page.plan.rooms] == ["Ambiente 2"]
        assert page.scenario.occupancies == (Occupancy("Ambiente 2", "niño", 4),)

    def test_draw_room_with_polygon_tool(self, page: RoomsPage) -> None:
        page.draw_button.setChecked(True)
        assert page.view.tool is Tool.POLYGON
        for x, y in ((0, 0), (100, 0), (100, 100)):
            page.view.add_polygon_vertex(QPointF(x, y))
        page.view.add_polygon_vertex(QPointF(100, 100.5))  # clic repetido: se ignora
        page.view.finish_polygon()
        assert len(page.plan.rooms) == 1
        assert len(page.plan.rooms[0].area.vertices) == 3
        assert page.plan.rooms[0].use is UseType.EDUCATION
        # menos de 3 vértices no crea nada
        page.view.add_polygon_vertex(QPointF(0, 0))
        page.view.finish_polygon()
        assert len(page.plan.rooms) == 1

    def test_change_use(self, page: RoomsPage) -> None:
        page.detect_rooms()
        page.set_room_use(0, UseType.OFFICE)
        assert page.plan.rooms[0].use is UseType.OFFICE


class TestViewer:
    @pytest.fixture
    def viewer(self, qtbot: QtBot) -> SimulationViewer:
        out = make_simulation(two_rooms(), [Occupancy("Aula 1", "adulto", 15)]).run()
        widget = SimulationViewer()
        qtbot.addWidget(widget)
        widget.set_plan(two_rooms(), np.full((300, 600, 3), 255, np.uint8))
        widget.set_run(out.trajectories, out.result, SCALE)
        return widget

    def test_timeline_and_interpolation(self, viewer: SimulationViewer) -> None:
        assert viewer.end_time > 0
        assert viewer.agents.visible_count == 15
        viewer.set_time(viewer.end_time)
        assert viewer.agents.visible_count == 0
        assert viewer.slider.value() == 1000
        viewer.set_time(-5)
        assert viewer.current_time == 0
        assert "0 de 15" in viewer.evacuated_label.text()

    def test_play_pause_and_speed(self, viewer: SimulationViewer) -> None:
        viewer.play()
        assert viewer.is_playing
        viewer.set_speed(100)
        assert viewer.speed == SPEEDS[-1]
        viewer.set_speed(0.1)
        assert viewer.speed == SPEEDS[0]
        viewer.set_speed(4.0)
        viewer.advance(1.0)
        assert viewer.current_time == pytest.approx(4.0)
        viewer.advance(10_000)
        assert not viewer.is_playing
        assert viewer.current_time == viewer.end_time
        viewer.play()  # al terminar, reproducir vuelve al inicio
        assert viewer.current_time == 0.0
        viewer.toggle_play()
        assert not viewer.is_playing

    def test_heatmap_toggle(self, viewer: SimulationViewer) -> None:
        assert not viewer.heatmap.isVisible()
        viewer.heatmap_check.setChecked(True)
        assert viewer.heatmap.isVisible()

    def test_clear(self, viewer: SimulationViewer) -> None:
        viewer.set_run(None, None, 1.0)
        assert not viewer.play_button.isEnabled()
        assert viewer.end_time == 0.0


def test_heatmap_colors_and_time_format() -> None:
    density = np.array([[0.0, 1.0], [5.0, 10.0]])
    rgba = heatmap_rgba(density)
    assert rgba.shape == (2, 2, 4)
    assert rgba[0, 0, 3] == 0  # sin gente: transparente
    assert rgba[1, 1, 3] > rgba[0, 1, 3]  # más densidad: más opaco
    assert heatmap_rgba(np.zeros((2, 2)))[..., 3].max() == 0
    assert format_time(155.4) == "2:35"
    assert format_time(-3) == "0:00"
