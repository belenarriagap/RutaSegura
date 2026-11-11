"""Motor de reglas: carga/validación del YAML y verificaciones de aforo y anchos."""

from __future__ import annotations

import dataclasses

import pytest

from rutasegura.domain.enums import ObservationType, UseType
from rutasegura.domain.people import Occupancy
from rutasegura.domain.plan import Door, Exit, FloorPlan, Room
from rutasegura.engines.norms.evaluate import corridor_width, distance_to_boundary, evaluate
from rutasegura.engines.norms.rules import RuleError, parse_rules
from tests.fixtures.simple_plans import SCALE, _seg, rect, single_room, two_rooms
from tests.unit.norms.helpers import packaged_rules

RULES = packaged_rules()


def _ids(observations: object) -> list[str]:
    return [o.description for o in observations]  # type: ignore[attr-defined]


class TestRules:
    def test_packaged_rules_are_valid_and_unverified(self) -> None:
        assert len(RULES.rules) >= 10
        assert all(not r.verified for r in RULES.rules)  # hasta confirmarlas con el RNE
        for use in UseType:
            categories = RULES.categories(use)
            assert categories, use
            assert categories[0].default
            assert any(c.circulation for c in categories)

    def test_category_lookup_falls_back_to_default(self) -> None:
        assert RULES.category(UseType.EDUCATION, "taller").id == "taller"  # type: ignore[union-attr]
        assert RULES.category(UseType.EDUCATION, "").id == "aula"  # type: ignore[union-attr]
        assert RULES.category(UseType.OFFICE, "no-existe").id == "oficina"  # type: ignore[union-attr]

    @pytest.mark.parametrize(
        ("yaml_text", "message"),
        [
            ("otra: 1", "lista «reglas»"),
            ("reglas: [1]", "diccionario"),
            ("reglas:\n  - id: X\n    tipo: indice_ocupacion", "falta el campo"),
            (
                "reglas:\n  - {id: X, tipo: rara, descripcion: d, norma: n, articulo: a, "
                "verificado: false, recomendacion: r}",
                "tipo desconocido",
            ),
            (
                "reglas:\n  - {id: X, tipo: ancho_minimo, descripcion: d, norma: n, articulo: a, "
                "verificado: 'no', recomendacion: r, elemento: puerta, metros: 1}",
                "true o false",
            ),
            (
                "reglas:\n  - {id: X, tipo: ancho_minimo, descripcion: d, norma: n, articulo: a, "
                "verificado: false, recomendacion: r, elemento: ventana, metros: 1}",
                "elemento desconocido",
            ),
            (
                "reglas:\n  - {id: X, tipo: indice_ocupacion, descripcion: d, norma: n, "
                "articulo: a, verificado: false, recomendacion: r, uso: hotel, categoria: c, "
                "m2_por_persona: 1}",
                "uso desconocido",
            ),
            (
                "reglas:\n  - {id: X, tipo: indice_ocupacion, descripcion: d, norma: n, "
                "articulo: a, verificado: false, recomendacion: r, uso: oficinas, categoria: c}",
                "m2_por_persona",
            ),
            ("reglas: [", "no es válido"),
        ],
    )
    def test_invalid_files(self, yaml_text: str, message: str) -> None:
        with pytest.raises(RuleError, match=message):
            parse_rules([("prueba.yaml", yaml_text)])

    def test_duplicate_ids(self) -> None:
        rule = (
            "reglas:\n  - {id: X, tipo: barra_antipanico, descripcion: d, norma: n, articulo: a, "
            "verificado: true, recomendacion: r, umbral_personas: 100}"
        )
        with pytest.raises(RuleError, match="repetido"):
            parse_rules([("a.yaml", rule), ("b.yaml", rule)])


