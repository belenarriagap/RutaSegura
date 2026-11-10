# RutaSegura

Aplicación de escritorio, **100% offline**, que convierte el plano 2D de un local (colegio,
oficina, tienda) en un modelo del edificio, verifica aforo y anchos mínimos según la norma peruana
(RNE A.130), simula la evacuación ante un sismo y entrega un informe PDF.

> Este informe es de apoyo y no reemplaza la Inspección Técnica de Seguridad en Edificaciones
> (ITSE) ni el estudio de un profesional colegiado.

**Estado:** Hito 0 (base del proyecto). Ver [docs/CHANGELOG.md](docs/CHANGELOG.md).

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
- [CLAUDE.md](CLAUDE.md): especificación completa del proyecto.
