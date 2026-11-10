# Rendimiento (RNF02)

**Meta:** al menos 20 pasos de simulación por segundo con 500 agentes en un Core i5 con 8 GB de RAM.
El motor y el render se miden por separado.

```bash
uv run pytest tests/benchmarks -s
```

## Resultados

Medidos el 2026-11-10 en el equipo de desarrollo (Windows 11, Python 3.12.16, NumPy 2.5.4), en un
ambiente de 30 × 20 m con dos salidas y todos los agentes en movimiento.

### Motor, sin render

| Agentes | Pasos por segundo |
|---|---|
| 100 | ≈ 1170 |
| 300 | ≈ 690 |
| 500 | ≈ 470 |
| 1000 | ≈ 205 |

### Render del visor

Con 500 agentes, el render por software en modo `offscreen` a 1000 × 700 px alcanza
**≈ 270 cuadros/s**.

## Conclusión

- **Motor:** con 500 agentes es unas 23 veces más rápido que la meta. Numba no hace falta por ahora
  (CLAUDE.md §2).
- **Pendiente:** repetir la medición en el equipo de referencia (Core i5 / 8 GB) y anotarla aquí.
  La prueba `test_engine_speed[500]` falla si el motor baja de 20 pasos/s.
