"""Motor de evacuación con agentes (RF07, RF08).

Modelo (CLAUDE.md §5.3):

* Estado en arrays NumPy (``AgentArrays``), paso de tiempo fijo; no depende del render.
* Dirección deseada: campo de direcciones del campo de distancia, interpolado.
* Velocidad deseada según densidad local: ``v = v_max·max(f_min, 1 − ρ/ρ_max)``.
* Fuerza social simplificada: relajación a la velocidad deseada + repulsión exponencial entre
  personas (vecinos por hash espacial) y de muros.
* Corrección de superposición y bloqueo de movimientos hacia celdas no transitables.
* Determinista: con las mismas entradas da resultados idénticos bit a bit.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import cv2
import numpy as np
import numpy.typing as npt

from rutasegura.domain.agents import AgentArrays
from rutasegura.domain.enums import AgentStatus
from rutasegura.domain.results import SimulationResult, Trajectories
from rutasegura.engines.navigation.fields import direction_field, distance_field, wall_distance
from rutasegura.engines.navigation.grid import NavGrid
from rutasegura.engines.simulation.metrics import find_bottlenecks
from rutasegura.engines.simulation.neighbors import neighbor_pairs
from rutasegura.engines.simulation.params import SimulationParams

FloatArray = npt.NDArray[np.float64]
ProgressCallback = Callable[[float], None]
CancelCheck = Callable[[], bool]

WAITING = int(AgentStatus.WAITING)
MOVING = int(AgentStatus.MOVING)
EVACUATED = int(AgentStatus.EVACUATED)


class SimulationCancelled(Exception):  # noqa: N818 - nombre de dominio
    """El usuario canceló la simulación."""


@dataclass(frozen=True, eq=False)
class SimulationOutput:
    """Resultado agregado + trayectorias + datos por agente."""

    result: SimulationResult
    trajectories: Trajectories
    exit_index: npt.NDArray[np.int16]  # salida usada por cada agente (−1 si no salió)
    evacuation_time_s: FloatArray  # instante de evacuación de cada agente (nan si no salió)


def bilinear(field: FloatArray, grid: NavGrid, xy: FloatArray) -> FloatArray:
    """Interpola un campo definido en los centros de celda (2D o 3D) en posiciones (n, 2)."""
    rows, cols = field.shape[:2]
    u = (xy[:, 0] - grid.origin[0]) / grid.cell_size - 0.5
    v = (xy[:, 1] - grid.origin[1]) / grid.cell_size - 0.5
    c0 = np.clip(np.floor(u).astype(np.int64), 0, cols - 1)
    r0 = np.clip(np.floor(v).astype(np.int64), 0, rows - 1)
    c1 = np.minimum(c0 + 1, cols - 1)
    r1 = np.minimum(r0 + 1, rows - 1)
    fu = np.clip(u - c0, 0.0, 1.0)
    fv = np.clip(v - r0, 0.0, 1.0)
    if field.ndim == 3:
        fu, fv = fu[:, None], fv[:, None]
    top = field[r0, c0] * (1 - fu) + field[r0, c1] * fu
    bottom = field[r1, c0] * (1 - fu) + field[r1, c1] * fu
    return np.asarray(top * (1 - fv) + bottom * fv, dtype=np.float64)


class Simulation:
    """Simulación de una evacuación en un piso."""

    def __init__(
        self,
        grid: NavGrid,
        agents: AgentArrays,
        params: SimulationParams,
        *,
        seed: int,
        profile_names: Sequence[str] = (),
        distance: FloatArray | None = None,
    ) -> None:
        self.grid = grid
        self.agents = agents
        self.params = params
        self.seed = seed
        self.profile_names = tuple(profile_names)
        walkable = grid.walkable
        self._walkable = walkable
        self.distance = (
            distance
            if distance is not None
            else distance_field(walkable, grid.targets, grid.cell_size)
        )
        self._directions = direction_field(self.distance, walkable)
        self._wall_dist, self._wall_grad = wall_distance(walkable, grid.cell_size)
        n = len(agents)
        self.time_s = 0.0
        self.steps = 0
        self.exit_index = np.full(n, -1, dtype=np.int16)
        self.evacuation_time = np.full(n, np.nan)
        shape = grid.shape
        self.density_accumulated = np.zeros(shape)
        self.time_above = np.zeros(shape)
        self.density_when_above = np.zeros(shape)
        self._record_every = max(1, round(params.record_every_s / params.dt_s))
        self._frames_t: list[float] = []
        self._frames_pos: list[npt.NDArray[np.float32]] = []
        self._frames_status: list[npt.NDArray[np.int8]] = []
        self._curve_t: list[float] = []
        self._curve_n: list[int] = []
        self._record()

    # ------------------------------------------------------------------ estado
    @property
    def evacuated(self) -> int:
        """Personas que ya salieron."""
        return self.agents.evacuated_count

    @property
    def finished(self) -> bool:
        """Todos salieron o se alcanzó el tiempo máximo."""
        return self.evacuated == len(self.agents) or self.time_s >= self.params.max_time_s - 1e-9

    def _cells_walkable(self, xy: FloatArray) -> npt.NDArray[np.bool_]:
        r, c = self.grid.to_cell(xy)
        return np.asarray(self._walkable[r, c], dtype=np.bool_)

    # ------------------------------------------------------------------ paso
    def step(self) -> None:
        """Avanza un paso de tiempo ``dt``."""
        p = self.params
        dt = p.dt_s
        a = self.agents
        status = a.status
        status[(status == WAITING) & (a.reaction_time <= self.time_s)] = MOVING
        active = np.flatnonzero(status != EVACUATED)
        if active.size == 0:
            self.time_s += dt
            self.steps += 1
            return
        pos = a.position[active]
        vel = a.velocity[active]
        radius = a.radius[active]
        moving = status[active] == MOVING

        density = self._density(pos)
        r, c = self.grid.to_cell(pos)
        rho = density[r, c]

        # velocidad deseada y relajación
        direction = bilinear(self._directions, self.grid, pos)
        norm = np.linalg.norm(direction, axis=1, keepdims=True)
        direction = np.where(norm > 1e-9, direction / np.maximum(norm, 1e-12), 0.0)
        factor = np.maximum(p.min_speed_factor, 1.0 - rho / p.jam_density)
        desired_speed = a.max_speed[active] * factor
        accel = (desired_speed[:, None] * direction - vel) / p.relaxation_s

        # repulsión entre personas
        i, j, dist, nx, ny = self._pairs(pos, radius)
        if i.size:
            overlap_term = radius[i] + radius[j] - dist
            force = p.agent_strength * np.exp(overlap_term / p.agent_range_m)
            n_act = active.size
            accel[:, 0] += np.bincount(i, weights=force * nx, minlength=n_act)
            accel[:, 1] += np.bincount(i, weights=force * ny, minlength=n_act)

        # repulsión de muros
        wall_d = bilinear(self._wall_dist, self.grid, pos)
        wall_g = bilinear(self._wall_grad, self.grid, pos)
        wall_force = p.wall_strength * np.exp((radius - wall_d) / p.wall_range_m)
        accel += wall_force[:, None] * wall_g

        # integración (los que esperan no se desplazan)
        new_vel = vel + accel * dt
        speed = np.linalg.norm(new_vel, axis=1)
        limit = a.max_speed[active]
        too_fast = speed > limit
        new_vel[too_fast] *= (limit[too_fast] / speed[too_fast])[:, None]
        new_vel[~moving] = 0.0
        new_pos = self._move_with_walls(pos, new_vel * dt)

        # corrección de superposición
        i, j, dist, nx, ny = self._pairs(new_pos, radius)
        if i.size:
            overlap = np.maximum(radius[i] + radius[j] - dist, 0.0)
            push = np.minimum(0.5 * overlap, 0.05)
            n_act = active.size
            shift = np.column_stack(
                [
                    np.bincount(i, weights=push * nx, minlength=n_act),
                    np.bincount(i, weights=push * ny, minlength=n_act),
                ]
            )
            shift[~moving] *= 0.5
            candidate = new_pos + shift
            ok = self._cells_walkable(candidate)
            new_pos[ok] = candidate[ok]

        a.position[active] = new_pos
        a.velocity[active] = (new_pos - pos) / dt
        a.velocity[active[~moving]] = 0.0

        # evacuación
        r, c = self.grid.to_cell(new_pos)
        target = self.grid.target_ids[r, c]
        out = (target >= 0) & moving
        if out.any():
            leaving = active[out]
            status[leaving] = EVACUATED
            self.exit_index[leaving] = target[out]
            self.evacuation_time[leaving] = self.time_s + dt

        # métricas de densidad
        self.density_accumulated += density * dt
        above = density >= p.congestion_density
        self.time_above[above] += dt
        self.density_when_above[above] += density[above] * dt

        self.time_s += dt
        self.steps += 1
        if self.steps % self._record_every == 0:
            self._record()

    def _density(self, pos: FloatArray) -> FloatArray:
        """Personas por m² en cada celda, promediando una ventana de 3×3 celdas."""
        r, c = self.grid.to_cell(pos)
        rows, cols = self.grid.shape
        counts = np.bincount(r * cols + c, minlength=rows * cols).reshape(rows, cols)
        window = cv2.boxFilter(
            counts.astype(np.float64), -1, (3, 3), normalize=False, borderType=cv2.BORDER_CONSTANT
        )
        result = window / (9.0 * self.grid.cell_size**2)
        return np.asarray(np.where(self._walkable, result, 0.0), dtype=np.float64)

    def _pairs(
        self, pos: FloatArray, radius: FloatArray
    ) -> tuple[npt.NDArray[np.int64], npt.NDArray[np.int64], FloatArray, FloatArray, FloatArray]:
        cutoff = self.params.interaction_cutoff_m
        i, j = neighbor_pairs(pos, cutoff)
        delta = pos[i] - pos[j]
        dist = np.hypot(delta[:, 0], delta[:, 1])
        close = dist < cutoff
        i, j, delta, dist = i[close], j[close], delta[close], dist[close]
        # personas en el mismo punto: dirección fija según el índice (determinista)
        same = dist < 1e-9
        safe = np.where(same, 1.0, dist)
        nx = np.where(same, np.sign(i - j).astype(np.float64), delta[:, 0] / safe)
        ny = np.where(same, 0.0, delta[:, 1] / safe)
        return i, j, np.maximum(dist, 1e-9), nx, ny

    def _move_with_walls(self, pos: FloatArray, delta: FloatArray) -> FloatArray:
        """Aplica el desplazamiento; si cae en celda no transitable, intenta deslizar por x o y."""
        target = pos + delta
        blocked = ~self._cells_walkable(target)
        if blocked.any():
            only_x = pos[blocked] + np.column_stack([delta[blocked, 0], np.zeros(blocked.sum())])
            only_y = pos[blocked] + np.column_stack([np.zeros(blocked.sum()), delta[blocked, 1]])
            ok_x = self._cells_walkable(only_x)
            ok_y = self._cells_walkable(only_y) & ~ok_x
            fallback = pos[blocked].copy()
            fallback[ok_x] = only_x[ok_x]
            fallback[ok_y] = only_y[ok_y]
            target[blocked] = fallback
        return target

    def _record(self) -> None:
        self._frames_t.append(self.time_s)
        self._frames_pos.append(self.agents.position.astype(np.float32))
        self._frames_status.append(self.agents.status.copy())
        self._curve_t.append(self.time_s)
        self._curve_n.append(self.evacuated)

    # ------------------------------------------------------------------ ejecución completa
    def run(
        self,
        progress: ProgressCallback | None = None,
        should_cancel: CancelCheck | None = None,
    ) -> SimulationOutput:
        """Ejecuta hasta que todos salgan o se alcance el tiempo máximo."""
        total = max(len(self.agents), 1)
        last_report = -1.0
        while not self.finished:
            self.step()
            if should_cancel is not None and self.steps % 10 == 0 and should_cancel():
                raise SimulationCancelled
            if progress is not None:
                fraction = max(self.evacuated / total, self.time_s / self.params.max_time_s)
                if fraction - last_report >= 0.01:
                    last_report = fraction
                    progress(min(fraction, 1.0))
        if self._frames_t[-1] != self.time_s:
            self._record()
        if progress is not None:
            progress(1.0)
        return self.output()

    def output(self) -> SimulationOutput:
        """Resultados acumulados hasta el momento."""
        names = self.grid.target_names
        per_exit: list[tuple[str, float]] = []
        for k, name in enumerate(names):
            used = self.exit_index == k
            if used.any():
                per_exit.append((name, round(float(np.nanmax(self.evacuation_time[used])), 2)))
        completed = self.evacuated == len(self.agents)
        if completed and len(self.agents):
            total_time = float(np.nanmax(self.evacuation_time))
        else:
            total_time = self.time_s if len(self.agents) else 0.0
        bottlenecks = find_bottlenecks(
            self.grid,
            self.time_above,
            self.density_when_above,
            min_duration_s=self.params.congestion_min_duration_s,
        )
        result = SimulationResult(
            seed=self.seed,
            total_time_s=round(total_time, 2),
            time_per_exit_s=tuple(per_exit),
            curve_times_s=np.array(self._curve_t, dtype=np.float64),
            curve_evacuated=np.array(self._curve_n, dtype=np.int32),
            density_map=self.density_accumulated.copy(),
            bottlenecks=bottlenecks,
            agents_total=len(self.agents),
            agents_evacuated=self.evacuated,
            completed=completed,
            grid_origin_m=self.grid.origin,
            cell_size_m=self.grid.cell_size,
        )
        trajectories = Trajectories(
            times_s=np.array(self._frames_t, dtype=np.float64),
            positions=np.stack(self._frames_pos).astype(np.float32)
            if self._frames_pos
            else np.zeros((0, 0, 2), np.float32),
            status=np.stack(self._frames_status).astype(np.int8),
            radius_m=self.agents.radius.astype(np.float32),
            profile_index=self.agents.profile_index.astype(np.int32),
            profile_names=self.profile_names,
        )
        return SimulationOutput(
            result, trajectories, self.exit_index.copy(), self.evacuation_time.copy()
        )
