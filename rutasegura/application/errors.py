"""Errores que la interfaz puede mostrar tal cual al usuario (mensajes en español claro)."""

from __future__ import annotations


class UserFacingError(Exception):
    """Error con un mensaje apto para el usuario final."""

    @property
    def message(self) -> str:
        """Mensaje para mostrar."""
        return str(self)


class OperationCancelled(Exception):  # noqa: N818 - nombre de dominio
    """El usuario canceló una operación larga (por ejemplo, la simulación)."""
