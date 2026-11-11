"""Widgets comunes: títulos de paso, franjas de mensaje y tarjetas de resultados."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from rutasegura.presentation.theme import repolish

KINDS = ("success", "warning", "error", "info")
_ICONS = {"success": "✓", "warning": "!", "error": "✕", "info": "i"}


def page_title(text: str) -> QLabel:
    """Título grande de un paso."""
    label = QLabel(text)
    label.setObjectName("pageTitle")
    return label


def page_help(text: str) -> QLabel:
    """Texto de ayuda bajo el título."""
    label = QLabel(text)
    label.setObjectName("pageHelp")
    label.setWordWrap(True)
    return label


def section_title(text: str) -> QLabel:
    """Subtítulo de una sección."""
    label = QLabel(text)
    label.setObjectName("sectionTitle")
    return label


def muted(text: str = "") -> QLabel:
    """Texto secundario (gris)."""
    label = QLabel(text)
    label.setObjectName("muted")
    label.setWordWrap(True)
    return label


class Banner(QFrame):
    """Franja de mensaje dentro de la ventana (en lugar de una ventana emergente).

    ``kind``: ``success``, ``warning``, ``error`` o ``info``. Puede llevar un botón de acción
    (por ejemplo «Ir al paso 2») y, si ``closable``, una ✕ para cerrarla.
    """

    action_triggered = Signal()
    closed = Signal()

    def __init__(self, closable: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("banner")
        self._kind = "info"
        self.icon_label = QLabel()
        self.icon_label.setObjectName("bannerIcon")
        self.icon_label.setFixedWidth(22)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_label = QLabel()
        self.text_label.setWordWrap(True)
        self.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.action_button = QPushButton()
        self.action_button.clicked.connect(self.action_triggered)
        self.action_button.setVisible(False)
        self.close_button = QPushButton("×")
        self.close_button.setObjectName("bannerClose")
        self.close_button.setToolTip("Cerrar")
        self.close_button.clicked.connect(self.dismiss)
        self.close_button.setVisible(closable)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 6, 6)
        layout.addWidget(self.icon_label, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.text_label, stretch=1)
        layout.addWidget(self.action_button)
        layout.addWidget(self.close_button, alignment=Qt.AlignmentFlag.AlignTop)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.dismiss)
        self._action: Callable[[], None] | None = None
        self.action_triggered.connect(self._run_action)
        self.setVisible(False)

    @property
    def kind(self) -> str:
        """Tipo de mensaje mostrado."""
        return self._kind

    @property
    def text(self) -> str:
        """Texto mostrado."""
        return self.text_label.text()

    def show_message(
        self,
        text: str,
        kind: str = "info",
        *,
        action_text: str = "",
        action: Callable[[], None] | None = None,
        timeout_ms: int = 0,
    ) -> None:
        """Muestra el mensaje (``timeout_ms`` > 0 lo oculta solo después de ese tiempo)."""
        if kind not in KINDS:
            raise ValueError(f"Tipo de mensaje desconocido: {kind}")
        self._kind = kind
        self.setProperty("kind", kind)
        self.icon_label.setText(_ICONS[kind])
        self.text_label.setText(text)
        self._action = action
        self.action_button.setText(action_text)
        self.action_button.setVisible(bool(action_text))
        repolish(self)
        for child in (self.icon_label, self.text_label):
            repolish(child)
        self.setVisible(True)
        self._timer.stop()
        if timeout_ms > 0:
            self._timer.start(timeout_ms)

    def dismiss(self) -> None:
        """Oculta la franja."""
        self._timer.stop()
        was_shown = not self.isHidden()
        self.setVisible(False)
        if was_shown:
            self.closed.emit()

    def _run_action(self) -> None:
        if self._action is not None:
            self._action()


class MetricCard(QFrame):
    """Tarjeta con un indicador grande (p. ej. «Tiempo total: 1 min 30 s») y su color."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.title_label = QLabel(title)
        self.title_label.setObjectName("cardTitle")
        self.value_label = QLabel("—")
        self.value_label.setObjectName("cardValue")
        self.note_label = QLabel()
        self.note_label.setObjectName("cardNote")
        self.note_label.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(2)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.note_label)
        self.set_value("—")

    @property
    def kind(self) -> str:
        """Color del indicador (``success``, ``warning``, ``error``, ``info``)."""
        value = self.property("kind")
        return str(value) if value else "info"

    def set_value(self, value: str, note: str = "", kind: str = "info") -> None:
        """Actualiza el valor, la nota y el color."""
        self.value_label.setText(value)
        self.note_label.setText(note)
        self.note_label.setVisible(bool(note))
        self.setProperty("kind", kind)
        repolish(self)
        repolish(self.value_label)
