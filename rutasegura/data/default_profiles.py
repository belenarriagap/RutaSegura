"""Carga del catálogo de perfiles por defecto (``resources/profiles/perfiles_por_defecto.yaml``)."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import resources
from typing import Any

import yaml

from rutasegura.domain.people import PersonProfile

PROFILES_RESOURCE = ("rutasegura.resources", "profiles/perfiles_por_defecto.yaml")
_VALUE_FIELDS = ("vel_max_mps", "reaccion_media_s", "reaccion_desv_s", "radio_m")


@dataclass(frozen=True, slots=True)
class DefaultProfile:
    """Perfil por defecto con la fuente de cada valor."""

    profile: PersonProfile
    provisional: bool
    sources: dict[str, str] = field(default_factory=dict)


def parse_default_profiles(text: str) -> list[DefaultProfile]:
    """Interpreta el YAML de perfiles; exige una fuente para cada valor."""
    data: Any = yaml.safe_load(text)
    if not isinstance(data, dict) or not isinstance(data.get("perfiles"), list):
        raise ValueError("El archivo de perfiles debe tener una lista 'perfiles'.")
    result: list[DefaultProfile] = []
    for item in data["perfiles"]:
        sources = {str(k): str(v) for k, v in (item.get("fuentes") or {}).items()}
        missing = [f for f in _VALUE_FIELDS if f not in sources]
        if missing:
            raise ValueError(f"Perfil «{item.get('nombre')}»: falta la fuente de {missing}.")
        profile = PersonProfile(
            name=str(item["nombre"]),
            max_speed_mps=float(item["vel_max_mps"]),
            reaction_mean_s=float(item["reaccion_media_s"]),
            reaction_std_s=float(item["reaccion_desv_s"]),
            radius_m=float(item["radio_m"]),
        )
        result.append(DefaultProfile(profile, bool(item.get("provisional", True)), sources))
    return result


def load_default_profiles() -> list[DefaultProfile]:
    """Lee el catálogo empaquetado con la aplicación (sin red)."""
    package, name = PROFILES_RESOURCE
    text = resources.files(package).joinpath(name).read_text(encoding="utf-8")
    return parse_default_profiles(text)
