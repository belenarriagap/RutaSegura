"""Resultados de simulación y observaciones del informe."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import numpy.typing as npt

from rutasegura.domain.enums import ObservationType
from rutasegura.domain.geometry import Point


@dataclass(frozen=True, slots=True)
class Bottleneck:
    """Zona con densidad alta sostenida."""

    location: Point  # metros
    mean_density: float  # personas/m²
    duration_s: float
    severity: float  # mayor = peor; se usa para ordenar el ranking


@dataclass(frozen=True, eq=False, slots=True)
class SimulationResult:
    """Resultado agregado de una corrida. Las trayectorias van en un archivo binario aparte."""

    seed: int
    total_time_s: float
    time_per_exit_s: tuple[tuple[str, float], ...]
    curve_times_s: npt.NDArray[np.float64]  # (k,)
    curve_evacuated: npt.NDArray[np.int32]  # (k,) evacuados acumulados
    density_map: npt.NDArray[np.float64]  # (filas, columnas) densidad acumulada por celda
    bottlenecks: tuple[Bottleneck, ...] = field(default_factory=tuple)
    trajectories_path: str | None = None

    def __post_init__(self) -> None:
        if self.curve_times_s.shape != self.curve_evacuated.shape:
            raise ValueError("La curva de evacuados necesita tiempos y conteos del mismo largo.")


@dataclass(frozen=True, slots=True)
class SimulationSummary:
    """Resumen guardado de una corrida (sin arrays), para listados y comparaciones."""

    seed: int
    total_time_s: float
    time_per_exit_s: tuple[tuple[str, float], ...]
    trajectories_path: str | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Observation:
    """Observación del informe, normativa o de congestión.

    Las normativas siempre citan norma y artículo; ``verified`` es falso si la regla usada aún
    no fue contrastada con el texto oficial (el informe debe advertirlo).
    """

    kind: ObservationType
    description: str
    recommendation: str
    location: Point | None = None
    norm: str | None = None
    article: str | None = None
    verified: bool = True

    def __post_init__(self) -> None:
        if self.kind is ObservationType.NORM and not (self.norm and self.article):
            raise ValueError("Una observación normativa debe citar norma y artículo.")
