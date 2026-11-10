"""Ensamblado de los servicios que usa la interfaz."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rutasegura.application.plan_import import PlanImportService
from rutasegura.application.projects import ProjectService
from rutasegura.application.simulation_service import SimulationService
from rutasegura.data.database import Database, default_database_path


@dataclass(frozen=True)
class AppServices:
    """Servicios de aplicación disponibles para la capa de presentación."""

    projects: ProjectService
    plans: PlanImportService
    simulations: SimulationService
    database: Database

    @classmethod
    def open(cls, db_path: Path | None = None) -> AppServices:
        """Abre la base local (creándola si no existe) y arma los servicios."""
        path = db_path or default_database_path()
        database = Database.open(path)
        return cls(
            projects=ProjectService(database, path.parent / "planos"),
            plans=PlanImportService(),
            simulations=SimulationService(database, path.parent / "trayectorias"),
            database=database,
        )

    def close(self) -> None:
        """Libera recursos."""
        self.database.close()
