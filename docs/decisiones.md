# Registro de decisiones (ADR)

Formato corto: contexto, decisión, alternativas, consecuencias.

---

## ADR-001: prueba de arquitectura propia en lugar de import-linter

- **Fecha:** 2026-11-10 · **Estado:** aceptada
- **Contexto:** hay que impedir que se rompan las reglas de capas, de red y de aleatoriedad
  (CLAUDE.md §3).
- **Decisión:** un verificador basado en `ast` (`tests/architecture/import_rules.py`) que corre
  como prueba de pytest. Además de las capas, revisa:
  - los imports externos prohibidos por capa;
  - los módulos de red;
  - el uso de `random` y de la API global `np.random.*`.

  Incluye pruebas que confirman que detecta cada tipo de violación.
- **Alternativa:** `import-linter`. Cubre bien los contratos de capas, pero no revisa
  `np.random.seed` y sería una dependencia más.
- **Consecuencias:**
  - Las reglas se mantienen en un solo archivo.
  - Los imports dinámicos (`importlib`) no se detectan.
  - Ruff también bloquea `random` (TID251) y la API global de NumPy (NPY002), como segunda barrera.

## ADR-002: uv con `uv.lock` para fijar dependencias

- **Fecha:** 2026-11-10 · **Estado:** aceptada
- **Decisión:**
  - `pyproject.toml` declara cotas mínimas.
  - `uv.lock` fija las versiones exactas de todo el árbol de dependencias.
  - CI instala con `uv sync --locked`, que falla si el lock no coincide con el `pyproject.toml`.
- **Alternativa:** pip con `requirements.txt` fijado con `pip-tools`. Necesita más pasos.
- **Consecuencias:** basta `uv sync` para reproducir el entorno. uv también instala Python 3.12.

## ADR-003: PySide6-Essentials en lugar del paquete PySide6 completo

- **Fecha:** 2026-11-10 · **Estado:** aceptada
- **Contexto:** el paquete `PySide6` arrastra `Addons` y `WebEngine`: varios cientos de MB, que
  incluyen módulos de red y un navegador.
- **Decisión:** depender solo de `PySide6-Essentials`. Incluye QtWidgets, QtGui y QtCore, con
  `QGraphicsView`, `QUndoStack` y `QThread`.
- **Consecuencias:** el instalador PyInstaller sale más liviano. Si más adelante se necesita
  algo de Addons (por ejemplo QtCharts), se agrega con una justificación. Los gráficos del
  informe usan Matplotlib.

## ADR-004: reglas de capas más estrictas que el diagrama

- **Fecha:** 2026-11-10 · **Estado:** aceptada (se puede revisar)
- **Contexto:** el diagrama de CLAUDE.md pone `data` debajo de `engines`. Por otro lado, dice que
  `engines` no toca la base de datos.
- **Decisión:**
  - `engines` y `data` son capas hermanas: ninguna importa a la otra, y ambas dependen solo de
    `domain`. Quien las combina es `application`.
  - `application` tampoco importa Qt, para poder probar los servicios sin interfaz. El hilo de
    trabajo (`QThread`) vive en `presentation` y llama a `application`.
  - `rutasegura/__main__.py` es la raíz de composición y puede ensamblar todas las capas.
- **Consecuencias:** los motores se prueban aislados. Si algún motor necesita leer archivos de
  reglas YAML, los lee de `resources` o los recibe como datos.

## ADR-005: geometría en píxeles más escala

- **Fecha:** 2026-11-10 · **Estado:** aceptada
- **Decisión:** los elementos del plano guardan su geometría en coordenadas de la imagen. La
  conversión a metros pasa por `FloorPlan.scale_m_per_px`, que se define en RF04.
- **Alternativa:** convertir todo a metros al fijar la escala. Si el usuario corrige la escala,
  habría que recalcular toda la geometría.
- **Consecuencias:**
  - El editor trabaja directamente sobre la imagen.
  - Los motores de navegación y simulación convierten a metros al construir la grilla.

## ADR-006: dataclasses inmutables en el dominio

- **Fecha:** 2026-11-10 · **Estado:** aceptada
- **Decisión:**
  - Las estructuras del plano, los escenarios y los resultados son `frozen=True`. El editor genera
    versiones nuevas con `dataclasses.replace`, lo que facilita el deshacer/rehacer.
  - La excepción es `AgentArrays`: es mutable para que la simulación vectorizada actualice los
    arrays en el lugar.
