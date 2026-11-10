"""Grilla de navegación de 0.4 m construida a partir del plano.

Coordenadas en metros: ``x_m = x_px * escala``. La celda (fila, columna) cubre
``[origen + columna·tamaño, origen + (columna+1)·tamaño)`` en x (y lo análogo en y).

Reglas de construcción:

* Muros: líneas 4-conexas (no dejan pasar movimientos diagonales).
* Puertas: celdas transitables sobre el vano.
* Salidas confirmadas y no bloqueadas: celdas objetivo. Las bloqueadas o sin confirmar se sellan
  como muro (un vano exterior sin salida activa no se puede usar).
* Zonas seguras dentro del edificio: celdas objetivo.
* Todo lo conectado con el borde de la grilla sin pasar por un objetivo es exterior.
"""

from __future__ import annotations

import math
from collections.abc import Collection, Sequence
from dataclasses import dataclass

import cv2
import numpy as np
import numpy.typing as npt

from rutasegura.domain.enums import CellType
from rutasegura.domain.geometry import Point, Polygon, Segment
from rutasegura.domain.plan import FloorPlan

CELL_SIZE_M = 0.4
WALKABLE = (CellType.FREE, CellType.DOOR, CellType.EXIT, CellType.STAIR, CellType.SAFE_ZONE)
TARGETS = (CellType.EXIT, CellType.SAFE_ZONE)
_SHIFT = 4  # precisión subpíxel de cv2 (1/16 de celda)

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]
BoolArray = npt.NDArray[np.bool_]


@dataclass(frozen=True, eq=False)
class NavGrid:
    """Grilla de celdas con tipo, objetivos (salidas y zonas seguras) y georreferencia."""

    cells: npt.NDArray[np.int8]
    cell_size: float
    origin: tuple[float, float]
    target_ids: npt.NDArray[np.int16]  # -1 = no es objetivo; si no, índice en target_names
    target_names: tuple[str, ...]

    @property
    def shape(self) -> tuple[int, int]:
        """(filas, columnas)."""
        rows, cols = self.cells.shape
        return int(rows), int(cols)

    @property
    def walkable(self) -> BoolArray:
        """Celdas por donde se puede caminar."""
        return np.isin(self.cells, [int(c) for c in WALKABLE])

    @property
    def targets(self) -> BoolArray:
        """Celdas objetivo (al llegar, la persona está evacuada)."""
        return np.asarray(self.target_ids >= 0, dtype=np.bool_)

    def to_cell(self, xy: FloatArray) -> tuple[IntArray, IntArray]:
        """Posiciones (n, 2) en metros → (filas, columnas), recortadas a la grilla."""
        rows, cols = self.shape
        c = np.floor((xy[:, 0] - self.origin[0]) / self.cell_size).astype(np.int64)
        r = np.floor((xy[:, 1] - self.origin[1]) / self.cell_size).astype(np.int64)
        return np.clip(r, 0, rows - 1), np.clip(c, 0, cols - 1)

    def cell_centers(self, r: IntArray, c: IntArray) -> FloatArray:
        """Centros (n, 2) en metros de las celdas indicadas."""
        x = self.origin[0] + (c + 0.5) * self.cell_size
        y = self.origin[1] + (r + 0.5) * self.cell_size
        return np.column_stack([x, y]).astype(np.float64)

    def polygon_mask(self, polygon_m: Polygon) -> BoolArray:
        """Celdas cuyo centro cae dentro de un polígono (en metros)."""
        mask = np.zeros(self.shape, dtype=np.uint8)
        cv2.fillPoly(mask, [self._to_cv(polygon_m.vertices)], 1, cv2.LINE_8, _SHIFT)
        return np.asarray(mask > 0, dtype=np.bool_)

    def _to_cv(self, points: Sequence[Point]) -> npt.NDArray[np.int32]:
        scale = 1 << _SHIFT
        pts = [
            (
                round(((p.x - self.origin[0]) / self.cell_size - 0.5) * scale),
                round(((p.y - self.origin[1]) / self.cell_size - 0.5) * scale),
            )
            for p in points
        ]
        return np.array(pts, dtype=np.int32).reshape(-1, 1, 2)


def _scale_point(p: Point, s: float) -> Point:
    return Point(p.x * s, p.y * s)


def segment_to_m(segment: Segment, scale: float) -> Segment:
    """Segmento en píxeles → metros."""
    return Segment(_scale_point(segment.start, scale), _scale_point(segment.end, scale))


def polygon_to_m(polygon: Polygon, scale: float) -> Polygon:
    """Polígono en píxeles → metros."""
    return Polygon(tuple(_scale_point(p, scale) for p in polygon.vertices))


