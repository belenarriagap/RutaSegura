# Registro de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [Sin publicar]

### Hito 6: entrega (2026-11-10)

#### Agregado
- **Empaquetado para Windows (RNF05)** con PyInstaller en modo carpeta (`packaging/rutasegura.spec`):
  - incluye las reglas YAML, los perfiles, las migraciones de Alembic, el ícono y las fuentes de
    Matplotlib;
  - la instalación ocupa unos 373 MB y el zip portable unos 176 MB.
- **`scripts/build_windows.py`:** construye el paquete, ejecuta la **autoprueba del `.exe`**, crea el
  zip portable y, si Inno Setup 6 está instalado, el instalador.
- **Instalador de Inno Setup** (`packaging/rutasegura.iss`):
  - en español, se instala por usuario y sin permisos de administrador;
  - crea accesos directos en Inicio y, opcionalmente, en el escritorio;
  - conserva los proyectos al desinstalar.
- **Flujo de CI «Paquete Windows»** (manual o al publicar una etiqueta `v*`): construye, autoprueba
  y publica el zip y el instalador como artefactos.
- **`rutasegura --self-test [--log ARCHIVO]`:** comprueba sin red las reglas, los perfiles, la base
  de datos con sus migraciones, OpenCV, la simulación y el informe PDF. También se agrega
  `rutasegura --version`.
- **Ícono de la aplicación** (señal de salida), generado con `scripts/make_icon.py`.
- **Manual de usuario** en `docs/manual_usuario.md`, con 10 capturas generadas por
  `scripts/capture_screenshots.py`.

- **Varios pisos (RF12),** hasta 4:
  - **Motor** `engines/simulation/multifloor.py`:
    - un campo de distancia y un `Simulation` por piso, con índices de agente compartidos;
    - en los pisos altos, las escaleras son objetivos;
    - al bajar hay una cola con capacidad (flujo específico × ancho) y un tiempo de bajada con
      velocidad reducida;
    - la persona aparece en la escalera emparejada del piso de abajo.
  - **Escaleras:** se emparejan por nombre (o con la única escalera del piso de abajo) y se nombran
    solas («Escalera A», «Escalera B»…).
  - **Interfaz:**
    - barra «Piso» para cambiar, agregar y eliminar pisos;
    - los pasos 1 a 5 trabajan sobre el piso elegido;
    - la simulación, el comparador y el visor muestran el edificio completo, con un selector de
      piso.
  - **Normas del edificio:** las salidas del piso 1 deben dar paso a todas las personas del
    edificio, y las observaciones indican el piso.
  - **Informe:** un mapa de calor por piso, y los cuellos de botella indican su piso.
  - **Archivo de corrida:** el `.npz` pasa a la versión 2, con el piso de cada persona y un mapa
    por piso. Los archivos de la versión 1 se siguen leyendo.
- **Parámetros provisionales nuevos:** recorrido de escalera por piso, factor de velocidad al
  bajar y flujo específico de la escalera.

### Hito 5: escenarios y calibración (2026-11-10)

#### Agregado
- **Escenarios «qué pasa si» (RF10):**
  - variantes del escenario base con un porcentaje de ocupación y salidas bloqueadas;
  - se pueden renombrar y eliminar;
  - cada escenario guarda su semilla y su última simulación;
  - el paso 6 tiene un selector de escenario.
- **Comparador:** dos escenarios lado a lado, con animación y mapa de calor, un botón «Reproducir
  ambos» y una tabla con la diferencia B − A de estos indicadores:
  - personas y salidas bloqueadas;
  - tiempo total y tiempo para evacuar al 50 % y al 90 %;
  - evacuados;
  - cuellos de botella;
  - tiempo por salida.
- **Informe PDF:** agrega la comparación de escenarios cuando hay dos o más simulados.
- **Calibración (RF11),** en el menú «Herramientas»:
  - se registra el simulacro real, con fecha, participantes, tiempo total y tiempos por salida;
  - búsqueda en rejilla de los factores de reacción y velocidad (36 combinaciones), que minimiza
    el RMSE de los errores relativos;
  - muestra el error antes y después, con la meta de quedar por debajo de 20 %;
  - un botón aplica los factores a los perfiles;
  - corre en segundo plano y se puede cancelar.
- **Motor `engines/calibration/grid_search.py`:** es puro, recibe la función de evaluación como
  parámetro y tiene 100 % de cobertura.
- **`SimulationResult.time_to_evacuate(fracción)`:** devuelve el tiempo para evacuar a una fracción
  de las personas, calculado con la curva de evacuados.
- **Guía de uso:** `docs/calibracion.md`.

#### Cambiado
- `SimulationService` separa la simulación sin guardar (`simulate`) del guardado (`run`). También
  agrega `list_scenarios`, `save_variant`, `delete_scenario` y `last_run` por escenario.
- Nuevo método `ScenarioRepository.rename`.
- Nuevo menú «Herramientas».

### Hito 4: normas e informe (2026-11-10)

#### Agregado
- **Motor de reglas guiado por datos** (`engines/norms`): las reglas viven en
  `resources/norms/*.yaml`, con validación de formato y mensajes claros. Tipos de regla:
  - índice de ocupación por uso y categoría;
  - ancho por persona de puertas y salidas;
  - anchos mínimos de puertas, salidas y pasillos;
  - aviso de barra antipánico.
