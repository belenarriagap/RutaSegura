"""Ensamblado de los servicios que usa la interfaz."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rutasegura.application.calibration_service import CalibrationService
from rutasegura.application.norms_service import NormsService
from rutasegura.application.plan_import import PlanImportService
from rutasegura.application.projects import ProjectService
from rutasegura.application.report_service import ReportService
from rutasegura.application.simulation_service import SimulationService
from rutasegura.data.database import Database, default_database_path


@dataclass(frozen=True)
class AppServices:
    """Servicios de aplicación disponibles para la capa de presentación."""

    projects: ProjectService
    plans: PlanImportService
    simulations: SimulationService
    norms: NormsService
    reports: ReportService
    calibration: CalibrationService
    database: Database

    @classmethod
    def open(cls, db_path: Path | None = None) -> AppServices:
        """Abre la base local (creándola si no existe) y arma los servicios."""
        path = db_path or default_database_path()
        database = Database.open(path)
        norms = NormsService()
        projects = ProjectService(database, path.parent / "planos")
        simulations = SimulationService(database, path.parent / "trayectorias", norms=norms)
        return cls(
            projects=projects,
            plans=PlanImportService(),
            simulations=simulations,
            norms=norms,
            reports=ReportService(projects, simulations, norms),
            calibration=CalibrationService(database, simulations),
            database=database,
        )

    def close(self) -> None:
        """Libera recursos."""
        self.database.close()
