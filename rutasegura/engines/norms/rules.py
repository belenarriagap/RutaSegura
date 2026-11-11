"""Motor de reglas guiado por datos: carga y valida las reglas normativas desde YAML."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

import yaml

from rutasegura.domain.enums import UseType
from rutasegura.domain.norms import NormRule

KIND_OCCUPANCY = "indice_ocupacion"
KIND_WIDTH_PER_PERSON = "ancho_por_persona"
KIND_MIN_WIDTH = "ancho_minimo"
KIND_ANTIPANIC = "barra_antipanico"
KINDS = frozenset({KIND_OCCUPANCY, KIND_WIDTH_PER_PERSON, KIND_MIN_WIDTH, KIND_ANTIPANIC})
ELEMENTS = frozenset({"puerta", "salida", "pasillo"})
_COMMON = ("id", "tipo", "descripcion", "norma", "articulo", "verificado", "recomendacion")


class RuleError(ValueError):
    """El archivo de reglas tiene un error de formato."""


@dataclass(frozen=True)
class Rule:
    """Regla normativa con sus parámetros específicos."""

    id: str
    kind: str
    description: str
    norm: str
    article: str
    verified: bool
    recommendation: str
    params: Mapping[str, Any] = field(default_factory=dict)

    def as_domain(self) -> NormRule:
        """Versión de dominio (para citar en observaciones e informes)."""
        return NormRule(
            self.id, self.kind, self.description, self.norm, self.article, self.verified
        )

    def number(self, key: str) -> float:
        """Parámetro numérico obligatorio."""
        return float(self.params[key])


@dataclass(frozen=True)
class Category:
    """Categoría de ambiente (actividad) con su índice de ocupación."""

    id: str
    label: str
    use: UseType
    m2_per_person: float | None
    circulation: bool
    default: bool
    rule: Rule


class RuleSet:
    """Conjunto de reglas con consultas por tipo, uso y categoría."""

    def __init__(self, rules: Iterable[Rule]) -> None:
        self.rules: tuple[Rule, ...] = tuple(rules)
        ids = [r.id for r in self.rules]
        duplicated = sorted({i for i in ids if ids.count(i) > 1})
        if duplicated:
            raise RuleError(f"Hay reglas con id repetido: {', '.join(duplicated)}.")
        self._categories: dict[UseType, list[Category]] = {u: [] for u in UseType}
        for rule in self.rules:
            if rule.kind != KIND_OCCUPANCY:
                continue
            m2 = rule.params.get("m2_por_persona")
            use = UseType(rule.params["uso"])
            self._categories[use].append(
                Category(
                    id=str(rule.params["categoria"]),
                    label=str(rule.params.get("etiqueta", rule.params["categoria"])),
                    use=use,
                    m2_per_person=None if m2 is None else float(m2),
                    circulation=bool(rule.params.get("circulacion", False)),
                    default=bool(rule.params.get("por_defecto", False)),
                    rule=rule,
                )
            )

    def categories(self, use: UseType) -> list[Category]:
        """Categorías disponibles para un uso (la de por defecto primero)."""
        return sorted(self._categories[use], key=lambda c: not c.default)

    def category(self, use: UseType, category_id: str) -> Category | None:
        """Categoría pedida, o la de por defecto si no se indica o no existe."""
        options = self.categories(use)
        for option in options:
            if option.id == category_id:
                return option
        return options[0] if options else None

    def of_kind(self, kind: str, element: str | None = None) -> list[Rule]:
        """Reglas de un tipo (y, si se indica, de un elemento)."""
        return [
            r
            for r in self.rules
            if r.kind == kind and (element is None or r.params.get("elemento") == element)
        ]

    def first(self, kind: str, element: str | None = None) -> Rule | None:
        """Primera regla de un tipo/elemento, o ``None``."""
        found = self.of_kind(kind, element)
        return found[0] if found else None


def _require(item: Mapping[str, Any], key: str, where: str) -> Any:
    if key not in item or item[key] is None or item[key] == "":
        raise RuleError(f"{where}: falta el campo «{key}».")
    return item[key]


def _parse_rule(item: Any, source: str) -> Rule:
    if not isinstance(item, dict):
        raise RuleError(f"{source}: cada regla debe ser un diccionario.")
    where = f"{source}, regla {item.get('id', '?')}"
    for key in _COMMON:
        _require(item, key, where)
    kind = str(item["tipo"])
    if kind not in KINDS:
        raise RuleError(f"{where}: tipo desconocido «{kind}».")
    if not isinstance(item["verificado"], bool):
        raise RuleError(f"{where}: «verificado» debe ser true o false.")
    if kind == KIND_OCCUPANCY:
        _require(item, "uso", where)
        _require(item, "categoria", where)
        try:
            UseType(item["uso"])
        except ValueError as exc:
            raise RuleError(f"{where}: uso desconocido «{item['uso']}».") from exc
        if "m2_por_persona" not in item:
            raise RuleError(f"{where}: falta el campo «m2_por_persona» (use null si no aplica).")
        m2 = item["m2_por_persona"]
        if m2 is not None and float(m2) <= 0:
            raise RuleError(f"{where}: «m2_por_persona» debe ser positivo.")
    elif kind in (KIND_WIDTH_PER_PERSON, KIND_MIN_WIDTH):
        element = _require(item, "elemento", where)
        if element not in ELEMENTS:
            raise RuleError(f"{where}: elemento desconocido «{element}».")
        key = "metros_por_persona" if kind == KIND_WIDTH_PER_PERSON else "metros"
        if float(_require(item, key, where)) <= 0:
            raise RuleError(f"{where}: «{key}» debe ser positivo.")
    elif kind == KIND_ANTIPANIC and int(_require(item, "umbral_personas", where)) <= 0:
        raise RuleError(f"{where}: «umbral_personas» debe ser positivo.")
    params = {k: v for k, v in item.items() if k not in _COMMON}
    return Rule(
        id=str(item["id"]),
        kind=kind,
        description=str(item["descripcion"]),
        norm=str(item["norma"]),
        article=str(item["articulo"]),
        verified=bool(item["verificado"]),
        recommendation=" ".join(str(item["recomendacion"]).split()),
        params=params,
    )


def parse_rules(documents: Iterable[tuple[str, str]]) -> RuleSet:
    """Lee reglas desde pares (nombre de archivo, texto YAML)."""
    rules: list[Rule] = []
    for source, text in documents:
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise RuleError(f"{source}: el YAML no es válido ({exc}).") from exc
        if not isinstance(data, dict) or not isinstance(data.get("reglas"), list):
            raise RuleError(f"{source}: debe tener una lista «reglas».")
        rules.extend(_parse_rule(item, source) for item in data["reglas"])
    return RuleSet(rules)
