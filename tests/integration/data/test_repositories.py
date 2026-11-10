"""Repositorios contra una base SQLite real (archivo temporal, migrada con Alembic)."""

from __future__ import annotations

import dataclasses
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pytest
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.exc import IntegrityError

from rutasegura.data.database import Database, plain_sqlite_engine
from rutasegura.data.models import (
    ElementRecord,
    OccupancyRecord,
    PersonProfileRecord,
    RoomRecord,
)
from rutasegura.data.repositories import NotFoundError
from rutasegura.domain import (
    Door,
    Exit,
    FloorPlan,
    Observation,
    ObservationType,
    Obstacle,
    Occupancy,
    PersonProfile,
    Point,
    Polygon,
    Project,
    RealDrill,
    Room,
    SafeZone,
    Scenario,
    Segment,
    SimulationResult,
    Stair,
    UseType,
    Wall,
)


def _rect(x: float, y: float, w: float, h: float) -> Polygon:
    return Polygon((Point(x, y), Point(x + w, y), Point(x + w, y + h), Point(x, y + h)))


def _plan(level: int = 0) -> FloorPlan:
    return FloorPlan(
        level=level,
        image_path="planos/colegio.png",
        scale_m_per_px=0.02,
        walls=(
            Wall(Segment(Point(0, 0), Point(500, 0))),
            Wall(Segment(Point(0, 0), Point(0, 300)), confidence=0.8),
        ),
        doors=(Door(Segment(Point(100, 0), Point(150, 0)), confidence=0.9),),
        exits=(Exit(Segment(Point(400, 300), Point(460, 300)), name="Salida principal"),),
        stairs=(Stair(_rect(450, 10, 40, 80), connects_to_level=1),),
        obstacles=(Obstacle(_rect(200, 100, 20, 20)),),
        safe_zones=(SafeZone(_rect(600, 0, 100, 100), name="Patio"),),
        rooms=(
            Room("Aula 1", UseType.EDUCATION, _rect(0, 0, 250, 300)),
            Room("Dirección", UseType.OFFICE, _rect(250, 0, 250, 300)),
        ),
    )


def _project(db: Database) -> int:
    with db.unit_of_work() as uow:
        return uow.projects.add(Project("I.E. San Martín", UseType.EDUCATION, "Av. Lima 123"))


class TestProjects:
    def test_crud(self, db: Database) -> None:
        pid = _project(db)
        with db.unit_of_work() as uow:
            project = uow.projects.get(pid)
            assert project.name == "I.E. San Martín"
            assert project.use is UseType.EDUCATION
            assert isinstance(project.created_at, datetime)
            uow.projects.update(pid, dataclasses.replace(project, name="Colegio San Martín"))
        with db.unit_of_work() as uow:
            assert [p.name for _, p in uow.projects.list_all()] == ["Colegio San Martín"]
            uow.projects.delete(pid)
        with db.unit_of_work() as uow, pytest.raises(NotFoundError):
            uow.projects.get(pid)

    def test_transaction_rolls_back_on_error(self, db: Database) -> None:
        def add_then_fail() -> None:
            with db.unit_of_work() as uow:
                uow.projects.add(Project("Temporal", UseType.COMMERCE))
                raise RuntimeError("falla a mitad")

        with pytest.raises(RuntimeError, match="falla a mitad"):
            add_then_fail()
        with db.unit_of_work() as uow:
            assert uow.projects.list_all() == []


