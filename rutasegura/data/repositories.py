"""Repositorios: traducen entre el dominio y las tablas, para que ``application`` no escriba SQL.

Cada repositorio trabaja sobre una ``Session`` abierta; la transacción la controla quien la
crea (``Database.unit_of_work``).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from rutasegura.data.geojson import (
    feature_dumps,
    feature_loads,
    geometry_dumps,
    geometry_loads,
    point_from_geojson,
    point_to_geojson,
    polygon_from_geojson,
    polygon_to_geojson,
    segment_from_geojson,
    segment_to_geojson,
)
from rutasegura.data.models import (
    ElementRecord,
    FloorRecord,
    ObservationRecord,
    OccupancyRecord,
    PersonProfileRecord,
    ProjectRecord,
    RealDrillRecord,
    RoomRecord,
    ScenarioRecord,
    SimulationRecord,
)
from rutasegura.domain.enums import ElementType, ObservationType, UseType
from rutasegura.domain.people import Occupancy, PersonProfile
from rutasegura.domain.plan import (
    Door,
    Exit,
    FloorPlan,
    Obstacle,
    Room,
    SafeZone,
    Stair,
    Wall,
)
from rutasegura.domain.project import Project
from rutasegura.domain.results import Observation, SimulationResult, SimulationSummary
from rutasegura.domain.scenario import RealDrill, Scenario


class NotFoundError(LookupError):
    """El registro pedido no existe."""


def _get[T](session: Session, model: type[T], record_id: int, label: str) -> T:
    record = session.get(model, record_id)
    if record is None:
        raise NotFoundError(f"No existe {label} con id {record_id}.")
    return record


# --------------------------------------------------------------------------- proyectos


class ProjectRepository:
    """Proyectos (locales evaluados)."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def add(self, project: Project) -> int:
        """Guarda un proyecto nuevo y devuelve su id."""
        record = ProjectRecord(name=project.name, use_type=project.use, address=project.address)
        if project.created_at is not None:
            record.created_at = project.created_at
        self._s.add(record)
        self._s.flush()
        return record.id

    def get(self, project_id: int) -> Project:
        """Proyecto por id."""
        return self._to_domain(_get(self._s, ProjectRecord, project_id, "el proyecto"))

    def list_all(self) -> list[tuple[int, Project]]:
        """Todos los proyectos, del más reciente al más antiguo."""
        records = self._s.scalars(
            select(ProjectRecord).order_by(ProjectRecord.created_at.desc(), ProjectRecord.id.desc())
        )
        return [(r.id, self._to_domain(r)) for r in records]

    def update(self, project_id: int, project: Project) -> None:
        """Actualiza nombre, uso y dirección."""
        record = _get(self._s, ProjectRecord, project_id, "el proyecto")
        record.name = project.name
        record.use_type = project.use
        record.address = project.address

    def delete(self, project_id: int) -> None:
        """Elimina el proyecto con sus pisos, escenarios, simulaciones y simulacros."""
        self._s.delete(_get(self._s, ProjectRecord, project_id, "el proyecto"))
        self._s.flush()

    @staticmethod
    def _to_domain(record: ProjectRecord) -> Project:
        return Project(
            name=record.name,
            use=UseType(record.use_type),
            address=record.address,
            created_at=record.created_at,
        )


# --------------------------------------------------------------------------- pisos


