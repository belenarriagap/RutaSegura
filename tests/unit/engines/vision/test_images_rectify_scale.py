"""Carga de archivos (RF01), rectificación de perspectiva y escala (RF04)."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pymupdf
import pytest

from rutasegura.domain.geometry import Point
from rutasegura.engines.vision.images import (
    PlanFileError,
    is_supported,
    load_plan_file,
    page_count,
    rasterize_pdf_page,
    read_image,
    write_png,
)
from rutasegura.engines.vision.rectify import order_corners, rectify
from rutasegura.engines.vision.scale import scale_from_reference


def _sample_image() -> np.ndarray:
    img = np.full((60, 80, 3), 255, dtype=np.uint8)
    img[10:20, 10:70] = (200, 30, 30)
    return img


class TestImages:
    def test_png_round_trip_with_non_ascii_path(self, tmp_path: Path) -> None:
        path = tmp_path / "Ingeniería" / "plano ñandú.png"
        image = _sample_image()
        write_png(path, image)
        assert np.array_equal(read_image(path), image)
        assert page_count(path) == 1
        assert np.array_equal(load_plan_file(path), image)

    def test_jpg_is_loaded_as_rgb(self, tmp_path: Path) -> None:
        path = tmp_path / "plano.jpg"
        ok, buf = cv2.imencode(".jpg", cv2.cvtColor(_sample_image(), cv2.COLOR_RGB2BGR))
        assert ok
        buf.tofile(path)
        image = read_image(path)
        assert image.shape == (60, 80, 3)
        assert image[15, 40, 0] > 150  # el rojo sigue en el canal R
        assert image[15, 40, 2] < 100

    def test_pdf_pages_are_rasterized(self, tmp_path: Path) -> None:
        path = tmp_path / "planos.pdf"
        with pymupdf.open() as doc:
            for _ in range(2):
                page = doc.new_page(width=288, height=144)  # 4 x 2 pulgadas
                page.draw_rect(pymupdf.Rect(36, 36, 252, 108), color=(0, 0, 0), fill=(0, 0, 0))
            doc.save(path)
        assert page_count(path) == 2
        image = rasterize_pdf_page(path, page=1, dpi=100)
        assert image.shape == (200, 400, 3)
        assert image[100, 200].max() < 50  # dentro del rectángulo negro
        assert image[5, 5].min() > 200  # margen blanco
        with pytest.raises(PlanFileError, match="no existe la 3"):
            rasterize_pdf_page(path, page=2)

    def test_unsupported_and_broken_files(self, tmp_path: Path) -> None:
        dwg = tmp_path / "plano.dwg"
        dwg.write_bytes(b"x")
        assert not is_supported(dwg)
        assert is_supported(tmp_path / "a.PDF")
        with pytest.raises(PlanFileError, match="no soportado"):
            load_plan_file(dwg)
        broken = tmp_path / "roto.png"
        broken.write_bytes(b"no es una imagen")
        with pytest.raises(PlanFileError, match="dañado"):
            load_plan_file(broken)
        with pytest.raises(PlanFileError, match="no existe"):
            load_plan_file(tmp_path / "falta.png")


class TestRectify:
    def test_order_corners_any_input_order(self) -> None:
        corners = [Point(100, 90), Point(5, 10), Point(110, 5), Point(0, 100)]
        ordered = order_corners(corners)
        assert ordered.tolist() == [[5, 10], [110, 5], [100, 90], [0, 100]]

    def test_invalid_corners(self) -> None:
        with pytest.raises(ValueError, match="4 esquinas"):
            order_corners([Point(0, 0), Point(1, 1)])
        with pytest.raises(ValueError, match="pequeña"):
            order_corners([Point(0, 0), Point(5, 0), Point(5, 5), Point(0, 5)])

    def test_rectify_restores_a_warped_rectangle(self) -> None:
        # Rectángulo 200x100 deformado en perspectiva sobre un lienzo mayor.
        src = np.full((100, 200, 3), 255, np.uint8)
        src[:, :10] = 0  # banda negra a la izquierda
        quad = np.array([[40, 30], [260, 50], [250, 170], [30, 150]], np.float32)
        rect = np.array([[0, 0], [199, 0], [199, 99], [0, 99]], np.float32)
        matrix = cv2.getPerspectiveTransform(rect, quad)
        warped = np.asarray(
            cv2.warpPerspective(src, matrix, (300, 200), borderValue=(128, 128, 128)),
            dtype=np.uint8,
        )
        result = rectify(warped, [Point(float(x), float(y)) for x, y in quad])
        assert abs(result.shape[1] - 220) < 5
        assert abs(result.shape[0] - 120) < 5
        assert result[:, :5].mean() < 80  # la banda negra quedó a la izquierda
        assert result[:, -20:].mean() > 200


class TestScale:
    def test_scale_from_two_points(self) -> None:
        assert scale_from_reference(Point(0, 0), Point(300, 400), 10.0) == pytest.approx(0.02)

    def test_invalid_reference(self) -> None:
        with pytest.raises(ValueError, match="mayor que cero"):
            scale_from_reference(Point(0, 0), Point(10, 0), 0)
        with pytest.raises(ValueError, match="demasiado cerca"):
            scale_from_reference(Point(0, 0), Point(0.5, 0), 1.0)
