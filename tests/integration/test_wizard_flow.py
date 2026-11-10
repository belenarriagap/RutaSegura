"""Flujo completo de los pasos 1–3 a través de la interfaz real y la base de datos."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from pytestqt.qtbot import QtBot

from rutasegura.application.errors import UserFacingError
from rutasegura.application.services import AppServices
from rutasegura.domain.enums import UseType
from rutasegura.domain.geometry import Point
from rutasegura.domain.plan import FloorPlan
from rutasegura.engines.vision.images import write_png
from rutasegura.presentation.main_window import STEP_EDIT, STEP_SCALE, MainWindow
from tests.fixtures.synthetic_plans import generate_plan


@pytest.fixture
def plan_file(tmp_path: Path) -> tuple[Path, float]:
    synthetic = generate_plan(1)
    path = tmp_path / "planos" / "colegio ñ.png"
    write_png(path, synthetic.image)
    return path, synthetic.scale_m_per_px


def test_load_scale_detect_save_and_reopen(
    qtbot: QtBot,
    services: AppServices,
    plan_file: tuple[Path, float],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, true_scale = plan_file
    window = MainWindow(services)
    qtbot.addWidget(window)
    errors: list[str] = []
    monkeypatch.setattr(window, "show_error", errors.append)
    project_id = window.create_project("I.E. Prueba", UseType.EDUCATION, "Jr. Lima 1")
    assert project_id is not None

    # Paso 1: cargar plano
    window.load_page.open_file(path)
    assert window.load_page.image is not None
    assert window.is_dirty

    # Paso 2: escala con una referencia de 10 m
    window.go_to_step(STEP_SCALE)
    px = 10.0 / true_scale
    window.scale_page.set_reference(Point(100, 100), Point(100 + px, 100))
    window.scale_page.meters_spin.setValue(10.0)
    window.scale_page.apply_scale()
    assert window.plan.scale_m_per_px == pytest.approx(true_scale)

    # Paso 3: al entrar se detecta automáticamente
    with qtbot.waitSignal(window.editor_page.detection_finished, timeout=60_000):
        window.go_to_step(STEP_EDIT)
    plan = window.editor_page.editor.plan()
    assert len(plan.walls) > 4
    assert plan.doors
    assert plan.exits
    assert plan.has_pending_proposals

    # Confirmar salidas y guardar
    window.editor_page.editor.confirm_exits(range(len(plan.exits)))
    assert window.save()
    assert not window.is_dirty
    assert errors == []

    # Reabrir en otra ventana: todo sigue ahí, con la imagen procesada
    other = MainWindow(services)
    qtbot.addWidget(other)
    other.open_project(project_id)
    reopened = other.editor_page.editor.plan()
    assert reopened.walls == window.plan.walls
    assert not reopened.has_pending_proposals
    assert reopened.scale_m_per_px == pytest.approx(true_scale)
    assert other.current_step() == STEP_EDIT
    assert other.editor_page.editor.scene.has_image


def test_loading_new_image_resets_geometry(
    qtbot: QtBot, services: AppServices, plan_file: tuple[Path, float]
) -> None:
    path, _ = plan_file
    window = MainWindow(services)
    qtbot.addWidget(window)
    window.create_project("Tienda", UseType.COMMERCE)
    window.load_page.open_file(path)
    window._plan = FloorPlan(scale_m_per_px=0.02)
    window.load_page.open_file(path)
    assert window.plan == FloorPlan()


def test_bad_file_reports_error(
    qtbot: QtBot, services: AppServices, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = MainWindow(services)
    qtbot.addWidget(window)
    errors: list[str] = []
    monkeypatch.setattr(window, "show_error", errors.append)
    window.create_project("Oficina", UseType.OFFICE)
    bad = tmp_path / "plano.dwg"
    bad.write_bytes(b"x")
    window.load_page.open_file(bad)
    assert errors
    assert "no soportado" in errors[0]


def test_scale_without_line_reports_error(
    qtbot: QtBot, services: AppServices, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = MainWindow(services)
    qtbot.addWidget(window)
    errors: list[str] = []
    monkeypatch.setattr(window, "show_error", errors.append)
    window.scale_page.apply_scale()
    assert errors == [window.scale_page._texts.scale_draw_first]


def test_project_service_errors(services: AppServices) -> None:
    with pytest.raises(UserFacingError, match="nombre"):
        services.projects.create_project("", UseType.EDUCATION)
    with pytest.raises(UserFacingError, match="ya no existe"):
        services.projects.get_project(999)
    assert services.projects.load_floor(999) is None
    assert services.projects.load_floor_image(FloorPlan(image_path="no/existe.png")) is None
    blank = np.zeros((10, 10, 3), np.uint8)
    with pytest.raises(UserFacingError, match="4 esquinas"):
        services.plans.straighten(blank, [Point(0, 0)])
