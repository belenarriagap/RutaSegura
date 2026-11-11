"""Escenarios, ocupantes y ejecución de la simulación (RF05, RF07, RF08, RF10)."""

from __future__ import annotations

import contextlib
import dataclasses
import math
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from rutasegura.application.errors import OperationCancelled, UserFacingError
from rutasegura.application.norms_service import NormsService
from rutasegura.data.database import Database
from rutasegura.data.repositories import NotFoundError
from rutasegura.data.trajectories import load_run, save_run
from rutasegura.domain.enums import ObservationType
from rutasegura.domain.geometry import Point
from rutasegura.domain.people import Occupancy, PersonProfile
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
from rutasegura.engines.simulation.engine import (
    Simulation,
    SimulationCancelled,
    SimulationOutput,
)
from rutasegura.engines.simulation.multifloor import MultiFloorError, MultiFloorSimulation
from rutasegura.engines.simulation.params import SimulationParams
from rutasegura.engines.simulation.population import PopulationError, RoomArea, spawn_agents

BASE_SCENARIO = "Escenario base"
_NO_EXITS = (
    "El plano{floor} no tiene ninguna salida confirmada ni zona segura disponible. "
    "Dibuje una salida sobre un muro exterior (paso 3) o confirme las salidas propuestas."
)
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
    floor_scales: tuple[tuple[int, float], ...] = ()  # (nivel, escala) de cada piso

    def scale_of(self, level: int) -> float:
        """Escala (m/px) del piso indicado."""
        return dict(self.floor_scales).get(level, self.scale_m_per_px)


