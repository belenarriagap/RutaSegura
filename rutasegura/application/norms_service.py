"""Verificación normativa: aforo y anchos (RF06), con las reglas empaquetadas."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from importlib import resources

from rutasegura.application.errors import UserFacingError
from rutasegura.domain.enums import UseType
from rutasegura.domain.norms import NormEvaluation, NormRule, RoomCapacity
from rutasegura.domain.plan import FloorPlan
from rutasegura.domain.results import Observation
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

    def evaluate(
        self, plan: FloorPlan, scenario: Scenario | None, *, exit_occupants: int | None = None
    ) -> NormEvaluation:
        """Evalúa un piso con la ocupación del escenario."""
        occupancies = scenario.occupancies if scenario is not None else ()
        try:
            return evaluate(plan, occupancies, self._rules, exit_occupants=exit_occupants)
        except ValueError as exc:
            raise UserFacingError(str(exc)) from exc

    def evaluate_building(
        self, floors: Sequence[FloorPlan], scenario: Scenario | None
    ) -> NormEvaluation:
        """Evalúa todos los pisos. En varios pisos, las salidas del piso más bajo deben dar
        paso a todo el edificio y los pisos altos no se evalúan por salidas (bajan por escaleras).
        Las observaciones indican el piso.
        """
        ordered = sorted(floors, key=lambda f: f.level)
        if len(ordered) <= 1:
            return self.evaluate(ordered[0], scenario) if ordered else NormEvaluation()
        total = scenario.total_occupants if scenario is not None else 0
        capacities: list[RoomCapacity] = []
        observations: list[Observation] = []
        rules: dict[str, NormRule] = {}
        for k, plan in enumerate(ordered):
            result = self.evaluate(plan, scenario, exit_occupants=total if k == 0 else 0)
            capacities.extend(result.capacities)
            observations.extend(
                dataclasses.replace(o, description=f"Piso {plan.level + 1}: {o.description}")
                for o in result.observations
            )
            rules.update({r.id: r for r in result.rules_used})
        return NormEvaluation(
            capacities=tuple(capacities),
            observations=tuple(observations),
            rules_used=tuple(rules[k] for k in sorted(rules)),
        )
