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
    """Resultado agregado de una corrida. Las trayectorias van en un archivo binario aparte.

    ``density_map`` es la densidad acumulada por celda de la grilla (personas·s/m²); la celda
    (0, 0) empieza en ``grid_origin_m`` y mide ``cell_size_m``. ``completed`` es falso si se
    alcanzó el tiempo máximo con personas todavía dentro.
    """

    seed: int
    total_time_s: float
    time_per_exit_s: tuple[tuple[str, float], ...]
    curve_times_s: npt.NDArray[np.float64]  # (k,)
    curve_evacuated: npt.NDArray[np.int32]  # (k,) evacuados acumulados
    density_map: npt.NDArray[np.float64]  # (filas, columnas)
    bottlenecks: tuple[Bottleneck, ...] = field(default_factory=tuple)
    trajectories_path: str | None = None
    agents_total: int = 0
    agents_evacuated: int = 0
    completed: bool = True
    grid_origin_m: tuple[float, float] = (0.0, 0.0)
    cell_size_m: float = 0.4

    def __post_init__(self) -> None:
        if self.curve_times_s.shape != self.curve_evacuated.shape:
            raise ValueError("La curva de evacuados necesita tiempos y conteos del mismo largo.")

    def time_to_evacuate(self, fraction: float) -> float | None:
        """Primer instante registrado en que salió al menos ``fraction`` de las personas.

        Complementa al tiempo total, que suele depender de la persona que reacciona más tarde.
        ``None`` si esa fracción nunca se alcanzó.
        """
        if not 0 < fraction <= 1:
            raise ValueError("La fracción debe estar entre 0 y 1.")
        needed = fraction * self.agents_total
        reached = np.flatnonzero(self.curve_evacuated >= needed - 1e-9)
        if self.agents_total == 0 or reached.size == 0:
            return None
        return float(self.curve_times_s[reached[0]])


@dataclass(frozen=True, eq=False, slots=True)
class Trajectories:
    """Posiciones registradas cada cierto tiempo, para reproducir la animación.

    ``positions`` está en metros, con forma (cuadros, agentes, 2); ``status`` usa
    ``AgentStatus``. ``profile_index`` indexa ``profile_names``.
    """

    times_s: npt.NDArray[np.float64]  # (cuadros,)
    positions: npt.NDArray[np.float32]  # (cuadros, agentes, 2)
    status: npt.NDArray[np.int8]  # (cuadros, agentes)
    radius_m: npt.NDArray[np.float32]  # (agentes,)
    profile_index: npt.NDArray[np.int32]  # (agentes,)
    profile_names: tuple[str, ...]

    def __post_init__(self) -> None:
        frames, agents = self.status.shape
        if self.positions.shape != (frames, agents, 2) or self.times_s.shape != (frames,):
            raise ValueError("Las trayectorias tienen dimensiones inconsistentes.")
        if self.radius_m.shape != (agents,) or self.profile_index.shape != (agents,):
            raise ValueError("Las trayectorias tienen dimensiones inconsistentes.")

    @property
    def frame_count(self) -> int:
        """Cantidad de cuadros."""
        return int(self.times_s.shape[0])

    @property
    def agent_count(self) -> int:
        """Cantidad de agentes."""
        return int(self.status.shape[1])


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
