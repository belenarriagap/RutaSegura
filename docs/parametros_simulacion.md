# Parámetros del modelo de simulación

> **Todos los valores marcados como PROVISIONAL deben verificarse con la fuente original y
> calibrarse con un simulacro real (RF11, Hito 5).** El tiempo de reacción (premovimiento) de
> cada perfil es el parámetro que más influye; está en `docs/perfiles.md`.

Los valores están definidos en `rutasegura/engines/simulation/params.py` (`SimulationParams`).

## Numéricos

| Parámetro | Valor | Comentario |
|---|---|---|
| Paso de tiempo | 0.1 s | Fijo (CLAUDE.md §5.3). |
| Tiempo máximo | 1800 s | Si se alcanza, el resultado queda marcado como «incompleto». |
| Registro de trayectorias | cada 0.5 s | El visor interpola entre cuadros. |
| Grilla de navegación | 0.4 m | CLAUDE.md §5.2. |

## Comportamiento

| Parámetro | Valor | Estado | Fuente o comentario |
|---|---|---|---|
| Tiempo de relajación τ | 0.5 s | PROVISIONAL | Orden de magnitud habitual en modelos de fuerza social (Helbing et al., 2000). |
| Densidad máxima ρ_max | 5.4 p/m² | PROVISIONAL | Densidad de detención del diagrama fundamental de Weidmann (1993). Verificar. |
| Factor mínimo de velocidad | 0.1 | PROVISIONAL | Evita bloqueos totales (CLAUDE.md §5.3). |
| Variación individual de la velocidad | ±10 % (1 σ) | PROVISIONAL | Normal truncada entre 0.7 y 1.3 veces la velocidad del perfil. |
| Repulsión entre personas A, B | 2.0 m/s², 0.3 m | PROVISIONAL | Más suave que en Helbing et al. (2000), que usan A/m ≈ 25 m/s² y B = 0.08 m. Con paso de 0.1 s y Euler explícito, esos valores son inestables. Calibrar. |
| Radio de interacción | 1.2 m | — | Por encima de este radio, la repulsión es despreciable. |
| Repulsión de muros A_w, B_w | 5.0 m/s², 0.2 m | PROVISIONAL | Mismo criterio que la repulsión entre personas. |

### Velocidad según la densidad

`v = v_max · max(0.1, 1 − ρ/ρ_max)`

- La densidad ρ se calcula con **todas las personas presentes** (también las que esperan), contando
  las personas en una ventana de 3 × 3 celdas (1.44 m²).

## Escaleras (varios pisos)

| Parámetro | Valor | Estado | Comentario |
|---|---|---|---|
| Recorrido por piso | 8 m | PROVISIONAL | Dos tramos y un descanso. Depende del edificio; medir si es posible. |
| Factor de velocidad al bajar | 0.5 | PROVISIONAL | Respecto de la velocidad horizontal de cada perfil. Contrastar con la literatura de evacuación en escaleras. |
| Flujo específico | 1.1 personas/(s·m) | PROVISIONAL | Orden de magnitud del SFPE Handbook para escaleras. Verificar. |

- **Cola de entrada:** se pasa una persona cada 1 / (flujo × ancho) segundos. El ancho es el lado
  corto del rectángulo que contiene a la escalera dibujada.
- **Tiempo de bajada:** recorrido / (velocidad máxima × factor).

## Cuellos de botella y mapa de calor

| Parámetro | Valor | Estado | Comentario |
|---|---|---|---|
| Umbral de congestión | 2.0 p/m² | PROVISIONAL | Contrastar con los niveles de servicio peatonal (Fruin) o con la guía que se adopte. |
| Duración mínima | 5 s | PROVISIONAL | Densidad alta sostenida (CLAUDE.md §5.3). |

- **Quiénes cuentan:** para el mapa de calor y los cuellos de botella solo se cuentan las personas
  **en movimiento**. Un aula llena mientras sus ocupantes reaccionan no es un cuello de botella;
  la aglomeración al circular sí lo es (ver ADR-017).
- **Severidad:** duración × densidad media (personas·s/m²). Los cuellos de botella se ordenan de
  mayor a menor severidad.

## Referencias

- Helbing, D., Farkas, I. y Vicsek, T. (2000). Simulating dynamical features of escape panic.
  *Nature*, 407, 487–490.
- Weidmann, U. (1993). *Transporttechnik der Fussgänger*. IVT, ETH Zürich.
- Fruin, J. J. (1971). *Pedestrian Planning and Design*. Metropolitan Association of Urban
  Designers and Environmental Planners.
