"""Ubicación inicial de los ocupantes y muestreo de sus parámetros (RF05).

Toda la aleatoriedad usa el ``Generator`` recibido (creado con la semilla del escenario).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from rutasegura.domain.agents import AgentArrays
from rutasegura.domain.enums import CellType
from rutasegura.domain.geometry import Polygon
from rutasegura.domain.people import Occupancy, PersonProfile
from rutasegura.engines.navigation.grid import NavGrid
from rutasegura.engines.simulation.params import SimulationParams


class PopulationError(ValueError):
    """No se pudo ubicar a los ocupantes (ambiente inexistente, sin salida alcanzable…)."""


@dataclass(frozen=True)
class RoomArea:
    """Ambiente en metros, identificado como en las ocupaciones (nivel, nombre)."""

    name: str
    level: int
    polygon_m: Polygon


def lognormal_params(mean: float, std: float) -> tuple[float, float]:
    """(μ, σ) de una lognormal con la media y desviación indicadas."""
    if mean <= 0:
        return -math.inf, 0.0
    sigma2 = math.log(1.0 + (std / mean) ** 2)
    return math.log(mean) - sigma2 / 2.0, math.sqrt(sigma2)


def sample_reaction_times(
    rng: np.random.Generator, mean: float, std: float, n: int
) -> npt.NDArray[np.float64]:
    """Tiempos de premovimiento (s) con distribución lognormal."""
    if n == 0:
        return np.zeros(0)
    if mean <= 0:
        return np.zeros(n)
    if std <= 0:
        return np.full(n, float(mean))
    mu, sigma = lognormal_params(mean, std)
    return np.asarray(rng.lognormal(mu, sigma, size=n), dtype=np.float64)


def spawn_agents(
    grid: NavGrid,
    distance: npt.NDArray[np.float64],
    rooms: Sequence[RoomArea],
    occupancies: Sequence[Occupancy],
    profiles: Sequence[PersonProfile],
    rng: np.random.Generator,
    params: SimulationParams,
) -> AgentArrays:
    """Crea los agentes: posición al azar dentro de su ambiente y parámetros de su perfil."""
    profile_index: Mapping[str, int] = {p.name: i for i, p in enumerate(profiles)}
    room_index = {(r.level, r.name): r for r in rooms}
    # solo celdas libres: nadie empieza sobre una puerta, salida o zona segura
    usable = (grid.cells == int(CellType.FREE)) & np.isfinite(distance)
    blocks = []
    for occ in occupancies:
        if occ.count == 0:
            continue
        room = room_index.get((occ.level, occ.room_name))
        if room is None:
            raise PopulationError(f"No existe el ambiente «{occ.room_name}».")
        if occ.profile_name not in profile_index:
            raise PopulationError(f"No existe el perfil «{occ.profile_name}».")
        cells = grid.polygon_mask(room.polygon_m) & usable
        rows, cols = np.nonzero(cells)
        if rows.size == 0:
            raise PopulationError(
                f"Las personas de «{occ.room_name}» no pueden llegar a ninguna salida. Revise que "
                "el ambiente tenga una puerta y que las salidas estén dibujadas sobre un muro "
                "exterior (si quedan separadas del muro, el paso sigue cerrado)."
            )
        pick = rng.integers(0, rows.size, size=occ.count)
        centers = grid.cell_centers(rows[pick], cols[pick])
        jitter = rng.uniform(-0.45, 0.45, size=(occ.count, 2)) * grid.cell_size
        profile = profiles[profile_index[occ.profile_name]]
        factor = np.clip(rng.normal(1.0, params.speed_variation, size=occ.count), 0.7, 1.3)
        blocks.append(
            (
                centers + jitter,
                profile.max_speed_mps * factor,
                np.full(occ.count, profile.radius_m),
                sample_reaction_times(
                    rng, profile.reaction_mean_s, profile.reaction_std_s, occ.count
                ),
                np.full(occ.count, profile_index[occ.profile_name], dtype=np.int32),
            )
        )
    if not blocks:
        return AgentArrays.empty(0)
    agents = AgentArrays.empty(sum(len(b[0]) for b in blocks))
    agents.position[:] = np.vstack([b[0] for b in blocks])
    agents.max_speed[:] = np.concatenate([b[1] for b in blocks])
    agents.radius[:] = np.concatenate([b[2] for b in blocks])
    agents.reaction_time[:] = np.concatenate([b[3] for b in blocks])
    agents.profile_index[:] = np.concatenate([b[4] for b in blocks])
    return agents
