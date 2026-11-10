"""Escenarios de simulación y simulacros reales."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from rutasegura.domain.people import Occupancy


@dataclass(frozen=True, slots=True)
class Scenario:
    """Escenario «qué pasa si»: ocupación, salidas bloqueadas y semilla.

    Toda la aleatoriedad de la simulación sale de ``numpy.random.default_rng(seed)``.
    """

    name: str
    seed: int
    occupancies: tuple[Occupancy, ...] = field(default_factory=tuple)
    blocked_exits: frozenset[int] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if self.seed < 0:
            raise ValueError("La semilla debe ser un entero no negativo.")

    @property
    def total_occupants(self) -> int:
        """Total de personas en el escenario."""
        return sum(o.count for o in self.occupancies)


@dataclass(frozen=True, slots=True)
class RealDrill:
    """Datos de un simulacro real, usados para calibrar (RF11)."""

    drill_date: date
    participants: int
    total_time_s: float
    time_per_exit_s: tuple[tuple[str, float], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.participants <= 0:
            raise ValueError("Debe haber al menos un participante.")
        if self.total_time_s <= 0:
            raise ValueError("El tiempo total debe ser positivo.")
