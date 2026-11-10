"""Primitivas geométricas 2D (en coordenadas del plano, normalmente píxeles)."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Point:
    """Punto 2D."""

    x: float
    y: float

    def distance_to(self, other: Point) -> float:
        """Distancia euclidiana a otro punto."""
        return math.hypot(self.x - other.x, self.y - other.y)


@dataclass(frozen=True, slots=True)
class Segment:
    """Segmento de recta entre dos puntos."""

    start: Point
    end: Point

    @property
    def length(self) -> float:
        """Longitud del segmento."""
        return self.start.distance_to(self.end)

    @property
    def midpoint(self) -> Point:
        """Punto medio del segmento."""
        return Point((self.start.x + self.end.x) / 2, (self.start.y + self.end.y) / 2)


@dataclass(frozen=True, slots=True)
class Polygon:
    """Polígono simple (sin autointersecciones), vértices en orden."""

    vertices: tuple[Point, ...]

    def __post_init__(self) -> None:
        if len(self.vertices) < 3:
            raise ValueError("Un polígono necesita al menos 3 vértices.")

    @property
    def area(self) -> float:
        """Área por la fórmula del lazo (shoelace), siempre positiva."""
        pts = self.vertices
        twice = sum(
            pts[i].x * pts[(i + 1) % len(pts)].y - pts[(i + 1) % len(pts)].x * pts[i].y
            for i in range(len(pts))
        )
        return abs(twice) / 2

    @property
    def centroid(self) -> Point:
        """Promedio de vértices (aproximación suficiente para ubicar etiquetas)."""
        n = len(self.vertices)
        return Point(
            sum(p.x for p in self.vertices) / n,
            sum(p.y for p in self.vertices) / n,
        )
