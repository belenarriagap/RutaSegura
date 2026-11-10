"""Estado de los agentes como estructura de arrays NumPy (no lista de objetos)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from rutasegura.domain.enums import AgentStatus

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int32]
StatusArray = npt.NDArray[np.int8]


@dataclass(eq=False, slots=True)
class AgentArrays:
    """Estado mutable de *n* agentes. Cada array tiene longitud *n* en su primer eje."""

    position: FloatArray  # (n, 2) metros
    velocity: FloatArray  # (n, 2) m/s
    max_speed: FloatArray  # (n,) m/s
    radius: FloatArray  # (n,) m
    reaction_time: FloatArray  # (n,) s antes de empezar a moverse
    profile_index: IntArray  # (n,) índice en la lista de perfiles del escenario
    status: StatusArray  # (n,) valores de AgentStatus

    def __post_init__(self) -> None:
        n = len(self)
        if self.position.shape != (n, 2) or self.velocity.shape != (n, 2):
            raise ValueError("position y velocity deben tener forma (n, 2).")
        for name in ("max_speed", "radius", "reaction_time", "profile_index", "status"):
            if getattr(self, name).shape != (n,):
                raise ValueError(f"{name} debe tener forma ({n},).")

    def __len__(self) -> int:
        return int(self.position.shape[0])

    @classmethod
    def empty(cls, n: int) -> AgentArrays:
        """Crea *n* agentes en el origen, en espera."""
        return cls(
            position=np.zeros((n, 2), dtype=np.float64),
            velocity=np.zeros((n, 2), dtype=np.float64),
            max_speed=np.zeros(n, dtype=np.float64),
            radius=np.zeros(n, dtype=np.float64),
            reaction_time=np.zeros(n, dtype=np.float64),
            profile_index=np.zeros(n, dtype=np.int32),
            status=np.full(n, AgentStatus.WAITING, dtype=np.int8),
        )

    @property
    def evacuated_count(self) -> int:
        """Cantidad de agentes ya evacuados."""
        return int(np.count_nonzero(self.status == AgentStatus.EVACUATED))
