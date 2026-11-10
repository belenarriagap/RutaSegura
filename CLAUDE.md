# RutaSegura — Instrucciones para Claude Code

Eres el desarrollador principal de **RutaSegura**, un proyecto de tesis/curso de Ingeniería de Sistemas (Perú). Este archivo es la especificación del proyecto: léelo completo antes de cada tarea y respétalo. Si algo aquí entra en conflicto con lo que te pida en el chat, pregúntame antes de actuar.

## 1. Qué es el producto

Aplicación de **escritorio, 100% offline**, que:

1. Recibe una foto o PDF del plano 2D de un local (colegio, oficina, tienda).
2. Reconstruye el edificio (muros, puertas, salidas, escaleras) con visión por computadora + un editor de corrección manual.
3. Calcula el aforo y verifica anchos mínimos según la norma peruana (RNE A.130 y normas de uso relacionadas), citando el artículo en cada observación.
4. Simula con agentes la evacuación ante un sismo.
5. Entrega un informe PDF con tiempo estimado de evacuación, mapa de calor de congestión, ranking de cuellos de botella y recomendaciones.

Usuarios: directores de colegio, brigadistas, dueños de negocios pequeños. **No son técnicos**: la interfaz va en español, con lenguaje simple y flujos guiados.

Fuera de alcance (no implementar): importación DWG/BIM, fuego y humo, ascensores, edificios de más de 4 pisos, evacuación urbana, versión móvil.

## 2. Stack obligatorio

| Área | Tecnología |
|---|---|
| Lenguaje | Python 3.12 |
| Interfaz | PySide6 (Qt), `QGraphicsView` para el editor y el visor |
| Visión | OpenCV (`opencv-python-headless` en el núcleo); YOLO + ONNX Runtime solo como extra opcional |
| PDF de entrada | PyMuPDF (rasterizar páginas) |
| Simulación | NumPy (vectorizado); Numba solo si el benchmark lo exige |
| Datos | SQLite + SQLAlchemy 2.x (ORM tipado) + Alembic para migraciones |
| Informes | ReportLab + Matplotlib (backend `Agg`) |
| Calidad | pytest, pytest-cov, pytest-qt, pytest-socket, ruff, mypy |
| CI | GitHub Actions (lint + tipos + pruebas en Windows y Ubuntu) |
| Distribución | PyInstaller (un instalador para Windows 10/11) |
| Gestión | `pyproject.toml` (uv o pip), dependencias fijadas |

## 3. Reglas de arquitectura (no negociables)

Arquitectura en 4 capas. Las dependencias solo apuntan hacia abajo:

```
presentation  (PySide6: editor, visor de simulación, comparador)
     ↓
application   (servicios: gestor de proyectos, orquestador)
     ↓
engines       (vision, navigation, simulation, norms, calibration)
     ↓
data          (repositorios SQLite, archivos binarios de trayectorias, generador PDF)
```

- `presentation` **nunca** importa `engines` ni `data` directamente: solo habla con `application`.
- `engines` **no importa Qt** ni toca la base de datos. Son funciones/clases puras que reciben y devuelven estructuras de dominio (dataclasses) y arrays NumPy. Así se prueban sin interfaz.
- Las estructuras compartidas (Plano, Muro, Puerta, Ambiente, Agente, ResultadoSimulación, Observación…) viven en `rutasegura/domain/`.
- Agrega una prueba de arquitectura (por ejemplo con `import-linter` o un test que inspeccione imports) que falle si alguien rompe estas reglas.
- **Cero red**: ningún módulo hace llamadas a internet. Las pruebas corren con `pytest-socket` (`--disable-socket`). Nada de telemetría, fuentes web, CDNs ni descargas de modelos en tiempo de ejecución.
- Simulaciones totalmente reproducibles: toda aleatoriedad usa `numpy.random.Generator` creado a partir de la semilla del escenario. Prohibido `random` global o `np.random.seed`.

Estructura de carpetas sugerida:

```
rutasegura/
  domain/          # dataclasses y enums del dominio
  engines/
    vision/        # preprocesamiento, muros, puertas, rectificación
    navigation/    # grilla, campo de distancia, A*
    simulation/    # agentes, modelo de movimiento, métricas
    norms/         # motor de reglas + archivos de reglas
    calibration/   # ajuste de parámetros
  application/     # servicios y orquestador
  data/            # modelos ORM, repositorios, trayectorias, pdf
  presentation/    # ventanas, widgets, editor, visor
  resources/       # íconos, reglas normativas (YAML), textos de UI
tests/
  unit/  integration/  architecture/  benchmarks/  fixtures/
docs/
```

