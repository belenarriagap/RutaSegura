"""Parámetros del modelo de movimiento.

VALORES PROVISIONALES (ver docs/parametros_simulacion.md): hay que contrastarlos con la fuente y
calibrarlos con un simulacro real (RF11). Las fuerzas están expresadas por unidad de masa (m/s²)
y se eligieron más suaves que en Helbing et al. (2000) para que la integración explícita con
paso de 0.1 s sea estable.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SimulationParams:
    """Parámetros numéricos y de comportamiento."""

    dt_s: float = 0.1
    max_time_s: float = 1800.0
    record_every_s: float = 0.5  # cada cuánto se guarda un cuadro de trayectorias
    relaxation_s: float = 0.5  # tiempo para alcanzar la velocidad deseada
    # Velocidad según densidad: v = v_max · max(min_speed_factor, 1 − ρ/ρ_max)
    jam_density: float = 5.4  # p/m², PROVISIONAL (orden de magnitud de Weidmann, 1993)
    min_speed_factor: float = 0.1
    speed_variation: float = 0.1  # desviación relativa de la velocidad máxima individual
    # Repulsión entre personas: A·exp((r_ij − d)/B)
    agent_strength: float = 2.0  # m/s², PROVISIONAL
    agent_range_m: float = 0.3  # PROVISIONAL
    interaction_cutoff_m: float = 1.2
    # Repulsión de muros: A_w·exp((r − d_w)/B_w)
    wall_strength: float = 5.0  # m/s², PROVISIONAL
    wall_range_m: float = 0.2  # PROVISIONAL
    # Escaleras (varios pisos): tiempo de bajada = recorrido / (velocidad · factor) y capacidad
    # de entrada = flujo específico · ancho de la escalera.
    stair_travel_m: float = 8.0  # recorrido por piso (dos tramos y descanso), PROVISIONAL
    stair_speed_factor: float = 0.5  # velocidad al bajar respecto de la horizontal, PROVISIONAL
    stair_specific_flow: float = 1.1  # personas/(s·m), PROVISIONAL (orden de magnitud SFPE)
    # Cuellos de botella
    congestion_density: float = 2.0  # p/m², PROVISIONAL (verificar con niveles de servicio)
    congestion_min_duration_s: float = 5.0  # PROVISIONAL

    def __post_init__(self) -> None:
        if self.dt_s <= 0 or self.max_time_s <= 0:
            raise ValueError("El paso de tiempo y el tiempo máximo deben ser positivos.")
        if self.record_every_s < self.dt_s:
            raise ValueError("Los cuadros no pueden registrarse más seguido que el paso de tiempo.")
        if not 0 < self.min_speed_factor <= 1:
            raise ValueError("El factor mínimo de velocidad debe estar entre 0 y 1.")
