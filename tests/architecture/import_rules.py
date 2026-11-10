"""Verificador de reglas de arquitectura basado en el AST (sin dependencias externas).

Reglas (CLAUDE.md §3 y docs/decisiones.md ADR-001):

* Capas: presentation → application → engines/data → domain. ``presentation`` solo habla con
  ``application`` (y usa las estructuras de ``domain``).
* ``engines`` y ``domain`` no importan Qt ni SQLAlchemy; ``application`` y ``data`` no importan Qt.
* Cero red en todo el paquete.
* Aleatoriedad solo con ``numpy.random.Generator``: prohibido ``random`` y la API global de NumPy.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

PACKAGE = "rutasegura"

# Capas internas que cada capa puede importar.
ALLOWED_LAYERS: dict[str, frozenset[str]] = {
    "domain": frozenset({"domain"}),
    "resources": frozenset({"resources"}),
    "engines": frozenset({"domain", "engines", "resources"}),
    "data": frozenset({"domain", "data", "resources"}),
    "application": frozenset({"domain", "engines", "data", "application", "resources"}),
    "presentation": frozenset({"domain", "application", "presentation", "resources"}),
}
# Raíz de composición: puede ensamblar todas las capas.
UNRESTRICTED_LAYERS = frozenset({"__main__", "__init__"})

_QT = frozenset({"PySide6", "shiboken6"})
_DB = frozenset({"sqlalchemy", "alembic"})

FORBIDDEN_EXTERNAL: dict[str, frozenset[str]] = {
    "domain": _QT | _DB | {"cv2", "fitz", "pymupdf", "reportlab", "matplotlib", "yaml"},
    "resources": _QT | _DB,
    "engines": _QT | _DB | {"reportlab"},
    "data": _QT,
    "application": _QT,
    "presentation": _DB | {"cv2"},
}

NETWORK_MODULES = frozenset(
    {
        "socket",
        "ssl",
        "urllib.request",
        "urllib3",
        "http.client",
        "http.server",
        "requests",
        "httpx",
        "aiohttp",
        "ftplib",
        "smtplib",
        "websocket",
        "websockets",
        "PySide6.QtNetwork",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
    }
)

NUMPY_RANDOM_ALLOWED = frozenset(
    {
        "default_rng",
        "Generator",
        "SeedSequence",
        "BitGenerator",
        "PCG64",
        "PCG64DXSM",
        "Philox",
        "SFC64",
        "MT19937",
    }
)


@dataclass(frozen=True)
class Violation:
    """Incumplimiento de una regla, con su ubicación."""

    location: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.location}:{self.line}: {self.message}"


def _matches(name: str, prefixes: frozenset[str]) -> str | None:
    for prefix in prefixes:
        if name == prefix or name.startswith(prefix + "."):
            return prefix
    return None


def _imports(tree: ast.AST, module: str, is_package: bool) -> Iterator[tuple[str, int]]:
    """Nombres absolutos importados.

    Incluye ``paquete.nombre`` en ``from paquete import nombre`` para detectar submódulos.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node.lineno
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = module.split(".") if is_package else module.split(".")[:-1]
                base = parts[: len(parts) - (node.level - 1)]
                if node.module:
                    base = [*base, node.module]
                name = ".".join(base)
            else:
                name = node.module or ""
            yield name, node.lineno
            for alias in node.names:
                if alias.name != "*":
                    yield f"{name}.{alias.name}", node.lineno


def _numpy_aliases(tree: ast.AST) -> dict[str, str]:
    """Mapa alias → módulo para los imports de numpy (``np`` → ``numpy``)."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "numpy" or alias.name.startswith("numpy."):
                    aliases[alias.asname or alias.name.split(".")[0]] = (
                        alias.name if alias.asname else alias.name.split(".")[0]
                    )
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.level == 0
            and (node.module == "numpy" or node.module.startswith("numpy."))
        ):
            for alias in node.names:
                aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return aliases


def _dotted(node: ast.expr) -> list[str] | None:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return parts[::-1]
    return None


def _layer_of(module: str) -> str:
    parts = module.split(".")
    return parts[1] if len(parts) > 1 else "__init__"


def check_source(source: str, module: str, *, is_package: bool = False) -> list[Violation]:
    """Revisa el código fuente de un módulo de ``rutasegura`` y devuelve las violaciones."""
    tree = ast.parse(source)
    layer = _layer_of(module)
    found: list[Violation] = []

    def report(line: int, message: str) -> None:
        found.append(Violation(module, line, message))

    for name, line in _imports(tree, module, is_package):
        top = name.split(".")[0]
        if top == PACKAGE and layer not in UNRESTRICTED_LAYERS:
            target = _layer_of(name)
            allowed = ALLOWED_LAYERS.get(layer, frozenset())
            if target != "__init__" and target not in allowed:
                report(line, f"la capa '{layer}' no puede importar '{target}' ({name})")
        elif top != PACKAGE:
            banned = _matches(name, FORBIDDEN_EXTERNAL.get(layer, frozenset()))
            if banned:
                report(line, f"la capa '{layer}' no puede importar '{banned}'")
        net = _matches(name, NETWORK_MODULES)
        if net:
            report(line, f"acceso a red prohibido ('{net}')")
        if name == "random" or name.startswith("random."):
            report(line, "usa numpy.random.Generator con la semilla del escenario, no 'random'")
        if name.startswith("numpy.random."):
            leaf = name.split(".")[2]
            if leaf not in NUMPY_RANDOM_ALLOWED:
                report(line, f"API aleatoria global de NumPy prohibida ({name})")

    aliases = _numpy_aliases(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            parts = _dotted(node)
            if not parts or parts[0] not in aliases:
                continue
            full = ".".join([aliases[parts[0]], *parts[1:]]).split(".")
            is_global_random = (
                full[:2] == ["numpy", "random"]
                and len(full) > 2
                and full[2] not in NUMPY_RANDOM_ALLOWED
            )
            if is_global_random:
                report(node.lineno, f"API aleatoria global de NumPy prohibida ({'.'.join(full)})")
    return found


def check_package(package_dir: Path) -> tuple[list[Violation], int]:
    """Revisa todos los ``.py`` del paquete. Devuelve (violaciones, archivos revisados)."""
    violations: list[Violation] = []
    files = sorted(package_dir.rglob("*.py"))
    for path in files:
        rel = path.relative_to(package_dir.parent).with_suffix("")
        is_package = rel.name == "__init__"
        parts = rel.parts[:-1] if is_package else rel.parts
        module = ".".join(parts)
        violations.extend(
            check_source(path.read_text(encoding="utf-8"), module, is_package=is_package)
        )
    return violations, len(files)
