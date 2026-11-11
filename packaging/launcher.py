"""Punto de entrada del ejecutable empaquetado con PyInstaller."""

import sys

from rutasegura.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
