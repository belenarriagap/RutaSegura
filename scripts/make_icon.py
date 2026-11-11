"""Genera el ícono de RutaSegura (señal de salida: puerta y flecha blancas sobre verde).

Uso: uv run python scripts/make_icon.py
Crea rutasegura/resources/icons/rutasegura.png (256 px) y rutasegura.ico (varios tamaños).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "rutasegura" / "resources" / "icons"
GREEN = (30, 132, 73, 255)
WHITE = (255, 255, 255, 255)


def draw(size: int = 1024) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 1024
    d.rounded_rectangle((40 * s, 40 * s, 984 * s, 984 * s), radius=180 * s, fill=GREEN)
    # puerta
    d.rectangle((600 * s, 220 * s, 800 * s, 800 * s), outline=WHITE, width=round(60 * s))
    # flecha hacia la puerta
    d.rectangle((210 * s, 470 * s, 520 * s, 570 * s), fill=WHITE)
    d.polygon([(500 * s, 360 * s), (680 * s, 520 * s), (500 * s, 680 * s)], fill=WHITE)
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    big = draw()
    big.resize((256, 256), Image.Resampling.LANCZOS).save(OUT / "rutasegura.png")
    big.save(
        OUT / "rutasegura.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Íconos guardados en {OUT}")


if __name__ == "__main__":
    main()
