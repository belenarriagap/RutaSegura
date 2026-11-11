# -*- mode: python ; coding: utf-8 -*-
# Especificación de PyInstaller para RutaSegura (modo carpeta: arranque rápido, sin descompresión).
#
# Uso recomendado:  uv run python scripts/build_windows.py
# (construye, verifica con --self-test y, si está Inno Setup, genera el instalador).

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent  # noqa: F821 - variable que define PyInstaller
PKG = ROOT / "rutasegura"

datas = [
    # Reglas normativas y perfiles por defecto (se leen con importlib.resources).
    (str(PKG / "resources" / "norms"), "rutasegura/resources/norms"),
    (str(PKG / "resources" / "profiles"), "rutasegura/resources/profiles"),
    (str(PKG / "resources" / "icons" / "rutasegura.png"), "rutasegura/resources/icons"),
    # Alembic lee los archivos de migración desde disco.
    (str(PKG / "data" / "migrations"), "rutasegura/data/migrations"),
]

hiddenimports = [
    *collect_submodules("rutasegura"),
    *collect_submodules("reportlab.pdfbase"),
    *collect_submodules("reportlab.graphics"),
    "alembic.runtime.migration",
    "alembic.ddl.sqlite",
    "sqlalchemy.dialects.sqlite",
    "matplotlib.backends.backend_agg",
]

# Nada de esto se usa en tiempo de ejecución; excluirlo reduce el tamaño.
excludes = [
    "tkinter",
    "IPython",
    "pytest",
    "mypy",
    "ruff",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtNetwork",
    "matplotlib.backends.backend_qtagg",
    "matplotlib.backends.backend_tkagg",
]

a = Analysis(  # noqa: F821
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RutaSegura",
    console=False,
    icon=str(PKG / "resources" / "icons" / "rutasegura.ico"),
    upx=False,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    upx=False,
    name="RutaSegura",
)