class SimulationService:
    """Casos de uso de escenario y simulación."""

    def __init__(
        self,
        db: Database,
        runs_dir: Path,
        params: SimulationParams | None = None,
        norms: NormsService | None = None,
    ) -> None:
        self._db = db
        self._runs_dir = runs_dir
        self.params = params or SimulationParams()
        self._norms = norms

    # ------------------------------------------------------------------ escenario y perfiles
    def profiles(self) -> list[PersonProfile]:
        """Catálogo de perfiles."""
        with self._db.unit_of_work() as uow:
            return uow.profiles.list_all()

    def load_scenario(self, project_id: int, name: str = BASE_SCENARIO) -> Scenario:
        """Escenario por nombre (el base se crea vacío si todavía no existe)."""
        with self._db.unit_of_work() as uow:
            try:
                return uow.scenarios.get(uow.scenarios.find_id(project_id, name))
            except NotFoundError:
                if name == BASE_SCENARIO:
                    return Scenario(BASE_SCENARIO, DEFAULT_SEED)
                raise UserFacingError(f"No existe el escenario «{name}».") from None

    def list_scenarios(self, project_id: int) -> list[Scenario]:
        """Escenarios del proyecto; el base siempre primero (aunque no esté guardado)."""
        with self._db.unit_of_work() as uow:
            stored = [s for _, s in uow.scenarios.list_all(project_id)]
        base = next((s for s in stored if s.name == BASE_SCENARIO), None)
        others = [s for s in stored if s.name != BASE_SCENARIO]
        return [base or Scenario(BASE_SCENARIO, DEFAULT_SEED), *others]

    def save_variant(
        self,
        project_id: int,
        name: str,
        base: Scenario,
        occupancy_percent: float,
        blocked_exits: Collection[str],
        *,
        previous_name: str | None = None,
    ) -> Scenario:
        """Crea (o actualiza) un escenario «qué pasa si» a partir del escenario base.

        La ocupación es la del base multiplicada por ``occupancy_percent`` / 100; la semilla es
        la del base. ``previous_name`` permite renombrar un escenario existente.
        """
        name = name.strip()
        if not name:
            raise UserFacingError("Escriba un nombre para el escenario.")
        if name == BASE_SCENARIO:
            raise UserFacingError(f"«{BASE_SCENARIO}» se edita en el paso 4.")
        if occupancy_percent <= 0:
            raise UserFacingError("El porcentaje de ocupación debe ser mayor que cero.")
        target = round(base.total_occupants * occupancy_percent / 100)
        existing = {s.name for s in self.list_scenarios(project_id)}
        if name in existing and name != previous_name:
            raise UserFacingError(f"Ya existe un escenario llamado «{name}».")
        variant = Scenario(
            name=name,
            seed=base.seed,
            occupancies=scale_occupancies(base.occupancies, target),
            blocked_exits=frozenset(blocked_exits),
        )
        with self._db.unit_of_work() as uow:
            if previous_name is not None and previous_name != name:
                with contextlib.suppress(NotFoundError):
                    uow.scenarios.rename(uow.scenarios.find_id(project_id, previous_name), name)
            try:
                uow.scenarios.save(project_id, variant)
            except ValueError as exc:
                raise UserFacingError(str(exc)) from exc
        return variant

    def delete_scenario(self, project_id: int, name: str) -> None:
        """Elimina un escenario «qué pasa si» con sus simulaciones."""
        if name == BASE_SCENARIO:
            raise UserFacingError("El escenario base no se puede eliminar.")
        with self._db.unit_of_work() as uow:
            try:
                uow.scenarios.delete(uow.scenarios.find_id(project_id, name))
            except NotFoundError:
                return

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
        plan: FloorPlan | Sequence[FloorPlan],
        scenario: Scenario,
        *,
        progress: Callable[[float], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> SimulationRun:
        """Simula el escenario (uno o varios pisos), guarda el resultado y lo devuelve."""
        floors = _as_floors(plan)
        output = self.simulate(floors, scenario, progress=progress, should_cancel=should_cancel)
        return self._store(project_id, floors, scenario, output)

    def simulate(
        self,
        plan: FloorPlan | Sequence[FloorPlan],
        scenario: Scenario,
        profiles: Sequence[PersonProfile] | None = None,
        *,
        progress: Callable[[float], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> SimulationOutput:
        """Simula sin guardar nada (lo usa también la calibración con perfiles modificados)."""
        floors = _as_floors(plan)
        if len(floors) > 1:
            return self._simulate_building(
                floors, scenario, profiles, progress=progress, should_cancel=should_cancel
            )
        plan = floors[0]
        scale = self._validate(plan, scenario)
        grid = build_grid(plan, blocked_exits=scenario.blocked_exits)
        distance = distance_field(grid.walkable, grid.targets, grid.cell_size)
        rooms = [RoomArea(r.name, plan.level, polygon_to_m(r.area, scale)) for r in plan.rooms]
        profiles = list(profiles) if profiles is not None else self.profiles()
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
            return simulation.run(progress=progress, should_cancel=should_cancel)
        except SimulationCancelled as exc:
            raise OperationCancelled from exc

    def _simulate_building(
        self,
        floors: Sequence[FloorPlan],
        scenario: Scenario,
        profiles: Sequence[PersonProfile] | None,
        *,
        progress: Callable[[float], None] | None,
        should_cancel: Callable[[], bool] | None,
    ) -> SimulationOutput:
        self._validate_building(floors, scenario)
        try:
            simulation = MultiFloorSimulation(
                floors,
                scenario.occupancies,
                list(profiles) if profiles is not None else self.profiles(),
                self.params,
                seed=scenario.seed,
                blocked_exits=scenario.blocked_exits,
            )
            return simulation.run(progress=progress, should_cancel=should_cancel)
        except MultiFloorError as exc:
            raise UserFacingError(str(exc)) from exc
        except SimulationCancelled as exc:
            raise OperationCancelled from exc

    def _store(
        self,
        project_id: int,
        floors: Sequence[FloorPlan],
        scenario: Scenario,
        output: SimulationOutput,
    ) -> SimulationRun:
        by_level = {f.level: f for f in floors}
        multi = len(floors) > 1
        observations = tuple(
            self._congestion(b, by_level.get(b.level, floors[0]), multi)
            for b in output.result.bottlenecks[:5]
        )
        # Las observaciones normativas del plano se guardan junto con la corrida (tabla
        # «observacion», CLAUDE.md §6); la corrida muestra solo las de congestión.
        norm_observations = (
            self._norms.evaluate_building(floors, scenario).observations
            if self._norms is not None
            else ()
        )
        scales = tuple((f.level, f.scale_m_per_px or 1.0) for f in floors)
        scale = floors[0].scale_m_per_px or 1.0
        scenario_id = self.save_scenario(project_id, scenario)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = self._runs_dir / f"proyecto_{project_id}" / f"escenario_{scenario_id}_{stamp}.npz"
        save_run(path, output.result, output.trajectories)
        result = dataclasses.replace(output.result, trajectories_path=str(path))
        with self._db.unit_of_work() as uow:
            simulation_id = uow.simulations.add(
                scenario_id, result, observations + norm_observations
            )
        return SimulationRun(
            simulation_id, result, output.trajectories, observations, scale, scales
        )

    def last_run(self, project_id: int, name: str = BASE_SCENARIO) -> SimulationRun | None:
        """Última corrida de un escenario, si existe y su archivo sigue disponible."""
        plan_scale = None
        with self._db.unit_of_work() as uow:
            try:
                scenario_id = uow.scenarios.find_id(project_id, name)
            except NotFoundError:
                return None
            runs = uow.simulations.list_all(scenario_id)
            if not runs:
                return None
            simulation_id, summary = runs[-1]
            observations = tuple(
                o
                for o in uow.simulations.observations(simulation_id)
                if o.kind is ObservationType.CONGESTION
            )
            levels = uow.floors.levels(project_id)
            if not levels:
                return None
            scales = tuple(
                (level, uow.floors.get(project_id, level).scale_m_per_px or 1.0) for level in levels
            )
            plan_scale = scales[0][1]
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
            floor_maps=stored.floor_maps,
        )
        return SimulationRun(
            simulation_id, result, stored.trajectories, observations, plan_scale, scales
        )

    # ------------------------------------------------------------------ auxiliares
    @staticmethod
    def _validate(plan: FloorPlan, scenario: Scenario) -> float:
        if plan.scale_m_per_px is None:
            raise UserFacingError("Primero defina la escala del plano (paso 2).")
        # Las salidas propuestas sin confirmar no bloquean: se ignoran (quedan cerradas).
        usable_exits = [
            e for e in plan.exits if e.confirmed and e.name not in scenario.blocked_exits
        ]
        if not usable_exits and not plan.safe_zones:
            raise UserFacingError(_NO_EXITS.format(floor=""))
        if not plan.rooms:
            raise UserFacingError("Primero marque los ambientes del local (paso 4).")
        if scenario.total_occupants == 0:
            raise UserFacingError("Indique cuántas personas hay en cada ambiente (paso 4).")
        return plan.scale_m_per_px

    def _validate_building(self, floors: Sequence[FloorPlan], scenario: Scenario) -> None:
        for plan in floors:
            if plan.scale_m_per_px is None:
                raise UserFacingError(
                    f"El piso {plan.level + 1} no tiene escala; defínala en el paso 2."
                )
        if not any(plan.rooms for plan in floors):
            raise UserFacingError("Primero marque los ambientes del local (paso 4).")
        if scenario.total_occupants == 0:
            raise UserFacingError("Indique cuántas personas hay en cada ambiente (paso 4).")
        lowest = min(floors, key=lambda f: f.level)
        usable = [e for e in lowest.exits if e.confirmed and e.name not in scenario.blocked_exits]
        if not usable and not lowest.safe_zones:
            raise UserFacingError(_NO_EXITS.format(floor=f" del piso {lowest.level + 1}"))

    @staticmethod
    def _congestion(bottleneck: Bottleneck, plan: FloorPlan, multi: bool = False) -> Observation:
        scale = plan.scale_m_per_px or 1.0
        place = describe_place(plan, scale, bottleneck.location)
        if multi:
            place = f"en el piso {bottleneck.level + 1}, {place}"
        return Observation(
            kind=ObservationType.CONGESTION,
            description=CONGESTION_TEXT.format(
                place=place,
                density=bottleneck.mean_density,
                duration=bottleneck.duration_s,
            ),
            recommendation=CONGESTION_ADVICE,
            location=bottleneck.location,
        )


def _as_floors(plan: FloorPlan | Sequence[FloorPlan]) -> list[FloorPlan]:
    if isinstance(plan, FloorPlan):
        return [plan]
    floors = sorted(plan, key=lambda f: f.level)
    if not floors:
        raise UserFacingError("No hay pisos para simular.")
    return floors


def scale_occupancies(occupancies: Sequence[Occupancy], target_total: int) -> tuple[Occupancy, ...]:
    """Reparte ``target_total`` personas en las mismas proporciones (método del mayor resto)."""
    current = sum(o.count for o in occupancies)
    if current == 0 or target_total <= 0:
        return ()
    exact = [o.count * target_total / current for o in occupancies]
    counts = [math.floor(x) for x in exact]
    order = sorted(range(len(exact)), key=lambda i: (-(exact[i] - counts[i]), i))
    for i in order[: target_total - sum(counts)]:
        counts[i] += 1
    return tuple(
        dataclasses.replace(o, count=c) for o, c in zip(occupancies, counts, strict=True) if c > 0
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
