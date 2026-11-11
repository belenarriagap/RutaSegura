"""Servicio de importación de planos: carga, rectificación, escala y detección (RF01–RF04)."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import numpy.typing as npt

from rutasegura.application.errors import UserFacingError
from rutasegura.domain.enums import UseType
from rutasegura.domain.geometry import Point
from rutasegura.domain.plan import FloorPlan, Room
from rutasegura.engines.navigation.rooms import detect_rooms
from rutasegura.engines.vision.images import (
    IMAGE_SUFFIXES,
    PDF_SUFFIX,
    PlanFileError,
    load_plan_file,
    page_count,
)
from rutasegura.engines.vision.pipeline import VisionParams, detect_plan
from rutasegura.engines.vision.rectify import rectify
from rutasegura.engines.vision.scale import scale_from_reference

Image = npt.NDArray[np.uint8]


class PlanImportService:
    """Operaciones sobre la imagen del plano. No guarda nada: ver ``ProjectService``."""

    @staticmethod
    def supported_suffixes() -> tuple[str, ...]:
        """Extensiones aceptadas (para el diálogo de archivos)."""
        return (*sorted(IMAGE_SUFFIXES), PDF_SUFFIX)

    @staticmethod
    def page_count(path: Path) -> int:
        """Páginas del archivo (1 si es imagen)."""
        try:
            return page_count(path)
        except PlanFileError as exc:
            raise UserFacingError(str(exc)) from exc

    @staticmethod
    def load(path: Path, page: int = 0) -> Image:
        """Carga la imagen del plano (o una página del PDF)."""
        try:
            return load_plan_file(path, page)
        except PlanFileError as exc:
            raise UserFacingError(str(exc)) from exc

    @staticmethod
    def straighten(image: Image, corners: Sequence[Point]) -> Image:
        """Endereza una foto tomada en ángulo a partir de las 4 esquinas del plano."""
        try:
            return rectify(image, corners)
        except ValueError as exc:
            raise UserFacingError(str(exc)) from exc

    @staticmethod
    def scale_from_reference(p1: Point, p2: Point, meters: float) -> float:
        """Metros por píxel a partir de una medida conocida."""
        try:
            return scale_from_reference(p1, p2, meters)
        except ValueError as exc:
            raise UserFacingError(str(exc)) from exc

    @staticmethod
    def detect(image: Image, plan: FloorPlan) -> FloorPlan:
        """Devuelve ``plan`` con muros, puertas y salidas propuestas detectados en ``image``.

        Reemplaza muros y puertas. Conserva las salidas ya confirmadas por el usuario (las
        propuestas que caen sobre ellas se descartan), además de escaleras, obstáculos, zonas
        seguras, ambientes y escala.
        """
        result = detect_plan(image, VisionParams(scale_m_per_px=plan.scale_m_per_px))
        confirmed = [e for e in plan.exits if e.confirmed]
        near = (1.0 / plan.scale_m_per_px) if plan.scale_m_per_px else 40.0
        proposals = [
            e
            for e in result.exits
            if all(e.segment.midpoint.distance_to(c.segment.midpoint) > near for c in confirmed)
        ]
        used = {e.name for e in confirmed}
        renamed = []
        number = 1
        for exit_ in proposals:
            while f"Salida {number}" in used:
                number += 1
            used.add(f"Salida {number}")
            renamed.append(dataclasses.replace(exit_, name=f"Salida {number}"))
        return dataclasses.replace(
            plan, walls=result.walls, doors=result.doors, exits=(*confirmed, *renamed)
        )

    @staticmethod
    def detect_rooms(plan: FloorPlan, use: UseType, name_template: str) -> FloorPlan:
        """Agrega los ambientes cerrados que encuentre y que no se superpongan con los existentes.

        Los nombres nuevos siguen ``name_template`` (con ``{number}``) sin repetir los usados.
        """
        try:
            polygons = detect_rooms(plan)
        except ValueError as exc:
            raise UserFacingError(str(exc)) from exc
        used = {r.name for r in plan.rooms}
        taken_centers = [r.area.centroid for r in plan.rooms]
        rooms = list(plan.rooms)
        number = 1
        for polygon in polygons:
            center = polygon.centroid
            if any(_inside(r.area.vertices, center) for r in plan.rooms) or center in taken_centers:
                continue
            while name_template.format(number=number) in used:
                number += 1
            name = name_template.format(number=number)
            used.add(name)
            rooms.append(Room(name, use, polygon))
        return dataclasses.replace(plan, rooms=tuple(rooms))


def _inside(vertices: tuple[Point, ...], p: Point) -> bool:
    inside = False
    j = len(vertices) - 1
    for i, vi in enumerate(vertices):
        vj = vertices[j]
        if (vi.y > p.y) != (vj.y > p.y):
            x_cross = (vj.x - vi.x) * (p.y - vi.y) / (vj.y - vi.y) + vi.x
            if p.x < x_cross:
                inside = not inside
        j = i
    return inside
