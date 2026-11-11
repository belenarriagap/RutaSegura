# RutaSegura

Aplicación de escritorio, **100% offline**, que convierte el plano 2D de un local (colegio,
oficina, tienda) en un modelo del edificio, verifica aforo y anchos mínimos según la norma peruana
(RNE A.130), simula la evacuación ante un sismo y entrega un informe PDF.

> Este informe es de apoyo y no reemplaza la Inspección Técnica de Seguridad en Edificaciones
> (ITSE) ni el estudio de un profesional colegiado.

**Estado:** Hito 6 (entrega y varios pisos) terminado: todos los hitos completos. Ver [docs/CHANGELOG.md](docs/CHANGELOG.md).

## Requisitos

- Windows 10/11 (Linux opcional).
- [uv](https://docs.astral.sh/uv/). uv instala Python 3.12 y todas las dependencias, con las
  versiones fijadas en `uv.lock`.

## Instalación para desarrollo

```bash
uv sync
```

## Ejecutar la aplicación

```bash
uv run rutasegura
```

(también funciona `uv run python -m rutasegura`)

## Calidad

```bash
uv run ruff check
uv run ruff format --check
uv run mypy
uv run pytest --cov
```

Las pruebas corren **sin red** (`pytest-socket --disable-socket`). La interfaz se prueba con
pytest-qt en modo `offscreen`.

## Arquitectura

Cuatro capas; las dependencias solo apuntan hacia abajo:

```
presentation  (PySide6)          → solo habla con application (y usa domain)
application   (servicios)        → engines, data
engines       (cálculo puro)     → domain        · sin Qt, sin base de datos
data          (SQLite, PDF)      → domain
domain        (dataclasses)      ← compartido por todas las capas
```

`tests/architecture/test_architecture.py` verifica estas reglas y además que:

- ningún módulo use la red;
- toda la aleatoriedad use `numpy.random.Generator` (prohibido `random` y `np.random.seed`).

```
rutasegura/
  domain/        dataclasses y enums
  engines/       vision, navigation, simulation, norms, calibration
  application/   servicios y orquestador
  data/          ORM, repositorios, trayectorias, PDF
  presentation/  ventanas y widgets
  resources/     textos de UI, reglas normativas (YAML), íconos
tests/           unit, integration, architecture, benchmarks, fixtures
docs/            CHANGELOG, decisiones (ADR)
```

## Documentación

- [docs/CHANGELOG.md](docs/CHANGELOG.md): cambios por hito.
- [docs/decisiones.md](docs/decisiones.md): decisiones de diseño (ADR).
- [docs/perfiles.md](docs/perfiles.md): perfiles de personas por defecto y sus fuentes.
- [docs/formato_etiquetas.md](docs/formato_etiquetas.md): cómo etiquetar planos reales para evaluar la visión.
- [docs/parametros_simulacion.md](docs/parametros_simulacion.md): parámetros del modelo de movimiento (provisionales).
- [docs/rendimiento.md](docs/rendimiento.md): benchmarks del motor y del render.
- [docs/normas.md](docs/normas.md): reglas normativas, su estado de verificación y cómo corregirlas.
- [docs/calibracion.md](docs/calibracion.md): escenarios «qué pasa si», comparador y calibración con un simulacro real.
- [docs/manual_usuario.md](docs/manual_usuario.md): manual de usuario paso a paso.
- [CLAUDE.md](CLAUDE.md): especificación completa del proyecto.

## Base de datos

- La base de datos es SQLite local, en `%LOCALAPPDATA%\RutaSegura\rutasegura.db`.
- Al abrirse, aplica sola las migraciones pendientes.
- Las trayectorias de las simulaciones se guardan en archivos binarios aparte, no en SQLite.

Para crear una migración después de cambiar `rutasegura/data/models.py`:

```bash
uv run alembic revision --autogenerate -m "descripcion" --rev-id 0002
```

## Evaluar la detección de muros y puertas

La meta es ≥ 85 % de precisión y de exhaustividad.

```bash
uv run python scripts/eval_vision.py --synthetic 20
```

```bash
uv run python scripts/eval_vision.py --dataset planos_etiquetados --overlays control/
```

## Rendimiento

```bash
uv run pytest tests/benchmarks -s
```

## Empaquetado para Windows

```bash
uv run python scripts/build_windows.py
```

Genera `dist/RutaSegura/RutaSegura.exe`, verifica el ejecutable con `--self-test` y crea el zip
portable. Si Inno Setup 6 está instalado, también crea el instalador.

Para comprobar una instalación:

```bash
RutaSegura.exe --self-test --log autoprueba.txt
```
