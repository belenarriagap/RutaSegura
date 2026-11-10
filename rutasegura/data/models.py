"""Modelos ORM (SQLAlchemy 2.x tipado).

El esquema sigue la especificación §6: tablas y columnas en español (coinciden con el modelo de
datos de la tesis). Las clases y atributos de Python van en inglés. Las geometrías se guardan
como GeoJSON en texto y las listas o diccionarios como JSON.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Nombres de restricciones estables: Alembic los necesita para alterar tablas en SQLite.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    """Base declarativa con convención de nombres."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class ProjectRecord(Base):
    """Tabla ``proyecto``."""

    __tablename__ = "proyecto"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column("nombre", String(200))
    use_type: Mapped[str] = mapped_column("tipo_uso", String(30))
    address: Mapped[str] = mapped_column("direccion", String(300), default="")
    created_at: Mapped[datetime] = mapped_column("fecha_creacion", DateTime, default=_utcnow)

    floors: Mapped[list[FloorRecord]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="FloorRecord.level"
    )
    scenarios: Mapped[list[ScenarioRecord]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="ScenarioRecord.id"
    )
    drills: Mapped[list[RealDrillRecord]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="RealDrillRecord.id"
    )


class FloorRecord(Base):
    """Tabla ``piso``."""

    __tablename__ = "piso"
    __table_args__ = (UniqueConstraint("proyecto_id", "nivel"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        "proyecto_id", ForeignKey("proyecto.id", ondelete="CASCADE"), index=True
    )
    level: Mapped[int] = mapped_column("nivel", Integer)
    original_image: Mapped[str | None] = mapped_column("imagen_original", Text)
    scale_m_per_px: Mapped[float | None] = mapped_column("escala_m_por_px", Float)

    project: Mapped[ProjectRecord] = relationship(back_populates="floors")
    elements: Mapped[list[ElementRecord]] = relationship(
        back_populates="floor", cascade="all, delete-orphan", order_by="ElementRecord.id"
    )
    rooms: Mapped[list[RoomRecord]] = relationship(
        back_populates="floor", cascade="all, delete-orphan", order_by="RoomRecord.id"
    )


class ElementRecord(Base):
    """Tabla ``elemento``: muros, puertas, salidas, escaleras, obstáculos y zonas seguras."""

    __tablename__ = "elemento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    floor_id: Mapped[int] = mapped_column(
        "piso_id", ForeignKey("piso.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column("tipo", String(20))
    geometry: Mapped[str] = mapped_column("geometria", Text)  # GeoJSON Feature
    width_m: Mapped[float | None] = mapped_column("ancho_m", Float)

    floor: Mapped[FloorRecord] = relationship(back_populates="elements")


class RoomRecord(Base):
    """Tabla ``ambiente``."""

    __tablename__ = "ambiente"
    __table_args__ = (UniqueConstraint("piso_id", "nombre"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    floor_id: Mapped[int] = mapped_column(
        "piso_id", ForeignKey("piso.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column("nombre", String(200))
    use: Mapped[str] = mapped_column("uso", String(30))
    category: Mapped[str] = mapped_column("categoria", String(40), default="", server_default="")
    polygon: Mapped[str] = mapped_column("poligono", Text)  # GeoJSON Polygon
    area_m2: Mapped[float | None] = mapped_column(Float)

    floor: Mapped[FloorRecord] = relationship(back_populates="rooms")
    occupancies: Mapped[list[OccupancyRecord]] = relationship(
        back_populates="room", cascade="all, delete-orphan"
    )


class PersonProfileRecord(Base):
    """Tabla ``perfil_persona`` (catálogo)."""

    __tablename__ = "perfil_persona"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column("nombre", String(100), unique=True)
    max_speed_mps: Mapped[float] = mapped_column("vel_max_mps", Float)
    reaction_mean_s: Mapped[float] = mapped_column("reaccion_media_s", Float)
    reaction_std_s: Mapped[float] = mapped_column("reaccion_desv_s", Float)
    radius_m: Mapped[float] = mapped_column("radio_m", Float)


class ScenarioRecord(Base):
    """Tabla ``escenario``."""

    __tablename__ = "escenario"
    __table_args__ = (UniqueConstraint("proyecto_id", "nombre"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        "proyecto_id", ForeignKey("proyecto.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column("nombre", String(200))
    blocked_exits: Mapped[list[str]] = mapped_column("salidas_bloqueadas", JSON, default=list)
    seed: Mapped[int] = mapped_column("semilla", Integer)

    project: Mapped[ProjectRecord] = relationship(back_populates="scenarios")
    occupancies: Mapped[list[OccupancyRecord]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan", order_by="OccupancyRecord.id"
    )
    simulations: Mapped[list[SimulationRecord]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan", order_by="SimulationRecord.id"
    )


class OccupancyRecord(Base):
    """Tabla ``ocupacion``."""

    __tablename__ = "ocupacion"
    __table_args__ = (UniqueConstraint("escenario_id", "ambiente_id", "perfil_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario_id: Mapped[int] = mapped_column(
        "escenario_id", ForeignKey("escenario.id", ondelete="CASCADE"), index=True
    )
    room_id: Mapped[int] = mapped_column(
        "ambiente_id", ForeignKey("ambiente.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[int] = mapped_column(
        "perfil_id", ForeignKey("perfil_persona.id", ondelete="RESTRICT")
    )
    count: Mapped[int] = mapped_column("cantidad", Integer)

    scenario: Mapped[ScenarioRecord] = relationship(back_populates="occupancies")
    room: Mapped[RoomRecord] = relationship(back_populates="occupancies")
    profile: Mapped[PersonProfileRecord] = relationship()


class SimulationRecord(Base):
    """Tabla ``simulacion``. Las trayectorias van en un archivo binario aparte."""

    __tablename__ = "simulacion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario_id: Mapped[int] = mapped_column(
        "escenario_id", ForeignKey("escenario.id", ondelete="CASCADE"), index=True
    )
    seed: Mapped[int] = mapped_column("semilla", Integer)
    total_time_s: Mapped[float] = mapped_column("tiempo_total_s", Float)
    time_per_exit_s: Mapped[dict[str, float]] = mapped_column("tiempo_por_salida", JSON)
    trajectories_path: Mapped[str | None] = mapped_column("ruta_trayectorias", Text)
    created_at: Mapped[datetime] = mapped_column("fecha", DateTime, default=_utcnow)

    scenario: Mapped[ScenarioRecord] = relationship(back_populates="simulations")
    observations: Mapped[list[ObservationRecord]] = relationship(
        back_populates="simulation", cascade="all, delete-orphan", order_by="ObservationRecord.id"
    )


class ObservationRecord(Base):
    """Tabla ``observacion``."""

    __tablename__ = "observacion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    simulation_id: Mapped[int] = mapped_column(
        "simulacion_id", ForeignKey("simulacion.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column("tipo", String(20))
    description: Mapped[str] = mapped_column("descripcion", Text)
    norm: Mapped[str | None] = mapped_column("norma", String(100))
    article: Mapped[str | None] = mapped_column("articulo_rne", String(100))
    verified: Mapped[bool] = mapped_column("verificado", Boolean, default=True)
    location: Mapped[str | None] = mapped_column("ubicacion", Text)  # GeoJSON Point
    recommendation: Mapped[str] = mapped_column("recomendacion", Text)

    simulation: Mapped[SimulationRecord] = relationship(back_populates="observations")


class RealDrillRecord(Base):
    """Tabla ``simulacro_real``."""

    __tablename__ = "simulacro_real"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        "proyecto_id", ForeignKey("proyecto.id", ondelete="CASCADE"), index=True
    )
    drill_date: Mapped[date] = mapped_column("fecha", Date)
    participants: Mapped[int] = mapped_column("participantes", Integer)
    total_time_s: Mapped[float] = mapped_column("tiempo_total_s", Float)
    time_per_exit_s: Mapped[dict[str, float]] = mapped_column("tiempos_por_salida", JSON)

    project: Mapped[ProjectRecord] = relationship(back_populates="drills")
