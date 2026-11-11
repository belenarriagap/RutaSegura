"""Verificación normativa de un piso: aforo y anchos de evacuación (RF06).

* Aforo de cada ambiente = área útil ÷ índice de ocupación de su categoría (redondeo hacia abajo).
* Puertas de un ambiente: las puertas y salidas cuyo punto medio está sobre su contorno.
  Su ancho total se compara con ``ocupantes × metros_por_persona``.
* Salidas del local: ancho total de salidas confirmadas vs. ocupantes totales.
* Anchos mínimos de cada puerta, salida y pasillo (ambientes de categoría «circulación»; el ancho
  del pasillo se estima como el diámetro del mayor círculo inscrito).
* Barra antipánico: aviso cuando un ambiente supera el umbral de personas.

Cada observación cita norma y artículo y lleva ``verified`` de la regla usada.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

import cv2
import numpy as np

from rutasegura.domain.enums import ObservationType
from rutasegura.domain.geometry import Point, Polygon, Segment
from rutasegura.domain.norms import NormEvaluation, NormRule, RoomCapacity
from rutasegura.domain.people import Occupancy
from rutasegura.domain.plan import FloorPlan, Room
from rutasegura.domain.results import Observation
from rutasegura.engines.norms.rules import (
    KIND_ANTIPANIC,
    KIND_MIN_WIDTH,
    KIND_WIDTH_PER_PERSON,
    Rule,
    RuleSet,
)

DOOR_TOLERANCE_M = 0.6  # distancia máxima del vano al contorno del ambiente
CORRIDOR_RESOLUTION_M = 0.05


def _to_m(p: Point, scale: float) -> Point:
    return Point(p.x * scale, p.y * scale)


def _polygon_m(polygon: Polygon, scale: float) -> Polygon:
    return Polygon(tuple(_to_m(p, scale) for p in polygon.vertices))


def _segment_m(segment: Segment, scale: float) -> Segment:
    return Segment(_to_m(segment.start, scale), _to_m(segment.end, scale))


def _distance_to_segment(p: Point, a: Point, b: Point) -> float:
    dx, dy = b.x - a.x, b.y - a.y
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((p.x - a.x) * dx + (p.y - a.y) * dy) / length2))
    return math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy))


def distance_to_boundary(polygon: Polygon, p: Point) -> float:
    """Distancia de un punto al contorno de un polígono."""
    vertices = polygon.vertices
    return min(
        _distance_to_segment(p, vertices[i], vertices[(i + 1) % len(vertices)])
        for i in range(len(vertices))
    )


def corridor_width(polygon_m: Polygon, resolution: float = CORRIDOR_RESOLUTION_M) -> float:
    """Ancho de un pasillo ≈ diámetro del mayor círculo inscrito (m)."""
    xs = [p.x for p in polygon_m.vertices]
    ys = [p.y for p in polygon_m.vertices]
    x0, y0 = min(xs) - 2 * resolution, min(ys) - 2 * resolution
    cols = math.ceil((max(xs) - x0) / resolution) + 3
    rows = math.ceil((max(ys) - y0) / resolution) + 3
    mask = np.zeros((rows, cols), np.uint8)
    pts = np.array(
        [
            [round((p.x - x0) / resolution), round((p.y - y0) / resolution)]
            for p in polygon_m.vertices
        ],
        dtype=np.int32,
    )
    cv2.fillPoly(mask, [pts], 1)
    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    return float(2.0 * dist.max() * resolution)


def _observation(
    rule: Rule, description: str, location: Point | None, recommendation: str | None = None
) -> Observation:
    return Observation(
        kind=ObservationType.NORM,
        description=description,
        recommendation=recommendation or rule.recommendation,
        location=location,
        norm=rule.norm,
        article=rule.article,
        verified=rule.verified,
    )


def evaluate(
    plan: FloorPlan,
    occupancies: Sequence[Occupancy],
    rules: RuleSet,
    *,
    exit_occupants: int | None = None,
) -> NormEvaluation:
    """Evalúa aforo y anchos del piso con las reglas dadas.

    ``exit_occupants`` indica cuántas personas deben salir por las salidas de este piso (en un
    edificio de varios pisos, todo el edificio sale por el piso 1). ``0`` omite la verificación
    del ancho total de salidas (pisos altos, que se evacúan por escaleras).
    """
    scale = plan.scale_m_per_px
    if scale is None:
        raise ValueError("El plano no tiene escala; defínala en el paso 2.")
    used: dict[str, Rule] = {}
    observations: list[Observation] = []

    def use(rule: Rule) -> Rule:
        used[rule.id] = rule
        return rule

    counts: dict[str, int] = {}
    for occ in occupancies:
        if occ.level == plan.level:
            counts[occ.room_name] = counts.get(occ.room_name, 0) + occ.count

    # Vanos en metros (puertas y salidas) con sus nombres para describirlos.
    doors_m = [_segment_m(d.segment, scale) for d in plan.doors]
    exits_m = [(e.name, _segment_m(e.segment, scale), e.confirmed) for e in plan.exits]
    rooms_m = [(room, _polygon_m(room.area, scale)) for room in plan.rooms]

    def rooms_at(point: Point) -> list[str]:
        return [
            room.name
            for room, poly in rooms_m
            if distance_to_boundary(poly, point) <= DOOR_TOLERANCE_M
        ]

    # ------------------------------------------------------------------ aforo por ambiente
    capacities: list[RoomCapacity] = []
    for room, poly in rooms_m:
        capacities.append(_capacity(room, poly, plan.level, counts, rules, use, observations))

    # ------------------------------------------------------------------ puertas por ambiente
    per_person = rules.first(KIND_WIDTH_PER_PERSON, "puerta")
    if per_person is not None:
        factor = per_person.number("metros_por_persona")
        for room, poly in rooms_m:
            people = counts.get(room.name, 0)
            if people == 0:
                continue
            openings = [
                s for s in doors_m if distance_to_boundary(poly, s.midpoint) <= DOOR_TOLERANCE_M
            ]
            openings += [
                s
                for _, s, _ in exits_m
                if distance_to_boundary(poly, s.midpoint) <= DOOR_TOLERANCE_M
            ]
            available = sum(s.length for s in openings)
            required = people * factor
            use(per_person)
            if available + 1e-9 < required:
                observations.append(
                    _observation(
                        per_person,
                        f"Las puertas de «{room.name}» suman {available:.2f} m de ancho y, para "
                        f"{people} personas, se requieren {required:.2f} m.",
                        poly.centroid,
                    )
                )

    # ------------------------------------------------------------------ anchos mínimos
    door_min = rules.first(KIND_MIN_WIDTH, "puerta")
    if door_min is not None and doors_m:
        minimum = use(door_min).number("metros")
        for seg in doors_m:
            if seg.length + 1e-9 < minimum:
                where = " y ".join(f"«{n}»" for n in rooms_at(seg.midpoint)) or "sin ambiente"
                observations.append(
                    _observation(
                        door_min,
                        f"Una puerta de {where} mide {seg.length:.2f} m; el mínimo es "
                        f"{minimum:.2f} m.",
                        seg.midpoint,
                    )
                )
    exit_min = rules.first(KIND_MIN_WIDTH, "salida")
    if exit_min is not None and exits_m:
        minimum = use(exit_min).number("metros")
        for name, seg, _ in exits_m:
            if seg.length + 1e-9 < minimum:
                observations.append(
                    _observation(
                        exit_min,
                        f"«{name}» mide {seg.length:.2f} m; el mínimo es {minimum:.2f} m.",
                        seg.midpoint,
                    )
                )
    corridor_min = rules.first(KIND_MIN_WIDTH, "pasillo")
    if corridor_min is not None:
        for room, poly in rooms_m:
            category = rules.category(room.use, room.category)
            if category is None or not category.circulation:
                continue
            minimum = use(corridor_min).number("metros")
            width = corridor_width(poly)
            if width + 1e-9 < minimum:
                observations.append(
                    _observation(
                        corridor_min,
                        f"El pasillo «{room.name}» tiene unos {width:.2f} m de ancho libre; el "
                        f"mínimo es {minimum:.2f} m.",
                        poly.centroid,
                    )
                )

    # ------------------------------------------------------------------ salidas del local
    exit_rule = rules.first(KIND_WIDTH_PER_PERSON, "salida")
    total_people = sum(counts.values()) if exit_occupants is None else exit_occupants
    if exit_rule is not None and total_people > 0:
        factor = use(exit_rule).number("metros_por_persona")
        available = sum(seg.length for _, seg, confirmed in exits_m if confirmed)
        required = total_people * factor
        if available + 1e-9 < required:
            observations.append(
                _observation(
                    exit_rule,
                    f"Las salidas confirmadas suman {available:.2f} m de ancho y, para "
                    f"{total_people} personas, se requieren {required:.2f} m.",
                    None,
                )
            )

    # ------------------------------------------------------------------ barra antipánico
    antipanic = rules.first(KIND_ANTIPANIC)
    if antipanic is not None:
        threshold = int(antipanic.params["umbral_personas"])
        for room, poly in rooms_m:
            people = counts.get(room.name, 0)
            if people > threshold:
                use(antipanic)
                observations.append(
                    _observation(
                        antipanic,
                        f"«{room.name}» tiene {people} personas (más de {threshold}).",
                        poly.centroid,
                    )
                )

    return NormEvaluation(
        capacities=tuple(capacities),
        observations=tuple(observations),
        rules_used=tuple(r.as_domain() for r in sorted(used.values(), key=lambda r: r.id)),
    )


def _capacity(
    room: Room,
    poly: Polygon,
    level: int,
    counts: dict[str, int],
    rules: RuleSet,
    use: Callable[[Rule], Rule],
    observations: list[Observation],
) -> RoomCapacity:
    category = rules.category(room.use, room.category)
    area = poly.area
    people = counts.get(room.name, 0)
    if category is None:
        return RoomCapacity(room.name, level, room.category, "", area, None, None, people, None)
    rule = use(category.rule)
    capacity = None
    if category.m2_per_person is not None:
        capacity = math.floor(area / category.m2_per_person + 1e-9)
        if people > capacity:
            observations.append(
                _observation(
                    rule,
                    f"«{room.name}» tiene {people} personas asignadas y su aforo es {capacity} "
                    f"({area:.1f} m² ÷ {category.m2_per_person:g} m² por persona).",
                    poly.centroid,
                )
            )
    return RoomCapacity(
        room_name=room.name,
        level=level,
        category=category.id,
        category_label=category.label,
        area_m2=round(area, 2),
        m2_per_person=category.m2_per_person,
        capacity=capacity,
        occupants=people,
        rule_id=rule.id,
    )


def describe_rules(rules: Sequence[NormRule]) -> list[str]:
    """Líneas legibles «id — descripción (cita)»."""
    return [f"{r.id} — {r.description} ({r.citation})" for r in rules]