Convenciones: nombres de código en inglés; textos de interfaz, informe, mensajes al usuario y documentación en español. Type hints en todo, `mypy --strict` en `domain` y `engines`. Docstrings breves.

## 4. Requisitos

### Funcionales (MoSCoW)

| ID | Requisito | Prioridad |
|---|---|---|
| RF01 | Importar plano desde JPG, PNG o PDF | Must |
| RF02 | Detectar automáticamente muros, puertas y salidas | Must |
| RF03 | Editor: dibujar/borrar muros, marcar puertas, salidas, escaleras, obstáculos y zonas seguras | Must |
| RF04 | Definir la escala con una medida conocida (el usuario marca dos puntos e ingresa metros) | Must |
| RF05 | Asignar ocupantes por ambiente con perfiles (adulto, niño, movilidad reducida) | Must |
| RF06 | Calcular aforo y verificar anchos mínimos (RNE A.130), citando el artículo | Must |
| RF07 | Ejecutar la simulación con animación, pausa y control de velocidad | Must |
| RF08 | Mapa de calor de densidad y ranking de cuellos de botella | Must |
| RF09 | Informe PDF con resultados, recomendaciones y aclaración legal | Must |
| RF10 | Escenarios “qué pasa si” (salida bloqueada, aforo distinto) y comparación lado a lado | Should |
| RF11 | Registrar tiempos de un simulacro real y calibrar el modelo | Should |
| RF12 | Varios pisos conectados por escaleras | Could |

### No funcionales

| ID | Criterio de aceptación |
|---|---|
| RNF01 Offline | Todo funciona con el adaptador de red desactivado; pruebas con `--disable-socket` |
| RNF02 Rendimiento | ≥ 20 pasos de simulación por segundo con 500 agentes en Core i5 / 8 GB (medir el motor sin render, y aparte el render) |
| RNF03 Usabilidad | Diseñar para SUS ≥ 70: asistente paso a paso, mensajes claros, deshacer/rehacer en el editor |
| RNF04 Privacidad | Los planos nunca salen del equipo; base de datos local (dejar preparado el cifrado opcional, p. ej. SQLCipher, detrás de una interfaz) |
| RNF05 Portabilidad | Instalador para Windows 10/11; Linux opcional |
| RNF06 Mantenibilidad | Cobertura ≥ 70% en `engines/simulation` (y apuntar a lo mismo en todo `engines`) |
| RNF07 Reproducibilidad | Misma semilla ⇒ mismo resultado bit a bit (test dedicado) |

## 5. Algoritmos

### 5.1 Visión (RF01, RF02)
1. Carga: imagen o PDF rasterizado (PyMuPDF, ~200 dpi).
2. Rectificación opcional de perspectiva para fotos torcidas: el usuario marca 4 esquinas → `cv2.getPerspectiveTransform`.
3. Preprocesamiento: escala de grises, umbral adaptativo, eliminación de ruido.
4. Muros: morfología (apertura/cierre) para conservar trazos gruesos; `HoughLinesP` para segmentos; fusión de segmentos colineales cercanos; salida en polígonos/segmentos.
5. Puertas: huecos en muros dentro de un rango de ancho plausible + detección de arcos de apertura. Cada detección lleva un puntaje de confianza.
6. Salidas y escaleras: las propone el sistema y **el usuario confirma en el editor**. La detección es asistida, nunca obligatoria.
7. Conversión a metros con la escala de RF04.

Para probar sin planos reales, crea un **generador de planos sintéticos** (`tests/fixtures/synthetic_plans.py`) que dibuje muros y puertas con ruido, rotación y desenfoque, y guarde la verdad de referencia. Implementa la métrica de precisión y exhaustividad (`scripts/eval_vision.py`) para el objetivo de ≥ 85% en 20 planos reales etiquetados (los aportaré yo).

### 5.2 Navegación
- Grilla de celdas de **0.4 m**. Celdas: libre, muro, obstáculo, puerta, salida, escalera.
- **Campo de distancia** a las salidas con Dijkstra multiorigen (8-vecindad, costo diagonal √2). Fast Marching como alternativa opcional. Recalcular al bloquear salidas (escenarios).
- **A\*** para agentes con destino propio (p. ej. docente que va por su grupo).
- Multipiso (RF12): un campo por piso; las escaleras son salidas del piso superior y entradas del inferior, con velocidad reducida.

