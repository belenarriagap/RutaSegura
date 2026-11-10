"""RNF02 (render, medido aparte del motor): cuadros por segundo del visor con 500 agentes."""

from __future__ import annotations

import time

import numpy as np
import pytest
from PySide6.QtGui import QImage, QPainter
from pytestqt.qtbot import QtBot

from rutasegura.domain.people import Occupancy
from rutasegura.presentation.simulation_viewer import SimulationViewer
from tests.fixtures.simple_plans import SCALE, single_room
from tests.unit.engines.simulation.helpers import make_simulation

FRAMES = 30
MIN_FPS = 10.0  # holgado: el render por software en CI es lento


@pytest.mark.benchmark
def test_viewer_render_speed(qtbot: QtBot) -> None:
    plan = single_room(width=30.0, height=20.0, exit_width=1.8, second_exit=True)
    sim = make_simulation(plan, [Occupancy("Aula 1", "adulto", 500)], seed=3)
    sim.agents.reaction_time[:] = 0.0
    for _ in range(20):
        sim.step()
    out = sim.output()
    viewer = SimulationViewer()
    qtbot.addWidget(viewer)
    viewer.resize(1000, 700)
    viewer.set_plan(plan, np.full((1100, 1600, 3), 255, np.uint8))
    viewer.set_run(out.trajectories, out.result, SCALE)
    target = QImage(1000, 700, QImage.Format.Format_ARGB32)
    start = time.perf_counter()
    for k in range(FRAMES):
        viewer.set_time(out.trajectories.times_s[-1] * k / FRAMES)
        painter = QPainter(target)
        viewer.scene.render(painter)
        painter.end()
    fps = FRAMES / (time.perf_counter() - start)
    print(f"\nrender con 500 agentes: {fps:.1f} cuadros/s")
    assert fps >= MIN_FPS