class TestFloors:
    def test_round_trip_preserves_plan(self, db: Database) -> None:
        pid = _project(db)
        plan = _plan()
        with db.unit_of_work() as uow:
            uow.floors.save(pid, plan)
        with db.unit_of_work() as uow:
            assert uow.floors.get(pid, 0) == plan
            assert uow.floors.levels(pid) == [0]

    def test_widths_and_areas_in_meters(self, db: Database) -> None:
        pid = _project(db)
        with db.unit_of_work() as uow:
            uow.floors.save(pid, _plan())
        with db.unit_of_work() as uow:
            rooms = uow.session.scalars(select(RoomRecord).order_by(RoomRecord.id)).all()
            assert rooms[0].area_m2 == pytest.approx(250 * 300 * 0.02**2)  # 30 m²
            rows = uow.session.execute(
                select(ElementRecord.kind, ElementRecord.width_m).where(
                    ElementRecord.kind.in_(["puerta", "salida"])
                )
            )
            widths = {kind: width for kind, width in rows}
            assert widths["puerta"] == pytest.approx(1.0)  # 50 px x 0.02 m/px
            assert widths["salida"] == pytest.approx(1.2)

    def test_unscaled_plan_has_no_widths(self, db: Database) -> None:
        pid = _project(db)
        with db.unit_of_work() as uow:
            uow.floors.save(pid, dataclasses.replace(_plan(), scale_m_per_px=None))
            rooms = uow.session.scalars(select(RoomRecord)).all()
            assert all(r.area_m2 is None for r in rooms)

    def test_resave_keeps_occupancies_of_unchanged_rooms(self, db: Database) -> None:
        pid = _project(db)
        with db.unit_of_work() as uow:
            uow.floors.save(pid, _plan())
            uow.scenarios.save(
                pid,
                Scenario(
                    "Base",
                    seed=7,
                    occupancies=(
                        Occupancy("Aula 1", "niño", 30),
                        Occupancy("Dirección", "adulto", 2),
                    ),
                ),
            )
        edited = dataclasses.replace(
            _plan(), rooms=(Room("Aula 1", UseType.EDUCATION, _rect(0, 0, 260, 300)),)
        )
        with db.unit_of_work() as uow:
            uow.floors.save(pid, edited)
        with db.unit_of_work() as uow:
            scenario = uow.scenarios.get(uow.scenarios.find_id(pid, "Base"))
            assert scenario.occupancies == (Occupancy("Aula 1", "niño", 30),)
            assert uow.floors.get(pid, 0).rooms == edited.rooms

    def test_duplicate_room_names_rejected(self, db: Database) -> None:
        pid = _project(db)
        room = Room("Aula 1", UseType.EDUCATION, _rect(0, 0, 10, 10))
        with db.unit_of_work() as uow, pytest.raises(ValueError, match="mismo nombre"):
            uow.floors.save(pid, FloorPlan(rooms=(room, room)))

    def test_missing_floor(self, db: Database) -> None:
        pid = _project(db)
        with db.unit_of_work() as uow, pytest.raises(NotFoundError):
            uow.floors.get(pid, 3)

    def test_delete_project_cascades(self, db: Database) -> None:
        pid = _project(db)
        with db.unit_of_work() as uow:
            uow.floors.save(pid, _plan())
            uow.scenarios.save(pid, Scenario("Base", 1, (Occupancy("Aula 1", "niño", 5),)))
        with db.unit_of_work() as uow:
            uow.projects.delete(pid)
        with db.unit_of_work() as uow:
            assert uow.session.scalar(select(func.count()).select_from(RoomRecord)) == 0
            assert uow.session.scalar(select(func.count()).select_from(OccupancyRecord)) == 0


class TestProfiles:
    def test_defaults_are_seeded(self, db: Database) -> None:
        with db.unit_of_work() as uow:
            assert uow.profiles.get("adulto").max_speed_mps > 0
            assert len(uow.profiles.list_all()) == 3

    def test_user_edits_survive_reseeding(self, tmp_path: Path) -> None:
        path = tmp_path / "db.sqlite"
        db = Database.open(path)
        with db.unit_of_work() as uow:
            adult = uow.profiles.get("adulto")
            uow.profiles.save(dataclasses.replace(adult, max_speed_mps=1.1))
        db.close()
        db = Database.open(path)
        with db.unit_of_work() as uow:
            assert uow.profiles.get("adulto").max_speed_mps == pytest.approx(1.1)
        db.close()

    def test_custom_profile_and_missing(self, db: Database) -> None:
        with db.unit_of_work() as uow:
            uow.profiles.save(PersonProfile("docente", 1.3, 15, 5, 0.25))
            assert uow.profiles.get("docente").reaction_mean_s == 15
            with pytest.raises(NotFoundError):
                uow.profiles.get("astronauta")

    def test_profile_in_use_cannot_be_deleted(self, db: Database) -> None:
        pid = _project(db)
        with db.unit_of_work() as uow:
            uow.floors.save(pid, _plan())
            uow.scenarios.save(pid, Scenario("Base", 1, (Occupancy("Aula 1", "adulto", 5),)))
        with pytest.raises(IntegrityError), db.session() as session:
            session.execute(delete(PersonProfileRecord).where(PersonProfileRecord.name == "adulto"))


