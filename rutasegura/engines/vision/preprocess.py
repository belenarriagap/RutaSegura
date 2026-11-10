"""Preprocesamiento: escala de grises, binarización adaptativa, limpieza y adelgazamiento."""

from __future__ import annotations

import itertools

import cv2
import numpy as np

from rutasegura.engines.vision.images import GrayImage, Mask, RGBImage


def to_gray(image: RGBImage) -> GrayImage:
    """RGB → escala de grises."""
    if image.ndim == 2:
        return np.ascontiguousarray(image, dtype=np.uint8)
    return np.ascontiguousarray(cv2.cvtColor(image, cv2.COLOR_RGB2GRAY), dtype=np.uint8)


def binarize(gray: GrayImage, *, min_component_px: int = 12) -> Mask:
    """Tinta = True. Umbral adaptativo (tolera iluminación desigual en fotos) + limpieza de ruido.

    La ventana del umbral es grande respecto del grosor de un muro para que los muros gruesos
    salgan rellenos y no huecos.
    """
    smoothed = cv2.medianBlur(gray, 3)
    block = max(31, (min(gray.shape) // 25) | 1)
    adaptive = cv2.adaptiveThreshold(
        smoothed, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, block, 15
    )
    # Regiones oscuras grandes (muros rellenos muy gruesos) que el umbral adaptativo vacía.
    otsu_value, _ = cv2.threshold(smoothed, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    dark = smoothed < otsu_value * 0.6
    mask = (adaptive > 0) | dark
    return remove_small_components(mask, min_component_px)


def remove_small_components(mask: Mask, min_area: int) -> Mask:
    """Elimina manchas conectadas de menos de ``min_area`` píxeles."""
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), connectivity=8
    )
    if count <= 1:
        return mask.copy()
    keep = stats[:, cv2.CC_STAT_AREA] >= min_area
    keep[0] = False
    return np.asarray(keep[labels], dtype=np.bool_)


def thin(mask: Mask) -> Mask:
    """Esqueleto de 1 píxel (Zhang-Suen vectorizado con NumPy; no requiere opencv-contrib)."""
    img = np.pad(mask.astype(np.uint8), 1)
    while True:
        changed = False
        for step in (0, 1):
            p2 = img[:-2, 1:-1]
            p3 = img[:-2, 2:]
            p4 = img[1:-1, 2:]
            p5 = img[2:, 2:]
            p6 = img[2:, 1:-1]
            p7 = img[2:, :-2]
            p8 = img[1:-1, :-2]
            p9 = img[:-2, :-2]
            center = img[1:-1, 1:-1]
            neighbours = [p2, p3, p4, p5, p6, p7, p8, p9, p2]
            count = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9
            transitions = sum(
                ((a == 0) & (b == 1)).astype(np.uint8) for a, b in itertools.pairwise(neighbours)
            )
            if step == 0:
                cond = (p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0)
            else:
                cond = (p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0)
            remove = (center == 1) & (count >= 2) & (count <= 6) & (transitions == 1) & cond
            if remove.any():
                changed = True
                center[remove] = 0
        if not changed:
            break
    return np.asarray(img[1:-1, 1:-1] == 1, dtype=np.bool_)


def estimate_wall_thickness(mask: Mask) -> float:
    """Estima el grosor típico de los muros (px) a partir de la transformada de distancia.

    Los muros son los trazos más gruesos y largos del plano: se toma un percentil alto del
    grosor medido sobre las crestas de la transformada de distancia.
    """
    if not mask.any():
        return 0.0
    dist = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)
    ridge = dist >= cv2.dilate(dist, np.ones((3, 3), np.uint8)) - 1e-6
    values = dist[ridge & (dist >= 1.5)]
    if values.size == 0:
        return float(2 * dist.max())
    return float(2.0 * np.percentile(values, 80))