### 5.3 Movimiento de agentes
- Estado de agentes en arrays NumPy (estructura de arrays, no lista de objetos): posición, velocidad, perfil, tiempo de reacción, estado (esperando, moviéndose, evacuado).
- Dirección deseada = gradiente del campo de distancia (interpolado).
- Fuerza social simplificada: atracción a la salida, repulsión de muros y de otros agentes. Para vecinos usa un hash espacial por celdas (nada de O(n²)).
- Velocidad dependiente de la densidad local:
  `v_i = v_max_i · (1 − ρ_local / ρ_max)`, con un mínimo para evitar bloqueos totales.
- Tiempo de premovimiento (reacción) por perfil, muestreado de una distribución (normal truncada o lognormal) con la semilla del escenario. Es el parámetro más influyente: debe ser fácil de calibrar.
- Paso de tiempo fijo (p. ej. 0.1 s). El motor no depende del render.
- Métricas: tiempo total, tiempo por salida, curva de evacuados vs. tiempo, densidad acumulada por celda (mapa de calor), cuellos de botella = zonas con densidad alta sostenida, ordenadas por severidad.
- Trayectorias por cuadro guardadas en binario aparte (`.npz` o similar), no en SQLite.

### 5.4 Normas (RF06)
- Motor de reglas **guiado por datos**: las reglas viven en `resources/norms/*.yaml` (índices de ocupación por uso, anchos mínimos, criterios de pasillos, barra antipánico para ambientes de más de 100 personas, etc.), cada una con: id, descripción, fórmula/umbral, norma, artículo, y un campo `verificado: true/false`.
- Aforo = área útil ÷ índice de ocupación del uso. Luego compara anchos de puertas y pasillos con los mínimos.
- Cada observación generada incluye la norma y el artículo citado y una recomendación en lenguaje simple.
- **Importante: no inventes valores normativos.** Si no estás seguro de un índice o ancho, déjalo como marcador con `verificado: false` y un comentario `# VERIFICAR con texto oficial RNE`. Yo los completaré con el texto oficial y la guía de cálculo de aforo de CENEPRED. El informe debe advertir si se usó alguna regla no verificada.
- Tipos de uso mínimos: educación, oficinas, comercio.
- 10 casos de prueba de aforo en `tests/unit/norms/` (los resultados esperados los proporcionaré; deja la estructura lista con casos de ejemplo).

### 5.5 Calibración (RF11)
- Entrada: un `SimulacroReal` (participantes, tiempo total, tiempos por salida).
- Ajustar tiempo de reacción medio y velocidad media para minimizar el error (RMSE o error relativo) con búsqueda en rejilla primero; algoritmo genético opcional.
- Reportar error antes y después. Meta de validación: error < 20% en el tiempo total.

## 6. Modelo de datos (SQLite)

Tablas: `Proyecto`, `Piso`, `Elemento`, `Ambiente`, `PerfilPersona`, `Escenario`, `Ocupacion`, `Simulacion`, `Observacion`, `SimulacroReal`.

- Proyecto (id, nombre, tipo_uso, direccion, fecha_creacion) → muchos Pisos y Escenarios
- Piso (id, proyecto_id, nivel, imagen_original, escala_m_por_px) → muchos Elementos y Ambientes
- Elemento (id, piso_id, tipo [muro, puerta, salida, escalera, obstaculo], geometria, ancho_m)
- Ambiente (id, piso_id, nombre, uso, poligono, area_m2) → muchas Ocupaciones
- PerfilPersona (id, nombre, vel_max_mps, reaccion_media_s, reaccion_desv_s, radio_m) — catálogo con valores por defecto para adulto, niño y movilidad reducida (documenta la fuente de cada valor)
- Escenario (id, proyecto_id, nombre, salidas_bloqueadas, semilla)
- Ocupacion (id, escenario_id, ambiente_id, perfil_id, cantidad)
- Simulacion (id, escenario_id, tiempo_total_s, tiempo_por_salida, ruta_trayectorias, fecha) → muchas Observaciones
- Observacion (id, simulacion_id, tipo [norma, congestion], articulo_rne, ubicacion, recomendacion)
- SimulacroReal (id, proyecto_id, fecha, participantes, tiempo_total_s, tiempos_por_salida)

