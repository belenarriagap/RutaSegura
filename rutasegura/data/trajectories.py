"""Archivo binario de una corrida (.npz comprimido): trayectorias y arrays del resultado.

SQLite guarda solo el resumen (tabla ``simulacion``) y la ruta a este archivo.

Versión 2: agrega el piso de cada persona por cuadro y un mapa de calor por piso. Los archivos
de la versión 1 (un solo piso) se siguen leyendo.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from rutasegura.domain.geometry import Point
from rutasegura.domain.results import Bottleneck, FloorMap, SimulationResult, Trajectories

FORMAT_VERSION = 2
READABLE_VERSIONS = frozenset({1, 2})


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
    floor_maps: tuple[FloorMap, ...] = ()


def save_run(path: Path, result: SimulationResult, trajectories: Trajectories) -> None:
    """Guarda trayectorias y arrays del resultado."""
    path.parent.mkdir(parents=True, exist_ok=True)
    bottlenecks = np.array(
        [
            [b.location.x, b.location.y, b.mean_density, b.duration_s, b.severity, b.level]
            for b in result.bottlenecks
        ],
        dtype=np.float64,
    ).reshape(-1, 6)
    floors: dict[str, Any] = {}
    if result.floor_maps:
        floors["floor_levels"] = np.array([m.level for m in result.floor_maps], dtype=np.int32)
        floors["floor_origins"] = np.array(
            [m.grid_origin_m for m in result.floor_maps], dtype=np.float64
        )
        floors["floor_cells"] = np.array([m.cell_size_m for m in result.floor_maps])
        for k, floor_map in enumerate(result.floor_maps):
            floors[f"floor_density_{k}"] = floor_map.density_map
    if trajectories.level is not None:
        floors["level"] = trajectories.level
    with path.open("wb") as handle:
        arrays: dict[str, Any] = dict(
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
            **floors,
        )
        np.savez_compressed(handle, **arrays)


def load_run(path: Path) -> StoredRun:
    """Lee un archivo guardado con ``save_run``."""
    with np.load(path, allow_pickle=False) as data:
        version = int(data["version"])
        if version not in READABLE_VERSIONS:
            raise ValueError("El archivo de simulación tiene un formato no reconocido.")
        trajectories = Trajectories(
            times_s=data["times"].astype(np.float64),
            positions=data["positions"].astype(np.float32),
            status=data["status"].astype(np.int8),
            radius_m=data["radius"].astype(np.float32),
            profile_index=data["profile_index"].astype(np.int32),
            profile_names=tuple(str(n) for n in data["profile_names"]),
            level=data["level"].astype(np.int8) if "level" in data.files else None,
        )
        bottlenecks = tuple(
            Bottleneck(
                Point(float(row[0]), float(row[1])),
                float(row[2]),
                float(row[3]),
                float(row[4]),
                int(row[5]) if len(row) > 5 else 0,
            )
            for row in data["bottlenecks"]
        )
        floor_maps: tuple[FloorMap, ...] = ()
        if "floor_levels" in data.files:
            floor_maps = tuple(
                FloorMap(
                    level=int(level),
                    density_map=data[f"floor_density_{k}"].astype(np.float64),
                    grid_origin_m=(
                        float(data["floor_origins"][k][0]),
                        float(data["floor_origins"][k][1]),
                    ),
                    cell_size_m=float(data["floor_cells"][k]),
                )
                for k, level in enumerate(data["floor_levels"])
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
            floor_maps=floor_maps,
        )
