"""Motor de simulación: población, vecinos, movimiento, métricas y cuellos de botella."""

from __future__ import annotations

import math

import numpy as np
import pytest

from rutasegura.domain.enums import AgentStatus
from rutasegura.domain.people import Occupancy
from rutasegura.engines.navigation.grid import build_grid
from rutasegura.engines.simulation.engine import SimulationCancelled, bilinear
from rutasegura.engines.simulation.neighbors import neighbor_pairs
from rutasegura.engines.simulation.params import SimulationParams
from rutasegura.engines.simulation.population import (
    PopulationError,
    lognormal_params,
    sample_reaction_times,
)
from tests.fixtures.simple_plans import room_with_patio, single_room, two_rooms
from tests.unit.engines.simulation.helpers import make_simulation


class TestPopulation:
    def test_lognormal_matches_mean_and_std(self) -> None:
        rng = np.random.default_rng(0)
        samples = sample_reaction_times(rng, 30.0, 10.0, 200_000)
        assert samples.mean() == pytest.approx(30.0, rel=0.02)
        assert samples.std() == pytest.approx(10.0, rel=0.05)
        assert (samples > 0).all()
        mu, sigma = lognormal_params(30.0, 0.0)
        assert sigma == 0.0
        assert math.exp(mu) == pytest.approx(30.0)

    def test_degenerate_reaction_times(self) -> None:
        rng = np.random.default_rng(0)
        assert (sample_reaction_times(rng, 0.0, 5.0, 3) == 0).all()
        assert (sample_reaction_times(rng, 4.0, 0.0, 3) == 4.0).all()
        assert sample_reaction_times(rng, 4.0, 1.0, 0).size == 0

    def test_agents_start_inside_their_room(self) -> None:
        sim = make_simulation(two_rooms(), [Occupancy("Aula 1", "niño", 30)])
        assert len(sim.agents) == 30
        xs = sim.agents.position[:, 0]
        assert (xs > 0).all()
        assert (xs < 6).all()
        assert (sim.agents.status == AgentStatus.WAITING).all()
        assert (sim.agents.radius == 0.2).all()

    def test_population_errors(self) -> None:
        with pytest.raises(PopulationError, match="Aula 9"):
            make_simulation(single_room(), [Occupancy("Aula 9", "adulto", 1)])
        with pytest.raises(PopulationError, match="astronauta"):
            make_simulation(single_room(), [Occupancy("Aula 1", "astronauta", 1)])
        with pytest.raises(PopulationError, match="salida alcanzable"):
            make_simulation(single_room(), [Occupancy("Aula 1", "adulto", 1)], blocked={"Salida 1"})

    def test_no_occupants(self) -> None:
        sim = make_simulation(single_room(), [Occupancy("Aula 1", "adulto", 0)])
        out = sim.run()
        assert out.result.agents_total == 0
        assert out.result.total_time_s == 0.0
        assert out.result.completed


class TestNeighbors:
    def test_pairs_match_brute_force(self) -> None:
        rng = np.random.default_rng(3)
        pos = rng.uniform(0, 10, size=(300, 2))
        cutoff = 1.0
        i, j = neighbor_pairs(pos, cutoff)
        found = {
            (int(a), int(b))
            for a, b in zip(i, j, strict=True)
            if np.linalg.norm(pos[a] - pos[b]) < cutoff
        }
        diff = pos[:, None, :] - pos[None, :, :]
        close = np.argwhere((np.linalg.norm(diff, axis=2) < cutoff) & ~np.eye(300, dtype=bool))
        expected = {(int(a), int(b)) for a, b in close}
        assert found == expected

    def test_trivial_inputs(self) -> None:
        i, j = neighbor_pairs(np.zeros((1, 2)), 1.0)
        assert i.size == 0
        assert j.size == 0


