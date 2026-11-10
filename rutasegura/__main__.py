"""Punto de entrada: ``rutasegura`` o ``python -m rutasegura``.

Es la raíz de composición: aquí se ensamblan las capas (en próximos hitos, repositorios y
servicios) y se entregan a la interfaz.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from rutasegura.presentation.main_window import MainWindow
from rutasegura.resources.texts import TEXTS


def main() -> int:
    """Abre la ventana principal y ejecuta el bucle de eventos."""
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(TEXTS.app_name)
    window = MainWindow(TEXTS)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
