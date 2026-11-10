"""Tipos de imagen y carga de archivos de plano (JPG, PNG o PDF rasterizado) — RF01.

Convención: las imágenes son arrays ``uint8`` RGB de forma (alto, ancho, 3).
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt
import pymupdf

RGBImage = npt.NDArray[np.uint8]
GrayImage = npt.NDArray[np.uint8]
Mask = npt.NDArray[np.bool_]

IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"})
PDF_SUFFIX = ".pdf"
PDF_DPI = 200
MAX_SIDE_PX = 6000  # evita imágenes gigantes al rasterizar planos A1/A0


class PlanFileError(ValueError):
    """El archivo no se puede usar como plano (formato no soportado, dañado, página inválida)."""


def is_supported(path: Path) -> bool:
    """Indica si la extensión del archivo es de un formato soportado."""
    suffix = path.suffix.lower()
    return suffix in IMAGE_SUFFIXES or suffix == PDF_SUFFIX


def page_count(path: Path) -> int:
    """Cantidad de páginas: 1 para imágenes; las del documento para PDF."""
    if path.suffix.lower() == PDF_SUFFIX:
        try:
            with pymupdf.open(path) as doc:
                return int(doc.page_count)
        except (RuntimeError, ValueError) as exc:
            raise PlanFileError(f"No se pudo abrir el PDF: {exc}") from exc
    if path.suffix.lower() in IMAGE_SUFFIXES:
        return 1
    raise PlanFileError(f"Formato no soportado: {path.suffix or 'sin extensión'}.")


def read_image(path: Path) -> RGBImage:
    """Lee una imagen (admite rutas con tildes o eñes en Windows)."""
    try:
        data = np.fromfile(path, dtype=np.uint8)
    except OSError as exc:
        raise PlanFileError(f"No se pudo leer el archivo: {exc}") from exc
    decoded = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if decoded is None:
        raise PlanFileError("El archivo no es una imagen válida o está dañado.")
    return np.ascontiguousarray(cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB), dtype=np.uint8)


def write_png(path: Path, image: RGBImage) -> None:
    """Guarda una imagen RGB como PNG (admite rutas con caracteres no ASCII)."""
    ok, buffer = cv2.imencode(".png", cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
    if not ok:
        raise PlanFileError("No se pudo codificar la imagen.")
    path.parent.mkdir(parents=True, exist_ok=True)
    np.asarray(buffer, dtype=np.uint8).tofile(path)


def rasterize_pdf_page(path: Path, page: int = 0, dpi: int = PDF_DPI) -> RGBImage:
    """Convierte una página de PDF en imagen a ~``dpi`` (limitada a ``MAX_SIDE_PX``)."""
    try:
        with pymupdf.open(path) as doc:
            if not 0 <= page < doc.page_count:
                raise PlanFileError(
                    f"El PDF tiene {doc.page_count} página(s); no existe la {page + 1}."
                )
            pdf_page = doc[page]
            rect = pdf_page.rect
            longest_in = max(rect.width, rect.height) / 72.0
            effective_dpi = min(dpi, int(MAX_SIDE_PX / longest_in)) if longest_in > 0 else dpi
            pix = pdf_page.get_pixmap(
                dpi=max(effective_dpi, 36), alpha=False, colorspace=pymupdf.csRGB
            )
            raw = np.frombuffer(pix.samples, dtype=np.uint8)
            rows = raw.reshape(pix.height, pix.stride)[:, : pix.width * pix.n]
            image = rows.reshape(pix.height, pix.width, pix.n)
    except PlanFileError:
        raise
    except (RuntimeError, ValueError) as exc:
        raise PlanFileError(f"No se pudo leer el PDF: {exc}") from exc
    return np.ascontiguousarray(image[:, :, :3], dtype=np.uint8)


def load_plan_file(path: Path, page: int = 0) -> RGBImage:
    """Carga un plano desde JPG/PNG/BMP/TIFF o una página de PDF."""
    if not path.exists():
        raise PlanFileError("El archivo no existe.")
    if path.suffix.lower() == PDF_SUFFIX:
        return rasterize_pdf_page(path, page)
    if path.suffix.lower() in IMAGE_SUFFIXES:
        return read_image(path)
    raise PlanFileError(f"Formato no soportado: {path.suffix or 'sin extensión'}.")
