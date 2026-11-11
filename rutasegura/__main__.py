"""Punto de entrada: ``rutasegura`` o ``python -m rutasegura``.

Es la raíz de composición: abre la base de datos local, arma los servicios de aplicación y
se los entrega a la interfaz.

Opciones:
    --version            muestra la versión y termina
    --self-test          comprueba la instalación sin red (no toca los datos del usuario)
    --log ARCHIVO        escribe la salida de --self-test en un archivo (útil en el .exe)
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

import rutasegura


def _parse(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="rutasegura", add_help=True)
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--log", type=Path)
    args, _qt_args = parser.parse_known_args(argv)
    return args


def _logger(path: Path | None) -> Callable[[str], None]:
    lines: list[str] = []

    def log(text: str) -> None:
        lines.append(text)
        if sys.stdout is not None:  # el .exe sin consola no tiene stdout
            print(text, flush=True)
        if path is not None:
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return log


def main(argv: Sequence[str] | None = None) -> int:
    """Abre la ventana principal (o ejecuta la opción pedida)."""
    args = _parse(sys.argv[1:] if argv is None else argv)
    if args.version:
        _logger(args.log)(f"RutaSegura {rutasegura.__version__}")
        return 0
    if args.self_test:
        from rutasegura.application.self_test import run_self_test

        return 0 if run_self_test(_logger(args.log)) else 1

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from rutasegura.application.services import AppServices
    from rutasegura.presentation.main_window import MainWindow
    from rutasegura.presentation.theme import apply_theme
    from rutasegura.resources.icons import icon_path
    from rutasegura.resources.texts import TEXTS

    existing = QApplication.instance()
    app = existing if isinstance(existing, QApplication) else QApplication(sys.argv)
    app.setApplicationName(TEXTS.app_name)
    app.setWindowIcon(QIcon(str(icon_path())))
    apply_theme(app)
    services = AppServices.open()
    try:
        window = MainWindow(services, TEXTS)
        window.show()
        return app.exec()
    finally:
        services.close()


if __name__ == "__main__":
    sys.exit(main())
