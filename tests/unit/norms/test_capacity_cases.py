"""Los 10 casos de aforo de ``casos_aforo.yaml`` (resultados esperados por confirmar)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from rutasegura.domain.enums import UseType
from rutasegura.domain.plan import FloorPlan, Room
from rutasegura.engines.norms.evaluate import evaluate
from tests.fixtures.simple_plans import SCALE, rect
from tests.unit.norms.helpers import packaged_rules

CASES: list[dict[str, Any]] = yaml.safe_load(
    (Path(__file__).parent / "casos_aforo.yaml").read_text(encoding="utf-8")
)["casos"]


def test_there_are_ten_cases() -> None:
    assert len(CASES) == 10
    assert len({c["id"] for c in CASES}) == 10


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_capacity_case(case: dict[str, Any]) -> None:
    room = Room(
        "Ambiente",
        UseType(case["uso"]),
        rect(0, 0, float(case["ancho_m"]), float(case["largo_m"])),
        case["categoria"],
    )
    plan = FloorPlan(scale_m_per_px=SCALE, rooms=(room,))
    result = evaluate(plan, (), packaged_rules())
    capacity = result.capacities[0]
    assert capacity.category == case["categoria"]
    assert capacity.capacity == case["aforo_esperado"], case["descripcion"]
