"""Avance del asistente: qué pasos están completos y qué falta en cada uno.

La interfaz usa esto para marcar los pasos (✓, ⚠) y mostrar el recuadro «Qué falta». Solo
devuelve códigos; los textos los pone la capa de presentación.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rutasegura.domain.plan import FloorPlan
from rutasegura.domain.results import SimulationResult
from rutasegura.domain.scenario import Scenario

STEP_LOAD, STEP_SCALE, STEP_EDIT, STEP_ROOMS, STEP_NORMS, STEP_SIMULATE, STEP_REPORT = range(7)
STEP_COUNT = 7


class StepState(Enum):
    """Estado de un paso."""

    TODO = "pendiente"
    WARNING = "revisar"
    DONE = "completo"


class Issue(Enum):
    """Lo que falta (o conviene revisar) en un paso."""

    NO_IMAGE = "sin_imagen"
    NO_SCALE = "sin_escala"
    NO_WALLS = "sin_muros"
    NO_EXITS = "sin_salidas"
    PENDING_EXITS = "salidas_por_confirmar"
    NO_ROOMS = "sin_ambientes"
    NO_OCCUPANTS = "sin_ocupantes"
    NO_RUN = "sin_simulacion"
    RUN_INCOMPLETE = "simulacion_incompleta"


# Qué pasos deben estar completos antes de cada uno.
PREREQUISITES: dict[int, tuple[int, ...]] = {
    STEP_LOAD: (),
    STEP_SCALE: (STEP_LOAD,),
    STEP_EDIT: (STEP_LOAD,),
    STEP_ROOMS: (STEP_SCALE, STEP_EDIT),
    STEP_NORMS: (STEP_SCALE, STEP_ROOMS),
    STEP_SIMULATE: (STEP_SCALE, STEP_EDIT, STEP_ROOMS),
    STEP_REPORT: (),
}


@dataclass(frozen=True)
class StepProgress:
    """Estado de un paso y lo primero que le falta (si algo)."""

    state: StepState
    issue: Issue | None = None


@dataclass(frozen=True)
class Blocker:
    """Algo de un paso anterior que impide completar el paso actual."""

    step: int
    issue: Issue


@dataclass(frozen=True)
class WizardProgress:
    """Avance de los 7 pasos."""

    steps: tuple[StepProgress, ...]

    def blocker(self, step: int) -> Blocker | None:
        """Primer paso previo sin completar que necesita ``step`` (o ``None``)."""
        for previous in PREREQUISITES.get(step, ()):
            progress = self.steps[previous]
            if progress.state is StepState.TODO and progress.issue is not None:
                return Blocker(previous, progress.issue)
        return None


def _has_way_out(plan: FloorPlan, is_lowest: bool) -> bool:
    if any(e.confirmed for e in plan.exits) or plan.safe_zones:
        return True
    # En los pisos altos se baja por la escalera.
    return not is_lowest and any(s.confirmed for s in plan.stairs)


def wizard_progress(
    plan: FloorPlan,
    *,
    has_image: bool,
    scenario: Scenario | None,
    result: SimulationResult | None,
    is_lowest_floor: bool = True,
) -> WizardProgress:
    """Calcula el avance del piso en edición, su ocupación y la última simulación."""
    steps: list[StepProgress] = []
    # 1. Cargar plano
    steps.append(
        StepProgress(StepState.DONE) if has_image else StepProgress(StepState.TODO, Issue.NO_IMAGE)
    )
    # 2. Escala
    has_scale = plan.scale_m_per_px is not None
    steps.append(
        StepProgress(StepState.DONE) if has_scale else StepProgress(StepState.TODO, Issue.NO_SCALE)
    )
    # 3. Corregir plano
    if not plan.walls:
        steps.append(StepProgress(StepState.TODO, Issue.NO_WALLS))
    elif not _has_way_out(plan, is_lowest_floor):
        steps.append(StepProgress(StepState.TODO, Issue.NO_EXITS))
    elif plan.has_pending_proposals:
        steps.append(StepProgress(StepState.WARNING, Issue.PENDING_EXITS))
    else:
        steps.append(StepProgress(StepState.DONE))
    # 4. Ambientes y ocupantes
    occupants = 0
    if scenario is not None:
        occupants = sum(o.count for o in scenario.occupancies if o.level == plan.level)
    if not plan.rooms:
        steps.append(StepProgress(StepState.TODO, Issue.NO_ROOMS))
    elif occupants == 0:
        steps.append(StepProgress(StepState.TODO, Issue.NO_OCCUPANTS))
    else:
        steps.append(StepProgress(StepState.DONE))
    # 5. Revisar norma: se calcula sola cuando hay escala y ambientes
    ready = has_scale and bool(plan.rooms)
    steps.append(StepProgress(StepState.DONE if ready else StepState.TODO))
    # 6. Simular
    if result is None:
        steps.append(StepProgress(StepState.TODO, Issue.NO_RUN))
    elif not result.completed:
        steps.append(StepProgress(StepState.WARNING, Issue.RUN_INCOMPLETE))
    else:
        steps.append(StepProgress(StepState.DONE))
    # 7. Informe: siempre disponible
    steps.append(StepProgress(StepState.TODO))
    return WizardProgress(tuple(steps))
