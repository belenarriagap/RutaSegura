"""Servicio de importación de planos: carga, rectificación, escala y detección (RF01–RF04)."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import numpy.typing as npt

from rutasegura.application.errors import UserFacingError
from rutasegura.domain.geometry import Point
from rutasegura.domain.plan import FloorPlan
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

        Reemplaza los muros, puertas y salidas anteriores y conserva escaleras, obstáculos,
        zonas seguras, ambientes y escala.
        """
        result = detect_plan(image, VisionParams(scale_m_per_px=plan.scale_m_per_px))
        return dataclasses.replace(plan, walls=result.walls, doors=result.doors, exits=result.exits)