class FloorRepository:
    """Planos de cada piso: elementos y ambientes."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def _find(self, project_id: int, level: int) -> FloorRecord | None:
        return self._s.scalars(
            select(FloorRecord).where(
                FloorRecord.project_id == project_id, FloorRecord.level == level
            )
        ).one_or_none()

    def save(self, project_id: int, plan: FloorPlan) -> int:
        """Crea o reemplaza el plano del piso ``plan.level``.

        Los elementos se reemplazan completos. Los ambientes se sincronizan por nombre, para no
        perder las ocupaciones de los escenarios: un ambiente eliminado (o renombrado) pierde
        sus ocupaciones.
        """
        names = [room.name for room in plan.rooms]
        if len(names) != len(set(names)):
            raise ValueError("Hay ambientes con el mismo nombre en este piso.")
        _get(self._s, ProjectRecord, project_id, "el proyecto")

        floor = self._find(project_id, plan.level)
        if floor is None:
            floor = FloorRecord(project_id=project_id, level=plan.level)
            self._s.add(floor)
        floor.original_image = plan.image_path
        floor.scale_m_per_px = plan.scale_m_per_px

        floor.elements.clear()
        floor.elements.extend(self._elements_to_records(plan))

        existing = {room.name: room for room in floor.rooms}
        for room in plan.rooms:
            record = existing.pop(room.name, None)
            if record is None:
                record = RoomRecord(name=room.name)
                floor.rooms.append(record)
            record.use = room.use
            record.category = room.category
            record.polygon = geometry_dumps(polygon_to_geojson(room.area))
            record.area_m2 = plan.area_m2(room.area) if plan.is_scaled else None
        for removed in existing.values():
            floor.rooms.remove(removed)

        self._s.flush()
        return floor.id

    def get(self, project_id: int, level: int) -> FloorPlan:
        """Plano de un piso."""
        floor = self._find(project_id, level)
        if floor is None:
            raise NotFoundError(f"El proyecto {project_id} no tiene el piso {level}.")
        return self._to_domain(floor)

    def levels(self, project_id: int) -> list[int]:
        """Niveles con plano guardado, en orden."""
        return list(
            self._s.scalars(
                select(FloorRecord.level)
                .where(FloorRecord.project_id == project_id)
                .order_by(FloorRecord.level)
            )
        )

    def delete(self, project_id: int, level: int) -> None:
        """Elimina un piso con sus elementos y ambientes."""
        floor = self._find(project_id, level)
        if floor is None:
            raise NotFoundError(f"El proyecto {project_id} no tiene el piso {level}.")
        self._s.delete(floor)
        self._s.flush()

    @staticmethod
    def _elements_to_records(plan: FloorPlan) -> list[ElementRecord]:
        def width(length_px: float) -> float | None:
            return plan.to_meters(length_px) if plan.is_scaled else None

        records: list[ElementRecord] = []

        def add(
            kind: ElementType,
            geometry: dict[str, object],
            props: dict[str, object],
            width_m: float | None = None,
        ) -> None:
            records.append(
                ElementRecord(kind=kind, geometry=feature_dumps(geometry, props), width_m=width_m)
            )

        for wall in plan.walls:
            add(ElementType.WALL, segment_to_geojson(wall.segment), {"confianza": wall.confidence})
        for door in plan.doors:
            add(
                ElementType.DOOR,
                segment_to_geojson(door.segment),
                {"confianza": door.confidence},
                width(door.segment.length),
            )
        for exit_ in plan.exits:
            add(
                ElementType.EXIT,
                segment_to_geojson(exit_.segment),
                {"nombre": exit_.name, "confirmada": exit_.confirmed},
                width(exit_.segment.length),
            )
        for stair in plan.stairs:
            add(
                ElementType.STAIR,
                polygon_to_geojson(stair.area),
                {"conecta_con_nivel": stair.connects_to_level, "confirmada": stair.confirmed},
            )
        for obstacle in plan.obstacles:
            add(ElementType.OBSTACLE, polygon_to_geojson(obstacle.area), {})
        for zone in plan.safe_zones:
            add(ElementType.SAFE_ZONE, polygon_to_geojson(zone.area), {"nombre": zone.name})
        return records

    @staticmethod
    def _to_domain(floor: FloorRecord) -> FloorPlan:
        walls: list[Wall] = []
        doors: list[Door] = []
        exits: list[Exit] = []
        stairs: list[Stair] = []
        obstacles: list[Obstacle] = []
        safe_zones: list[SafeZone] = []
        for element in floor.elements:
            geometry, props = feature_loads(element.geometry)
            match ElementType(element.kind):
                case ElementType.WALL:
                    walls.append(
                        Wall(segment_from_geojson(geometry), float(props.get("confianza", 1.0)))
                    )
                case ElementType.DOOR:
                    doors.append(
                        Door(segment_from_geojson(geometry), float(props.get("confianza", 1.0)))
                    )
                case ElementType.EXIT:
                    exits.append(
                        Exit(
                            segment_from_geojson(geometry),
                            str(props.get("nombre", "")),
                            bool(props.get("confirmada", True)),
                        )
                    )
                case ElementType.STAIR:
                    level = props.get("conecta_con_nivel")
                    stairs.append(
                        Stair(
                            polygon_from_geojson(geometry),
                            None if level is None else int(level),
                            bool(props.get("confirmada", True)),
                        )
                    )
                case ElementType.OBSTACLE:
                    obstacles.append(Obstacle(polygon_from_geojson(geometry)))
                case ElementType.SAFE_ZONE:
                    safe_zones.append(
                        SafeZone(polygon_from_geojson(geometry), str(props.get("nombre", "")))
                    )
        rooms = tuple(
            Room(
                r.name,
                UseType(r.use),
                polygon_from_geojson(geometry_loads(r.polygon)),
                r.category,
            )
            for r in floor.rooms
        )
        return FloorPlan(
            level=floor.level,
            image_path=floor.original_image,
            scale_m_per_px=floor.scale_m_per_px,
            walls=tuple(walls),
            doors=tuple(doors),
            exits=tuple(exits),
            stairs=tuple(stairs),
            obstacles=tuple(obstacles),
            safe_zones=tuple(safe_zones),
            rooms=rooms,
        )


# --------------------------------------------------------------------------- perfiles


class ProfileRepository:
    """Catálogo de perfiles de personas."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def _find(self, name: str) -> PersonProfileRecord | None:
        return self._s.scalars(
            select(PersonProfileRecord).where(PersonProfileRecord.name == name)
        ).one_or_none()

    def list_all(self) -> list[PersonProfile]:
        """Todos los perfiles, en orden de creación."""
        records = self._s.scalars(select(PersonProfileRecord).order_by(PersonProfileRecord.id))
        return [self._to_domain(r) for r in records]

    def get(self, name: str) -> PersonProfile:
        """Perfil por nombre."""
        record = self._find(name)
        if record is None:
            raise NotFoundError(f"No existe el perfil «{name}».")
        return self._to_domain(record)

    def save(self, profile: PersonProfile) -> int:
        """Crea o actualiza (por nombre) un perfil."""
        record = self._find(profile.name)
        if record is None:
            record = PersonProfileRecord(name=profile.name)
            self._s.add(record)
        record.max_speed_mps = profile.max_speed_mps
        record.reaction_mean_s = profile.reaction_mean_s
        record.reaction_std_s = profile.reaction_std_s
        record.radius_m = profile.radius_m
        self._s.flush()
        return record.id

    def ensure(self, profiles: Iterable[PersonProfile]) -> int:
        """Agrega los perfiles que falten, sin tocar los existentes. Devuelve cuántos agregó."""
        added = 0
        for profile in profiles:
            if self._find(profile.name) is None:
                self.save(profile)
                added += 1
        return added

    @staticmethod
    def _to_domain(record: PersonProfileRecord) -> PersonProfile:
        return PersonProfile(
            name=record.name,
            max_speed_mps=record.max_speed_mps,
            reaction_mean_s=record.reaction_mean_s,
            reaction_std_s=record.reaction_std_s,
            radius_m=record.radius_m,
        )