def build_grid(
    plan: FloorPlan,
    *,
    blocked_exits: Collection[str] = (),
    cell_size: float = CELL_SIZE_M,
    margin_m: float = 1.2,
) -> NavGrid:
    """Construye la grilla de un piso. Requiere que el plano tenga escala."""
    scale = plan.scale_m_per_px
    if scale is None:
        raise ValueError("El plano no tiene escala; defínala en el paso 2.")
    walls = [segment_to_m(w.segment, scale) for w in plan.walls]
    doors = [segment_to_m(d.segment, scale) for d in plan.doors]
    active_exits = [e for e in plan.exits if e.confirmed and e.name not in blocked_exits]
    closed_exits = [e for e in plan.exits if not (e.confirmed and e.name not in blocked_exits)]
    obstacles = [polygon_to_m(o.area, scale) for o in plan.obstacles]
    zones = [(z.name, polygon_to_m(z.area, scale)) for z in plan.safe_zones]
    rooms = [polygon_to_m(r.area, scale) for r in plan.rooms]

    exit_segments = [segment_to_m(e.segment, scale) for e in plan.exits]
    points = [p for s in walls + doors + exit_segments for p in (s.start, s.end)]
    points += [p for poly in obstacles + rooms + [z for _, z in zones] for p in poly.vertices]
    if not points:
        raise ValueError("El plano está vacío: no hay muros ni ambientes.")
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    origin = (min(xs) - margin_m, min(ys) - margin_m)
    cols = math.ceil((max(xs) - origin[0] + margin_m) / cell_size) + 1
    rows = math.ceil((max(ys) - origin[1] + margin_m) / cell_size) + 1

    cells = np.full((rows, cols), int(CellType.FREE), dtype=np.uint8)
    target_ids = np.full((rows, cols), -1, dtype=np.int16)
    grid = NavGrid(cells.astype(np.int8), cell_size, origin, target_ids, ())

    def line(seg: Segment, value: CellType, line_type: int) -> None:
        pts = grid._to_cv([seg.start, seg.end]).reshape(2, 2)
        cv2.line(cells, tuple(pts[0]), tuple(pts[1]), int(value), 1, line_type, _SHIFT)

    def fill(poly: Polygon, value: CellType) -> None:
        cv2.fillPoly(cells, [grid._to_cv(poly.vertices)], int(value), cv2.LINE_8, _SHIFT)

    for poly in obstacles:
        fill(poly, CellType.OBSTACLE)
    for seg in walls:
        line(seg, CellType.WALL, cv2.LINE_4)
    for exit_ in closed_exits:
        line(segment_to_m(exit_.segment, scale), CellType.WALL, cv2.LINE_4)
    for seg in doors:
        line(seg, CellType.DOOR, cv2.LINE_8)

    names: list[str] = []
    for exit_ in active_exits:
        before = cells == int(CellType.EXIT)
        line(segment_to_m(exit_.segment, scale), CellType.EXIT, cv2.LINE_4)
        target_ids[(cells == int(CellType.EXIT)) & ~before] = len(names)
        names.append(exit_.name or f"Salida {len(names) + 1}")
    for i, (name, poly) in enumerate(zones):
        zone_mask = np.zeros_like(cells)
        cv2.fillPoly(zone_mask, [grid._to_cv(poly.vertices)], 1, cv2.LINE_8, _SHIFT)
        free_zone = (zone_mask > 0) & (cells == int(CellType.FREE))
        cells[free_zone] = int(CellType.SAFE_ZONE)
        target_ids[free_zone] = len(names)
        names.append(name or f"Zona segura {i + 1}")

    _mark_outside(cells)
    # Las zonas seguras que quedaron afuera no son alcanzables por dentro: dejan de ser objetivo.
    target_ids[cells == int(CellType.OUTSIDE)] = -1
    return NavGrid(cells.astype(np.int8), cell_size, origin, target_ids, tuple(names))


def _mark_outside(cells: npt.NDArray[np.uint8]) -> None:
    """Marca como exterior lo alcanzable desde el borde por celdas transitables no objetivo."""
    passable = np.isin(
        cells,
        [int(CellType.FREE), int(CellType.DOOR), int(CellType.STAIR), int(CellType.SAFE_ZONE)],
    ).astype(np.uint8)
    count, labels = cv2.connectedComponents(passable, connectivity=4)
    if count <= 1:
        return
    border = np.unique(np.concatenate([labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]]))
    border = border[border > 0]
    outside = np.isin(labels, border)
    cells[outside] = int(CellType.OUTSIDE)
