"""Verificación normativa: aforo y anchos (RF06), con las reglas empaquetadas."""

from __future__ import annotations

from importlib import resources

from rutasegura.application.errors import UserFacingError
from rutasegura.domain.enums import UseType
from rutasegura.domain.norms import NormEvaluation
from rutasegura.domain.plan import FloorPlan
from rutasegura.domain.scenario import Scenario
from rutasegura.engines.norms.evaluate import evaluate
from rutasegura.engines.norms.rules import RuleError, RuleSet, parse_rules


def load_packaged_rules() -> RuleSet:
    """Lee todas las reglas de ``rutasegura/resources/norms/*.yaml`` (sin red)."""
    folder = resources.files("rutasegura.resources").joinpath("norms")
    documents = sorted(
        (item.name, item.read_text(encoding="utf-8"))
        for item in folder.iterdir()
        if item.name.endswith(".yaml")
    )
    try:
        return parse_rules(documents)
    except RuleError as exc:
        raise UserFacingError(f"Las reglas normativas tienen un error: {exc}") from exc


class NormsService:
    """Aforo, anchos mínimos y observaciones normativas."""

    def __init__(self, rules: RuleSet | None = None) -> None:
        self._rules = rules or load_packaged_rules()

    def categories(self, use: UseType) -> list[tuple[str, str]]:
        """(id, etiqueta) de las categorías de ambiente de un uso; la de por defecto primero."""
        return [(c.id, c.label) for c in self._rules.categories(use)]

    def evaluate(self, plan: FloorPlan, scenario: Scenario | None) -> NormEvaluation:
        """Evalúa el plano con la ocupación del escenario."""
        occupancies = scenario.occupancies if scenario is not None else ()
        try:
            return evaluate(plan, occupancies, self._rules)
        except ValueError as exc:
            raise UserFacingError(str(exc)) from exc
