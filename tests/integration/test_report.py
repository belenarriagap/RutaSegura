"""Servicio de normas e informe PDF (RF06, RF09) de punta a punta."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import pymupdf
import pytest

from rutasegura.application.errors import UserFacingError
from rutasegura.application.services import AppServices
from rutasegura.domain.enums import ObservationType, UseType
from rutasegura.domain.people import Occupancy
from rutasegura.resources.texts import TEXTS
from tests.fixtures.simple_plans import two_rooms


def _pdf_text(path: Path) -> tuple[str, int]:
    with pymupdf.open(path) as doc:
        text = "\n".join(page.get_text() for page in doc)
        images = sum(len(page.get_images()) for page in doc)
    return " ".join(text.split()), images


@pytest.fixture
def project(services: AppServices) -> int:
    project_id = services.projects.create_project(
        "I.E. N.º 123 «San Martín»", UseType.EDUCATION, "Jr. Lima 456"
    )
    image = np.full((320, 640, 3), 245, np.uint8)
    services.projects.save_floor(project_id, two_rooms(), image)
    return project_id


def _scenario(services: AppServices, project_id: int, children: int):  # type: ignore[no-untyped-def]
    return dataclasses.replace(
        services.simulations.load_scenario(project_id),
        occupancies=(Occupancy("Aula 1", "niño", children), Occupancy("Aula 2", "adulto", 10)),
    )


def test_report_with_simulation(services: AppServices, project: int, tmp_path: Path) -> None:
    scenario = _scenario(services, project, 60)  # 60 niños en 36 m²: excede el aforo (24)
    plan = services.projects.load_floor(project)
    assert plan is not None
    run = services.simulations.run(project, plan, scenario)
    assert all(o.kind is ObservationType.CONGESTION for o in run.observations)
    with services.database.unit_of_work() as uow:
        stored = uow.simulations.observations(run.simulation_id)
    assert any(o.kind is ObservationType.NORM and "aforo es 24" in o.description for o in stored)

    path = services.reports.generate(project, tmp_path / "informes" / "informe")
    assert path.suffix == ".pdf"
    text, images = _pdf_text(path)
    assert "Informe de evacuación ante sismo" in text
    assert "I.E. N.º 123 «San Martín»" in text
    assert "Tiempo total estimado de evacuación" in text
    assert "«Aula 1» tiene 60 personas asignadas y su aforo es 24" in text
    assert "RNE A.040" in text
    assert "regla no verificada" in text
    assert "Advertencia" in text
    assert "Semilla: 2026" in text
    assert "(provisional)" in text
    assert " ".join(TEXTS.legal_disclaimer.split()) in text
    assert images >= 2  # mapa de calor y curva


def test_report_without_simulation(services: AppServices, project: int, tmp_path: Path) -> None:
    services.simulations.save_scenario(project, _scenario(services, project, 10))
    path = services.reports.generate(project, tmp_path / "sin_simular.pdf")
    text, images = _pdf_text(path)
    assert "Todavía no se ha simulado" in text
    assert "Aforo calculado: 48 personas" in text  # 2 aulas de 36 m² → 24 c/u
    assert images == 0


def test_report_requires_scale(services: AppServices, tmp_path: Path) -> None:
    project_id = services.projects.create_project("Tienda", UseType.COMMERCE)
    with pytest.raises(UserFacingError, match="escala"):
        services.reports.generate(project_id, tmp_path / "x.pdf")


def test_norms_service(services: AppServices) -> None:
    categories = services.norms.categories(UseType.EDUCATION)
    assert categories[0] == ("aula", "Aula")
    assert ("pasillo", "Pasillo o circulación") in categories
    evaluation = services.norms.evaluate(two_rooms(), None)
    assert evaluation.total_occupants == 0
    assert evaluation.total_capacity == 48
    with pytest.raises(UserFacingError, match="escala"):
        services.norms.evaluate(dataclasses.replace(two_rooms(), scale_m_per_px=None), None)


def test_report_compares_scenarios(services: AppServices, project: int, tmp_path: Path) -> None:
    plan = services.projects.load_floor(project)
    assert plan is not None
    base = _scenario(services, project, 20)
    services.simulations.save_scenario(project, base)
    services.simulations.run(project, plan, base)
    path = services.reports.generate(project, tmp_path / "solo_base.pdf")
    assert "Comparación de escenarios" not in _pdf_text(path)[0]  # un solo escenario
    variant = services.simulations.save_variant(project, "Doble aforo", base, 200, set())
    services.simulations.run(project, plan, variant)
    text, _ = _pdf_text(services.reports.generate(project, tmp_path / "comparacion.pdf"))
    assert "Comparación de escenarios" in text
    assert "Doble aforo" in text
    assert "Escenario base" in text
    assert "Reglas normativas usadas" in text
