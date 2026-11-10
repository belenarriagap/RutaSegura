# Registro de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [Sin publicar]

### Hito 0: base del proyecto (2026-11-10)

#### Agregado
- `pyproject.toml` con Python 3.12, gestionado con uv. Las versiones quedan fijadas en `uv.lock`.
- Estructura de carpetas `rutasegura/` (domain, engines, application, data, presentation,
  resources) y `tests/` (unit, integration, architecture, benchmarks, fixtures).
- Dominio (`rutasegura/domain/`):
  - geometría: `Point`, `Segment`, `Polygon`;
  - plano: `FloorPlan`, `Wall`, `Door`, `Exit`, `Stair`, `Obstacle`, `SafeZone`, `Room`;
  - personas y escenarios: `PersonProfile`, `Occupancy`, `Scenario`, `RealDrill`;
  - agentes: `AgentArrays`, estructura de arrays NumPy;
  - resultados: `SimulationResult`, `Bottleneck`, `Observation`;
  - enums de dominio.
- Configuración de ruff, mypy (`--strict` en `domain` y `engines`) y pytest con
  `--disable-socket`.
- Prueba de arquitectura propia basada en AST, que revisa:
  - las capas;
  - Qt y SQLAlchemy fuera de `engines` y `domain`;
  - que no haya acceso a red;
  - que no se use `random` ni la API aleatoria global de NumPy.
- Prueba de que los sockets están bloqueados durante las pruebas (RNF01).
- Ventana principal PySide6 con los 7 pasos del asistente (aún deshabilitados), menús en español
  y textos centralizados en `rutasegura/resources/texts.py`.
- CI de GitHub Actions: ruff, mypy y pytest en Windows y Ubuntu.
- README y registro de decisiones (`docs/decisiones.md`).