Geometrías como GeoJSON/WKT en texto. Usa Alembic desde el primer día. Repositorios en `data/` para que `application` no escriba SQL.

## 7. Interfaz

Flujo guiado tipo asistente: **1. Cargar plano → 2. Escala → 3. Corregir plano → 4. Ambientes y ocupantes → 5. Revisar norma → 6. Simular → 7. Informe.**

- Editor con deshacer/rehacer (`QUndoStack`), zoom y desplazamiento, capas visibles.
- Visor de simulación: reproducir, pausa, velocidad 0.5×–8×, línea de tiempo, mapa de calor superpuesto.
- Comparador: dos escenarios lado a lado con sus métricas.
- Simulación en un hilo de trabajo (`QThread`/worker) para no congelar la interfaz; barra de progreso y botón cancelar.
- Todos los textos de la UI centralizados (preparado para traducción, pero solo español por ahora).

## 8. Informe PDF (RF09)
Portada con datos del local; resumen con tiempo total estimado; tabla de aforo y observaciones normativas con artículo; mapa de calor; curva de evacuados vs. tiempo; ranking de cuellos de botella con recomendaciones; comparación de escenarios si existe; parámetros y semilla usados; y esta aclaración legal: *“Este informe es de apoyo y no reemplaza la Inspección Técnica de Seguridad en Edificaciones (ITSE) ni el estudio de un profesional colegiado.”* Fuentes empaquetadas localmente (sin descargas).

## 9. Plan de trabajo por hitos

Trabaja **un hito a la vez**. Al terminar cada hito: pruebas en verde, `ruff` y `mypy` sin errores, actualiza `docs/CHANGELOG.md` y dame un resumen corto de lo hecho, lo pendiente y cualquier decisión que deba tomar yo. No empieces el siguiente hito sin mi confirmación.

- **Hito 0 — Base del proyecto:** `pyproject.toml`, estructura de carpetas, dominio (dataclasses), configuración de ruff/mypy/pytest (con `--disable-socket`), prueba de arquitectura, CI de GitHub Actions, README inicial, ventana PySide6 vacía que abre.
- **Hito 1 — Datos:** modelos SQLAlchemy, migración inicial con Alembic, repositorios, perfiles por defecto, pruebas.
- **Hito 2 — Visión y editor (RF01–RF04):** carga de imagen/PDF, rectificación, detección de muros y puertas, generador de planos sintéticos, script de evaluación, editor con deshacer, escala.
- **Hito 3 — Navegación y simulación (RF05, RF07, RF08):** grilla, campo de distancia, A*, motor de agentes, métricas, mapa de calor, visor. Benchmark con 100, 300, 500 y 1000 agentes (`tests/benchmarks/`). Test de reproducibilidad.
- **Hito 4 — Normas e informe (RF06, RF09):** motor de reglas YAML, casos de prueba, generación del PDF.
- **Hito 5 — Escenarios y calibración (RF10, RF11):** escenarios, comparador, registro de simulacro real, calibración.
- **Hito 6 — Multipiso y entrega (RF12, RNF05):** escaleras entre pisos (si hay tiempo; es lo primero que se recorta), instalador PyInstaller, manual de usuario en `docs/`.

## 10. Definición de terminado (para cualquier tarea)
- Código con tipos, sin errores de ruff ni mypy.
- Pruebas unitarias para la lógica nueva en `engines`; integración cuando cruce capas.
- Ninguna dependencia nueva sin justificarla; nada que requiera internet en tiempo de ejecución.
- Sin regresiones en el benchmark de rendimiento.
- Documentación actualizada si cambia el comportamiento visible.

## 11. Cómo trabajar conmigo
- Antes de un cambio grande, propón un plan breve y espera mi visto bueno.
- Si una decisión tiene varias opciones razonables (por ejemplo, Dijkstra vs. Fast Marching), elige la más simple, implémentala y anota la alternativa en `docs/decisiones.md` (formato ADR corto).
- Si no conoces un dato del dominio (norma, velocidad de niños, tiempos de reacción), no lo inventes: usa un valor razonable marcado como provisional, cita la fuente si la tienes y avísame.
- Commits pequeños y descriptivos en español (`feat:`, `fix:`, `test:`, `docs:`).
