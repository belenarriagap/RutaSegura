"""Conexión a la base de datos local (SQLite) y migraciones.

El motor se crea con una ``EngineFactory`` intercambiable. Así queda listo el cifrado opcional
(RNF04): una fábrica para SQLCipher puede reemplazar a ``plain_sqlite_engine`` sin tocar los
repositorios ni la capa de aplicación (ver docs/decisiones.md, ADR-009).
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Protocol

from alembic import command
from alembic.config import Config
from sqlalchemy import URL, Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from rutasegura.data.default_profiles import load_default_profiles
from rutasegura.data.repositories import (
    FloorRepository,
    ProfileRepository,
    ProjectRepository,
    RealDrillRepository,
    ScenarioRepository,
    SimulationRepository,
)

APP_DIR_NAME = "RutaSegura"
DB_FILE_NAME = "rutasegura.db"
MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class EngineFactory(Protocol):
    """Crea un motor SQLAlchemy para un archivo de base de datos."""

    def __call__(self, path: Path) -> Engine: ...


def _enable_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def plain_sqlite_engine(path: Path) -> Engine:
    """Motor SQLite sin cifrado, con claves foráneas activadas."""
    engine = create_engine(URL.create("sqlite", database=str(path)))
    event.listen(engine, "connect", _enable_foreign_keys)
    return engine


def default_database_path() -> Path:
    """Ruta local del usuario: ``%LOCALAPPDATA%\\RutaSegura`` en Windows."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / APP_DIR_NAME / DB_FILE_NAME


def alembic_config() -> Config:
    """Configuración de Alembic apuntando a las migraciones empaquetadas."""
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR).replace("%", "%%"))
    return config


def upgrade_to_head(engine: Engine) -> None:
    """Aplica todas las migraciones pendientes."""
    config = alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


class UnitOfWork:
    """Repositorios que comparten una misma transacción."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.projects = ProjectRepository(session)
        self.floors = FloorRepository(session)
        self.profiles = ProfileRepository(session)
        self.scenarios = ScenarioRepository(session)
        self.simulations = SimulationRepository(session)
        self.drills = RealDrillRepository(session)


class Database:
    """Punto de acceso a la base de datos: crea sesiones transaccionales."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self._sessions = sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def open(
        cls,
        path: Path,
        *,
        engine_factory: EngineFactory = plain_sqlite_engine,
        migrate: bool = True,
        seed_defaults: bool = True,
    ) -> Database:
        """Abre (o crea) la base de datos en *path*.

        Aplica las migraciones pendientes y agrega los perfiles por defecto que falten (sin
        sobrescribir los que el usuario haya editado).
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        engine = engine_factory(path)
        if migrate:
            upgrade_to_head(engine)
        database = cls(engine)
        if seed_defaults:
            with database.unit_of_work() as uow:
                uow.profiles.ensure(d.profile for d in load_default_profiles())
        return database

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Sesión dentro de una transacción: confirma al salir, revierte si hay error."""
        with self._sessions.begin() as session:
            yield session

    @contextmanager
    def unit_of_work(self) -> Iterator[UnitOfWork]:
        """Repositorios sobre una sola transacción."""
        with self.session() as session:
            yield UnitOfWork(session)

    def close(self) -> None:
        """Libera las conexiones."""
        self.engine.dispose()
