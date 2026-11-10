"""Evalúa la detección de muros y vanos (precisión y exhaustividad). Meta: ≥ 85 %.

Uso:
    uv run python scripts/eval_vision.py --synthetic 20
    uv run python scripts/eval_vision.py --dataset ruta/a/planos_etiquetados
    uv run python scripts/eval_vision.py --synthetic 5 --overlays salida/

Formato del conjunto etiquetado (ver docs/formato_etiquetas.md): por cada plano ``nombre.png``
(o .jpg/.pdf) un ``nombre.json`` con ``escala_m_por_px`` y listas ``muros``, ``puertas`` y
``salidas`` de segmentos ``[x1, y1, x2, y2]`` en píxeles de la imagen.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rutasegura.domain.geometry import Point, Segment  # noqa: E402
from rutasegura.engines.vision.images import RGBImage, load_plan_file, write_png  # noqa: E402
from rutasegura.engines.vision.metrics import opening_score, wall_score  # noqa: E402
from rutasegura.engines.vision.pipeline import DetectionResult, VisionParams, detect_plan  # noqa: E402

TARGET = 0.85
WALL_TOL_M = 0.2


@dataclass(frozen=True)
class Case:
    """Plano a evaluar con su verdad de referencia."""

    name: str
    image: RGBImage
    walls: tuple[Segment, ...]
    openings: tuple[Segment, ...]
    scale_m_per_px: float | None


def _segments(raw: list[list[float]]) -> tuple[Segment, ...]:
    return tuple(Segment(Point(a, b), Point(c, d)) for a, b, c, d in raw)


def synthetic_cases(count: int, first_seed: int) -> Iterator[Case]:
    from tests.fixtures.synthetic_plans import generate_plan

    for seed in range(first_seed, first_seed + count):
        plan = generate_plan(seed)
        yield Case(
            f"sintetico_{seed:03d}", plan.image, plan.walls, plan.openings, plan.scale_m_per_px
        )


def dataset_cases(folder: Path) -> Iterator[Case]:
    for label in sorted(folder.glob("*.json")):
        data = json.loads(label.read_text(encoding="utf-8"))
        image_path = next(
            (p for p in folder.glob(f"{label.stem}.*") if p.suffix.lower() != ".json"), None
        )
        if image_path is None:
            print(f"[aviso] {label.name}: no se encontró la imagen; se omite.")
            continue
        yield Case(
            label.stem,
            load_plan_file(image_path, int(data.get("pagina", 0))),
            _segments(data.get("muros", [])),
            _segments(data.get("puertas", [])) + _segments(data.get("salidas", [])),
            data.get("escala_m_por_px"),
        )


def draw_overlay(case: Case, result: DetectionResult) -> RGBImage:
    """Verdad en verde, detección en rojo (muros) y azul (vanos)."""
    img = case.image.copy()

    def line(seg: Segment, color: tuple[int, int, int], width: int) -> None:
        p1 = (round(seg.start.x), round(seg.start.y))
        p2 = (round(seg.end.x), round(seg.end.y))
        cv2.line(img, p1, p2, color, width, cv2.LINE_AA)

    for seg in case.walls + case.openings:
        line(seg, (0, 200, 0), 5)
    for wall in result.walls:
        line(wall.segment, (220, 0, 0), 2)
    for opening in [d.segment for d in result.doors] + [e.segment for e in result.exits]:
        line(opening, (0, 80, 255), 3)
    return np.ascontiguousarray(img, dtype=np.uint8)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--synthetic", type=int, default=0, help="cantidad de planos sintéticos")
    parser.add_argument("--first-seed", type=int, default=0)
    parser.add_argument("--dataset", type=Path, help="carpeta con planos etiquetados")
    parser.add_argument("--overlays", type=Path, help="carpeta donde guardar imágenes de control")
    args = parser.parse_args(argv)

    cases: list[Case] = []
    if args.synthetic:
        cases.extend(synthetic_cases(args.synthetic, args.first_seed))
    if args.dataset:
        cases.extend(dataset_cases(args.dataset))
    if not cases:
        parser.error("indique --synthetic N y/o --dataset CARPETA")

    rows = []
    print(f"{'plano':<22}{'muros P':>9}{'muros R':>9}{'vanos P':>9}{'vanos R':>9}")
    for case in cases:
        result = detect_plan(case.image, VisionParams(scale_m_per_px=case.scale_m_per_px))
        tol = WALL_TOL_M / case.scale_m_per_px if case.scale_m_per_px else 10.0
        walls = wall_score([w.segment for w in result.walls], case.walls, tol)
        predicted_openings = [d.segment for d in result.doors] + [e.segment for e in result.exits]
        openings = opening_score(predicted_openings, case.openings, tol)
        rows.append((walls.precision, walls.recall, openings.precision, openings.recall))
        print(
            f"{case.name:<22}{walls.precision:>9.1%}{walls.recall:>9.1%}"
            f"{openings.precision:>9.1%}{openings.recall:>9.1%}"
        )
        if args.overlays:
            write_png(args.overlays / f"{case.name}.png", draw_overlay(case, result))

    means = np.mean(np.array(rows), axis=0)
    print("-" * 58)
    print(f"{'PROMEDIO':<22}" + "".join(f"{m:>9.1%}" for m in means))
    ok = bool((means >= TARGET).all())
    print(f"Meta ≥ {TARGET:.0%} en las cuatro métricas: {'CUMPLE' if ok else 'NO CUMPLE'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
