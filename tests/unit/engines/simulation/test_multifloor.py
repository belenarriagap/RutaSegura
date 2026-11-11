"""Evacuación de varios pisos por escaleras (RF12)."""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from rutasegura.domain.enums import AgentStatus
from rutasegura.domain.people import Occupancy
from rutasegura.domain.plan import Stair
from rutasegura.engines.navigation.grid import build_grid
from rutasegura.engines.simulation.multifloor import (
    IN_STAIRS,
    MultiFloorError,
    MultiFloorSimulation,
    pair_stairs,
    stair_width_m,
)
from rutasegura.engines.simulation.params import SimulationParams
from tests.fixtures.simple_plans import rect, two_floor_building
from tests.unit.engines.simulation.helpers import PROFILES

PARAMS = SimulationParams()


def _sim(occupancies: list[Occupancy], *, seed: int = 3, **kwargs: object) -> MultiFloorSimulation:
    ground, upper = two_floor_building(**kwargs)  # type: ignore[arg-type]
    return MultiFloorSimulation([upper, ground], occupancies, PROFILES, PARAMS, seed=seed)


class TestStairs:
    def test_stairs_are_targets_only_on_upper_floors(self) -> None:
        ground, upper = two_floor_building()
        assert build_grid(ground).target_names == ("Salida 1",)
        upper_grid = build_grid(upper, stairs_as_targets=True)
        assert upper_grid.target_names == ("Escalera A",)
        assert upper_grid.stair_of(0) == 0
        assert build_grid(ground, stairs_as_targets=False).stair_of(0) == -1

    def test_pairing_by_name_and_single_fallback(self) -> None:
        ground, upper = two_floor_building()
        assert pair_stairs(upper, ground) == {0: 0}
        renamed = dataclasses.replace(
            ground, stairs=(dataclasses.replace(ground.stairs[0], name="Otra"),)
        )
        assert pair_stairs(upper, renamed) == {0: 0}  # única escalera abajo
        two_below = dataclasses.replace(
            ground,
            stairs=(
                Stair(rect(0.5, 0.5, 1.2, 2), name="Norte"),
                Stair(rect(7, 0.5, 1.2, 2), name="Sur"),
            ),
        )
        with pytest.raises(MultiFloorError, match="no tiene una escalera correspondiente"):
            pair_stairs(upper, two_below)

    def test_stair_width(self) -> None:
        ground, _ = two_floor_building(stair_width=1.5)
        assert stair_width_m(ground, 0) == pytest.approx(1.5, abs=0.01)


class TestEvacuation:
    def test_upper_floor_goes_down_and_everyone_leaves(self) -> None:
        sim = _sim([Occupancy("Aula 201", "adulto", 20, level=1), Occupancy("Hall", "niño", 10)])
        out = sim.run()
        result = out.result
        assert result.completed
        assert result.agents_evacuated == 30
        assert result.time_per_exit_s[0][0] == "Salida 1"
        levels = out.trajectories.level
        assert levels is not None
        assert {int(v) for v in np.unique(levels)} == {IN_STAIRS, 0, 1}
        assert [m.level for m in result.floor_maps] == [0, 1]
        assert result.curve_evacuated[-1] == 30

    def test_agents_stay_inside_walls_on_every_floor(self) -> None:
        sim = _sim([Occupancy("Aula 201", "adulto", 25, level=1)])
        while not sim.finished:
            sim.step()
            for level, floor in sim.sims.items():
                here = (sim.level == level) & (floor.agents.status != AgentStatus.EVACUATED)
                r, c = floor.grid.to_cell(floor.agents.position[here])
                assert floor.grid.walkable[r, c].all()
        assert sim.evacuated == 25

    def test_upper_floor_takes_longer_than_ground(self) -> None:
        ground_only = _sim([Occupancy("Hall", "adulto", 15)]).run().result
        upstairs = _sim([Occupancy("Aula 201", "adulto", 15, level=1)]).run().result
        travel = PARAMS.stair_travel_m / (1.3 * 1.3 * PARAMS.stair_speed_factor)
        assert upstairs.total_time_s > ground_only.total_time_s + travel * 0.5

    def test_narrow_stair_limits_the_flow(self) -> None:
        people = [Occupancy("Aula 201", "adulto", 60, level=1)]
        wide = _sim(people, stair_width=2.0).run().result
        narrow = _sim(people, stair_width=0.6).run().result
        assert narrow.total_time_s > wide.total_time_s
        # 60 personas por una escalera de 0.6 m: al menos 60 / (1.1 · 0.6) s de cola
        assert narrow.total_time_s >= 60 / (PARAMS.stair_specific_flow * 0.6)

    def test_reproducible(self) -> None:
        people = [Occupancy("Aula 201", "adulto", 20, level=1), Occupancy("Hall", "niño", 5)]
        a, b = _sim(people, seed=9).run(), _sim(people, seed=9).run()
        assert a.result.total_time_s == b.result.total_time_s
        assert a.trajectories.positions.tobytes() == b.trajectories.positions.tobytes()
        assert a.trajectories.level is not None
        assert b.trajectories.level is not None
        assert a.trajectories.level.tobytes() == b.trajectories.level.tobytes()

    def test_bottlenecks_carry_their_floor(self) -> None:
        params = dataclasses.replace(PARAMS, congestion_min_duration_s=2.0)
        ground, upper = two_floor_building(stair_width=0.6)
        sim = MultiFloorSimulation(
            [ground, upper],
            [Occupancy("Aula 201", "adulto", 80, level=1)],
            PROFILES,
            params,
            seed=1,
        )
        result = sim.run().result
        assert result.bottlenecks
        assert {b.level for b in result.bottlenecks} <= {0, 1}
        assert any(b.level == 1 for b in result.bottlenecks)  # cola en la escalera de arriba


class TestErrors:
    def test_lower_floor_without_stair(self) -> None:
        ground, upper = two_floor_building()
        no_stair = dataclasses.replace(ground, stairs=())
        with pytest.raises(MultiFloorError, match="no tiene una escalera correspondiente"):
            MultiFloorSimulation([no_stair, upper], [], PROFILES, PARAMS, seed=1)

    def test_upper_floor_without_stairs_or_exits(self) -> None:
        ground, upper = two_floor_building()
        trapped = dataclasses.replace(upper, stairs=())
        with pytest.raises(MultiFloorError, match="Piso 2"):
            MultiFloorSimulation(
                [ground, trapped],
                [Occupancy("Aula 201", "adulto", 3, level=1)],
                PROFILES,
                PARAMS,
                seed=1,
            )

    def test_floor_limits(self) -> None:
        ground, upper = two_floor_building()
        with pytest.raises(MultiFloorError, match="consecutivos"):
            MultiFloorSimulation(
                [ground, dataclasses.replace(upper, level=2)], [], PROFILES, PARAMS, seed=1
            )
        floors = [dataclasses.replace(upper, level=k) for k in range(1, 5)] + [ground]
        with pytest.raises(MultiFloorError, match="hasta 4 pisos"):
            MultiFloorSimulation(floors, [], PROFILES, PARAMS, seed=1)
        with pytest.raises(MultiFloorError, match="escala"):
            MultiFloorSimulation(
                [ground, dataclasses.replace(upper, scale_m_per_px=None)],
                [],
                PROFILES,
                PARAMS,
                seed=1,
            )
        with pytest.raises(MultiFloorError, match="No hay pisos"):
            MultiFloorSimulation([], [], PROFILES, PARAMS, seed=1)