- **Todas las reglas quedan sin verificar** (`verificado: false` y `# VERIFICAR con texto oficial
  RNE`). La lista y la forma de verificarlas están en `docs/normas.md`.
- **Verificación normativa (RF06):**
  - aforo por ambiente;
  - ancho total de las puertas de cada ambiente;
  - ancho total de las salidas del local;
  - anchos mínimos;
  - ancho estimado de los pasillos;
  - barra antipánico.

  Cada observación cita norma y artículo y dice si la regla está verificada.
- **10 casos de prueba de aforo** en `tests/unit/norms/casos_aforo.yaml`. Los resultados esperados
  son provisionales (`confirmado: false`).
- **Informe PDF (RF09)** con ReportLab y Matplotlib, que incluye:
  - portada;
  - resumen con el tiempo total;
  - advertencia cuando hay reglas no verificadas;
  - tabla de aforo y observaciones normativas;
  - mapa de calor con los cuellos de botella numerados;
  - curva de evacuados;
  - tiempo por salida;
  - ranking de cuellos de botella;
  - parámetros, perfiles y semilla;
  - reglas usadas;
  - aclaración legal en la portada, al final y al pie de cada página.

  La fuente DejaVu Sans va incrustada desde la instalación local de Matplotlib.
- **Paso 5, revisar norma:**
  - tabla de aforo con la categoría de cada ambiente editable;
  - ambientes que exceden el aforo resaltados;
  - aviso de reglas no verificadas y lista de observaciones.
- **Paso 7, informe:** genera el PDF en segundo plano y tiene un botón para abrirlo.
- **Observaciones guardadas:** las observaciones normativas se guardan con cada simulación en la
  tabla `observacion`.

#### Cambiado
- `Room` tiene el nuevo campo `category`. La migración 0002 agrega la columna `ambiente.categoria`.
- Los 7 pasos del asistente están activos.
- Nueva dependencia de desarrollo: `types-reportlab`, que solo se usa para revisar tipos.

#### Corregido
- La detección de vanos subestimaba el ancho en unos 4 cm. Ahora el sesgo medio es de −0.4 cm en
  20 planos sintéticos, y una prueba lo vigila.
- El script de evaluación de visión fallaba al redirigir su salida en la consola de Windows.

### Hito 3: navegación y simulación (2026-11-10)

#### Agregado
- **Grilla de navegación de 0.4 m** (`engines/navigation/grid.py`):
  - los muros cortan la diagonal;
  - las salidas bloqueadas o sin confirmar se sellan;
  - las zonas seguras interiores son destinos de evacuación;
  - lo conectado con el borde se marca como exterior.
- **Campo de distancia:** Dijkstra multiorigen con 8 vecinos, costo √2 en diagonal y sin cortar
  esquinas.
- **Campo de direcciones suavizado.**
- **Distancia a muros con su gradiente.**
- **A\*** para agentes con destino propio.
- **Detección automática de ambientes:** espacios cerrados por muros, puertas y salidas.
- **Motor de agentes** (`engines/simulation/`):
  - el estado se guarda en arrays NumPy;
  - fuerza social simplificada, con vecinos buscados por hash espacial vectorizado;
  - velocidad según densidad, tiempo de reacción lognormal y corrección de superposición;
  - el paso de tiempo es fijo, el progreso se informa y se puede cancelar.
- **Métricas:**
  - tiempo total y tiempo por salida;
  - curva de evacuados;
  - mapa de calor;
  - ranking de cuellos de botella (densidad alta sostenida de personas en movimiento).
- **Reproducibilidad (RNF07):** una prueba exige resultados idénticos bit a bit con la misma
  semilla.
- **Benchmarks** con 100, 300, 500 y 1000 agentes. Con 500 agentes, el motor da unos 470 pasos/s
  (la meta es 20) y el render unos 270 cuadros/s. Detalle en `docs/rendimiento.md`.
- **Trayectorias y arrays de resultado** en un `.npz` comprimido (`data/trajectories.py`). SQLite
  guarda el resumen y las observaciones de congestión.
- **`SimulationService`:**
  - escenario base con semilla;
  - validaciones con mensajes claros;
  - ejecución, guardado y recuperación de la última corrida;
  - cada cuello de botella se describe en palabras (por ejemplo, «junto a "Salida 1" de "Aula 2"»).
- **Paso 4, ambientes y ocupantes (RF05):**
  - detección automática de ambientes;
  - dibujo de polígonos (clic por vértice y doble clic para cerrar);
  - tabla con nombre, uso, área y personas por perfil, con el total.
- **Paso 6, simular (RF07, RF08):**
  - la simulación corre en segundo plano, con barra de progreso y botón cancelar;
  - la semilla es editable;
  - visor con reproducir y pausar, velocidad de 0.5× a 8×, línea de tiempo y mapa de calor;
  - panel con los resultados y los cuellos de botella.
- **Documentación:** `docs/parametros_simulacion.md`, con los parámetros provisionales y sus
  fuentes.

#### Cambiado
- `CellType` tiene los nuevos valores `SAFE_ZONE` y `OUTSIDE`.
- `SimulationResult` agrega campos nuevos:
  - totales de agentes;
  - si la evacuación terminó;
  - origen y tamaño de celda del mapa de calor.
- Nueva dataclass `Trajectories` en el dominio.

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