class TestEvaluation:
    def test_capacity_and_overcrowding(self) -> None:
        plan = single_room()  # aula de 10 × 6 m = 60 m² → aforo 40 con 1.5 m²/persona
        ok = evaluate(plan, [Occupancy("Aula 1", "niño", 40)], RULES)
        assert ok.capacities[0].capacity == 40
        assert not ok.capacities[0].exceeded
        assert ok.total_capacity == 40
        assert not any("aforo" in d for d in _ids(ok.observations))
        over = evaluate(plan, [Occupancy("Aula 1", "niño", 45)], RULES)
        assert over.capacities[0].exceeded
        observation = next(o for o in over.observations if "aforo es 40" in o.description)
        assert observation.kind is ObservationType.NORM
        assert observation.norm == "RNE A.040"
        assert observation.article
        assert not observation.verified
        assert any(r.id == "OCU-EDU-AULA" for r in over.unverified_rules)

    def test_door_width_per_person(self) -> None:
        plan = two_rooms()  # Aula 1 tiene una puerta de 0.9 m
        fine = evaluate(plan, [Occupancy("Aula 1", "niño", 20)], RULES)
        assert not any("puertas de «Aula 1»" in d for d in _ids(fine.observations))
        # 0.9 m alcanza para 180 personas con 0.005 m/persona
        crowded = evaluate(plan, [Occupancy("Aula 1", "niño", 200)], RULES)
        assert any("puertas de «Aula 1» suman 0.90 m" in d for d in _ids(crowded.observations))

    def test_minimum_widths_of_doors_and_exits(self) -> None:
        narrow = dataclasses.replace(
            two_rooms(),
            doors=(Door(_seg(6, 2.7, 6, 3.3)),),  # 0.6 m
            exits=(Exit(_seg(12, 2.6, 12, 3.4), "Salida principal"),),  # 0.8 m
        )
        result = evaluate(narrow, [], RULES)
        texts = _ids(result.observations)
        assert any("Una puerta de «Aula 1» y «Aula 2» mide 0.60 m" in t for t in texts)
        assert any("«Salida principal» mide 0.80 m" in t for t in texts)

    def test_total_exit_width(self) -> None:
        plan = single_room(exit_width=1.2)  # 1.2 m → 240 personas
        result = evaluate(plan, [Occupancy("Aula 1", "adulto", 300)], RULES)
        assert any("salidas confirmadas suman 1.20 m" in d for d in _ids(result.observations))
        unconfirmed = evaluate(single_room(confirmed=False), [Occupancy("Aula 1", "a", 1)], RULES)
        assert any("suman 0.00 m" in d for d in _ids(unconfirmed.observations))

    def test_antipanic_warning(self) -> None:
        plan = single_room(width=20, height=10)
        result = evaluate(plan, [Occupancy("Aula 1", "adulto", 101)], RULES)
        assert any("más de 100" in d for d in _ids(result.observations))
        assert not any(
            "más de 100" in d
            for d in _ids(evaluate(plan, [Occupancy("Aula 1", "adulto", 100)], RULES).observations)
        )

    def test_corridor_width(self) -> None:
        corridor = Room("Pasillo", UseType.EDUCATION, rect(0, 0, 1.0, 10.0), "pasillo")
        plan = FloorPlan(scale_m_per_px=SCALE, rooms=(corridor,))
        result = evaluate(plan, [], RULES)
        assert result.capacities[0].capacity is None
        assert any("pasillo «Pasillo»" in d for d in _ids(result.observations))
        wide = dataclasses.replace(
            plan, rooms=(dataclasses.replace(corridor, area=rect(0, 0, 2.0, 10.0)),)
        )
        assert not evaluate(wide, [], RULES).observations

    def test_requires_scale(self) -> None:
        with pytest.raises(ValueError, match="escala"):
            evaluate(dataclasses.replace(single_room(), scale_m_per_px=None), [], RULES)

    def test_other_levels_are_ignored(self) -> None:
        result = evaluate(single_room(), [Occupancy("Aula 1", "niño", 500, level=1)], RULES)
        assert result.capacities[0].occupants == 0


def test_geometry_helpers() -> None:
    poly = rect(0, 0, 4, 2)
    poly_m = type(poly)(tuple(type(p)(p.x * SCALE, p.y * SCALE) for p in poly.vertices))
    assert corridor_width(poly_m) == pytest.approx(2.0, abs=0.15)
    assert distance_to_boundary(poly_m, type(poly.vertices[0])(2.0, 1.0)) == pytest.approx(1.0)
