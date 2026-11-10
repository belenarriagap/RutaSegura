"""El script de evaluación de visión funciona con planos sintéticos y con un conjunto etiquetado."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from rutasegura.engines.vision.images import write_png
from tests.fixtures.synthetic_plans import generate_plan

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "eval_vision.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("eval_vision", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # las dataclasses del script buscan su módulo aquí
    spec.loader.exec_module(module)
    return module


def test_synthetic_evaluation_meets_target(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    script = _load_script()
    assert script.main(["--synthetic", "2", "--overlays", str(tmp_path)]) == 0
    assert "CUMPLE" in capsys.readouterr().out
    assert len(list(tmp_path.glob("*.png"))) == 2


def test_labeled_dataset_format(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    plan = generate_plan(5)
    write_png(tmp_path / "local_a.png", plan.image)

    def raw(segments: tuple) -> list[list[float]]:  # type: ignore[type-arg]
        return [[s.start.x, s.start.y, s.end.x, s.end.y] for s in segments]

    label = {
        "escala_m_por_px": plan.scale_m_per_px,
        "muros": raw(plan.walls),
        "puertas": raw(plan.doors),
        "salidas": raw(plan.exits),
    }
    (tmp_path / "local_a.json").write_text(json.dumps(label), encoding="utf-8")
    script = _load_script()
    assert script.main(["--dataset", str(tmp_path)]) == 0
    assert "local_a" in capsys.readouterr().out
