"""RNF02: ≥ 20 pasos de simulación por segundo con 500 agentes (solo el motor, sin render).

Ejecutar con detalle:  uv run pytest tests/benchmarks -m benchmark -s
"""

from __future__ import annotations

import time

import pytest

from rutasegura.domain.people import Occupancy
from rutasegura.domain.plan import FloorPlan
from tests.fixtures.simple_plans import single_room
from tests.unit.engines.simulation.helpers import make_simulation

MIN_STEPS_PER_SECOND_500 = 20.0
STEPS = 50


def _big_room() -> FloorPlan:
    # 30 × 20 m con dos salidas: cabe holgadamente 1000 personas
    return single_room(width=30.0, height=20.0, exit_width=1.8, second_exit=True)


def steps_per_second(agents: int) -> float:
    """Pasos por segundo con todos los agentes en movimiento."""
    sim = make_simulation(_big_room(), [Occupancy("Aula 1", "adulto", agents)], seed=5)
    sim.agents.reaction_time[:] = 0.0
    for _ in range(3):  # calentamiento
        sim.step()
    start = time.perf_counter()
    for _ in range(STEPS):
        sim.step()
    return STEPS / (time.perf_counter() - start)


@pytest.mark.benchmark
@pytest.mark.parametrize("agents", [100, 300, 500, 1000])
def test_engine_speed(agents: int) -> None:
    rate = steps_per_second(agents)
    print(f"\n{agents:>5} agentes: {rate:8.1f} pasos/s")
    if agents == 500:
        assert rate >= MIN_STEPS_PER_SECOND_500
