# Registro de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [Sin publicar]

### Hito 2: visión y editor (2026-11-10)

#### Agregado
- **Carga de planos (RF01)** en `engines/vision/images.py`:
  - acepta JPG, PNG, BMP, TIFF y PDF; el PDF se rasteriza a 200 dpi, con un límite de 6000 px;
  - admite rutas con tildes y eñes.
- **Rectificación de perspectiva:** el usuario marca 4 esquinas, en cualquier orden.
- **Detección automática (RF02)** en `engines/vision/pipeline.py`:
  1. umbral adaptativo;
  2. máscara de trazos gruesos;
  3. esqueleto (Zhang-Suen);
  4. HoughLinesP;
  5. fusión de segmentos colineales con reajuste por mínimos cuadrados;
  6. unión de esquinas.
- **Detección de puertas:** son los tramos vacíos a lo largo de cada muro, también los que están
  junto a una esquina. La confianza aumenta si se encuentra el arco de apertura.
- **Salidas propuestas:** son los vanos que están en el contorno exterior. Quedan
  **sin confirmar** hasta que el usuario las acepte.
- **Escala (RF04):** se define con dos puntos y una medida real en metros.
- **Generador de planos sintéticos** (`tests/fixtures/synthetic_plans.py`):
  - el resultado es reproducible con una semilla;
  - incluye ruido, desenfoque, rotación, iluminación desigual, textos, cotas y mobiliario.
- **Script de evaluación** `scripts/eval_vision.py`:
  - funciona con planos sintéticos y con planos reales etiquetados;
  - puede guardar imágenes de control;
  - el formato de las etiquetas está en `docs/formato_etiquetas.md`.
- **Resultado en 40 planos sintéticos:**
  - muros: 100 % de precisión y 99.9 % de exhaustividad;
  - vanos: 100 % de precisión y 98.9 % de exhaustividad.
- **Editor (RF03):**
  - dibuja muros, puertas, salidas, escaleras, obstáculos y zonas seguras;
  - selecciona y borra elementos;
  - confirma las salidas propuestas;
  - deshace y rehace con `QUndoStack`;
  - zoom con la rueda y desplazamiento con el botón central;
  - capas visibles;
  - líneas rectas con Mayús;
  - los elementos de baja confianza se ven en naranja discontinuo.
- **Asistente, pasos 1 a 3:** cargar plano, escala y corregir plano. Al entrar al paso 3 la
  detección se ejecuta sola, en segundo plano.
- **Proyectos:**
  - se pueden crear y abrir;
  - se guardan automáticamente al cambiar de paso y al cerrar, y también con Ctrl+S;
  - la imagen procesada se guarda en `%LOCALAPPDATA%\RutaSegura\planos\`.
- **Servicios de aplicación:** `ProjectService` y `PlanImportService`. Los errores llegan al
  usuario como mensajes claros (`UserFacingError`).

#### Cambiado
- `Exit` y `Stair` tienen el nuevo campo `confirmed`. Se guarda como `confirmada` en las
  propiedades GeoJSON.
- `MainWindow` ahora recibe `AppServices`. `__main__` abre la base de datos local al iniciar.

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
