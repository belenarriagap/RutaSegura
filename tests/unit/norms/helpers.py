"""Utilidades para las pruebas de normas."""

from __future__ import annotations

from pathlib import Path

import rutasegura
from rutasegura.engines.norms.rules import RuleSet, parse_rules

NORMS_DIR = Path(rutasegura.__file__).parent / "resources" / "norms"


def packaged_rules() -> RuleSet:
    """Reglas empaquetadas con la aplicación."""
    return parse_rules(
        (p.name, p.read_text(encoding="utf-8")) for p in sorted(NORMS_DIR.glob("*.yaml"))
    )
