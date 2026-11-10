"""Utilidades de Qt: conversión de imágenes y tareas en segundo plano."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

import numpy as np
import numpy.typing as npt
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtGui import QImage, QPixmap

from rutasegura.application.errors import OperationCancelled, UserFacingError

UNEXPECTED_ERROR = "Ocurrió un error inesperado: {error}"


def to_pixmap(image: npt.NDArray[np.uint8]) -> QPixmap:
    """Array RGB (alto, ancho, 3) o gris (alto, ancho) → ``QPixmap``."""
    data = np.ascontiguousarray(image)
    h, w = data.shape[:2]
    if data.ndim == 2:
        fmt = QImage.Format.Format_Grayscale8
    elif data.shape[2] == 4:
        fmt = QImage.Format.Format_RGBA8888
    else:
        fmt = QImage.Format.Format_RGB888
    qimage = QImage(data.data, w, h, data.strides[0], fmt)
    return QPixmap.fromImage(qimage.copy())  # copy(): Qt no debe apuntar al buffer de NumPy


class _TaskSignals(QObject):
    done = Signal(object)
    failed = Signal(str)


class _Task(QRunnable):
    def __init__(self, fn: Callable[[], Any], signals: _TaskSignals) -> None:
        super().__init__()
        self._fn = fn
        self.signals = signals

    def run(self) -> None:
        try:
            result = self._fn()
        except UserFacingError as exc:
            self.signals.failed.emit(exc.message)
        except Exception as exc:
            self.signals.failed.emit(UNEXPECTED_ERROR.format(error=exc))
        else:
            self.signals.done.emit(result)


_running: set[_TaskSignals] = set()


def run_in_background(
    fn: Callable[[], Any],
    on_done: Callable[[Any], None],
    on_error: Callable[[str], None],
) -> None:
    """Ejecuta ``fn`` en un hilo del pool para no congelar la interfaz.

    Los callbacks se llaman en el hilo de la interfaz (conexión en cola de Qt).
    """
    signals = _TaskSignals()
    _running.add(signals)

    def finished_ok(result: object) -> None:
        _running.discard(signals)
        on_done(result)

    def finished_error(message: str) -> None:
        _running.discard(signals)
        on_error(message)

    signals.done.connect(finished_ok)
    signals.failed.connect(finished_error)
    QThreadPool.globalInstance().start(_Task(fn, signals))


class BackgroundJob(QObject):
    """Tarea larga con progreso y cancelación (p. ej. la simulación).

    ``fn(report_progress, should_cancel)`` se ejecuta en otro hilo. Si lanza
    ``OperationCancelled`` se emite ``cancelled``; si lanza ``UserFacingError``, ``failed``.
    """

    progress = Signal(float)
    done = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        fn: Callable[[Callable[[float], None], Callable[[], bool]], Any],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._fn = fn
        self._cancel = threading.Event()
        self.running = False

    def start(self) -> None:
        """Inicia la tarea en el pool de hilos."""
        self._cancel.clear()
        self.running = True
        QThreadPool.globalInstance().start(_JobRunnable(self))

    def cancel(self) -> None:
        """Pide cancelar (la tarea lo revisa periódicamente)."""
        self._cancel.set()

    def _execute(self) -> None:
        try:
            result = self._fn(self.progress.emit, self._cancel.is_set)
        except OperationCancelled:
            self.running = False
            self.cancelled.emit()
        except UserFacingError as exc:
            self.running = False
            self.failed.emit(exc.message)
        except Exception as exc:
            self.running = False
            self.failed.emit(UNEXPECTED_ERROR.format(error=exc))
        else:
            self.running = False
            self.done.emit(result)


class _JobRunnable(QRunnable):
    def __init__(self, job: BackgroundJob) -> None:
        super().__init__()
        self._job = job

    def run(self) -> None:
        self._job._execute()
