"""Genera las capturas del manual de usuario (docs/img/*.png) con un plano sintético.

Uso:  uv run python scripts/capture_screenshots.py [carpeta_de_salida]
Trabaja en una base de datos temporal; no toca los proyectos del usuario.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from rutasegura.application.services import AppServices  # noqa: E402
from rutasegura.domain.enums import UseType  # noqa: E402
from rutasegura.domain.geometry import Point  # noqa: E402
from rutasegura.engines.vision.images import write_png  # noqa: E402
from rutasegura.presentation.main_window import (  # noqa: E402
    STEP_EDIT,
    STEP_NORMS,
    STEP_REPORT,
    STEP_ROOMS,
    STEP_SCALE,
    STEP_SIMULATE,
    MainWindow,
)
from rutasegura.presentation.theme import apply_theme  # noqa: E402
from tests.fixtures.synthetic_plans import generate_plan  # noqa: E402

OUT = ROOT / "docs" / "img"
WIDTH = 1200


def save(app: QApplication, widget: QWidget, name: str) -> None:
    app.processEvents()
    pixmap = widget.grab()
    if pixmap.width() > WIDTH:
        pixmap = pixmap.scaledToWidth(WIDTH, Qt.TransformationMode.SmoothTransformation)
    pixmap.save(str(OUT / f"{name}.png"))
    print(f"  {name}.png")


def offscreen(widget: QWidget, width: int = 1400, height: int = 850) -> None:
    widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    widget.resize(width, height)
    widget.show()


def main() -> None:
    global OUT
    if len(sys.argv) > 1:
        OUT = Path(sys.argv[1])
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv[:1])
    apply_theme(app)
    with tempfile.TemporaryDirectory() as tmp:
        services = AppServices.open(Path(tmp) / "db" / "rs.db")
        try:
            capture(app, services, Path(tmp))
        finally:
            services.close()


def capture(app: QApplication, services: AppServices, tmp: Path) -> None:
    synthetic = generate_plan(1)
    plan_file = tmp / "plano_colegio.png"
    write_png(plan_file, synthetic.image)

    w = MainWindow(services)
    offscreen(w)
    save(app, w, "00_bienvenida")
    project_id = w.create_project("I.E. N.º 123 San Martín", UseType.EDUCATION, "Jr. Lima 456")
    assert project_id is not None

    w.load_page.open_file(plan_file)
    save(app, w, "01_cargar_plano")

    w.go_to_step(STEP_SCALE)
    px = 10.0 / synthetic.scale_m_per_px
    w.scale_page.set_reference(Point(100, 60), Point(100 + px, 60))
    w.scale_page.meters_spin.setValue(10.0)
    w.scale_page.apply_scale()
    save(app, w, "02_escala")

    w._plan = services.plans.detect(w._image, w.plan)  # detección síncrona para la captura
    w._dirty = True
    w.go_to_step(STEP_EDIT)
    save(app, w, "03_corregir_plano")
    w.editor_page.editor.confirm_exits(range(len(w.plan.exits)))

    w.go_to_step(STEP_ROOMS)
    w.rooms_page.detect_rooms()
    for i, room in enumerate(w.rooms_page.plan.rooms):
        w.rooms_page.set_occupants(room.name, "niño" if i % 3 else "adulto", 25 if i % 3 else 2)
    save(app, w, "04_ambientes_ocupantes")

    w.go_to_step(STEP_NORMS)
    save(app, w, "05_revisar_norma")

    w.go_to_step(STEP_SIMULATE)
    page = w.simulation_page
    scenario = w.scenario
    assert scenario is not None
    page.set_run(services.simulations.run(project_id, w.plan, scenario))
    page.viewer.pause()
    page.viewer.set_time(page.viewer.end_time * 0.35)
    page.viewer.heatmap_check.setChecked(True)
    save(app, w, "06_simular")

    page.create_variant("Salida 2 bloqueada", 100, frozenset({"Salida 2"}))
    services.simulations.run(project_id, w.plan, page.current_scenario)
    page.select_scenario("Salida 2 bloqueada")
    dialog = page.comparison_dialog()
    assert dialog is not None
    offscreen(dialog, 1300, 850)
    for viewer in dialog.viewers:
        viewer.set_time(30)
        viewer.heatmap_check.setChecked(True)
    save(app, dialog, "07_comparar_escenarios")
    dialog.close()

    calibration = w.calibration_dialog()
    assert calibration is not None
    offscreen(calibration, 620, 480)
    calibration.minutes_spin.setValue(2)
    calibration.seconds_spin.setValue(10)
    save(app, calibration, "08_calibrar")
    calibration.close()

    w.go_to_step(STEP_REPORT)
    save(app, w, "09_informe")

    w.add_floor()  # piso 2: selector de pisos y guía del paso 1
    w.load_page.open_file(plan_file)
    save(app, w, "10_varios_pisos")
    w._dirty = w._scenario_dirty = False
    w.close()


if __name__ == "__main__":
    main()
