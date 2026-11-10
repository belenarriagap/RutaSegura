# Registro de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [Sin publicar]

### Hito 1: datos (2026-11-10)

#### Agregado
- Modelos SQLAlchemy 2.x tipados (`rutasegura/data/models.py`) para las 10 tablas de la §6. Las
  tablas y columnas están en español y los atributos de Python en inglés.
- Migración inicial de Alembic (`0001`). Se aplica sola al abrir la base de datos, sin depender de
  `alembic.ini`. El `alembic.ini` de la raíz sirve solo para crear nuevas migraciones.
- `Database` y `UnitOfWork` (`rutasegura/data/database.py`):
  - activa las claves foráneas;
  - ejecuta cada unidad de trabajo en una transacción;
  - recibe una fábrica de motores intercambiable, que deja listo el cifrado opcional con
    SQLCipher (RNF04).
- Ruta por defecto de la base de datos: `%LOCALAPPDATA%\RutaSegura\rutasegura.db`.
- Repositorios de proyectos, pisos (plano completo), perfiles, escenarios, simulaciones con sus
  observaciones y simulacros reales.
- Geometrías guardadas como GeoJSON (`rutasegura/data/geojson.py`).
- Perfiles por defecto en YAML, con la fuente de cada valor: adulto, niño y movilidad reducida.
  Todos los valores son **provisionales**; el detalle está en `docs/perfiles.md`.
- Pruebas:
  - la migración genera exactamente el esquema de los modelos, y se puede bajar y volver a subir;
  - los repositorios guardan y leen los datos sin pérdida;
  - los borrados en cascada funcionan;
  - las transacciones se revierten ante un error;
  - los perfiles editados por el usuario se respetan.

#### Cambiado
- `ElementType` tiene el nuevo valor `SAFE_ZONE` (`zona_segura`), porque RF03 pide marcar zonas
  seguras.
- `Occupancy` tiene el nuevo campo `level` (piso del ambiente).
- `Scenario.blocked_exits` ahora guarda nombres de salidas en lugar de índices.
- Nuevas dataclasses `Project` y `SimulationSummary` en el dominio.

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
