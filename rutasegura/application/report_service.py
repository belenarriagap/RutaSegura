"""Informe PDF del proyecto (RF09): reúne plano, aforo, simulación y parámetros."""

from __future__ import annotations

from pathlib import Path

import rutasegura
from rutasegura.application.errors import UserFacingError
from rutasegura.application.norms_service import NormsService
from rutasegura.application.projects import ProjectService
from rutasegura.application.simulation_service import SimulationService
from rutasegura.data.default_profiles import load_default_profiles
from rutasegura.data.report_pdf import ReportContent, ScenarioRow, write_report
from rutasegura.engines.simulation.params import SimulationParams
from rutasegura.resources.texts import TEXTS


def describe_parameters(params: SimulationParams) -> tuple[tuple[str, str], ...]:
    """Parámetros del modelo en palabras (los provisionales se indican)."""
    p = params
    return (
        ("Paso de tiempo", f"{p.dt_s:g} s"),
        ("Tamaño de celda de la grilla", "0.4 m"),
        ("Densidad máxima (provisional)", f"{p.jam_density:g} personas/m²"),
        ("Factor mínimo de velocidad (provisional)", f"{p.min_speed_factor:g}"),
        ("Variación individual de velocidad (provisional)", f"{p.speed_variation:.0%}"),
        ("Umbral de congestión (provisional)", f"{p.congestion_density:g} personas/m²"),
        ("Duración mínima de congestión (provisional)", f"{p.congestion_min_duration_s:g} s"),
        ("Tiempo máximo simulado", f"{p.max_time_s:g} s"),
        ("Recorrido de escalera por piso (provisional)", f"{p.stair_travel_m:g} m"),
        (
            "Velocidad al bajar escaleras (provisional)",
            f"{p.stair_speed_factor:.0%} de la horizontal",
        ),
        ("Flujo específico de escalera (provisional)", f"{p.stair_specific_flow:g} personas/(s·m)"),
    )


class ReportService:
    """Genera el informe a partir de lo guardado en el proyecto."""

    def __init__(
        self, projects: ProjectService, simulations: SimulationService, norms: NormsService
    ) -> None:
        self._projects = projects
        self._simulations = simulations
        self._norms = norms

    def build_content(self, project_id: int) -> ReportContent:
        """Reúne el contenido del informe (plano y escenario guardados, última corrida)."""
        project = self._projects.get_project(project_id)
        floors = [f for f in self._projects.load_floors(project_id) if f.is_scaled]
        if not floors:
            raise UserFacingError("Primero cargue el plano y defina su escala (pasos 1 y 2).")
        plan = floors[0]
        scenario = self._simulations.load_scenario(project_id)
        run = self._simulations.last_run(project_id)
        profiles = tuple(self._simulations.profiles())
        defaults = {d.profile.name: d for d in load_default_profiles()}
        provisional = tuple(
            p.name
            for p in profiles
            if p.name in defaults and defaults[p.name].provisional and defaults[p.name].profile == p
        )
        return ReportContent(
            project=project,
            plan=plan,
            plan_image=self._projects.load_floor_image(plan),
            floors=tuple((f, self._projects.load_floor_image(f)) for f in floors),
            scenario=scenario,
            norms=self._norms.evaluate_building(floors, scenario),
            result=None if run is None else run.result,
            congestion=() if run is None else run.observations,
            profiles=profiles,
            provisional_profiles=provisional,
            parameters=describe_parameters(self._simulations.params),
            legal_disclaimer=TEXTS.legal_disclaimer,
            app_version=rutasegura.__version__,
            comparison=self._comparison(project_id),
        )

    def _comparison(self, project_id: int) -> tuple[ScenarioRow, ...]:
        rows = []
        for scenario in self._simulations.list_scenarios(project_id):
            run = self._simulations.last_run(project_id, scenario.name)
            if run is None:
                continue
            result = run.result
            rows.append(
                ScenarioRow(
                    name=scenario.name,
                    occupants=scenario.total_occupants,
                    blocked_exits=tuple(sorted(scenario.blocked_exits)),
                    total_time_s=result.total_time_s,
                    time_90_s=result.time_to_evacuate(0.9),
                    evacuated=result.agents_evacuated,
                    agents=result.agents_total,
                    completed=result.completed,
                    bottlenecks=len(result.bottlenecks),
                )
            )
        return tuple(rows)

    def generate(self, project_id: int, path: Path) -> Path:
        """Escribe el informe en ``path`` (agrega «.pdf» si falta)."""
        if path.suffix.lower() != ".pdf":
            path = path.with_suffix(".pdf")
        content = self.build_content(project_id)
        try:
            write_report(path, content)
        except OSError as exc:
            raise UserFacingError(f"No se pudo guardar el informe: {exc}") from exc
        return path
