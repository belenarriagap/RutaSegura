"""Archivo binario de una corrida (.npz comprimido): trayectorias y arrays del resultado.

SQLite guarda solo el resumen (tabla ``simulacion``) y la ruta a este archivo.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt

from rutasegura.domain.geometry import Point
from rutasegura.domain.results import Bottleneck, SimulationResult, Trajectories

FORMAT_VERSION = 1


@dataclass(frozen=True, eq=False)
class StoredRun:
    """Contenido del archivo de una corrida."""

    trajectories: Trajectories
    curve_times_s: npt.NDArray[np.float64]
    curve_evacuated: npt.NDArray[np.int32]
    density_map: npt.NDArray[np.float64]
    bottlenecks: tuple[Bottleneck, ...]
    grid_origin_m: tuple[float, float]
    cell_size_m: float
    agents_total: int
    agents_evacuated: int
    completed: bool


def save_run(path: Path, result: SimulationResult, trajectories: Trajectories) -> None:
    """Guarda trayectorias y arrays del resultado."""
    path.parent.mkdir(parents=True, exist_ok=True)
    bottlenecks = np.array(
        [
            [b.location.x, b.location.y, b.mean_density, b.duration_s, b.severity]
            for b in result.bottlenecks
        ],
        dtype=np.float64,
    ).reshape(-1, 5)
    with path.open("wb") as handle:
        np.savez_compressed(
            handle,
            version=np.array(FORMAT_VERSION),
            times=trajectories.times_s,
            positions=trajectories.positions,
            status=trajectories.status,
            radius=trajectories.radius_m,
            profile_index=trajectories.profile_index,
            profile_names=np.array(trajectories.profile_names, dtype=np.str_),
            curve_times=result.curve_times_s,
            curve_evacuated=result.curve_evacuated,
            density=result.density_map,
            bottlenecks=bottlenecks,
            origin=np.array(result.grid_origin_m, dtype=np.float64),
            cell_size=np.array(result.cell_size_m),
            counts=np.array([result.agents_total, result.agents_evacuated, int(result.completed)]),
        )


def load_run(path: Path) -> StoredRun:
    """Lee un archivo guardado con ``save_run``."""
    with np.load(path, allow_pickle=False) as data:
        if int(data["version"]) != FORMAT_VERSION:
            raise ValueError("El archivo de simulación tiene un formato no reconocido.")
        trajectories = Trajectories(
            times_s=data["times"].astype(np.float64),
            positions=data["positions"].astype(np.float32),
            status=data["status"].astype(np.int8),
            radius_m=data["radius"].astype(np.float32),
            profile_index=data["profile_index"].astype(np.int32),
            profile_names=tuple(str(n) for n in data["profile_names"]),
        )
        bottlenecks = tuple(
            Bottleneck(Point(float(x), float(y)), float(rho), float(dur), float(sev))
            for x, y, rho, dur, sev in data["bottlenecks"]
        )
        origin = data["origin"]
        total, evacuated, completed = (int(v) for v in data["counts"])
        return StoredRun(
            trajectories=trajectories,
            curve_times_s=data["curve_times"].astype(np.float64),
            curve_evacuated=data["curve_evacuated"].astype(np.int32),
            density_map=data["density"].astype(np.float64),
            bottlenecks=bottlenecks,
            grid_origin_m=(float(origin[0]), float(origin[1])),
            cell_size_m=float(data["cell_size"]),
            agents_total=total,
            agents_evacuated=evacuated,
            completed=bool(completed),
        )
