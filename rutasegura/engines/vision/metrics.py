"""Métricas de precisión y exhaustividad de la detección (objetivo ≥ 85 %)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from rutasegura.domain.geometry import Segment


@dataclass(frozen=True, slots=True)
class Score:
    """Precisión (lo detectado es correcto) y exhaustividad (se detectó lo que hay)."""

    precision: float
    recall: float

    @property
    def f1(self) -> float:
        """Media armónica."""
        total = self.precision + self.recall
        return 0.0 if total == 0 else 2 * self.precision * self.recall / total


def _sample(segments: Sequence[Segment], step: float) -> npt.NDArray[np.float64]:
    points = []
    for seg in segments:
        n = max(2, int(np.ceil(seg.length / step)) + 1)
        t = np.linspace(0.0, 1.0, n)
        xs = seg.start.x + t * (seg.end.x - seg.start.x)
        ys = seg.start.y + t * (seg.end.y - seg.start.y)
        points.append(np.column_stack([xs, ys]))
    return np.vstack(points) if points else np.zeros((0, 2))


def _distance_to_segments(
    points: npt.NDArray[np.float64], segments: Sequence[Segment]
) -> npt.NDArray[np.float64]:
    """Distancia mínima de cada punto a cualquiera de los segmentos."""
    if not segments:
        return np.full(len(points), np.inf)
    a = np.array([[s.start.x, s.start.y] for s in segments])
    b = np.array([[s.end.x, s.end.y] for s in segments])
    ab = b - a
    len2 = np.maximum((ab**2).sum(axis=1), 1e-12)
    ap = points[:, None, :] - a[None, :, :]
    t = np.clip((ap * ab[None]).sum(axis=2) / len2[None], 0.0, 1.0)
    closest = a[None] + t[..., None] * ab[None]
    dist = np.hypot(*(points[:, None, :] - closest).transpose(2, 0, 1))
    return np.asarray(dist.min(axis=1), dtype=np.float64)


def coverage(source: Sequence[Segment], reference: Sequence[Segment], tol: float) -> float:
    """Fracción de la longitud de ``source`` que está a menos de ``tol`` de ``reference``."""
    points = _sample(source, step=max(tol / 2, 1.0))
    if len(points) == 0:
        return 1.0 if not reference else 0.0
    return float((_distance_to_segments(points, reference) <= tol).mean())


def wall_score(predicted: Sequence[Segment], truth: Sequence[Segment], tol: float) -> Score:
    """Precisión y exhaustividad por longitud de muro, con tolerancia ``tol`` px."""
    return Score(precision=coverage(predicted, truth, tol), recall=coverage(truth, predicted, tol))


def opening_score(predicted: Sequence[Segment], truth: Sequence[Segment], tol: float) -> Score:
    """Precisión y exhaustividad de vanos (puertas y salidas) con emparejamiento uno a uno.

    Un vano detectado corresponde a uno real si sus puntos medios están a menos de
    ``tol + ancho_real / 2``.
    """
    if not predicted and not truth:
        return Score(1.0, 1.0)
    pairs = []
    for i, p in enumerate(predicted):
        for j, t in enumerate(truth):
            d = p.midpoint.distance_to(t.midpoint)
            if d <= tol + t.length / 2:
                pairs.append((d, i, j))
    used_p: set[int] = set()
    used_t: set[int] = set()
    for _, i, j in sorted(pairs):
        if i not in used_p and j not in used_t:
            used_p.add(i)
            used_t.add(j)
    matched = len(used_p)
    precision = matched / len(predicted) if predicted else 1.0
    recall = matched / len(truth) if truth else 1.0
    return Score(precision, recall)
