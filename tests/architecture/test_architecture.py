"""Prueba de arquitectura: falla si alguien rompe las reglas de capas, red o aleatoriedad."""

from __future__ import annotations

from pathlib import Path

import pytest

import rutasegura
from tests.architecture.import_rules import check_package, check_source

PACKAGE_DIR = Path(rutasegura.__file__).parent


def test_package_respects_architecture_rules() -> None:
    violations, checked = check_package(PACKAGE_DIR)
    assert checked >= 15, "No se encontraron los módulos del paquete; ¿cambió la ruta?"
    assert not violations, "Violaciones de arquitectura:\n" + "\n".join(map(str, violations))


# --- El verificador debe detectar cada tipo de violación (evita que la prueba sea vacía). ---


@pytest.mark.parametrize(
    ("module", "source"),
    [
        ("rutasegura.presentation.window", "from rutasegura.engines import vision"),
        ("rutasegura.presentation.window", "import rutasegura.data.repositories"),
        ("rutasegura.presentation.window", "from ..data import repositories"),
        ("rutasegura.presentation.window", "from rutasegura import engines"),
        ("rutasegura.application.service", "from rutasegura.presentation import window"),
        ("rutasegura.engines.vision.walls", "from rutasegura.data import models"),
        ("rutasegura.engines.vision.walls", "from ...application import orchestrator"),
        ("rutasegura.data.repo", "from rutasegura.engines import norms"),
        ("rutasegura.domain.plan", "from rutasegura.engines import simulation"),
        ("rutasegura.engines.simulation.model", "from PySide6.QtCore import QObject"),
        ("rutasegura.engines.simulation.model", "import sqlalchemy"),
        ("rutasegura.domain.plan", "import cv2"),
        ("rutasegura.application.service", "from PySide6 import QtCore"),
        ("rutasegura.presentation.window", "from sqlalchemy.orm import Session"),
        ("rutasegura.data.repo", "import socket"),
        ("rutasegura.data.repo", "from urllib import request"),
        ("rutasegura.data.repo", "import requests"),
        ("rutasegura.presentation.window", "from PySide6.QtNetwork import QNetworkAccessManager"),
        ("rutasegura.engines.simulation.model", "import random"),
        ("rutasegura.engines.simulation.model", "from random import uniform"),
        ("rutasegura.engines.simulation.model", "import numpy as np\nnp.random.seed(1)"),
        ("rutasegura.engines.simulation.model", "import numpy as np\nx = np.random.rand(3)"),
        ("rutasegura.engines.simulation.model", "import numpy\nnumpy.random.normal()"),
        ("rutasegura.engines.simulation.model", "from numpy import random as npr\nnpr.seed(3)"),
        ("rutasegura.engines.simulation.model", "from numpy.random import seed"),
    ],
)
def test_checker_detects_violation(module: str, source: str) -> None:
    assert check_source(source, module), f"No se detectó la violación en {module}: {source!r}"


@pytest.mark.parametrize(
    ("module", "source"),
    [
        ("rutasegura.presentation.window", "from rutasegura.application import orchestrator"),
        ("rutasegura.presentation.window", "from rutasegura.domain import FloorPlan"),
        ("rutasegura.presentation.window", "from rutasegura.resources.texts import TEXTS"),
        ("rutasegura.presentation.window", "from PySide6.QtWidgets import QMainWindow"),
        ("rutasegura.presentation.window", "from . import widgets"),
        (
            "rutasegura.application.service",
            "from rutasegura.engines import vision\nimport rutasegura.data",
        ),
        ("rutasegura.engines.vision.walls", "import cv2\nimport numpy as np"),
        ("rutasegura.engines.vision.walls", "from ..navigation import grid"),
        ("rutasegura.data.repo", "from sqlalchemy.orm import Session"),
        (
            "rutasegura.engines.simulation.model",
            "import numpy as np\nrng = np.random.default_rng(7)",
        ),
        ("rutasegura.engines.simulation.model", "from numpy.random import Generator, default_rng"),
        ("rutasegura.engines.simulation.model", "def f(rng):\n    return rng.random()"),
        (
            "rutasegura.__main__",
            "from rutasegura.data import repo\nfrom rutasegura.presentation import w",
        ),
    ],
)
def test_checker_allows_valid_code(module: str, source: str) -> None:
    assert check_source(source, module) == []
