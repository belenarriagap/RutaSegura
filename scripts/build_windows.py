"""Construye RutaSegura para Windows y verifica el resultado.

Pasos:
1. PyInstaller con ``packaging/rutasegura.spec`` → ``dist/RutaSegura/RutaSegura.exe``.
2. Ejecuta el .exe con ``--self-test`` (sin red) y revisa que pase.
3. Crea ``dist/RutaSegura-<versión>-portable.zip``.
4. Si Inno Setup (``ISCC.exe``) está instalado, genera ``dist/RutaSegura-<versión>-instalador.exe``.

Uso:  uv run python scripts/build_windows.py [--skip-build]
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
APP_DIR = DIST / "RutaSegura"
EXE = APP_DIR / "RutaSegura.exe"
ISS = ROOT / "packaging" / "rutasegura.iss"
ISCC_CANDIDATES = [
    Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
    / "Inno Setup 6"
    / "ISCC.exe",
    Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Inno Setup 6" / "ISCC.exe",
]


def version() -> str:
    sys.path.insert(0, str(ROOT))
    import rutasegura

    return rutasegura.__version__


def build() -> None:
    print("1/4 PyInstaller…", flush=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(DIST),
            "--workpath",
            str(ROOT / "build"),
            str(ROOT / "packaging" / "rutasegura.spec"),
        ],
        check=True,
    )


def self_test() -> None:
    print("2/4 Autoprueba del ejecutable…", flush=True)
    log = DIST / "autoprueba.txt"
    log.unlink(missing_ok=True)
    result = subprocess.run([str(EXE), "--self-test", "--log", str(log)], timeout=600)
    text = log.read_text(encoding="utf-8") if log.exists() else "(sin registro)"
    print(text)
    if result.returncode != 0:
        raise SystemExit(f"La autoprueba del ejecutable falló (código {result.returncode}).")


def portable_zip(ver: str) -> Path:
    print("3/4 Paquete portable…", flush=True)
    target = DIST / f"RutaSegura-{ver}-portable"
    archive = Path(shutil.make_archive(str(target), "zip", DIST, "RutaSegura"))
    print(f"    {archive} ({archive.stat().st_size // (1024 * 1024)} MB)")
    return archive


def installer(ver: str) -> Path | None:
    print("4/4 Instalador (Inno Setup)…", flush=True)
    iscc = next((p for p in ISCC_CANDIDATES if p.exists()), None) or shutil.which("ISCC.exe")
    if iscc is None:
        print(
            "    Inno Setup 6 no está instalado: se omite el instalador (queda el .zip portable)."
        )
        return None
    subprocess.run([str(iscc), f"/DAppVersion={ver}", f"/O{DIST}", str(ISS)], check=True)
    out = DIST / f"RutaSegura-{ver}-instalador.exe"
    print(f"    {out}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-build", action="store_true", help="reusar dist/RutaSegura")
    args = parser.parse_args()
    if sys.platform != "win32":
        print("Este script genera el paquete de Windows; ejecútelo en Windows.")
        return 1
    ver = version()
    if not args.skip_build:
        build()
    self_test()
    portable_zip(ver)
    installer(ver)
    print("Listo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
