# Formato de los planos etiquetados (evaluación de visión)

La meta de la visión es **≥ 85 %** de precisión y de exhaustividad, medida sobre 20 planos reales
etiquetados. Este documento explica cómo preparar esos planos para
`scripts/eval_vision.py`.

## Estructura de la carpeta

```
planos_etiquetados/
  colegio_san_martin.jpg
  colegio_san_martin.json
  oficina_centro.pdf
  oficina_centro.json
  ...
```

Cada plano necesita una imagen (`.png`, `.jpg`, `.jpeg`, `.bmp`, `.tif` o `.pdf`) y un `.json`
con el mismo nombre.

## Contenido del `.json`

```json
{
  "escala_m_por_px": 0.02,
  "pagina": 0,
  "muros":   [[x1, y1, x2, y2], ...],
  "puertas": [[x1, y1, x2, y2], ...],
  "salidas": [[x1, y1, x2, y2], ...]
}
```

- **Coordenadas:** en píxeles de la imagen tal como la carga el programa. Si el plano es un PDF,
  son píxeles de la página rasterizada a 200 dpi.
- **`escala_m_por_px`:** es opcional, pero conviene incluirla.
  - Con escala, la tolerancia es de 0.20 m y el rango de anchos de puerta se expresa en metros.
  - Sin escala, la tolerancia es de 10 px.
- **`pagina`:** solo se usa con PDF. Es la página a evaluar, contando desde 0.
- **`muros`:** cada muro es un segmento que sigue el **eje** del muro. Un muro cortado por una
  puerta se anota como dos segmentos.
- **`puertas` y `salidas`:** cada una es el segmento del **vano**, de jamba a jamba, sobre el eje
  del muro. Salida es toda puerta que da al exterior o a una zona segura.

## Ejecutar la evaluación

```bash
uv run python scripts/eval_vision.py --dataset planos_etiquetados --overlays control/
```

En `control/` se guardan imágenes con la verdad de referencia en verde, los muros detectados en
rojo y los vanos detectados en azul. Sirven para ver dónde falla la detección.

## Métricas

- **Muros:** se miden por longitud.
  - Precisión: fracción de la longitud detectada que cae a menos de la tolerancia de un muro real.
  - Exhaustividad: fracción de la longitud real que cae a menos de la tolerancia de un muro
    detectado.
- **Vanos (puertas y salidas):** cada vano detectado se empareja con un solo vano real. Cuentan
  como pareja si sus puntos medios están a menos de la tolerancia más medio ancho del vano real.
