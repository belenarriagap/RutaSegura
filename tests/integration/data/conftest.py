"""Fixtures de base de datos temporal."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from rutasegura.data.database import Database


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database.open(tmp_path / "prueba.db")
    yield database
    database.close()