# --------------------------------------------------------------------------- escenarios


class ScenarioRepository:
    """Escenarios con su ocupación."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def save(self, project_id: int, scenario: Scenario) -> int:
        """Crea o reemplaza (por nombre) un escenario del proyecto."""
        _get(self._s, ProjectRecord, project_id, "el proyecto")
        record = self._s.scalars(
            select(ScenarioRecord).where(
                ScenarioRecord.project_id == project_id, ScenarioRecord.name == scenario.name
            )
        ).one_or_none()
        if record is None:
            record = ScenarioRecord(project_id=project_id, name=scenario.name)
            self._s.add(record)
        record.seed = scenario.seed
        record.blocked_exits = sorted(scenario.blocked_exits)
        record.occupancies.clear()
        self._s.flush()  # elimina las ocupaciones anteriores antes de insertar (restricción única)
        record.occupancies.extend(self._occupancy_records(project_id, scenario.occupancies))
        self._s.flush()
        return record.id

    def get(self, scenario_id: int) -> Scenario:
        """Escenario por id."""
        return self._to_domain(_get(self._s, ScenarioRecord, scenario_id, "el escenario"))

    def find_id(self, project_id: int, name: str) -> int:
        """Id de un escenario por nombre."""
        scenario_id = self._s.scalars(
            select(ScenarioRecord.id).where(
                ScenarioRecord.project_id == project_id, ScenarioRecord.name == name
            )
        ).one_or_none()
        if scenario_id is None:
            raise NotFoundError(f"No existe el escenario «{name}».")
        return scenario_id

    def list_all(self, project_id: int) -> list[tuple[int, Scenario]]:
        """Escenarios del proyecto, en orden de creación."""
        records = self._s.scalars(
            select(ScenarioRecord)
            .where(ScenarioRecord.project_id == project_id)
            .order_by(ScenarioRecord.id)
        )
        return [(r.id, self._to_domain(r)) for r in records]

    def rename(self, scenario_id: int, name: str) -> None:
        """Cambia el nombre de un escenario."""
        _get(self._s, ScenarioRecord, scenario_id, "el escenario").name = name
        self._s.flush()

    def delete(self, scenario_id: int) -> None:
        """Elimina el escenario con sus simulaciones."""
        self._s.delete(_get(self._s, ScenarioRecord, scenario_id, "el escenario"))
        self._s.flush()

    def _occupancy_records(
        self, project_id: int, occupancies: Sequence[Occupancy]
    ) -> list[OccupancyRecord]:
        rooms = {
            (level, name): room_id
            for room_id, name, level in self._s.execute(
                select(RoomRecord.id, RoomRecord.name, FloorRecord.level)
                .join(FloorRecord)
                .where(FloorRecord.project_id == project_id)
            )
        }
        profiles = {
            name: profile_id
            for name, profile_id in self._s.execute(
                select(PersonProfileRecord.name, PersonProfileRecord.id)
            )
        }
        records: list[OccupancyRecord] = []
        for occ in occupancies:
            room_id = rooms.get((occ.level, occ.room_name))
            if room_id is None:
                raise ValueError(f"No existe el ambiente «{occ.room_name}» en el piso {occ.level}.")
            profile_id = profiles.get(occ.profile_name)
            if profile_id is None:
                raise ValueError(f"No existe el perfil «{occ.profile_name}».")
            records.append(OccupancyRecord(room_id=room_id, profile_id=profile_id, count=occ.count))
        return records

    @staticmethod
    def _to_domain(record: ScenarioRecord) -> Scenario:
        occupancies = tuple(
            Occupancy(
                room_name=o.room.name,
                profile_name=o.profile.name,
                count=o.count,
                level=o.room.floor.level,
            )
            for o in record.occupancies
        )
        return Scenario(
            name=record.name,
            seed=record.seed,
            occupancies=occupancies,
            blocked_exits=frozenset(record.blocked_exits),
        )


# --------------------------------------------------------------------------- simulaciones


class SimulationRepository:
    """Resultados de simulación (resumen) y sus observaciones."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def add(
        self,
        scenario_id: int,
        result: SimulationResult,
        observations: Sequence[Observation] = (),
    ) -> int:
        """Guarda el resumen de una corrida. Los arrays van en el archivo de trayectorias."""
        _get(self._s, ScenarioRecord, scenario_id, "el escenario")
        record = SimulationRecord(
            scenario_id=scenario_id,
            seed=result.seed,
            total_time_s=result.total_time_s,
            time_per_exit_s=dict(result.time_per_exit_s),
            trajectories_path=result.trajectories_path,
        )
        record.observations.extend(self._observation_record(o) for o in observations)
        self._s.add(record)
        self._s.flush()
        return record.id

    def get(self, simulation_id: int) -> SimulationSummary:
        """Resumen de una corrida."""
        return self._summary(_get(self._s, SimulationRecord, simulation_id, "la simulación"))

    def list_all(self, scenario_id: int) -> list[tuple[int, SimulationSummary]]:
        """Corridas de un escenario, en orden."""
        records = self._s.scalars(
            select(SimulationRecord)
            .where(SimulationRecord.scenario_id == scenario_id)
            .order_by(SimulationRecord.id)
        )
        return [(r.id, self._summary(r)) for r in records]

    def observations(self, simulation_id: int) -> list[Observation]:
        """Observaciones de una corrida."""
        record = _get(self._s, SimulationRecord, simulation_id, "la simulación")
        return [self._observation_domain(o) for o in record.observations]

    @staticmethod
    def _summary(record: SimulationRecord) -> SimulationSummary:
        return SimulationSummary(
            seed=record.seed,
            total_time_s=record.total_time_s,
            time_per_exit_s=tuple(record.time_per_exit_s.items()),
            trajectories_path=record.trajectories_path,
            created_at=record.created_at,
        )

    @staticmethod
    def _observation_record(obs: Observation) -> ObservationRecord:
        location = None if obs.location is None else geometry_dumps(point_to_geojson(obs.location))
        return ObservationRecord(
            kind=obs.kind,
            description=obs.description,
            norm=obs.norm,
            article=obs.article,
            verified=obs.verified,
            location=location,
            recommendation=obs.recommendation,
        )

    @staticmethod
    def _observation_domain(record: ObservationRecord) -> Observation:
        location = (
            None if record.location is None else point_from_geojson(geometry_loads(record.location))
        )
        return Observation(
            kind=ObservationType(record.kind),
            description=record.description,
            recommendation=record.recommendation,
            location=location,
            norm=record.norm,
            article=record.article,
            verified=record.verified,
        )


