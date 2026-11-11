# Escenarios y calibración (RF10, RF11)

## Escenarios «qué pasa si»

En el paso 6, el selector **Escenario** muestra el escenario base y sus variantes.

- **Escenario base:** sus ocupantes se indican en el paso 4.
- **Nuevo escenario…:** copia la ocupación del base con un porcentaje (100 % = igual, 150 % =
  50 % más de personas). En el mismo diálogo se marcan las salidas bloqueadas. El reparto entre
  ambientes y perfiles se mantiene, y el total es exacto (método del mayor resto).
- **Editar…:** cambia el nombre, el porcentaje o las salidas bloqueadas. La ocupación se vuelve a
  calcular desde el escenario base actual.
- **Eliminar:** borra la variante y sus simulaciones. El escenario base no se puede eliminar.
- **Semilla:** cada escenario guarda la suya. Las variantes nacen con la semilla del base, así
  las diferencias se deben a lo que se cambió y no al azar.
- **Comparar escenarios…:** muestra dos escenarios lado a lado, con su animación y mapa de calor,
  y una tabla de indicadores con la diferencia B − A. Si existen dos o más escenarios simulados,
  el informe PDF agrega esta comparación.

### Qué indicador mirar

El **tiempo total** suele depender de la persona que reacciona más tarde, que casi no cambia
entre escenarios con la misma semilla. Para ver el efecto de bloquear una salida o cambiar el
aforo, conviene mirar el **tiempo para evacuar al 90 %** y los **cuellos de botella**.

## Calibración con un simulacro real

Menú **Herramientas › Calibrar con un simulacro real…**

1. Ingrese la fecha, las personas que participaron y el tiempo total, es decir, cuándo salió la
   última persona.
2. Si los midió, ingrese también el tiempo de la última persona por cada salida. Deje 0 en las que
   no midió.
3. Pulse **Calibrar**. Se simula el escenario base, con la ocupación repartida para que el total
   sea igual a los participantes, y se prueban 36 combinaciones de dos factores:
   - **reacción** (multiplica la media y la desviación del tiempo de reacción de todos los
     perfiles): 0.5, 0.75, 1, 1.25, 1.5, 2;
   - **velocidad** (multiplica la velocidad máxima de todos los perfiles): 0.7, 0.8, 0.9, 1,
     1.1, 1.2.
4. El resultado muestra el error del tiempo total antes y después, y los factores elegidos.
   - **Meta de validación:** error menor que 20 % en el tiempo total.
   - **Error que se minimiza:** el RMSE de los errores relativos del tiempo total y de los tiempos
     por salida medidos.
   - **Empates:** gana la combinación que cambia menos el modelo.
5. **Aplicar a los perfiles** multiplica los perfiles guardados por los factores. Vuelva a simular
   para ver los tiempos calibrados.

### Datos que se guardan

- **Simulacro:** queda registrado en la tabla `simulacro_real`.
- **Calibración aplicada:**
  - modifica el catálogo de perfiles (tabla `perfil_persona`);
  - como los valores dejan de coincidir con los provisionales por defecto, el informe ya no los
    marca como «provisional»;
  - se puede volver a calibrar más adelante; cada calibración parte de los perfiles actuales.

### Límites

- **Dos factores globales:** se ajustan dos factores para todos los perfiles a la vez. Si en el
  simulacro, por ejemplo, los niños reaccionaron distinto de lo esperado respecto de los adultos,
  eso no se corrige por perfil.
- **Una semilla:** se usa la semilla del escenario para comparar todas las combinaciones en igualdad
  de condiciones. El resultado puede variar algo con otra semilla.
- **Duración:** con muchas personas, las 36 simulaciones pueden tardar varios minutos. La ventana
  sigue respondiendo y se puede cancelar.
