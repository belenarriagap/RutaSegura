"""RNF07: misma semilla ⇒ mismo resultado bit a bit."""

from __future__ import annotations

import numpy as np

from rutasegura.domain.people import Occupancy
from tests.fixtures.simple_plans import two_rooms
from tests.unit.engines.simulation.helpers import make_simulation

OCCUPANCY = [Occupancy("Aula 1", "niño", 35), Occupancy("Aula 2", "adulto", 25)]


def _run(seed: int):  # type: ignore[no-untyped-def]
    return make_simulation(two_rooms(), OCCUPANCY, seed=seed).run()


def test_same_seed_gives_identical_results() -> None:
    a, b = _run(42), _run(42)
    assert a.result.total_time_s == b.result.total_time_s
    assert a.result.time_per_exit_s == b.result.time_per_exit_s
    assert a.result.bottlenecks == b.result.bottlenecks
    for x, y in (
        (a.trajectories.positions, b.trajectories.positions),
        (a.trajectories.status, b.trajectories.status),
        (a.result.density_map, b.result.density_map),
        (a.result.curve_evacuated, b.result.curve_evacuated),
        (a.evacuation_time_s, b.evacuation_time_s),
        (a.exit_index, b.exit_index),
    ):
        assert x.dtype == y.dtype
        assert x.tobytes() == y.tobytes()  # igualdad bit a bit


def test_different_seed_gives_different_results() -> None:
    a, b = _run(1), _run(2)
    assert not np.array_equal(a.trajectories.positions[0], b.trajectories.positions[0])