# --------------------------------------------------------------------------- simulacros reales


class RealDrillRepository:
    """Simulacros reales registrados para calibrar (RF11)."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def add(self, project_id: int, drill: RealDrill) -> int:
        """Registra un simulacro."""
        _get(self._s, ProjectRecord, project_id, "el proyecto")
        record = RealDrillRecord(
            project_id=project_id,
            drill_date=drill.drill_date,
            participants=drill.participants,
            total_time_s=drill.total_time_s,
            time_per_exit_s=dict(drill.time_per_exit_s),
        )
        self._s.add(record)
        self._s.flush()
        return record.id

    def list_all(self, project_id: int) -> list[tuple[int, RealDrill]]:
        """Simulacros del proyecto, por fecha."""
        records = self._s.scalars(
            select(RealDrillRecord)
            .where(RealDrillRecord.project_id == project_id)
            .order_by(RealDrillRecord.drill_date, RealDrillRecord.id)
        )
        return [
            (
                r.id,
                RealDrill(
                    drill_date=r.drill_date,
                    participants=r.participants,
                    total_time_s=r.total_time_s,
                    time_per_exit_s=tuple(r.time_per_exit_s.items()),
                ),
            )
            for r in records
        ]

    def delete(self, drill_id: int) -> None:
        """Elimina un simulacro."""
        self._s.delete(_get(self._s, RealDrillRecord, drill_id, "el simulacro"))
        self._s.flush()
