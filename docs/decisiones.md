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

## ADR-007: esquema SQLite en español y atributos en inglés

- **Fecha:** 2026-11-10 · **Estado:** aceptada
- **Contexto:** la §6 define las tablas y columnas en español (`proyecto.nombre`,
  `piso.escala_m_por_px`...). La convención del código es usar inglés.
- **Decisión:**
  - Las tablas y columnas replican la §6, para que el modelo de datos de la tesis coincida con la
    base real.
  - Las clases ORM y sus atributos van en inglés (`ProjectRecord.name` se mapea a la columna
    `nombre`).
- **Columnas agregadas a la §6:**
  - `simulacion.semilla`: el informe debe mostrar la semilla aunque luego se edite el escenario.
  - `observacion.descripcion` y `observacion.norma`.
  - `observacion.verificado`: el informe debe advertir cuando usó una regla no verificada.
- **Alternativa:** todo en inglés. Es más uniforme, pero se aleja del documento de la tesis.

## ADR-008: referencias por nombre entre escenarios y plano

- **Fecha:** 2026-11-10 · **Estado:** aceptada
- **Decisión:**
  - Las ocupaciones identifican el ambiente por (nivel, nombre) y el perfil por su nombre.
  - Las salidas bloqueadas se guardan como lista de nombres de salida.
  - Al guardar un piso, los elementos se reemplazan completos y los ambientes se sincronizan por
    nombre. Así un escenario no pierde sus ocupaciones cuando se corrige un muro.
- **Consecuencias:**
  - Los nombres de ambiente son únicos en cada piso; la base lo exige con una restricción.
  - Renombrar o eliminar un ambiente elimina sus ocupaciones.
  - Las salidas deben tener nombre para poder bloquearlas. El editor (Hito 2) las nombrará solo,
    como «Salida 1», «Salida 2», etc.
- **Alternativa:** ids estables (UUID) en el dominio. Son más robustos frente a renombres, pero
  agregan complejidad que hoy no hace falta.

## ADR-009: cifrado opcional detrás de una fábrica de motores

- **Fecha:** 2026-11-10 · **Estado:** aceptada (implementación del cifrado pendiente)
- **Decisión:** `Database.open(path, engine_factory=...)` recibe un `EngineFactory`. Hoy se usa
  `plain_sqlite_engine`. Para cifrar bastará una fábrica que cree el motor con SQLCipher (por
  ejemplo, `sqlcipher3` mediante `creator=`) y ejecute `PRAGMA key`. No hay que tocar los
  repositorios.
- **Pendiente:** elegir el paquete de SQLCipher para Windows y decidir cómo pedir y guardar la
  clave. Esto se haría en el Hito 6, si se prioriza.

## ADR-010: perfiles por defecto en YAML con fuentes

- **Fecha:** 2026-11-10 · **Estado:** aceptada
- **Decisión:**
  - El catálogo inicial vive en `resources/profiles/perfiles_por_defecto.yaml`, con la fuente de
    cada valor y la marca `provisional`. El cargador rechaza perfiles a los que les falte la
    fuente de algún valor.
  - Al abrir la base se agregan los perfiles que falten, sin sobrescribir los que el usuario haya
    editado.
- **Consecuencias:** los valores se corrigen sin tocar código. El informe (Hito 4) podrá advertir
  cuando se usen perfiles provisionales.

## ADR-011: muros por esqueleto + Hough y puertas por tramos vacíos

- **Fecha:** 2026-11-10 · **Estado:** aceptada
- **Decisión:**
  - **Máscara de muros:** se aplica una apertura morfológica con un núcleo de 0.6 × el grosor
    estimado. Así desaparecen el texto, las cotas, los arcos y el mobiliario de trazo fino.
  - **Ejes:** se calcula el esqueleto con Zhang-Suen (implementado en NumPy, sin opencv-contrib) y
    se aplica HoughLinesP.
  - **Agrupación:** los segmentos se agrupan por recta y luego cada recta se reajusta por mínimos
    cuadrados totales.
  - **Vanos:** a lo largo de cada recta, el tramo más largo sin muro en la máscara. Esto da el ancho
    real del vano, que RF06 necesita.
  - **Salidas:** son los vanos que están sobre el contorno exterior del edificio.
- **Alternativas descartadas:**
  - Hough sobre la máscara rellena: da muchas paralelas por cada muro.
  - Segmentación con YOLO u otra red: queda como extra opcional según la especificación.
  - Detectar el arco como condición obligatoria: muchos planos no dibujan arcos. El arco solo sube
    la confianza.
- **Limitaciones conocidas:**
  - Muros curvos.
  - Planos con relleno de trama (hatching).
  - Muros más delgados que el texto en negrita.
  - Las escaleras no se detectan; se marcan a mano.

## ADR-012: salidas propuestas y confirmación explícita

- **Fecha:** 2026-11-10 · **Estado:** aceptada
- **Contexto:** la §5.1 pide que el sistema proponga las salidas y que el usuario las confirme.
- **Decisión:**
  - `Exit.confirmed` y `Stair.confirmed`: lo detectado entra con `False` y lo dibujado a mano, con
    `True`.
  - El editor muestra las propuestas en línea discontinua, con «?» y un aviso.
  - La simulación (Hito 3) usará solo las salidas confirmadas.

## ADR-013: guardado automático en lugar de preguntar

- **Fecha:** 2026-11-10 · **Estado:** aceptada
- **Decisión:** el plano se guarda solo al cambiar de paso, al abrir o crear otro proyecto y al
  cerrar la aplicación. También se puede guardar con Ctrl+S.
- **Motivo:** los usuarios no son técnicos (RNF03). El diálogo «¿Guardar cambios?» es una fuente
  frecuente de pérdida de trabajo, y el deshacer ya protege contra errores de edición.
- **Consecuencia:** cargar un plano nuevo reemplaza el anterior apenas se cambia de paso.

## ADR-014: el editor reemplaza el plano completo en cada comando

- **Fecha:** 2026-11-10 · **Estado:** aceptada
- **Decisión:** cada edición crea un `FloorPlan` nuevo (el dominio es inmutable) y el
  `QUndoCommand` guarda el plano anterior y el nuevo. La escena se vuelve a dibujar completa.
- **Alternativa:** un comando por tipo de operación con cambios mínimos en la escena. Es más
  eficiente en planos enormes, pero tiene más código y más riesgo de que la escena y el modelo se
  desincronicen.
- **Consecuencia:** basta para planos de cientos de elementos. Si un plano muy grande se pone
  lento, se optimiza el redibujado.
