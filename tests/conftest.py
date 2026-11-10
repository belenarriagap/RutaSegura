"""Configuración común de pruebas."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

# Qt sin pantalla: necesario en CI (Ubuntu sin X) y cómodo en local. Debe fijarse antes de crear
# la QApplication, que pytest-qt crea de forma perezosa.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def services(tmp_path: Path) -> Iterator[object]:
    """Servicios de aplicación sobre una base de datos temporal."""
    from rutasegura.application.services import AppServices

    app_services = AppServices.open(tmp_path / "datos" / "rutasegura.db")
    yield app_services
    app_services.close()
