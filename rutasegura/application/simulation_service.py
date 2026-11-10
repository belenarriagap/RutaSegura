"""Escenario base, ocupantes y ejecución de la simulación (RF05, RF07, RF08)."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from rutasegura.application.errors import OperationCancelled, UserFacingError
from rutasegura.data.database import Database
from rutasegura.data.repositories import NotFoundError
from rutasegura.data.trajectories import load_run, save_run
from rutasegura.domain.enums import ObservationType
from rutasegura.domain.geometry import Point
from rutasegura.domain.people import PersonProfile
from rutasegura.domain.plan import FloorPlan
from rutasegura.domain.results import (
    Bottleneck,
    Observation,
    SimulationResult,
    Trajectories,
)
from rutasegura.domain.scenario import Scenario
from rutasegura.engines.navigation.fields import distance_field
from rutasegura.engines.navigation.grid import build_grid, polygon_to_m, segment_to_m
from rutasegura.engines.simulation.engine import Simulation, SimulationCancelled
from rutasegura.engines.simulation.params import SimulationParams
from rutasegura.engines.simulation.population import PopulationError, RoomArea, spawn_agents

BASE_SCENARIO = "Escenario base"
DEFAULT_SEED = 2026

CONGESTION_TEXT = (
    "Congestión {place}: densidad media de {density:.1f} personas/m² durante {duration:.0f} s."
)
CONGESTION_ADVICE = (
    "Revise este paso: puede ensancharlo, retirar obstáculos, señalizar una ruta alternativa "
    "o habilitar otra salida para repartir a las personas."
)


@dataclass(frozen=True, eq=False)
class SimulationRun:
    """Una corrida guardada, lista para mostrar."""

    simulation_id: int
    result: SimulationResult
    trajectories: Trajectories
    observations: tuple[Observation, ...]
    scale_m_per_px: float


class SimulationService:
    """Casos de uso de escenario y simulación."""

    def __init__(
        self, db: Database, runs_dir: Path, params: SimulationParams | None = None
    ) -> None:
        self._db = db
        self._runs_dir = runs_dir
        self.params = params or SimulationParams()

    # ------------------------------------------------------------------ escenario y perfiles
    def profiles(self) -> list[PersonProfile]:
        """Catálogo de perfiles."""
        with self._db.unit_of_work() as uow:
            return uow.profiles.list_all()

    def load_scenario(self, project_id: int) -> Scenario:
        """Escenario base del proyecto (vacío si todavía no existe)."""
        with self._db.unit_of_work() as uow:
            try:
                return uow.scenarios.get(uow.scenarios.find_id(project_id, BASE_SCENARIO))
            except NotFoundError:
                return Scenario(BASE_SCENARIO, DEFAULT_SEED)

    def save_scenario(self, project_id: int, scenario: Scenario) -> int:
        """Guarda el escenario (los ambientes del plano deben estar guardados antes)."""
        with self._db.unit_of_work() as uow:
            try:
                return uow.scenarios.save(project_id, scenario)
            except ValueError as exc:
                raise UserFacingError(str(exc)) from exc

    # ------------------------------------------------------------------ ejecución
    def run(
        self,
        project_id: int,
        plan: FloorPlan,
        scenario: Scenario,
        *,
        progress: Callable[[float], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> SimulationRun:
        """Simula el escenario sobre el plano, guarda el resultado y lo devuelve."""
        scale = self._validate(plan, scenario)
        grid = build_grid(plan, blocked_exits=scenario.blocked_exits)
        distance = distance_field(grid.walkable, grid.targets, grid.cell_size)
        rooms = [RoomArea(r.name, plan.level, polygon_to_m(r.area, scale)) for r in plan.rooms]
        profiles = self.profiles()
        rng = np.random.default_rng(scenario.seed)
        try:
            agents = spawn_agents(
                grid, distance, rooms, scenario.occupancies, profiles, rng, self.params
            )
        except PopulationError as exc:
            raise UserFacingError(str(exc)) from exc
        simulation = Simulation(
            grid,
            agents,
            self.params,
            seed=scenario.seed,
            profile_names=[p.name for p in profiles],
            distance=distance,
        )
        try:
            output = simulation.run(progress=progress, should_cancel=should_cancel)
        except SimulationCancelled as exc:
            raise OperationCancelled from exc

        observations = tuple(
            self._congestion(b, plan, scale) for b in output.result.bottlenecks[:5]
        )
        scenario_id = self.save_scenario(project_id, scenario)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = self._runs_dir / f"proyecto_{project_id}" / f"escenario_{scenario_id}_{stamp}.npz"
        save_run(path, output.result, output.trajectories)
        result = dataclasses.replace(output.result, trajectories_path=str(path))
        with self._db.unit_of_work() as uow:
            simulation_id = uow.simulations.add(scenario_id, result, observations)
        return SimulationRun(simulation_id, result, output.trajectories, observations, scale)

    def last_run(self, project_id: int) -> SimulationRun | None:
        """Última corrida del escenario base, si existe y su archivo sigue disponible."""
        plan_scale = None
        with self._db.unit_of_work() as uow:
            try:
                scenario_id = uow.scenarios.find_id(project_id, BASE_SCENARIO)
            except NotFoundError:
                return None
            runs = uow.simulations.list_all(scenario_id)
            if not runs:
                return None
            simulation_id, summary = runs[-1]
            observations = tuple(uow.simulations.observations(simulation_id))
            try:
                plan_scale = uow.floors.get(project_id, 0).scale_m_per_px
            except NotFoundError:
                return None
        if summary.trajectories_path is None or plan_scale is None:
            return None
        try:
            stored = load_run(Path(summary.trajectories_path))
        except (OSError, ValueError, KeyError):
            return None
        result = SimulationResult(
            seed=summary.seed,
            total_time_s=summary.total_time_s,
            time_per_exit_s=summary.time_per_exit_s,
            curve_times_s=stored.curve_times_s,
            curve_evacuated=stored.curve_evacuated,
            density_map=stored.density_map,
            bottlenecks=stored.bottlenecks,
            trajectories_path=summary.trajectories_path,
            agents_total=stored.agents_total,
            agents_evacuated=stored.agents_evacuated,
            completed=stored.completed,
            grid_origin_m=stored.grid_origin_m,
            cell_size_m=stored.cell_size_m,
        )
        return SimulationRun(simulation_id, result, stored.trajectories, observations, plan_scale)

    # ------------------------------------------------------------------ auxiliares
    @staticmethod
    def _validate(plan: FloorPlan, scenario: Scenario) -> float:
        if plan.scale_m_per_px is None:
            raise UserFacingError("Primero defina la escala del plano (paso 2).")
        if any(not e.confirmed for e in plan.exits):
            raise UserFacingError(
                "Hay salidas propuestas sin confirmar. Confírmelas o bórrelas en el paso 3."
            )
        usable_exits = [e for e in plan.exits if e.name not in scenario.blocked_exits]
        if not usable_exits and not plan.safe_zones:
            raise UserFacingError("El plano no tiene ninguna salida ni zona segura disponible.")
        if not plan.rooms:
            raise UserFacingError("Primero marque los ambientes del local (paso 4).")
        if scenario.total_occupants == 0:
            raise UserFacingError("Indique cuántas personas hay en cada ambiente (paso 4).")
        return plan.scale_m_per_px

    @staticmethod
    def _congestion(bottleneck: Bottleneck, plan: FloorPlan, scale: float) -> Observation:
        return Observation(
            kind=ObservationType.CONGESTION,
            description=CONGESTION_TEXT.format(
                place=describe_place(plan, scale, bottleneck.location),
                density=bottleneck.mean_density,
                duration=bottleneck.duration_s,
            ),
            recommendation=CONGESTION_ADVICE,
            location=bottleneck.location,
        )


def describe_place(plan: FloorPlan, scale: float, point_m: Point) -> str:
    """Descripción en palabras de un lugar: junto a qué salida o puerta, o en qué ambiente."""
    best_name, best_dist = "", 2.5  # metros
    for exit_ in plan.exits:
        seg = segment_to_m(exit_.segment, scale)
        dist = seg.midpoint.distance_to(point_m)
        if dist < best_dist:
            best_name, best_dist = f"junto a «{exit_.name}»", dist
    if not best_name:
        for door in plan.doors:
            if segment_to_m(door.segment, scale).midpoint.distance_to(point_m) < 1.5:
                best_name = "junto a una puerta"
                break
    for room in plan.rooms:
        polygon = polygon_to_m(room.area, scale)
        if _inside(polygon.vertices, point_m):
            suffix = f" de «{room.name}»" if best_name else f"en «{room.name}»"
            return (best_name + suffix) if best_name else suffix.strip()
    return best_name or "en un pasillo o zona de circulación"


def _inside(vertices: tuple[Point, ...], p: Point) -> bool:
    inside = False
    j = len(vertices) - 1
    for i, vi in enumerate(vertices):
        vj = vertices[j]
        if (vi.y > p.y) != (vj.y > p.y):
            x_cross = (vj.x - vi.x) * (p.y - vi.y) / (vj.y - vi.y) + vi.x
            if p.x < x_cross:
                inside = not inside
        j = i
    return inside
