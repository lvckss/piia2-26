# Evaluación y trazabilidad de resultados

## Qué construir

Se construirá un proceso reproducible para evaluar las estrategias de análisis
de daños sobre conjuntos de imágenes versionados. El proceso deberá ejecutar
una estrategia con una configuración concreta, comparar sus predicciones con la
referencia disponible y producir:

- métricas globales y por clase de daño;
- métricas de localización o segmentación;
- latencia y uso de recursos relevantes;
- resultados separados para imágenes limpias y condiciones adversas;
- ejemplos visuales de verdaderos positivos, falsos positivos y falsos
  negativos;
- un registro de la configuración y versiones utilizadas.

## Por qué

Una demostración visual aislada no permite saber si el sistema es fiable ni
comparar cambios entre estrategias. Esta funcionalidad aporta evidencia
cuantitativa, facilita el análisis de errores y evita que una mejora aparente
provenga de usar datos, umbrales o configuraciones diferentes.

## Restricciones y supuestos

- Las particiones de datos y sus anotaciones deberán permanecer identificadas y
  no mezclarse accidentalmente.
- Dos estrategias solo se considerarán comparables si usan el mismo conjunto de
  evaluación y el mismo protocolo de métricas.
- Las métricas agregadas deberán conservar un desglose por clase para evitar que
  el rendimiento de categorías frecuentes oculte fallos en categorías raras.
- Los artefactos pesados, datasets, credenciales y salidas temporales no se
  incluirán en el repositorio de la asignatura.
- Los experimentos deberán registrar semilla cuando exista aleatoriedad.
- Los resultados deberán distinguir entre ausencia real de daños y fallo del
  pipeline.

## Criterios de aceptación

1. Una ejecución de evaluación guarda el nombre y versión de la estrategia, sus
   parámetros, la versión del conjunto de datos y la fecha de ejecución.
2. La evaluación produce métricas globales y un desglose para cada categoría
   presente en la referencia o en las predicciones.
3. El informe incluye, como mínimo, calidad de segmentación o localización,
   falsos positivos por imagen y tiempo medio de inferencia.
4. Repetir una evaluación determinista con la misma entrada y configuración
   produce los mismos resultados numéricos, salvo tolerancias documentadas.
5. La comparación entre dos estrategias rechaza o señala ejecuciones realizadas
   con particiones o protocolos incompatibles.
6. Es posible localizar desde una métrica agregada los resultados por imagen que
   contribuyen a ella y visualizar ejemplos de error.
7. La evaluación de robustez identifica por separado cada condición adversa y
   cuantifica su degradación respecto al conjunto limpio.