class TestScenarios:
    def test_round_trip_and_replace(self, db: Database) -> None:
        pid = _project(db)
        scenario = Scenario(
            "Salida bloqueada",
            seed=123,
            occupancies=(Occupancy("Aula 1", "niño", 28), Occupancy("Aula 1", "adulto", 1)),
            blocked_exits=frozenset({"Salida principal"}),
        )
        with db.unit_of_work() as uow:
            uow.floors.save(pid, _plan())
            sid = uow.scenarios.save(pid, scenario)
        with db.unit_of_work() as uow:
            assert uow.scenarios.get(sid) == scenario
            changed = dataclasses.replace(scenario, seed=5, occupancies=scenario.occupancies[:1])
            assert uow.scenarios.save(pid, changed) == sid
        with db.unit_of_work() as uow:
            assert uow.scenarios.get(sid) == changed
            assert [s.name for _, s in uow.scenarios.list_all(pid)] == ["Salida bloqueada"]
            uow.scenarios.delete(sid)
            assert uow.scenarios.list_all(pid) == []

    def test_multi_floor_rooms_with_same_name(self, db: Database) -> None:
        pid = _project(db)
        scenario = Scenario(
            "Dos pisos",
            seed=1,
            occupancies=(Occupancy("Aula 1", "niño", 10), Occupancy("Aula 1", "niño", 20, level=1)),
        )
        with db.unit_of_work() as uow:
            uow.floors.save(pid, _plan(0))
            uow.floors.save(pid, _plan(1))
            sid = uow.scenarios.save(pid, scenario)
        with db.unit_of_work() as uow:
            assert uow.scenarios.get(sid) == scenario
            assert uow.floors.levels(pid) == [0, 1]

    @pytest.mark.parametrize(
        ("occupancy", "message"),
        [
            (Occupancy("Aula 9", "niño", 1), "ambiente"),
            (Occupancy("Aula 1", "astronauta", 1), "perfil"),
        ],
    )
    def test_unknown_references(self, db: Database, occupancy: Occupancy, message: str) -> None:
        pid = _project(db)
        with db.unit_of_work() as uow:
            uow.floors.save(pid, _plan())
            with pytest.raises(ValueError, match=message):
                uow.scenarios.save(pid, Scenario("X", 1, (occupancy,)))


class TestSimulationsAndDrills:
    def test_simulation_summary_and_observations(self, db: Database) -> None:
        pid = _project(db)
        result = SimulationResult(
            seed=42,
            total_time_s=183.5,
            time_per_exit_s=(("Salida principal", 183.5), ("Salida 2", 120.0)),
            curve_times_s=np.array([0.0, 1.0]),
            curve_evacuated=np.array([0, 3], dtype=np.int32),
            density_map=np.zeros((2, 2)),
            trajectories_path="trayectorias/sim_1.npz",
        )
        observations = [
            Observation(
                ObservationType.NORM,
                "La puerta del Aula 1 mide menos que el mínimo.",
                "Ensanchar la puerta.",
                location=Point(3.0, 0.5),
                norm="RNE A.130",
                article="Art. (por verificar)",
                verified=False,
            ),
            Observation(ObservationType.CONGESTION, "Congestión en pasillo", "Señalizar"),
        ]
        with db.unit_of_work() as uow:
            uow.floors.save(pid, _plan())
            sid = uow.scenarios.save(pid, Scenario("Base", 42))
            sim_id = uow.simulations.add(sid, result, observations)
        with db.unit_of_work() as uow:
            summary = uow.simulations.get(sim_id)
            assert summary.total_time_s == pytest.approx(183.5)
            assert summary.time_per_exit_s == result.time_per_exit_s
            assert summary.seed == 42
            assert uow.simulations.observations(sim_id) == observations
            assert [i for i, _ in uow.simulations.list_all(sid)] == [sim_id]

    def test_real_drills(self, db: Database) -> None:
        pid = _project(db)
        later = RealDrill(date(2026, 10, 8), 310, 240.0, (("Salida principal", 240.0),))
        earlier = RealDrill(date(2026, 5, 31), 300, 260.0)
        with db.unit_of_work() as uow:
            uow.drills.add(pid, later)
            first = uow.drills.add(pid, earlier)
        with db.unit_of_work() as uow:
            assert [d for _, d in uow.drills.list_all(pid)] == [earlier, later]
            uow.drills.delete(first)
            assert [d for _, d in uow.drills.list_all(pid)] == [later]


def test_custom_engine_factory_is_used(tmp_path: Path) -> None:
    """La fábrica de motores es intercambiable (preparado para SQLCipher, RNF04)."""
    calls: list[Path] = []

    def factory(path: Path) -> Engine:
        calls.append(path)
        return plain_sqlite_engine(path)

    db = Database.open(tmp_path / "x.db", engine_factory=factory)
    db.close()
    assert calls == [tmp_path / "x.db"]
