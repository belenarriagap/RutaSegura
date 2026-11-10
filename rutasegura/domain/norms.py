"""Resultados de la verificación normativa (RF06)."""

from __future__ import annotations

from dataclasses import dataclass, field

from rutasegura.domain.results import Observation


@dataclass(frozen=True, slots=True)
class NormRule:
    """Regla normativa aplicada (para citarla y advertir si no está verificada)."""

    id: str
    kind: str
    description: str
    norm: str
    article: str
    verified: bool

    @property
    def citation(self) -> str:
        """Cita corta: «RNE A.130, Art. 22»."""
        return f"{self.norm}, {self.article}"


@dataclass(frozen=True, slots=True)
class RoomCapacity:
    """Aforo de un ambiente: área útil ÷ índice de ocupación de su categoría."""

    room_name: str
    level: int
    category: str
    category_label: str
    area_m2: float
    m2_per_person: float | None  # None = la categoría no tiene índice (p. ej. pasillo)
    capacity: int | None
    occupants: int
    rule_id: str | None

    @property
    def exceeded(self) -> bool:
        """Hay más ocupantes que el aforo calculado."""
        return self.capacity is not None and self.occupants > self.capacity


@dataclass(frozen=True, slots=True)
class NormEvaluation:
    """Aforo por ambiente, observaciones normativas y reglas usadas."""

    capacities: tuple[RoomCapacity, ...] = field(default_factory=tuple)
    observations: tuple[Observation, ...] = field(default_factory=tuple)
    rules_used: tuple[NormRule, ...] = field(default_factory=tuple)

    @property
    def total_capacity(self) -> int:
        """Suma de aforos de los ambientes con índice."""
        return sum(c.capacity or 0 for c in self.capacities)

    @property
    def total_occupants(self) -> int:
        """Ocupantes asignados en total."""
        return sum(c.occupants for c in self.capacities)

    @property
    def unverified_rules(self) -> tuple[NormRule, ...]:
        """Reglas usadas que aún no se contrastaron con el texto oficial."""
        return tuple(r for r in self.rules_used if not r.verified)
