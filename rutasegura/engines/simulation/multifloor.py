"""Evacuación de un edificio de varios pisos (RF12, CLAUDE.md §5.2).

* Un ``Simulation`` (y un campo de distancia) por piso. Todos comparten los índices de agente:
  en cada piso, quien no está en él figura como inactivo.
* En los pisos altos las escaleras son objetivos. Quien llega a una escalera entra a una cola
  (capacidad = flujo específico × ancho), baja durante ``recorrido / (velocidad · factor)`` y
  aparece en la escalera emparejada del piso de abajo.
* Las escaleras se emparejan por nombre; si en el piso de abajo hay una sola, se usa esa.
* Una persona está evacuada cuando llega a una salida o zona segura (en cualquier piso).
* Determinista: la ubicación al llegar usa un ``Generator`` derivado de la semilla.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass

import cv2
import numpy as np
import numpy.typing as npt

from rutasegura.domain.agents import AgentArrays
from rutasegura.domain.enums import AgentStatus, CellType
from rutasegura.domain.people import Occupancy, PersonProfile
from rutasegura.domain.plan import FloorPlan
from rutasegura.domain.results import FloorMap, SimulationResult, Trajectories
from rutasegura.engines.navigation.fields import distance_field
from rutasegura.engines.navigation.grid import NavGrid, build_grid, polygon_to_m
from rutasegura.engines.simulation.engine import (
    CancelCheck,
    ProgressCallback,
    Simulation,
    SimulationCancelled,
    SimulationOutput,
)
from rutasegura.engines.simulation.metrics import find_bottlenecks
from rutasegura.engines.simulation.params import SimulationParams
from rutasegura.engines.simulation.population import PopulationError, RoomArea, spawn_agents

MAX_FLOORS = 4
IN_STAIRS = -1
EVACUATED = int(AgentStatus.EVACUATED)
MOVING = int(AgentStatus.MOVING)


class MultiFloorError(ValueError):
    """El edificio no se puede simular (piso sin escala, escaleras sin pareja…)."""


@dataclass(frozen=True)
class _Stair:
    """Escalera de un piso alto: a qué escalera del piso de abajo lleva y su capacidad."""

    lower_index: int
    seconds_per_person: float  # 1 / (flujo específico · ancho)


def stair_width_m(plan: FloorPlan, index: int) -> float:
    """Ancho de una escalera: lado corto del rectángulo mínimo que la contiene (m)."""
    scale = plan.scale_m_per_px or 1.0
    pts = np.array([[p.x, p.y] for p in plan.stairs[index].area.vertices], np.float32) * scale
    (_, _), (w, h), _ = cv2.minAreaRect(pts)
    return float(max(min(w, h), 0.3))


def pair_stairs(upper: FloorPlan, lower: FloorPlan) -> dict[int, int]:
    """Empareja cada escalera confirmada del piso de arriba con una del piso de abajo."""
    lower_ok = [i for i, st in enumerate(lower.stairs) if st.confirmed]
    by_name = {lower.stairs[i].name.strip().lower(): i for i in lower_ok if lower.stairs[i].name}
    pairs: dict[int, int] = {}
    for i, stair in enumerate(upper.stairs):
        if not stair.confirmed:
            continue
        key = stair.name.strip().lower()
        if key and key in by_name:
            pairs[i] = by_name[key]
        elif len(lower_ok) == 1:
            pairs[i] = lower_ok[0]
        else:
            label = stair.name or f"Escalera {i + 1}"
            raise MultiFloorError(
                f"La escalera «{label}» del piso {upper.level + 1} no tiene una escalera "
                f"correspondiente en el piso {lower.level + 1}. Dibújela en ese piso con el "
                "mismo nombre."
            )
    return pairs


class MultiFloorSimulation:
    """Coordina un ``Simulation`` por piso y el paso de personas por las escaleras."""

    def __init__(
        self,
        floors: Sequence[FloorPlan],
        occupancies: Sequence[Occupancy],
        profiles: Sequence[PersonProfile],
        params: SimulationParams,
        *,
        seed: int,
        blocked_exits: Collection[str] = (),
    ) -> None:
        if not floors:
            raise MultiFloorError("No hay pisos para simular.")
        if len(floors) > MAX_FLOORS:
            raise MultiFloorError(f"RutaSegura simula edificios de hasta {MAX_FLOORS} pisos.")
        self.params = params
        self.seed = seed
        self.plans = {plan.level: plan for plan in sorted(floors, key=lambda f: f.level)}
        self.levels = sorted(self.plans)
        self.profile_names = tuple(p.name for p in profiles)
        bottom = self.levels[0]
        self.grids: dict[int, NavGrid] = {}
        distances: dict[int, npt.NDArray[np.float64]] = {}
        for level, plan in self.plans.items():
            if plan.scale_m_per_px is None:
                raise MultiFloorError(f"El piso {level + 1} no tiene escala.")
            grid = build_grid(plan, blocked_exits=blocked_exits, stairs_as_targets=level > bottom)
            self.grids[level] = grid
            distances[level] = distance_field(grid.walkable, grid.targets, grid.cell_size)

        # Escaleras: pareja en el piso de abajo y capacidad.
        self._stairs: dict[int, dict[int, _Stair]] = {}
        for upper, lower in zip(self.levels[1:], self.levels[:-1], strict=True):
            if upper - lower != 1:
                raise MultiFloorError(
                    f"Falta el piso {lower + 2}: los pisos deben ser consecutivos."
                )
            pairs = pair_stairs(self.plans[upper], self.plans[lower])
            self._stairs[upper] = {
                i: _Stair(
                    j,
                    1.0 / (params.stair_specific_flow * stair_width_m(self.plans[upper], i)),
                )
                for i, j in pairs.items()
            }
        self._arrivals = {
            level: {
                i: self._arrival_cells(level, i)
                for i, st in enumerate(self.plans[level].stairs)
                if st.confirmed
            }
            for level in self.levels
        }

        # Población: se ubica piso por piso con un único generador (reproducible).
        rng = np.random.default_rng(seed)
        blocks: list[tuple[int, AgentArrays]] = []
        for level in self.levels:
            plan = self.plans[level]
            scale = plan.scale_m_per_px or 1.0
            rooms = [RoomArea(r.name, level, polygon_to_m(r.area, scale)) for r in plan.rooms]
            mine = [o for o in occupancies if o.level == level]
            try:
                agents = spawn_agents(
                    self.grids[level], distances[level], rooms, mine, profiles, rng, params
                )
            except PopulationError as exc:
                raise MultiFloorError(f"Piso {level + 1}: {exc}") from exc
            blocks.append((level, agents))
        n = sum(len(a) for _, a in blocks)
        self.agents_total = n
        self.level = np.full(n, IN_STAIRS, dtype=np.int8)
        self.max_speed = np.zeros(n)
        self.radius = np.zeros(n, dtype=np.float32)
        self.profile_index = np.zeros(n, dtype=np.int32)
        reaction = np.zeros(n)
        start = 0
        for level, agents in blocks:
            sl = slice(start, start + len(agents))
            self.level[sl] = level
            self.max_speed[sl] = agents.max_speed
            self.radius[sl] = agents.radius
            self.profile_index[sl] = agents.profile_index
            reaction[sl] = agents.reaction_time
            start += len(agents)

        self.sims: dict[int, Simulation] = {}
        for level, agents in blocks:
            floor_agents = AgentArrays.empty(n)
            floor_agents.max_speed[:] = self.max_speed
            floor_agents.radius[:] = self.radius
            floor_agents.reaction_time[:] = reaction
            floor_agents.profile_index[:] = self.profile_index
            floor_agents.status[:] = EVACUATED  # inactivo en este piso
            here = np.flatnonzero(self.level == level)
            floor_agents.position[here] = agents.position
            floor_agents.status[here] = agents.status
            self.sims[level] = Simulation(
                self.grids[level],
                floor_agents,
                params,
                seed=seed,
                profile_names=self.profile_names,
                distance=distances[level],
                record=False,
            )

        self.time_s = 0.0
        self.steps = 0
        self.evacuation_time = np.full(n, np.nan)
        self.exit_name: list[str | None] = [None] * n
        self._transit_until = np.full(n, np.inf)
        self._transit_to: list[tuple[int, int] | None] = [None] * n
        self._stair_free_at: dict[tuple[int, int], float] = {}
        self._arrival_rng = np.random.default_rng([seed, 1])
        self._record_every = max(1, round(params.record_every_s / params.dt_s))
        self._frames_t: list[float] = []
        self._frames_pos: list[npt.NDArray[np.float32]] = []
        self._frames_status: list[npt.NDArray[np.int8]] = []
        self._frames_level: list[npt.NDArray[np.int8]] = []
        self._record()

    # ------------------------------------------------------------------ estado
    @property
    def evacuated(self) -> int:
        """Personas que llegaron a una salida o zona segura."""
        return int(np.count_nonzero(~np.isnan(self.evacuation_time)))

    @property
    def finished(self) -> bool:
        """Todos salieron o se alcanzó el tiempo máximo."""
        return self.evacuated == self.agents_total or self.time_s >= self.params.max_time_s - 1e-9

    def _arrival_cells(self, level: int, index: int) -> npt.NDArray[np.float64]:
        plan = self.plans[level]
        grid = self.grids[level]
        mask = grid.polygon_mask(polygon_to_m(plan.stairs[index].area, plan.scale_m_per_px or 1))
        rows, cols = np.nonzero(mask & (grid.cells == int(CellType.STAIR)))
        if rows.size == 0:
            rows, cols = np.nonzero(mask & grid.walkable)
        return grid.cell_centers(rows, cols)

    # ------------------------------------------------------------------ paso
    def step(self) -> None:
        """Avanza ``dt`` en todos los pisos y resuelve el paso por las escaleras."""
        dt = self.params.dt_s
        now = self.time_s + dt
        for level in self.levels:
            sim = self.sims[level]
            before = sim.agents.status.copy()
            sim.step()
            arrived = np.flatnonzero(
                (before != EVACUATED) & (sim.agents.status == EVACUATED) & (self.level == level)
            )
            for agent in arrived:
                self._leave_floor(int(agent), level, int(sim.exit_index[agent]), now)
        self._arrive(now)
        self.time_s = now
        self.steps += 1
        if self.steps % self._record_every == 0:
            self._record()

    def _leave_floor(self, agent: int, level: int, target: int, now: float) -> None:
        grid = self.grids[level]
        stair = grid.stair_of(target)
        if stair < 0:  # salida o zona segura: evacuada
            self.evacuation_time[agent] = now
            self.exit_name[agent] = grid.target_names[target]
            return
        info = self._stairs[level][stair]
        key = (level, stair)
        enter = max(now, self._stair_free_at.get(key, 0.0))
        self._stair_free_at[key] = enter + info.seconds_per_person
        speed = max(self.max_speed[agent] * self.params.stair_speed_factor, 0.05)
        self._transit_until[agent] = enter + self.params.stair_travel_m / speed
        self._transit_to[agent] = (level - 1, info.lower_index)
        self.level[agent] = IN_STAIRS

    def _arrive(self, now: float) -> None:
        due = np.flatnonzero((self.level == IN_STAIRS) & (self._transit_until <= now + 1e-9))
        for agent in due:
            destination = self._transit_to[agent]
            if destination is None:
                continue
            level, stair = destination
            cells = self._arrivals[level][stair]
            center = cells[int(self._arrival_rng.integers(0, len(cells)))]
            jitter = self._arrival_rng.uniform(-0.15, 0.15, size=2)
            sim = self.sims[level]
            sim.agents.position[agent] = center + jitter
            sim.agents.velocity[agent] = 0.0
            sim.agents.status[agent] = MOVING
            sim.exit_index[agent] = -1
            sim.evacuation_time[agent] = np.nan
            self.level[agent] = level
            self._transit_until[agent] = np.inf
            self._transit_to[agent] = None

    def _record(self) -> None:
        n = self.agents_total
        positions = np.zeros((n, 2), dtype=np.float32)
        for level, sim in self.sims.items():
            here = self.level == level
            positions[here] = sim.agents.position[here]
        status = np.where(
            ~np.isnan(self.evacuation_time),
            EVACUATED,
            np.where(self._started(), MOVING, int(AgentStatus.WAITING)),
        ).astype(np.int8)
        self._frames_t.append(self.time_s)
        self._frames_pos.append(positions)
        self._frames_status.append(status)
        self._frames_level.append(self.level.copy())

    def _started(self) -> npt.NDArray[np.bool_]:
        started = np.zeros(self.agents_total, dtype=bool)
        for level, sim in self.sims.items():
            here = self.level == level
            started[here] = sim.agents.status[here] != int(AgentStatus.WAITING)
        return np.asarray(started | (self.level == IN_STAIRS), dtype=np.bool_)

    # ------------------------------------------------------------------ ejecución completa
    def run(
        self,
        progress: ProgressCallback | None = None,
        should_cancel: CancelCheck | None = None,
    ) -> SimulationOutput:
        """Ejecuta hasta que todos salgan o se alcance el tiempo máximo."""
        total = max(self.agents_total, 1)
        last = -1.0
        while not self.finished:
            self.step()
            if should_cancel is not None and self.steps % 10 == 0 and should_cancel():
                raise SimulationCancelled
            if progress is not None:
                fraction = max(self.evacuated / total, self.time_s / self.params.max_time_s)
                if fraction - last >= 0.01:
                    last = fraction
                    progress(min(fraction, 1.0))
        if self._frames_t[-1] != self.time_s:
            self._record()
        if progress is not None:
            progress(1.0)
        return self.output()

    def output(self) -> SimulationOutput:
        """Resultado global, mapas por piso y trayectorias con el piso de cada persona."""
        names = sorted({n for n in self.exit_name if n is not None})
        per_exit = tuple(
            (
                name,
                round(
                    float(
                        max(
                            t
                            for t, e in zip(self.evacuation_time, self.exit_name, strict=True)
                            if e == name
                        )
                    ),
                    2,
                ),
            )
            for name in names
        )
        completed = self.evacuated == self.agents_total
        if completed and self.agents_total:
            total_time = float(np.nanmax(self.evacuation_time))
        else:
            total_time = self.time_s if self.agents_total else 0.0
        bottlenecks = sorted(
            (
                dataclasses.replace(b, level=level)
                for level in self.levels
                for b in find_bottlenecks(
                    self.grids[level],
                    self.sims[level].time_above,
                    self.sims[level].density_when_above,
                    min_duration_s=self.params.congestion_min_duration_s,
                )
            ),
            key=lambda b: (-b.severity, b.level, b.location.x, b.location.y),
        )[:10]
        floor_maps = tuple(
            FloorMap(
                level,
                self.sims[level].density_accumulated.copy(),
                self.grids[level].origin,
                self.grids[level].cell_size,
            )
            for level in self.levels
        )
        bottom = floor_maps[0]
        curve_t = np.array(self._frames_t, dtype=np.float64)
        evac = np.array(
            [np.count_nonzero(self.evacuation_time <= t + 1e-9) for t in curve_t], dtype=np.int32
        )
        result = SimulationResult(
            seed=self.seed,
            total_time_s=round(total_time, 2),
            time_per_exit_s=per_exit,
            curve_times_s=curve_t,
            curve_evacuated=evac,
            density_map=bottom.density_map,
            bottlenecks=tuple(bottlenecks),
            agents_total=self.agents_total,
            agents_evacuated=self.evacuated,
            completed=completed,
            grid_origin_m=bottom.grid_origin_m,
            cell_size_m=bottom.cell_size_m,
            floor_maps=floor_maps,
        )
        trajectories = Trajectories(
            times_s=curve_t,
            positions=np.stack(self._frames_pos).astype(np.float32),
            status=np.stack(self._frames_status).astype(np.int8),
            radius_m=self.radius.astype(np.float32),
            profile_index=self.profile_index.astype(np.int32),
            profile_names=self.profile_names,
            level=np.stack(self._frames_level).astype(np.int8),
        )
        exit_index = np.full(self.agents_total, -1, dtype=np.int16)
        for i, name in enumerate(self.exit_name):
            if name is not None:
                exit_index[i] = names.index(name)
        return SimulationOutput(result, trajectories, exit_index, self.evacuation_time.copy())


def simulate_building(
    floors: Sequence[FloorPlan],
    occupancies: Sequence[Occupancy],
    profiles: Sequence[PersonProfile],
    params: SimulationParams,
    *,
    seed: int,
    blocked_exits: Collection[str] = (),
    progress: Callable[[float], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> SimulationOutput:
    """Atajo: arma la simulación de varios pisos y la ejecuta."""
    simulation = MultiFloorSimulation(
        floors, occupancies, profiles, params, seed=seed, blocked_exits=blocked_exits
    )
    return simulation.run(progress=progress, should_cancel=should_cancel)
