"""Resultado de calibrar el modelo con un simulacro real (RF11)."""

from __future__ import annotations

from dataclasses import dataclass

TARGET_ERROR = 0.20  # meta de validación: error relativo < 20 % en el tiempo total


@dataclass(frozen=True, slots=True)
class CalibrationPoint:
    """Una combinación evaluada de factores."""

    reaction_factor: float  # multiplica el tiempo de reacción (media y desviación) de cada perfil
    speed_factor: float  # multiplica la velocidad máxima de cada perfil
    total_time_s: float
    error: float  # RMSE de los errores relativos (tiempo total y por salida)


@dataclass(frozen=True, slots=True)
class CalibrationResult:
    """Búsqueda en rejilla: punto inicial (factores 1 y 1), mejor punto y todos los evaluados."""

    observed_total_s: float
    baseline: CalibrationPoint
    best: CalibrationPoint
    points: tuple[CalibrationPoint, ...]

    @property
    def total_error_before(self) -> float:
        """Error relativo del tiempo total antes de calibrar."""
        return abs(self.baseline.total_time_s - self.observed_total_s) / self.observed_total_s

    @property
    def total_error_after(self) -> float:
        """Error relativo del tiempo total con los factores calibrados."""
        return abs(self.best.total_time_s - self.observed_total_s) / self.observed_total_s

    @property
    def meets_target(self) -> bool:
        """Cumple la meta de validación (< 20 % en el tiempo total)."""
        return self.total_error_after < TARGET_ERROR
