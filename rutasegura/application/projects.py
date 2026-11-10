"""Servicio de proyectos: crear, abrir y guardar el plano de cada piso."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import numpy.typing as npt

from rutasegura.application.errors import UserFacingError
from rutasegura.data.database import Database
from rutasegura.data.repositories import NotFoundError
from rutasegura.domain.enums import UseType
from rutasegura.domain.plan import FloorPlan
from rutasegura.domain.project import Project
from rutasegura.engines.vision.images import PlanFileError, read_image, write_png

Image = npt.NDArray[np.uint8]


class ProjectService:
    """Casos de uso de proyectos. Las imágenes procesadas se guardan junto a la base de datos.

    La geometría del plano está en coordenadas de la imagen procesada (rasterizada y, si
    corresponde, enderezada); por eso se guarda esa imagen y no el archivo original.
    """

    def __init__(self, db: Database, images_dir: Path) -> None:
        self._db = db
        self._images_dir = images_dir

    def create_project(self, name: str, use: UseType, address: str = "") -> int:
        """Crea un proyecto y devuelve su id."""
        try:
            project = Project(name=name.strip(), use=use, address=address.strip())
        except ValueError as exc:
            raise UserFacingError(str(exc)) from exc
        with self._db.unit_of_work() as uow:
            return uow.projects.add(project)

    def list_projects(self) -> list[tuple[int, Project]]:
        """Proyectos existentes, del más reciente al más antiguo."""
        with self._db.unit_of_work() as uow:
            return uow.projects.list_all()

    def get_project(self, project_id: int) -> Project:
        """Datos de un proyecto."""
        with self._db.unit_of_work() as uow:
            try:
                return uow.projects.get(project_id)
            except NotFoundError as exc:
                raise UserFacingError("El proyecto ya no existe.") from exc

    def image_path(self, project_id: int, level: int) -> Path:
        """Ubicación de la imagen procesada de un piso."""
        return self._images_dir / f"proyecto_{project_id}" / f"piso_{level}.png"

    def save_floor(self, project_id: int, plan: FloorPlan, image: Image | None = None) -> FloorPlan:
        """Guarda el plano del piso (y su imagen, si se entrega). Devuelve el plano guardado."""
        if image is not None:
            path = self.image_path(project_id, plan.level)
            write_png(path, image)
            plan = dataclasses.replace(plan, image_path=str(path))
        with self._db.unit_of_work() as uow:
            try:
                uow.floors.save(project_id, plan)
            except ValueError as exc:
                raise UserFacingError(str(exc)) from exc
            except NotFoundError as exc:
                raise UserFacingError("El proyecto ya no existe.") from exc
        return plan

    def load_floor(self, project_id: int, level: int = 0) -> FloorPlan | None:
        """Plano guardado del piso, o ``None`` si todavía no hay."""
        with self._db.unit_of_work() as uow:
            try:
                return uow.floors.get(project_id, level)
            except NotFoundError:
                return None

    @staticmethod
    def load_floor_image(plan: FloorPlan) -> Image | None:
        """Imagen de fondo del plano, o ``None`` si falta el archivo."""
        if not plan.image_path:
            return None
        try:
            return read_image(Path(plan.image_path))
        except PlanFileError:
            return None
