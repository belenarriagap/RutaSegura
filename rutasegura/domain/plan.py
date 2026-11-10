"""Plano de un piso: muros, puertas, salidas, escaleras, obstáculos y ambientes.

La geometría se guarda en coordenadas de la imagen (píxeles). La conversión a metros usa
``FloorPlan.scale_m_per_px``, que el usuario define en el paso de escala (RF04).
Las clases son inmutables: el editor crea versiones nuevas con ``dataclasses.replace``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rutasegura.domain.enums import UseType
from rutasegura.domain.geometry import Polygon, Segment


def _check_confidence(value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"La confianza debe estar entre 0 y 1 (se recibió {value}).")


@dataclass(frozen=True, slots=True)
class Wall:
    """Muro como segmento; ``confidence`` < 1 si lo detectó la visión."""

    segment: Segment
    confidence: float = 1.0

    def __post_init__(self) -> None:
        _check_confidence(self.confidence)


@dataclass(frozen=True, slots=True)
class Door:
    """Puerta interior representada por el segmento de su vano."""

    segment: Segment
    confidence: float = 1.0

    def __post_init__(self) -> None:
        _check_confidence(self.confidence)


@dataclass(frozen=True, slots=True)
class Exit:
    """Salida al exterior o a zona segura; siempre confirmada por el usuario."""

    segment: Segment
    name: str = ""


@dataclass(frozen=True, slots=True)
class Stair:
    """Escalera; ``connects_to_level`` es el piso al que lleva (RF12)."""

    area: Polygon
    connects_to_level: int | None = None


@dataclass(frozen=True, slots=True)
class Obstacle:
    """Obstáculo fijo que bloquea el paso (mobiliario, columnas)."""

    area: Polygon


@dataclass(frozen=True, slots=True)
class SafeZone:
    """Zona segura interna marcada por el usuario."""

    area: Polygon
    name: str = ""


@dataclass(frozen=True, slots=True)
class Room:
    """Ambiente con nombre y uso."""

    name: str
    use: UseType
    area: Polygon


@dataclass(frozen=True, slots=True)
class FloorPlan:
    """Plano completo de un piso."""

    level: int = 0
    image_path: str | None = None
    scale_m_per_px: float | None = None
    walls: tuple[Wall, ...] = field(default_factory=tuple)
    doors: tuple[Door, ...] = field(default_factory=tuple)
    exits: tuple[Exit, ...] = field(default_factory=tuple)
    stairs: tuple[Stair, ...] = field(default_factory=tuple)
    obstacles: tuple[Obstacle, ...] = field(default_factory=tuple)
    safe_zones: tuple[SafeZone, ...] = field(default_factory=tuple)
    rooms: tuple[Room, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.scale_m_per_px is not None and self.scale_m_per_px <= 0:
            raise ValueError("La escala debe ser positiva.")

    @property
    def is_scaled(self) -> bool:
        """Indica si el usuario ya definió la escala."""
        return self.scale_m_per_px is not None

    def to_meters(self, length_px: float) -> float:
        """Convierte una longitud en píxeles a metros."""
        if self.scale_m_per_px is None:
            raise ValueError("Primero define la escala del plano.")
        return length_px * self.scale_m_per_px

    def area_m2(self, polygon: Polygon) -> float:
        """Convierte el área de un polígono (px²) a m²."""
        if self.scale_m_per_px is None:
            raise ValueError("Primero define la escala del plano.")
        return polygon.area * self.scale_m_per_px**2
