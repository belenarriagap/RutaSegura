"""Las migraciones de Alembic producen exactamente el esquema de los modelos ORM."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from rutasegura.data.database import Database, alembic_config, plain_sqlite_engine, upgrade_to_head
from rutasegura.data.models import Base

EXPECTED_TABLES = {
    "proyecto",
    "piso",
    "elemento",
    "ambiente",
    "perfil_persona",
    "escenario",
    "ocupacion",
    "simulacion",
    "observacion",
    "simulacro_real",
}


def test_upgrade_creates_spec_tables(tmp_path: Path) -> None:
    engine = plain_sqlite_engine(tmp_path / "db.sqlite")
    upgrade_to_head(engine)
    tables = set(inspect(engine).get_table_names()) - {"alembic_version"}
    assert tables == EXPECTED_TABLES
    engine.dispose()


def test_migrations_match_models(tmp_path: Path) -> None:
    engine = plain_sqlite_engine(tmp_path / "db.sqlite")
    upgrade_to_head(engine)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    assert diff == [], f"Los modelos cambiaron sin migración: {diff}"


def test_downgrade_and_upgrade_again(tmp_path: Path) -> None:
    engine = plain_sqlite_engine(tmp_path / "db.sqlite")
    upgrade_to_head(engine)
    config = alembic_config()
    with engine.begin() as conn:
        config.attributes["connection"] = conn
        command.downgrade(config, "base")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    upgrade_to_head(engine)
    assert set(inspect(engine).get_table_names()) >= EXPECTED_TABLES
    engine.dispose()


def test_open_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "carpeta nueva" / "rutasegura.db"
    Database.open(path).close()
    db = Database.open(path)  # reabrir no falla ni duplica perfiles
    with db.unit_of_work() as uow:
        names = [p.name for p in uow.profiles.list_all()]
    db.close()
    assert names == ["adulto", "niño", "movilidad reducida"]
