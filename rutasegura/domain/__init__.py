"""Estructuras de dominio compartidas por todas las capas (dataclasses, enums, arrays)."""

from rutasegura.domain.agents import AgentArrays
from rutasegura.domain.enums import AgentStatus, CellType, ElementType, ObservationType, UseType
from rutasegura.domain.geometry import Point, Polygon, Segment
from rutasegura.domain.norms import NormEvaluation, NormRule, RoomCapacity
from rutasegura.domain.people import Occupancy, PersonProfile
from rutasegura.domain.plan import Door, Exit, FloorPlan, Obstacle, Room, SafeZone, Stair, Wall
from rutasegura.domain.project import Project
from rutasegura.domain.results import (
    Bottleneck,
    Observation,
    SimulationResult,
    SimulationSummary,
    Trajectories,
)
from rutasegura.domain.scenario import RealDrill, Scenario

__all__ = [
    "AgentArrays",
    "AgentStatus",
    "Bottleneck",
    "CellType",
    "Door",
    "ElementType",
    "Exit",
    "FloorPlan",
    "NormEvaluation",
    "NormRule",
    "Observation",
    "ObservationType",
    "Obstacle",
    "Occupancy",
    "PersonProfile",
    "Point",
    "Polygon",
    "Project",
    "RealDrill",
    "Room",
    "RoomCapacity",
    "SafeZone",
    "Scenario",
    "Segment",
    "SimulationResult",
    "SimulationSummary",
    "Stair",
    "Trajectories",
    "UseType",
    "Wall",
]
