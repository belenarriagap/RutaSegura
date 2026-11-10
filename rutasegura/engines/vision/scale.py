"""Escala del plano a partir de una medida conocida (RF04)."""

from __future__ import annotations

from rutasegura.domain.geometry import Point


def scale_from_reference(p1: Point, p2: Point, meters: float) -> float:
    """Metros por píxel, dada la distancia real entre dos puntos marcados por el usuario."""
    if meters <= 0:
        raise ValueError("La medida real debe ser mayor que cero.")
    pixels = p1.distance_to(p2)
    if pixels < 1.0:
        raise ValueError("Los dos puntos están demasiado cerca; márquelos más separados.")
    return meters / pixels
