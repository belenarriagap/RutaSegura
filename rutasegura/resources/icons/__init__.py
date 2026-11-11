"""Íconos de la aplicación (generados con ``scripts/make_icon.py``)."""

from __future__ import annotations

from pathlib import Path

ICONS_DIR = Path(__file__).parent


def icon_path() -> Path:
    """Ícono de la ventana (PNG de 256 px)."""
    return ICONS_DIR / "rutasegura.png"
