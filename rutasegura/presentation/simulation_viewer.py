"""Visor de la simulación: reproducir, pausar, velocidad 0.5×–8×, línea de tiempo y calor."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QStyleOptionGraphicsItem,
    QVBoxLayout,
    QWidget,
)

from rutasegura.domain.enums import AgentStatus
from rutasegura.domain.plan import FloorPlan
from rutasegura.domain.results import SimulationResult, Trajectories
from rutasegura.presentation.editor.scene import PlanScene
from rutasegura.presentation.editor.view import PlanView
from rutasegura.presentation.qt_support import to_pixmap
from rutasegura.resources.texts import TEXTS, FloorTexts, SimulationTexts

PROFILE_COLORS = ("#2471a3", "#e67e22", "#8e44ad", "#16a085", "#c0392b", "#7f8c8d")
SPEEDS = (0.5, 1.0, 2.0, 4.0, 8.0)
TICK_MS = 33
SLIDER_STEPS = 1000


def format_time(seconds: float) -> str:
    """Segundos → «m:ss»."""
    seconds = max(0.0, seconds)
    minutes, secs = divmod(round(seconds), 60)
    return f"{minutes}:{secs:02d}"


def heatmap_rgba(density: npt.NDArray[np.float64]) -> npt.NDArray[np.uint8]:
    """Densidad acumulada → imagen RGBA (transparente donde no hubo gente; amarillo → rojo)."""
    peak = float(density.max()) if density.size else 0.0
    rgba = np.zeros((*density.shape, 4), dtype=np.uint8)
    if peak <= 0:
        return rgba
    v = np.clip(density / peak, 0.0, 1.0)
    shown = v > 0.02
    rgba[..., 0] = np.where(shown, 255 - 40 * v, 0).astype(np.uint8)
    rgba[..., 1] = np.where(shown, 235 * (1 - v), 0).astype(np.uint8)
    rgba[..., 2] = np.where(shown, 60 * (1 - v), 0).astype(np.uint8)
    rgba[..., 3] = np.where(shown, 70 + 150 * np.sqrt(v), 0).astype(np.uint8)
    return rgba


class AgentsItem(QGraphicsItem):
    """Dibuja todas las personas en un solo ítem (mucho más rápido que un ítem por persona)."""

    def __init__(self) -> None:
        super().__init__()
        self._bounds = QRectF()
        self._xy = np.zeros((0, 2))
        self._radius = np.zeros(0)
        self._groups: list[tuple[QColor, npt.NDArray[np.int64]]] = []
        self._visible = np.zeros(0, dtype=bool)
        self.setZValue(100)

    def configure(
        self,
        bounds: QRectF,
        radius_px: npt.NDArray[np.float64],
        profile_index: npt.NDArray[np.int32],
    ) -> None:
        """Define las personas (radio y color por perfil)."""
        self.prepareGeometryChange()
        self._bounds = QRectF(bounds)
        self._radius = radius_px
        self._groups = [
            (QColor(PROFILE_COLORS[k % len(PROFILE_COLORS)]), np.flatnonzero(profile_index == k))
            for k in np.unique(profile_index)
        ]
        self._xy = np.zeros((len(radius_px), 2))
        self._visible = np.zeros(len(radius_px), dtype=bool)

    def set_frame(self, xy_px: npt.NDArray[np.float64], visible: npt.NDArray[np.bool_]) -> None:
        """Posiciones del cuadro actual."""
        self._xy = xy_px
        self._visible = visible
        self.update()

    @property
    def visible_count(self) -> int:
        """Personas dibujadas."""
        return int(self._visible.sum())

    def boundingRect(self) -> QRectF:  # noqa: N802 - API de Qt
        return self._bounds

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        for color, indices in self._groups:
            painter.setBrush(QBrush(color))
            shown = indices[self._visible[indices]]
            for x, y, r in zip(
                self._xy[shown, 0], self._xy[shown, 1], self._radius[shown], strict=True
            ):
                painter.drawEllipse(QPointF(float(x), float(y)), float(r), float(r))


class SimulationViewer(QWidget):
    """Reproduce las trayectorias guardadas sobre el plano."""

    time_changed = Signal(float)

    def __init__(
        self,
        texts: SimulationTexts = TEXTS.simulation,
        parent: QWidget | None = None,
        floor_texts: FloorTexts = TEXTS.floors,
    ) -> None:
        super().__init__(parent)
        self._texts = texts
        self._floor_texts = floor_texts
        self._trajectories: Trajectories | None = None
        self._result: SimulationResult | None = None
        self._floors: dict[int, tuple[FloorPlan, npt.NDArray[np.uint8] | None]] = {}
        self._level = 0
        self._scale = 1.0
        self._fallback_scale = 1.0
        self._time = 0.0
        self._speed = 1.0
        self._end = 0.0
        self._total = 0

        self.scene = PlanScene(self)
        self.view = PlanView(self.scene)
        self.agents = AgentsItem()
        self.scene.addItem(self.agents)
        self.heatmap = QGraphicsPixmapItem()
        self.heatmap.setZValue(50)
        self.heatmap.setVisible(False)
        self.scene.addItem(self.heatmap)

        self.timer = QTimer(self)
        self.timer.setInterval(TICK_MS)
        self.timer.timeout.connect(self._tick)

        self.play_button = QPushButton(texts.play)
        self.play_button.clicked.connect(self.toggle_play)
        self.speed_combo = QComboBox()
        for speed in SPEEDS:
            self.speed_combo.addItem(f"{speed:g}×", speed)
        self.speed_combo.setCurrentIndex(SPEEDS.index(1.0))
        self.speed_combo.currentIndexChanged.connect(
            lambda i: self.set_speed(float(self.speed_combo.itemData(i)))
        )
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, SLIDER_STEPS)
        self.slider.sliderMoved.connect(self._on_slider)
        self.time_label = QLabel(texts.time.format(now="0:00", end="0:00"))
        self.evacuated_label = QLabel()
        self.heatmap_check = QCheckBox(texts.heatmap)
        self.heatmap_check.toggled.connect(self.heatmap.setVisible)
        self.floor_label = QLabel(floor_texts.label)
        self.floor_combo = QComboBox()
        self.floor_combo.currentIndexChanged.connect(self._on_floor_selected)

        controls = QHBoxLayout()
        controls.addWidget(self.floor_label)
        controls.addWidget(self.floor_combo)
        controls.addWidget(self.play_button)
        controls.addWidget(QLabel(texts.speed))
        controls.addWidget(self.speed_combo)
        controls.addWidget(self.slider, stretch=1)
        controls.addWidget(self.time_label)
        controls.addWidget(self.heatmap_check)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view, stretch=1)
        layout.addLayout(controls)
        layout.addWidget(self.evacuated_label)
        self._set_enabled(False)

    # ------------------------------------------------------------------ datos
    def set_plan(self, plan: FloorPlan, image: npt.NDArray[np.uint8] | None) -> None:
        """Fondo y elementos de un solo plano (sin edición)."""
        self.set_floors([(plan, image)])

    def set_floors(self, floors: list[tuple[FloorPlan, npt.NDArray[np.uint8] | None]]) -> None:
        """Pisos del edificio: con más de uno aparece el selector de piso."""
        self._floors = {plan.level: (plan, image) for plan, image in floors}
        levels = sorted(self._floors)
        self.floor_combo.blockSignals(True)
        self.floor_combo.clear()
        for level in levels:
            self.floor_combo.addItem(self._floor_texts.name.format(number=level + 1), level)
        self.floor_combo.blockSignals(False)
        multi = len(levels) > 1
        self.floor_label.setVisible(multi)
        self.floor_combo.setVisible(multi)
        self.show_floor(levels[0] if levels else 0)

    @property
    def level(self) -> int:
        """Piso mostrado."""
        return self._level

    def show_floor(self, level: int) -> None:
        """Muestra un piso: su plano, su mapa de calor y las personas que están en él."""
        self._level = level
        index = self.floor_combo.findData(level)
        if index >= 0 and self.floor_combo.currentIndex() != index:
            self.floor_combo.blockSignals(True)
            self.floor_combo.setCurrentIndex(index)
            self.floor_combo.blockSignals(False)
        plan, image = self._floors.get(level, (FloorPlan(level=level), None))
        self._scale = plan.scale_m_per_px or self._fallback_scale
        self.scene.set_image(image)
        self.scene.render_plan(plan)
        for item in self.scene.all_element_items():
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self._configure_run()
        self.view.fit_all()

    def _on_floor_selected(self, index: int) -> None:
        level = self.floor_combo.itemData(index)
        if level is not None:
            self.show_floor(int(level))

    def set_run(
        self, trajectories: Trajectories | None, result: SimulationResult | None, scale: float
    ) -> None:
        """Carga una corrida (o limpia el visor con ``None``).

        ``scale`` se usa solo si el plano del piso no tiene escala propia.
        """
        self.pause()
        self._trajectories = trajectories
        self._result = result
        self._fallback_scale = scale
        plan = self._floors.get(self._level, (FloorPlan(), None))[0]
        self._scale = plan.scale_m_per_px or scale
        self._configure_run()

    def _configure_run(self) -> None:
        trajectories, result, scale = self._trajectories, self._result, self._scale
        if trajectories is None or result is None or trajectories.frame_count == 0:
            self.agents.configure(QRectF(), np.zeros(0), np.zeros(0, np.int32))
            self.heatmap.setPixmap(to_pixmap(np.zeros((1, 1, 4), np.uint8)))
            self._end = 0.0
            self._total = 0
            self._set_enabled(False)
            self.evacuated_label.setText("")
            return
        self._end = float(trajectories.times_s[-1])
        self._total = trajectories.agent_count
        bounds = self.scene.sceneRect().united(self.scene.itemsBoundingRect())
        self.agents.configure(
            bounds.adjusted(-50, -50, 50, 50),
            trajectories.radius_m.astype(np.float64) / scale,
            trajectories.profile_index,
        )
        maps = {m.level: m for m in result.maps()}
        floor_map = maps.get(self._level) if result.floor_maps else result.maps()[0]
        if floor_map is None:
            self.heatmap.setPixmap(to_pixmap(np.zeros((1, 1, 4), np.uint8)))
        else:
            self.heatmap.setPixmap(to_pixmap(heatmap_rgba(floor_map.density_map)))
            self.heatmap.setScale(floor_map.cell_size_m / scale)
            self.heatmap.setPos(
                floor_map.grid_origin_m[0] / scale, floor_map.grid_origin_m[1] / scale
            )
        self._set_enabled(True)
        self.set_time(min(self._time, self._end))

    # ------------------------------------------------------------------ reproducción
    @property
    def current_time(self) -> float:
        """Instante mostrado (s)."""
        return self._time

    @property
    def end_time(self) -> float:
        """Duración de la corrida (s)."""
        return self._end

    @property
    def speed(self) -> float:
        """Factor de velocidad."""
        return self._speed

    @property
    def is_playing(self) -> bool:
        """Se está reproduciendo."""
        return self.timer.isActive()

    def play(self) -> None:
        """Reproduce desde el instante actual (o desde el inicio si terminó)."""
        if self._trajectories is None:
            return
        if self._time >= self._end:
            self.set_time(0.0)
        self.timer.start()
        self.play_button.setText(self._texts.pause)

    def pause(self) -> None:
        """Pausa."""
        self.timer.stop()
        self.play_button.setText(self._texts.play)

    def toggle_play(self) -> None:
        """Alterna reproducir/pausa."""
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def set_speed(self, factor: float) -> None:
        """Velocidad de reproducción (0.5× a 8×)."""
        self._speed = min(max(factor, SPEEDS[0]), SPEEDS[-1])

    def set_time(self, seconds: float) -> None:
        """Muestra el instante indicado (interpolando entre cuadros guardados)."""
        traj = self._trajectories
        if traj is None:
            return
        self._time = min(max(seconds, 0.0), self._end)
        times = traj.times_s
        idx = int(np.clip(np.searchsorted(times, self._time, side="right") - 1, 0, len(times) - 1))
        nxt = min(idx + 1, len(times) - 1)
        span = times[nxt] - times[idx]
        alpha = 0.0 if span <= 0 else (self._time - times[idx]) / span
        pos = traj.positions[idx] * (1 - alpha) + traj.positions[nxt] * alpha
        present = traj.status[idx] != AgentStatus.EVACUATED
        visible = present
        if traj.level is not None:
            here = traj.levels_at(idx)
            visible = present & (here == self._level)
            # quien cambia de piso entre cuadros no se interpola entre dos planos distintos
            jumped = here != traj.levels_at(nxt)
            pos[jumped] = traj.positions[idx][jumped]
        self.agents.set_frame(pos.astype(np.float64) / self._scale, visible)
        evacuated = self._total - int(present.sum())
        self.evacuated_label.setText(
            self._texts.evacuated.format(done=evacuated, total=self._total)
        )
        self.time_label.setText(
            self._texts.time.format(now=format_time(self._time), end=format_time(self._end))
        )
        if not self.slider.isSliderDown():
            self.slider.blockSignals(True)
            self.slider.setValue(round(SLIDER_STEPS * self._time / self._end) if self._end else 0)
            self.slider.blockSignals(False)
        self.time_changed.emit(self._time)

    def advance(self, real_seconds: float) -> None:
        """Avanza la reproducción ``real_seconds`` de reloj (× velocidad)."""
        self.set_time(self._time + real_seconds * self._speed)
        if self._time >= self._end:
            self.pause()

    def _tick(self) -> None:
        self.advance(TICK_MS / 1000.0)

    def _on_slider(self, value: int) -> None:
        self.set_time(self._end * value / SLIDER_STEPS)

    def _set_enabled(self, enabled: bool) -> None:
        for widget in (self.play_button, self.speed_combo, self.slider, self.heatmap_check):
            widget.setEnabled(enabled)
