"""Diálogos de escenarios «qué pasa si» y comparador lado a lado (RF10)."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np
import numpy.typing as npt
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rutasegura.application.simulation_service import SimulationRun
from rutasegura.domain.plan import FloorPlan
from rutasegura.domain.scenario import Scenario
from rutasegura.presentation.simulation_viewer import SimulationViewer, format_time
from rutasegura.resources.texts import TEXTS, ScenarioTexts, SimulationTexts

Image = npt.NDArray[np.uint8]


class ScenarioDialog(QDialog):
    """Nombre, porcentaje de ocupación respecto del base y salidas bloqueadas."""

    def __init__(
        self,
        exit_names: Sequence[str],
        base_total: int,
        *,
        name: str = "",
        percent: int = 100,
        blocked: frozenset[str] = frozenset(),
        editing: bool = False,
        texts: ScenarioTexts = TEXTS.scenarios,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._texts = texts
        self._base_total = base_total
        self.setWindowTitle(texts.dialog_edit_title if editing else texts.dialog_new_title)
        self.name_edit = QLineEdit(name)
        self.percent_spin = QSpinBox()
        self.percent_spin.setRange(10, 500)
        self.percent_spin.setSingleStep(10)
        self.percent_spin.setSuffix(" %")
        self.percent_spin.setValue(percent)
        self.result_label = QLabel()
        self.percent_spin.valueChanged.connect(self._update_result)
        self.exits_list = QListWidget()
        for exit_name in exit_names:
            item = QListWidgetItem(exit_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            checked = exit_name in blocked
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            self.exits_list.addItem(item)
        hint = QLabel(texts.base_hint)
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #7f8c8d;")
        form = QFormLayout()
        form.addRow(texts.name, self.name_edit)
        form.addRow(texts.occupancy, self.percent_spin)
        form.addRow("", self.result_label)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel(texts.blocked if exit_names else texts.no_exits))
        layout.addWidget(self.exits_list)
        layout.addWidget(hint)
        layout.addWidget(buttons)
        self._update_result()

    def values(self) -> tuple[str, int, frozenset[str]]:
        """(nombre, porcentaje, salidas bloqueadas)."""
        blocked = {
            self.exits_list.item(i).text()
            for i in range(self.exits_list.count())
            if self.exits_list.item(i).checkState() == Qt.CheckState.Checked
        }
        return self.name_edit.text().strip(), self.percent_spin.value(), frozenset(blocked)

    def _update_result(self) -> None:
        count = round(self._base_total * self.percent_spin.value() / 100)
        self.result_label.setText(
            self._texts.occupancy_result.format(count=count, base=self._base_total)
        )


def _signed(seconds: float) -> str:
    sign = "+" if seconds > 0 else "−" if seconds < 0 else "±"
    return sign + format_time(abs(seconds))


def comparison_rows(
    a: tuple[Scenario, SimulationRun], b: tuple[Scenario, SimulationRun], texts: ScenarioTexts
) -> list[tuple[str, str, str, str]]:
    """Filas (indicador, A, B, diferencia) de la comparación."""
    (sa, ra), (sb, rb) = a, b
    rows = [
        (
            texts.row_people,
            str(sa.total_occupants),
            str(sb.total_occupants),
            f"{sb.total_occupants - sa.total_occupants:+d}",
        ),
        (
            texts.row_blocked,
            ", ".join(sorted(sa.blocked_exits)) or texts.none,
            ", ".join(sorted(sb.blocked_exits)) or texts.none,
            "",
        ),
        (
            texts.row_total,
            format_time(ra.result.total_time_s),
            format_time(rb.result.total_time_s),
            _signed(rb.result.total_time_s - ra.result.total_time_s),
        ),
        (
            texts.row_evacuated,
            f"{ra.result.agents_evacuated} / {ra.result.agents_total}",
            f"{rb.result.agents_evacuated} / {rb.result.agents_total}",
            "",
        ),
        (
            texts.row_bottlenecks,
            str(len(ra.result.bottlenecks)),
            str(len(rb.result.bottlenecks)),
            f"{len(rb.result.bottlenecks) - len(ra.result.bottlenecks):+d}",
        ),
    ]
    for label, fraction in ((texts.row_half, 0.5), (texts.row_ninety, 0.9)):
        ta, tb = ra.result.time_to_evacuate(fraction), rb.result.time_to_evacuate(fraction)
        rows.insert(
            3 if fraction == 0.5 else 4,
            (
                label,
                format_time(ta) if ta is not None else "—",
                format_time(tb) if tb is not None else "—",
                _signed(tb - ta) if ta is not None and tb is not None else "",
            ),
        )
    times_a = dict(ra.result.time_per_exit_s)
    times_b = dict(rb.result.time_per_exit_s)
    for name in sorted(set(times_a) | set(times_b)):
        ta, tb = times_a.get(name), times_b.get(name)
        diff = _signed(tb - ta) if ta is not None and tb is not None else ""
        rows.append(
            (
                texts.row_exit.format(name=name),
                format_time(ta) if ta is not None else texts.not_used,
                format_time(tb) if tb is not None else texts.not_used,
                diff,
            )
        )
    return rows


class ComparisonDialog(QDialog):
    """Dos escenarios lado a lado: visor, mapa de calor y métricas."""

    def __init__(
        self,
        scenarios: Sequence[Scenario],
        load_run: Callable[[str], SimulationRun | None],
        floors: Sequence[tuple[FloorPlan, Image | None]],
        *,
        texts: ScenarioTexts = TEXTS.scenarios,
        sim_texts: SimulationTexts = TEXTS.simulation,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._texts = texts
        self.setWindowTitle(texts.compare_title)
        self.resize(1300, 850)
        self._runs: dict[str, tuple[Scenario, SimulationRun]] = {}
        for scenario in scenarios:
            run = load_run(scenario.name)
            if run is not None:
                self._runs[scenario.name] = (scenario, run)
        names = list(self._runs)
        self.combos = (QComboBox(), QComboBox())
        self.viewers = (SimulationViewer(sim_texts), SimulationViewer(sim_texts))
        sides = QHBoxLayout()
        for k, (combo, viewer) in enumerate(zip(self.combos, self.viewers, strict=True)):
            combo.addItems(names)
            if len(names) > k:
                combo.setCurrentIndex(k)
            combo.currentIndexChanged.connect(self._refresh)
            viewer.set_floors(list(floors))
            column = QVBoxLayout()
            column.addWidget(QLabel("A" if k == 0 else "B"))
            column.addWidget(combo)
            column.addWidget(viewer, stretch=1)
            sides.addLayout(column)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([texts.metric, "A", "B", texts.difference])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.play_button = QPushButton(texts.play_both)
        self.play_button.clicked.connect(self.play_both)
        self.message = QLabel(texts.compare_need_two if len(names) < 2 else "")
        layout = QVBoxLayout(self)
        layout.addLayout(sides, stretch=3)
        layout.addWidget(self.play_button)
        layout.addWidget(self.message)
        layout.addWidget(self.table, stretch=1)
        self._refresh()

    @property
    def available(self) -> list[str]:
        """Escenarios con simulación."""
        return list(self._runs)

    def play_both(self) -> None:
        """Reproduce ambos desde el inicio, a la vez."""
        for viewer in self.viewers:
            viewer.set_time(0.0)
            viewer.play()

    def _refresh(self) -> None:
        chosen = [self._runs.get(c.currentText()) for c in self.combos]
        for viewer, data in zip(self.viewers, chosen, strict=True):
            if data is None:
                viewer.set_run(None, None, 1.0)
            else:
                run = data[1]
                viewer.set_run(run.trajectories, run.result, run.scale_m_per_px)
        self.play_button.setEnabled(all(d is not None for d in chosen))
        self.table.setRowCount(0)
        if chosen[0] is None or chosen[1] is None:
            return
        rows = comparison_rows(chosen[0], chosen[1], self._texts)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, text in enumerate(row):
                self.table.setItem(r, c, QTableWidgetItem(text))
        self.table.resizeColumnsToContents()
