"""Catálogo de perfiles por defecto."""

from __future__ import annotations

import pytest

from rutasegura.data.default_profiles import load_default_profiles, parse_default_profiles


def test_packaged_catalog_has_the_three_spec_profiles() -> None:
    defaults = load_default_profiles()
    assert [d.profile.name for d in defaults] == ["adulto", "niño", "movilidad reducida"]


def test_every_value_documents_its_source() -> None:
    for default in load_default_profiles():
        assert set(default.sources) >= {
            "vel_max_mps",
            "reaccion_media_s",
            "reaccion_desv_s",
            "radio_m",
        }
        assert all(text.strip() for text in default.sources.values())


def test_values_are_marked_provisional_until_verified() -> None:
    # Cuando se verifiquen con la fuente, cambiar a provisional: false y ajustar esta prueba.
    assert all(d.provisional for d in load_default_profiles())


def test_reduced_mobility_is_slowest() -> None:
    speeds = {d.profile.name: d.profile.max_speed_mps for d in load_default_profiles()}
    assert speeds["movilidad reducida"] < speeds["niño"] <= speeds["adulto"]


def test_missing_source_is_rejected() -> None:
    text = """
perfiles:
  - nombre: x
    vel_max_mps: 1
    reaccion_media_s: 1
    reaccion_desv_s: 1
    radio_m: 0.2
    fuentes:
      vel_max_mps: algo
"""
    with pytest.raises(ValueError, match="falta la fuente"):
        parse_default_profiles(text)


def test_malformed_file_is_rejected() -> None:
    with pytest.raises(ValueError, match="perfiles"):
        parse_default_profiles("otra_cosa: 1")
