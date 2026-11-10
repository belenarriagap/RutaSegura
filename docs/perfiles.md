# Perfiles de personas por defecto

> **Todos los valores son PROVISIONALES.** Hay que contrastarlos con la fuente original y
> calibrarlos con un simulacro real (RF11) antes de usarlos en un informe definitivo.

Los valores viven en
[`rutasegura/resources/profiles/perfiles_por_defecto.yaml`](../rutasegura/resources/profiles/perfiles_por_defecto.yaml).
Al abrir la base de datos, la aplicación agrega los perfiles que falten. Si el usuario ya editó un
perfil, sus cambios se respetan.

| Perfil | vel. máx. (m/s) | reacción media (s) | desv. reacción (s) | radio (m) |
|---|---|---|---|---|
| adulto | 1.34 | 30 | 10 | 0.25 |
| niño | 1.0 | 20 | 10 | 0.20 |
| movilidad reducida | 0.8 | 45 | 15 | 0.35 |

## Fuentes y estado de cada valor

| Perfil | Valor | Fuente | Estado |
|---|---|---|---|
| adulto | Velocidad | Weidmann (1993): velocidad media de marcha libre. | Verificar en la fuente original. |
| adulto | Reacción | Sin fuente directa. Orden de magnitud orientativo; la referencia a consultar es BSI PD 7974-6. | Provisional. |
| adulto | Radio | Helbing, Farkas y Vicsek (2000) usan radios entre 0.25 y 0.35 m. | Verificar. |
| niño | Velocidad | Sin fuente directa. Literatura sugerida: Larusdottir y Dederichs (2012). | Provisional. Depende mucho de la edad (inicial, primaria o secundaria). |
| niño | Reacción | Sin fuente directa. En colegios suele depender de la orden del docente. | Provisional. |
| niño | Radio | Sin fuente directa. | Provisional. |
| movilidad reducida | Velocidad | Sin fuente directa. Literatura sugerida: Boyce, Shields y Silcock (1999). | Provisional. |
| movilidad reducida | Reacción | Sin fuente directa. | Provisional. |
| movilidad reducida | Radio | Considera el ancho de una silla de ruedas (alrededor de 0.7 m). | Provisional. |

## Referencias

- Weidmann, U. (1993). *Transporttechnik der Fussgänger*. Schriftenreihe des IVT Nr. 90,
  ETH Zürich.
- Helbing, D., Farkas, I. y Vicsek, T. (2000). Simulating dynamical features of escape panic.
  *Nature*, 407, 487–490.
- Larusdottir, A. R. y Dederichs, A. S. (2012). Evacuation of children: movement on stairs and on
  horizontal plane. *Fire Technology*, 48.
- Boyce, K. E., Shields, T. J. y Silcock, G. W. H. (1999). Toward the characterization of
  building occupancies for fire safety engineering: capabilities of disabled people moving
  horizontally and on an incline. *Fire Technology*, 35(1).
- BSI PD 7974-6 (2019). *The application of fire safety engineering principles to fire safety
  design of buildings — Part 6: Human factors*.

## Cómo marcar un valor como verificado

1. Corregir el valor y la cita en el YAML.
2. Cuando los cuatro valores de un perfil estén verificados, cambiar `provisional: true` por
   `provisional: false`.
3. Ajustar `test_values_are_marked_provisional_until_verified` en
   `tests/unit/data/test_default_profiles.py`.
