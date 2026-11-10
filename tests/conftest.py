"""Configuración común de pruebas."""

from __future__ import annotations

import os

# Qt sin pantalla: necesario en CI (Ubuntu sin X) y cómodo en local. Debe fijarse antes de crear
# la QApplication, que pytest-qt crea de forma perezosa.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
