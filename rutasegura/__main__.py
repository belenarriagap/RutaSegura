"""Punto de entrada: ``rutasegura`` o ``python -m rutasegura``.

Es la raíz de composición: abre la base de datos local, arma los servicios de aplicación y
se los entrega a la interfaz.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from rutasegura.application.services import AppServices
from rutasegura.presentation.main_window import MainWindow
from rutasegura.resources.texts import TEXTS


def main() -> int:
    """Abre la ventana principal y ejecuta el bucle de eventos."""
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(TEXTS.app_name)
    services = AppServices.open()
    try:
        window = MainWindow(services, TEXTS)
        window.show()
        return app.exec()
    finally:
        services.close()


if __name__ == "__main__":
    sys.exit(main())
