"""Preparación común de simulaciones para las pruebas."""

from __future__ import annotations

from collections.abc import Collection, Sequence

import numpy as np

from rutasegura.domain.people import Occupancy, PersonProfile
from rutasegura.domain.plan import FloorPlan
from rutasegura.engines.navigation.fields import distance_field
from rutasegura.engines.navigation.grid import build_grid, polygon_to_m
from rutasegura.engines.simulation.engine import Simulation
from rutasegura.engines.simulation.params import SimulationParams
from rutasegura.engines.simulation.population import RoomArea, spawn_agents

PROFILES = (
    PersonProfile("adulto", 1.3, 5.0, 2.0, 0.25),
    PersonProfile("niño", 1.0, 3.0, 1.0, 0.2),
)


def make_simulation(
    plan: FloorPlan,
    occupancies: Sequence[Occupancy],
    *,
    seed: int = 1,
    params: SimulationParams | None = None,
    blocked: Collection[str] = (),
    profiles: Sequence[PersonProfile] = PROFILES,
) -> Simulation:
    """Grilla + agentes + simulación lista para correr."""
    params = params or SimulationParams()
    scale = plan.scale_m_per_px
    assert scale is not None
    grid = build_grid(plan, blocked_exits=blocked)
    dist = distance_field(grid.walkable, grid.targets, grid.cell_size)
    rooms = [RoomArea(r.name, plan.level, polygon_to_m(r.area, scale)) for r in plan.rooms]
    rng = np.random.default_rng(seed)
    agents = spawn_agents(grid, dist, rooms, occupancies, profiles, rng, params)
    return Simulation(
        grid, agents, params, seed=seed, profile_names=[p.name for p in profiles], distance=dist
    )
