# Reglas normativas (RF06)

> **Ninguna regla está verificada todavía.** Los valores y artículos de
> `rutasegura/resources/norms/*.yaml` son referencias que hay que confirmar con el texto oficial del
> RNE (A.130, A.040, A.070, A.080) y con la guía de cálculo de aforo de CENEPRED. Mientras una
> regla tenga `verificado: false`, la pantalla «Revisar norma» y el informe lo advierten.

## Archivos

| Archivo | Contenido |
|---|---|
| `indices_ocupacion.yaml` | Índice de ocupación (m² por persona) por uso y categoría de ambiente. |
| `medios_evacuacion.yaml` | Anchos por persona, anchos mínimos de puertas, salidas y pasillos, y barra antipánico. |

La aplicación lee todos los `.yaml` de esa carpeta. Si un archivo tiene un error de formato, la
aplicación lo informa con un mensaje que indica el archivo y la regla.

## Reglas cargadas y su estado

| Id | Qué verifica | Valor actual | Cita actual | Estado |
|---|---|---|---|---|
| OCU-EDU-AULA | Aforo de aulas | 1.5 m²/persona | RNE A.040, Art. 9 | VERIFICAR |
| OCU-EDU-TALLER | Aforo de talleres, laboratorios y bibliotecas | 5.0 m²/persona | RNE A.040, Art. 9 | VERIFICAR |
| OCU-EDU-SUM | Aforo de salas de uso múltiple | 1.0 m²/persona | RNE A.040, Art. 9 | VERIFICAR |
| OCU-EDU-ADMIN | Aforo de ambientes administrativos | 10.0 m²/persona | RNE A.040, Art. 9 | VERIFICAR |
| OCU-OFI-OFICINA | Aforo de oficinas | 9.5 m²/persona | RNE A.080, Art. 6 | VERIFICAR |
| OCU-COM-TIENDA | Aforo de áreas de venta | 2.8 m²/persona | RNE A.070, Art. 8 | VERIFICAR |
| OCU-*-PASILLO | Pasillos: sin aforo propio, se revisa su ancho | — | RNE A.130, Art. 22 | VERIFICAR |
| EVA-PUERTA-POR-PERSONA | Ancho total de puertas de un ambiente | 0.005 m/persona | RNE A.130, Art. 22 | VERIFICAR |
| EVA-SALIDA-POR-PERSONA | Ancho total de salidas del local | 0.005 m/persona | RNE A.130, Art. 22 | VERIFICAR |
| EVA-PUERTA-MINIMO | Ancho mínimo de puerta | 0.90 m | RNE A.130, Art. 5 | VERIFICAR |
| EVA-SALIDA-MINIMO | Ancho mínimo de salida | 1.00 m | RNE A.130, Art. 5 | VERIFICAR |
| EVA-PASILLO-MINIMO | Ancho mínimo de pasillo | 1.20 m | RNE A.130, Art. 22 | VERIFICAR |
| EVA-ANTIPANICO | Aviso de barra antipánico | más de 100 personas | RNE A.130, Art. 5 | VERIFICAR |

## Cómo se aplican

- **Aforo:** área del ambiente ÷ m² por persona de su categoría, redondeado hacia abajo. La
  categoría se elige en el paso 5. Si no se elige, se usa la categoría por defecto del uso.
- **Puertas de un ambiente:** son las puertas y salidas que están a menos de 0.6 m de su contorno.
  Su ancho total debe ser al menos ocupantes × metros por persona.
- **Salidas del local:** el ancho total de las salidas confirmadas debe ser al menos ocupantes
  totales × metros por persona.
- **Anchos mínimos:**
  - cada puerta y cada salida se compara con su mínimo;
  - el ancho de un pasillo (categoría «Pasillo o circulación») se estima como el diámetro del mayor
    círculo inscrito en su polígono.
- **Barra antipánico:** no se puede ver en el plano. El sistema avisa que hay que verificarla en
  los ambientes que superan el umbral.

## Cómo verificar una regla

1. Corrija `m2_por_persona`, `metros`, `metros_por_persona` o `umbral_personas`, y también `norma`
   y `articulo`, según el texto oficial.
2. Cambie `verificado: false` a `verificado: true` y borre el comentario `# VERIFICAR…`.
3. Actualice los resultados esperados de `tests/unit/norms/casos_aforo.yaml` y marque
   `confirmado: true` en los casos que haya contrastado.
4. Ejecute las pruebas:

```bash
uv run pytest tests/unit/norms
```

5. Cuando todas las reglas estén verificadas, cambie también la prueba
   `test_packaged_rules_are_valid_and_unverified` de `tests/unit/norms/test_norms.py`.

## Limitaciones

- **Precisión de los anchos:** los anchos medidos dependen de la escala y de la detección, con un
  error típico de ±2 cm en planos sintéticos. Una puerta de 0.88 m frente a un mínimo de 0.90 m
  puede deberse a la medición: revísela en el plano real.
- **Simplificación de puertas:** el cálculo supone que los ocupantes de un ambiente salen por las
  puertas de ese ambiente. No reparte el flujo entre ambientes encadenados.
