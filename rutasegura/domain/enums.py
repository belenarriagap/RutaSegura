"""Enumeraciones del dominio.

Los valores de texto coinciden con los que se guardan en la base de datos (especificación §6).
"""

from __future__ import annotations

from enum import IntEnum, StrEnum


class ElementType(StrEnum):
    """Tipo de elemento de un plano."""

    WALL = "muro"
    DOOR = "puerta"
    EXIT = "salida"
    STAIR = "escalera"
    OBSTACLE = "obstaculo"


class UseType(StrEnum):
    """Uso del local o ambiente (determina el índice de ocupación normativo)."""

    EDUCATION = "educacion"
    OFFICE = "oficinas"
    COMMERCE = "comercio"


class ObservationType(StrEnum):
    """Origen de una observación del informe."""

    NORM = "norma"
    CONGESTION = "congestion"


class AgentStatus(IntEnum):
    """Estado de un agente; entero para guardarse en arrays NumPy."""

    WAITING = 0
    MOVING = 1
    EVACUATED = 2


class CellType(IntEnum):
    """Tipo de celda de la grilla de navegación (0.4 m)."""

    FREE = 0
    WALL = 1
    OBSTACLE = 2
    DOOR = 3
    EXIT = 4
    STAIR = 5
