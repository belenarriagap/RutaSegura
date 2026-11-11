"""Autoprueba sin red: verifica que la instalación tiene todo lo necesario.

Se ejecuta con ``rutasegura --self-test``. Sirve sobre todo para comprobar el programa
empaquetado con PyInstaller (reglas YAML, perfiles, migraciones, OpenCV, PDF y fuentes).
Trabaja en una carpeta temporal: no toca la base de datos del usuario.
"""

from __future__ import annotations

import dataclasses
import tempfile
import traceback
from collections.abc import Callable
from pathlib import Path

import numpy as np

from rutasegura.application.norms_service import load_packaged_rules
from rutasegura.application.services import AppServices
from rutasegura.data.default_profiles import load_default_profiles
from rutasegura.domain.enums import UseType
from rutasegura.domain.geometry import Point, Polygon, Segment
from rutasegura.domain.people import Occupancy
from rutasegura.domain.plan import Exit, FloorPlan, Room, Wall

PX_PER_M = 50.0


def _m(x: float, y: float) -> Point:
    return Point(x * PX_PER_M, y * PX_PER_M)


def sample_plan() -> FloorPlan:
    """Aula de 8 × 6 m con una salida de 1.2 m."""
    walls = [
        Segment(_m(0, 0), _m(8, 0)),
        Segment(_m(0, 6), _m(8, 6)),
        Segment(_m(0, 0), _m(0, 6)),
        Segment(_m(8, 0), _m(8, 2.4)),
        Segment(_m(8, 3.6), _m(8, 6)),
    ]
    room = Polygon((_m(0, 0), _m(8, 0), _m(8, 6), _m(0, 6)))
    return FloorPlan(
        scale_m_per_px=1 / PX_PER_M,
        walls=tuple(Wall(w) for w in walls),
        exits=(Exit(Segment(_m(8, 2.4), _m(8, 3.6)), "Salida 1"),),
        rooms=(Room("Aula 1", UseType.EDUCATION, room),),
    )


def sample_image() -> np.ndarray:
    """Imagen del plano de ejemplo (para probar la visión)."""
    image = np.full((360, 480, 3), 255, np.uint8)
    image[20:30, 20:460] = 0
    image[330:340, 20:460] = 0
    image[20:340, 20:30] = 0
    image[20:140, 450:460] = 0
    image[200:340, 450:460] = 0
    return image


def run_self_test(log: Callable[[str], None]) -> bool:
    """Ejecuta las comprobaciones; devuelve ``True`` si todas pasan."""
    checks: list[tuple[str, Callable[[Path], str]]] = [
        ("Reglas normativas", lambda _: f"{len(load_packaged_rules().rules)} reglas"),
        ("Perfiles por defecto", lambda _: f"{len(load_default_profiles())} perfiles"),
        ("Base de datos y migraciones", _check_database),
        ("Visión (OpenCV)", _check_vision),
        ("Simulación e informe PDF", _check_simulation_and_report),
    ]
    ok = True
    with tempfile.TemporaryDirectory(prefix="rutasegura_autoprueba_") as tmp:
        for name, check in checks:
            try:
                detail = check(Path(tmp))
            except Exception:  # se informa todo error: es una prueba de diagnóstico
                ok = False
                log(f"FALLA  {name}\n{traceback.format_exc()}")
            else:
                log(f"OK     {name}: {detail}")
    log("Autoprueba superada." if ok else "La autoprueba encontró errores.")
    return ok


def _check_database(tmp: Path) -> str:
    services = AppServices.open(tmp / "db" / "prueba.db")
    try:
        project_id = services.projects.create_project("Autoprueba", UseType.EDUCATION)
        services.projects.save_floor(project_id, sample_plan(), sample_image())
        plan = services.projects.load_floor(project_id)
        if plan is None or not plan.rooms:
            raise RuntimeError("El plano guardado no se pudo leer.")
        return f"{len(services.simulations.profiles())} perfiles en la base"
    finally:
        services.close()


def _check_vision(tmp: Path) -> str:
    services = AppServices.open(tmp / "db_vision" / "prueba.db")
    try:
        plan = services.plans.detect(sample_image(), FloorPlan(scale_m_per_px=1 / PX_PER_M))
        return f"{len(plan.walls)} muros y {len(plan.exits)} salidas detectados"
    finally:
        services.close()


def _check_simulation_and_report(tmp: Path) -> str:
    services = AppServices.open(tmp / "db_sim" / "prueba.db")
    try:
        project_id = services.projects.create_project("Autoprueba", UseType.EDUCATION)
        plan = services.projects.save_floor(project_id, sample_plan(), sample_image())
        scenario = dataclasses.replace(
            services.simulations.load_scenario(project_id),
            occupancies=(Occupancy("Aula 1", "adulto", 15),),
        )
        run = services.simulations.run(project_id, plan, scenario)
        report = services.reports.generate(project_id, tmp / "informe.pdf")
        size = report.stat().st_size
        if not run.result.completed:
            raise RuntimeError("La simulación de prueba no terminó.")
        if size < 10_000:
            raise RuntimeError(f"El informe PDF es demasiado pequeño ({size} bytes).")
        return f"evacuación en {run.result.total_time_s:.0f} s, informe de {size // 1024} KB"
    finally:
        services.close()
