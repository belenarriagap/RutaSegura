"""Proyecto: un local evaluado (colegio, oficina, tienda)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from rutasegura.domain.enums import UseType


@dataclass(frozen=True, slots=True)
class Project:
    """Datos generales del local."""

    name: str
    use: UseType
    address: str = ""
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("El proyecto necesita un nombre.")
