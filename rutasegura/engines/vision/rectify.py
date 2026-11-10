"""Rectificación de perspectiva para fotos torcidas: el usuario marca 4 esquinas."""

from __future__ import annotations

from collections.abc import Sequence

import cv2
import numpy as np
import numpy.typing as npt

from rutasegura.domain.geometry import Point
from rutasegura.engines.vision.images import RGBImage


def order_corners(corners: Sequence[Point]) -> npt.NDArray[np.float32]:
    """Ordena 4 puntos como sup-izq, sup-der, inf-der, inf-izq."""
    if len(corners) != 4:
        raise ValueError("Se necesitan exactamente 4 esquinas.")
    pts = np.array([[p.x, p.y] for p in corners], dtype=np.float32)
    sums = pts.sum(axis=1)
    diffs = pts[:, 1] - pts[:, 0]
    ordered = np.array(
        [pts[np.argmin(sums)], pts[np.argmin(diffs)], pts[np.argmax(sums)], pts[np.argmax(diffs)]],
        dtype=np.float32,
    )
    if len({tuple(p) for p in ordered.tolist()}) != 4:
        raise ValueError("Las 4 esquinas deben ser puntos distintos de un cuadrilátero.")
    area = 0.5 * abs(
        float(
            np.dot(ordered[:, 0], np.roll(ordered[:, 1], -1))
            - np.dot(ordered[:, 1], np.roll(ordered[:, 0], -1))
        )
    )
    if area < 100.0:
        raise ValueError("Las esquinas marcadas encierran un área demasiado pequeña.")
    return ordered


def rectify(image: RGBImage, corners: Sequence[Point]) -> RGBImage:
    """Endereza la zona encerrada por las 4 esquinas y la devuelve como imagen rectangular."""
    src = order_corners(corners)
    tl, tr, br, bl = src
    width = round(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
    height = round(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
    dst = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], np.float32)
    matrix = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(
        image,
        matrix,
        (width, height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )
    return np.ascontiguousarray(warped, dtype=np.uint8)
