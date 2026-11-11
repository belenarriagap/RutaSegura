"""Detección automática de muros, puertas y salidas propuestas (RF02).

La detección es asistida: todo resultado se revisa en el editor. Las salidas se proponen sin
confirmar (``Exit.confirmed = False``) y el usuario las acepta o descarta.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from rutasegura.domain.geometry import Segment
from rutasegura.domain.plan import Door, Exit, Wall
from rutasegura.engines.vision.doors import (
    building_outline,
    corner_gaps,
    door_confidence,
    is_on_outline,
)
from rutasegura.engines.vision.images import RGBImage
from rutasegura.engines.vision.preprocess import binarize, estimate_wall_thickness, to_gray
from rutasegura.engines.vision.walls import (
    extend_to_mask_end,
    group_collinear,
    hough_segments,
    longest_empty_run,
    merge_intervals,
    merge_parallel_groups,
    occupancy,
    segment_coverage,
    snap_endpoints,
    wall_mask,
)


@dataclass(frozen=True, slots=True)
class VisionParams:
    """Parámetros de detección.

    Los anchos de puerta son un rango de plausibilidad para reconocer huecos, no valores
    normativos. Sin escala, el rango se expresa en múltiplos del grosor de muro.
    """

    scale_m_per_px: float | None = None
    wall_thickness_px: float | None = None
    door_min_m: float = 0.6
    door_max_m: float = 2.4
    door_min_thickness_factor: float = 3.5
    door_max_thickness_factor: float = 16.0
    angle_tol_deg: float = 3.0


@dataclass(frozen=True, slots=True)
class DetectionResult:
    """Elementos detectados, en coordenadas de la imagen."""

    walls: tuple[Wall, ...]
    doors: tuple[Door, ...]
    exits: tuple[Exit, ...]
    wall_thickness_px: float


EDGE_CORRECTION_PX = 1.0

EMPTY_RESULT = DetectionResult((), (), (), 0.0)


def detect_plan(image: RGBImage, params: VisionParams | None = None) -> DetectionResult:
    """Detecta muros, puertas y propone salidas en un plano."""
    params = params or VisionParams()
    binary = binarize(to_gray(image))
    thickness = params.wall_thickness_px or estimate_wall_thickness(binary)
    if thickness < 2.0:
        return EMPTY_RESULT
    if params.scale_m_per_px:
        door_min = params.door_min_m / params.scale_m_per_px
        door_max = params.door_max_m / params.scale_m_per_px
    else:
        door_min = params.door_min_thickness_factor * thickness
        door_max = params.door_max_thickness_factor * thickness

    mask = wall_mask(binary, thickness)
    segments = hough_segments(
        mask,
        min_length=max(2.0 * thickness, 10.0),
        max_gap=max(2.0, min(thickness, 0.4 * door_min)),
    )
    if len(segments) == 0:
        return DetectionResult((), (), (), thickness)

    dist_tol = max(0.6 * thickness, 3.0)
    groups = merge_parallel_groups(
        group_collinear(segments, angle_tol_deg=params.angle_tol_deg, dist_tol=dist_tol),
        angle_tol_deg=params.angle_tol_deg,
        dist_tol=dist_tol,
    )
    half_width = max(1.0, thickness / 4)
    raw_walls: list[Segment] = []
    gap_doors: list[Segment] = []
    gap_ends: set[tuple[int, int]] = set()
    for group in groups:
        intervals = [list(iv) for iv in merge_intervals(group.intervals(), 0.7 * door_min)]
        pieces: list[list[float]] = [intervals[0]]
        door_after: list[bool] = []  # door_after[k]: hay puerta entre pieces[k] y pieces[k+1]
        for nxt in intervals[1:]:
            prev = pieces[-1]
            run = longest_empty_run(*occupancy(mask, group, prev[1], nxt[0], half_width))
            if run is None or run[1] - run[0] < 0.75 * door_min:
                prev[1] = nxt[1]  # el "hueco" tiene muro: es el mismo muro
                continue
            # Corrección de borde: el tramo se mide entre muestras (medio píxel por lado) y el
            # antialias del muro invade el hueco ~1 px. Sin esto los vanos salen ~2 px angostos.
            prev[1], nxt[0] = run[0] - EDGE_CORRECTION_PX, run[1] + EDGE_CORRECTION_PX
            pieces.append(nxt)
            door_after.append(run[1] - run[0] <= 1.1 * door_max)
        pieces[0][0] = extend_to_mask_end(
            mask, group, pieces[0][0], -1.0, 1.5 * thickness, half_width
        )
        pieces[-1][1] = extend_to_mask_end(
            mask, group, pieces[-1][1], 1.0, 1.5 * thickness, half_width
        )
        first = len(raw_walls)
        raw_walls.extend(Segment(group.point_at(a), group.point_at(b)) for a, b in pieces)
        for k, is_door in enumerate(door_after):
            gap_ends.update({(first + k, 1), (first + k + 1, 0)})
            if is_door:
                gap_doors.append(
                    Segment(group.point_at(pieces[k][1]), group.point_at(pieces[k + 1][0]))
                )

    walls, joined = snap_endpoints(raw_walls, tol=1.5 * thickness)
    free_ends = [
        (i, end)
        for i, flags in enumerate(joined)
        for end, is_joined in enumerate(flags)
        if not is_joined and (i, end) not in gap_ends
    ]
    openings = gap_doors + corner_gaps(
        walls, free_ends, mask, thickness=thickness, min_px=door_min, max_px=door_max
    )

    thick = max(3, round(thickness) | 1)
    residual = binary & ~(cv2.dilate(mask.astype(np.uint8), np.ones((thick, thick), np.uint8)) > 0)
    outline = building_outline(mask, close_px=int(door_max * 1.2))
    doors: list[Door] = []
    exits: list[Exit] = []
    for opening in openings:
        if outline is not None and is_on_outline(outline, opening.midpoint, 1.5 * thickness):
            exits.append(Exit(opening, name=f"Salida {len(exits) + 1}", confirmed=False))
        else:
            doors.append(Door(opening, round(door_confidence(residual, opening), 3)))

    tolerant = cv2.dilate(mask.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    detected_walls = tuple(
        Wall(seg, round(min(1.0, segment_coverage(tolerant, seg)), 3))
        for seg in walls
        if seg.length >= thickness
    )
    return DetectionResult(detected_walls, tuple(doors), tuple(exits), thickness)