class TestMovement:
    def test_everyone_evacuates_single_room(self) -> None:
        sim = make_simulation(single_room(), [Occupancy("Aula 1", "adulto", 20)])
        progress: list[float] = []
        out = sim.run(progress=progress.append)
        result = out.result
        assert result.completed
        assert result.agents_evacuated == 20
        assert progress[-1] == 1.0
        assert progress == sorted(progress)
        # nadie sale antes de reaccionar y de recorrer su distancia a velocidad máxima
        assert np.all(out.evacuation_time_s >= sim.agents.reaction_time)
        assert result.time_per_exit_s[0][0] == "Salida 1"
        assert result.total_time_s == pytest.approx(result.time_per_exit_s[0][1])
        assert result.curve_evacuated[-1] == 20
        assert np.all(np.diff(result.curve_evacuated) >= 0)
        assert out.trajectories.frame_count == len(result.curve_times_s)

    def test_agents_never_walk_through_walls(self) -> None:
        sim = make_simulation(two_rooms(), [Occupancy("Aula 1", "niño", 40)])
        walkable = sim.grid.walkable
        while not sim.finished:
            sim.step()
            active = sim.agents.status != AgentStatus.EVACUATED
            r, c = sim.grid.to_cell(sim.agents.position[active])
            assert walkable[r, c].all()
        assert sim.agents.evacuated_count == 40

    def test_second_exit_reduces_time(self) -> None:
        occ = [Occupancy("Aula 1", "adulto", 60)]
        one = make_simulation(single_room(exit_width=0.9), occ).run().result
        two = make_simulation(single_room(exit_width=0.9, second_exit=True), occ).run().result
        assert two.total_time_s < one.total_time_s
        assert {name for name, _ in two.time_per_exit_s} == {"Salida 1", "Salida 2"}

    def test_safe_zone_evacuation(self) -> None:
        out = make_simulation(room_with_patio(), [Occupancy("Aula 1", "adulto", 10)]).run()
        assert out.result.completed
        assert out.result.time_per_exit_s[0][0] == "Patio"

    def test_time_limit_marks_incomplete(self) -> None:
        params = SimulationParams(max_time_s=3.0)
        out = make_simulation(two_rooms(), [Occupancy("Aula 1", "adulto", 20)], params=params).run()
        assert not out.result.completed
        assert out.result.total_time_s == pytest.approx(3.0)
        assert out.result.agents_evacuated < 20

    def test_cancellation(self) -> None:
        sim = make_simulation(single_room(), [Occupancy("Aula 1", "adulto", 10)])
        with pytest.raises(SimulationCancelled):
            sim.run(should_cancel=lambda: True)

    def test_crowding_creates_bottleneck_near_exit(self) -> None:
        params = SimulationParams(congestion_min_duration_s=2.0)
        plan = single_room(exit_width=0.8)
        out = make_simulation(plan, [Occupancy("Aula 1", "adulto", 80)], params=params).run()
        bottlenecks = out.result.bottlenecks
        assert bottlenecks
        worst = bottlenecks[0]
        assert worst.location.x > 7.0  # cerca de la salida (x = 10 m)
        assert worst.mean_density >= params.congestion_density
        assert [b.severity for b in bottlenecks] == sorted(
            (b.severity for b in bottlenecks), reverse=True
        )
        assert out.result.density_map.max() > 0


def test_bilinear_interpolation() -> None:
    grid = build_grid(single_room())
    rows, cols = grid.shape
    xs = grid.origin[0] + (np.arange(cols) + 0.5) * grid.cell_size
    field = np.tile(xs, (rows, 1))  # campo igual a x
    pts = np.array([[3.3, 2.0], [7.71, 4.4]])
    assert bilinear(field, grid, pts) == pytest.approx(pts[:, 0])
    vector = np.stack([field, field * 2], axis=2)
    assert bilinear(vector, grid, pts)[:, 1] == pytest.approx(2 * pts[:, 0])


def test_params_validation() -> None:
    with pytest.raises(ValueError, match="positivos"):
        SimulationParams(dt_s=0)
    with pytest.raises(ValueError, match="cuadros"):
        SimulationParams(record_every_s=0.01)
    with pytest.raises(ValueError, match="factor"):
        SimulationParams(min_speed_factor=0)
