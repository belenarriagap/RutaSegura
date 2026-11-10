"""Perfiles de personas y ocupación de ambientes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PersonProfile:
    """Perfil de movimiento (adulto, niño, movilidad reducida...).

    Los valores por defecto y sus fuentes se definen en el Hito 1 (catálogo en la base de datos).
    """

    name: str
    max_speed_mps: float
    reaction_mean_s: float
    reaction_std_s: float
    radius_m: float

    def __post_init__(self) -> None:
        if self.max_speed_mps <= 0:
            raise ValueError("La velocidad máxima debe ser positiva.")
        if self.reaction_mean_s < 0 or self.reaction_std_s < 0:
            raise ValueError("Los tiempos de reacción no pueden ser negativos.")
        if self.radius_m <= 0:
            raise ValueError("El radio debe ser positivo.")


@dataclass(frozen=True, slots=True)
class Occupancy:
    """Cantidad de personas de un perfil en un ambiente."""

    room_name: str
    profile_name: str
    count: int

    def __post_init__(self) -> None:
        if self.count < 0:
            raise ValueError("La cantidad de ocupantes no puede ser negativa.")
