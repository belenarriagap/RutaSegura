"""Generador de planos sintéticos con verdad de referencia, para probar la visión sin planos reales.

Dibuja un edificio rectangular dividido en ambientes, con muros gruesos, puertas (hueco + arco de
apertura + hoja), salidas en el muro exterior, textos, cotas y mobiliario fino. Luego aplica
rotación, desenfoque, ruido e iluminación desigual (como una foto). La verdad de referencia
(ejes de muros y vanos) se transforma con la misma rotación.

Toda la aleatoriedad sale de ``numpy.random.default_rng(seed)``: misma semilla, mismo plano.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

import cv2
import numpy as np
import numpy.typing as npt

from rutasegura.domain.geometry import Point, Segment

RGB = npt.NDArray[np.uint8]


@dataclass(frozen=True)
class SyntheticPlan:
    """Imagen + verdad de referencia en coordenadas de la imagen."""

    image: RGB
    walls: tuple[Segment, ...]
    doors: tuple[Segment, ...]
    exits: tuple[Segment, ...]
    wall_thickness_px: float
    scale_m_per_px: float
    seed: int

    @property
    def openings(self) -> tuple[Segment, ...]:
        """Puertas y salidas juntas."""
        return self.doors + self.exits


@dataclass
class _Line:
    """Eje de un muro con los vanos (intervalos en px a lo largo del eje) que lo cortan."""

    start: tuple[float, float]
    end: tuple[float, float]
    openings: list[tuple[float, float, bool]] = field(default_factory=list)  # (a, b, es_salida)

    @property
    def length(self) -> float:
        return math.dist(self.start, self.end)

    def at(self, t: float) -> tuple[float, float]:
        f = t / self.length
        return (
            self.start[0] + f * (self.end[0] - self.start[0]),
            self.start[1] + f * (self.end[1] - self.start[1]),
        )


def _splits(rng: np.random.Generator, total: float, count: int, min_gap: float) -> list[float]:
    """Posiciones de tabiques separadas al menos ``min_gap``."""
    for _ in range(100):
        values = sorted(rng.uniform(min_gap, total - min_gap, size=count).tolist())
        points = [0.0, *values, total]
        if all(b - a >= min_gap for a, b in itertools.pairwise(points)):
            return values
    return [total * (i + 1) / (count + 1) for i in range(count)]


def _place_opening(
    rng: np.random.Generator, line: _Line, a: float, b: float, width: float, clearance: float
) -> tuple[float, float] | None:
    """Ubica un vano de ancho ``width`` en el tramo [a, b] con ``clearance`` a cada lado."""
    lo, hi = a + clearance, b - clearance - width
    if hi <= lo:
        return None
    start = float(rng.uniform(lo, hi))
    return start, start + width


def generate_plan(
    seed: int,
    *,
    px_per_m: float = 50.0,
    max_rotation_deg: float = 4.0,
    photo_effects: bool = True,
    clutter: bool = True,
) -> SyntheticPlan:
    """Genera un plano sintético reproducible a partir de ``seed``."""
    rng = np.random.default_rng(seed)
    width_m = float(rng.uniform(12, 22))
    height_m = float(rng.uniform(8, 14))
    t = round(float(rng.uniform(0.15, 0.25)) * px_per_m)  # grosor de muro en px
    margin = int(2.0 * px_per_m)
    bw, bh = width_m * px_per_m, height_m * px_per_m
    canvas_w, canvas_h = int(bw + 2 * margin), int(bh + 2 * margin)
    x0, y0, x1, y1 = margin, margin, margin + bw, margin + bh

    xs = [x0 + v for v in _splits(rng, bw, int(rng.integers(1, 4)), 3.5 * px_per_m)]
    ys = [y0 + v for v in _splits(rng, bh, int(rng.integers(0, 2)), 3.5 * px_per_m)]

    outer = [
        _Line((x0, y0), (x1, y0)),
        _Line((x1, y0), (x1, y1)),
        _Line((x1, y1), (x0, y1)),
        _Line((x0, y1), (x0, y0)),
    ]
    inner = [_Line((x, y0), (x, y1)) for x in xs] + [_Line((x0, y), (x1, y)) for y in ys]

    door_w = 0.9 * px_per_m
    clearance = 0.4 * px_per_m + t
    # Puertas interiores: una por tramo entre cruces, con probabilidad alta.
    for line in inner:
        vertical = line.start[0] == line.end[0]
        cuts = [y - y0 for y in ys] if vertical else [x - x0 for x in xs]
        bounds = [0.0, *cuts, line.length]
        for a, b in itertools.pairwise(bounds):
            if rng.random() < 0.85:
                placed = _place_opening(rng, line, a + t / 2, b - t / 2, door_w, clearance)
                if placed:
                    line.openings.append((*placed, False))
    # Salidas: 1 o 2 en muros exteriores distintos.
    for side in rng.choice(4, size=int(rng.integers(1, 3)), replace=False):
        line = outer[int(side)]
        exit_w = float(rng.uniform(1.0, 1.8)) * px_per_m
        placed = _place_opening(rng, line, t / 2, line.length - t / 2, exit_w, clearance + 20)
        if placed:
            line.openings.append((*placed, True))

    gray = np.full((canvas_h, canvas_w), 255, dtype=np.uint8)

    def draw_wall(line: _Line) -> None:
        (ax, ay), (bx, by) = line.start, line.end
        ux, uy = (bx - ax) / line.length, (by - ay) / line.length
        nx, ny = -uy, ux
        half = t / 2
        corners = np.array(
            [
                (ax - ux * half + nx * half, ay - uy * half + ny * half),
                (bx + ux * half + nx * half, by + uy * half + ny * half),
                (bx + ux * half - nx * half, by + uy * half - ny * half),
                (ax - ux * half - nx * half, ay - uy * half - ny * half),
            ]
        )
        cv2.fillConvexPoly(gray, corners.round().astype(np.int32), 0)

    for line in outer + inner:
        draw_wall(line)

    for line in outer + inner:
        (ax, ay), (bx, by) = line.start, line.end
        ux, uy = (bx - ax) / line.length, (by - ay) / line.length
        nx, ny = -uy, ux
        for a, b, _ in line.openings:
            pa, pb = line.at(a), line.at(b)
            ext = t / 2 + 2
            gap = np.array(
                [
                    (pa[0] + nx * ext, pa[1] + ny * ext),
                    (pb[0] + nx * ext, pb[1] + ny * ext),
                    (pb[0] - nx * ext, pb[1] - ny * ext),
                    (pa[0] - nx * ext, pa[1] - ny * ext),
                ]
            )
            cv2.fillConvexPoly(gray, gap.round().astype(np.int32), 255)
            # arco de apertura y hoja
            hinge, other = (pa, pb) if rng.random() < 0.5 else (pb, pa)
            side = 1.0 if rng.random() < 0.5 else -1.0
            r = b - a
            dx, dy = other[0] - hinge[0], other[1] - hinge[1]
            base = math.degrees(math.atan2(dy, dx))
            sweep = 90.0 * side
            leaf_angle = math.radians(base + sweep)
            cv2.ellipse(
                gray,
                (round(hinge[0]), round(hinge[1])),
                (round(r), round(r)),
                0.0,
                base,
                base + sweep,
                0,
                1,
                cv2.LINE_AA,
            )
            leaf_end = (hinge[0] + r * math.cos(leaf_angle), hinge[1] + r * math.sin(leaf_angle))
            cv2.line(
                gray,
                (round(hinge[0]), round(hinge[1])),
                (round(leaf_end[0]), round(leaf_end[1])),
                0,
                2,
                cv2.LINE_AA,
            )

    if clutter:
        _draw_clutter(gray, rng, (x0, y0, x1, y1), xs, ys, px_per_m)

    # Verdad de referencia (antes de rotar).
    walls: list[Segment] = []
    doors: list[Segment] = []
    exits: list[Segment] = []
    for line in outer + inner:
        line_openings = sorted(line.openings)
        pos = 0.0
        for a, b, is_exit in line_openings:
            if a - pos > 1:
                walls.append(Segment(Point(*line.at(pos)), Point(*line.at(a))))
            (exits if is_exit else doors).append(Segment(Point(*line.at(a)), Point(*line.at(b))))
            pos = b
        if line.length - pos > 1:
            walls.append(Segment(Point(*line.at(pos)), Point(*line.at(line.length))))

    angle = float(rng.uniform(-max_rotation_deg, max_rotation_deg))
    image, matrix = _rotate(gray, angle)

    def tf(seg: Segment) -> Segment:
        pts = np.array([[seg.start.x, seg.start.y, 1.0], [seg.end.x, seg.end.y, 1.0]]) @ matrix.T
        return Segment(Point(*pts[0]), Point(*pts[1]))

    if photo_effects:
        image = _photo_effects(image, rng)
    rgb = np.ascontiguousarray(np.dstack([image, image, (image * 0.97).astype(np.uint8)]))
    return SyntheticPlan(
        image=rgb,
        walls=tuple(tf(s) for s in walls),
        doors=tuple(tf(s) for s in doors),
        exits=tuple(tf(s) for s in exits),
        wall_thickness_px=float(t),
        scale_m_per_px=1.0 / px_per_m,
        seed=seed,
    )


def _draw_clutter(
    gray: npt.NDArray[np.uint8],
    rng: np.random.Generator,
    box: tuple[float, float, float, float],
    xs: list[float],
    ys: list[float],
    px_per_m: float,
) -> None:
    """Textos de ambientes, cotas y mobiliario con trazo fino (no deben detectarse como muros)."""
    x0, y0, x1, y1 = box
    cols = [x0, *xs, x1]
    rows = [y0, *ys, y1]
    n = 1
    for ca, cb in itertools.pairwise(cols):
        for ra, rb in itertools.pairwise(rows):
            label = f"AULA {n}" if rng.random() < 0.6 else f"OF. {n}"
            n += 1
            org = (int(ca + 0.25 * (cb - ca)), int(ra + 0.5 * (rb - ra)))
            cv2.putText(gray, label, org, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 0, 2, cv2.LINE_AA)
            for _ in range(int(rng.integers(1, 4))):  # mesas
                w, h = rng.uniform(0.6, 1.4) * px_per_m, rng.uniform(0.5, 0.8) * px_per_m
                px = rng.uniform(
                    ca + 0.7 * px_per_m, max(ca + 0.8 * px_per_m, cb - w - 0.7 * px_per_m)
                )
                py = rng.uniform(
                    ra + 0.7 * px_per_m, max(ra + 0.8 * px_per_m, rb - h - 0.7 * px_per_m)
                )
                cv2.rectangle(gray, (int(px), int(py)), (int(px + w), int(py + h)), 0, 1)
    # cota superior
    yd = int(y0 - 0.9 * px_per_m)
    cv2.line(gray, (int(x0), yd), (int(x1), yd), 0, 1)
    for x in (x0, x1):
        cv2.line(gray, (int(x), yd - 8), (int(x), yd + 8), 0, 1)
    text = f"{(x1 - x0) / px_per_m:.2f}"
    cv2.putText(gray, text, (int((x0 + x1) / 2), yd - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 0, 1)


def _rotate(
    gray: npt.NDArray[np.uint8], angle_deg: float
) -> tuple[npt.NDArray[np.uint8], npt.NDArray[np.float64]]:
    h, w = gray.shape
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle_deg, 1.0)
    cos, sin = abs(matrix[0, 0]), abs(matrix[0, 1])
    new_w, new_h = int(h * sin + w * cos), int(h * cos + w * sin)
    matrix[0, 2] += new_w / 2 - w / 2
    matrix[1, 2] += new_h / 2 - h / 2
    rotated = cv2.warpAffine(gray, matrix, (new_w, new_h), flags=cv2.INTER_LINEAR, borderValue=255)
    return np.asarray(rotated, dtype=np.uint8), np.asarray(matrix, dtype=np.float64)


def _photo_effects(gray: npt.NDArray[np.uint8], rng: np.random.Generator) -> npt.NDArray[np.uint8]:
    """Desenfoque, iluminación desigual y ruido de sensor."""
    sigma = float(rng.uniform(0.5, 1.2))
    img = cv2.GaussianBlur(gray, (0, 0), sigma).astype(np.float64)
    h, w = img.shape
    gx = np.linspace(0, 1, w)[None, :]
    gy = np.linspace(0, 1, h)[:, None]
    light = 1.0 - float(rng.uniform(0.05, 0.25)) * (gx * rng.uniform(0, 1) + gy * rng.uniform(0, 1))
    img = img * light + rng.normal(0.0, float(rng.uniform(3, 9)), size=img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)
