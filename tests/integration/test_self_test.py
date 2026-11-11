"""Opciones de línea de comandos y autoprueba de la instalación."""

from __future__ import annotations

from pathlib import Path

import pytest

import rutasegura
from rutasegura.__main__ import main
from rutasegura.application import self_test
from rutasegura.resources.icons import icon_path


def test_version(tmp_path: Path) -> None:
    log = tmp_path / "version.txt"
    assert main(["--version", "--log", str(log)]) == 0
    assert log.read_text(encoding="utf-8").strip() == f"RutaSegura {rutasegura.__version__}"


def test_self_test_passes(tmp_path: Path) -> None:
    log = tmp_path / "autoprueba.txt"
    assert main(["--self-test", "--log", str(log)]) == 0
    text = log.read_text(encoding="utf-8")
    assert text.count("OK     ") == 5
    assert "Autoprueba superada." in text


def test_self_test_reports_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken() -> object:
        raise RuntimeError("faltan las reglas")

    monkeypatch.setattr(self_test, "load_packaged_rules", broken)
    lines: list[str] = []
    assert not self_test.run_self_test(lines.append)
    assert any(line.startswith("FALLA  Reglas normativas") for line in lines)
    assert lines[-1] == "La autoprueba encontró errores."


def test_icon_files_exist() -> None:
    assert icon_path().exists()
    assert icon_path().with_suffix(".ico").exists()
