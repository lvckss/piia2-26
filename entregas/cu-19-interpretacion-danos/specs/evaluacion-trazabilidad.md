# Evaluación y trazabilidad de resultados

## Qué construir

Procesos reproducibles que miden el sistema y dejan registrado con qué datos, configuración y versión se obtuvo cada resultado. Se organizan en dos niveles:

1. **Detección de PIIA1 (heredado).** Evaluación de estrategias de detección contra las anotaciones de CarDD, con el `Evaluator` de [`app/ml`](../app/ml/StrategyPipeline/evaluation/evaluator.py). Ejecuta una estrategia con una configuración concreta, compara sus predicciones con la referencia disponible y produce:
   - métricas globales y por clase de daño;
   - métricas de localización o segmentación;
   - latencia y uso de recursos relevantes;
   - resultados separados para imágenes limpias y condiciones adversas;
   - ejemplos visuales de verdaderos positivos, falsos positivos y falsos negativos;
   - un registro de la configuración y versiones utilizadas.

   Los resultados de esa detección están guardados para 500 imágenes de CarDD; PIIA2 los consume y no los vuelve a calcular ejecutando SAM3.
2. **Sistema PIIA2.** Evaluación de cada pieza con los datos disponibles: la segunda opinión del modelo de visión del Agente 1 y el techo que marcan las detecciones guardadas; el error de costes del Agente 2; la recuperación del RAG; y la coincidencia de las cifras del informe con las del Agente 2. La evaluación de la categoría del vehículo (Issue #28) queda fuera: la Issue está aparcada.

## Por qué

Una demostración visual aislada no permite saber si el sistema es fiable ni comparar cambios entre estrategias. Esta funcionalidad aporta evidencia cuantitativa, facilita el análisis de errores y evita que una mejora aparente provenga de usar datos, umbrales o configuraciones diferentes.

En PIIA2 hay una razón más: cada pieza del sistema se apoya en datos distintos (detecciones etiquetadas, siniestros sintéticos con coste facturado, preguntas con fuente esperada) y ninguno cubre la cadena completa desde la imagen. Medir cada pieza por separado, y declarar qué no se puede medir, evita presentar como verificado algo que solo está supuesto.

## Alcance

- **Incluido:** el proceso de evaluación de la detección de PIIA1 (heredado); la medición de la segunda opinión de visión; el análisis del techo de las detecciones guardadas; la evaluación del coste del Agente 2, del RAG, del informe (la evaluación de la categoría del vehículo queda fuera: la Issue #28 está aparcada); el registro de la configuración y de los datos usados en cada evaluación.
- **Fuera de alcance:** ejecutar SAM3 o mejorar la detección de PIIA1; el cálculo de costes, la recuperación de normativa y la redacción del informe, que son de los Agentes 2 y 3; calibrar los umbrales de confianza (ver [`agente-confianza-hallazgos.md`](agente-confianza-hallazgos.md)); cambiar el código de evaluación.

## Restricciones y supuestos

- Las particiones de datos y sus anotaciones deberán permanecer identificadas y no mezclarse accidentalmente.
- Dos estrategias solo se considerarán comparables si usan el mismo conjunto de evaluación y el mismo protocolo de métricas.
- Las métricas agregadas deberán conservar un desglose por clase para evitar que el rendimiento de categorías frecuentes oculte fallos en categorías raras.
- Los artefactos pesados, datasets, credenciales y salidas temporales no se incluirán en el repositorio de la asignatura.
- Los experimentos deberán registrar semilla cuando exista aleatoriedad.
- Los resultados deberán distinguir entre ausencia real de daños y fallo del pipeline.
- **`is_true_positive` infravalora a la visión en `dent`, `scratch` y `crack`.** Es el acierto de PIIA1 contra las anotaciones de CarDD (IoU de máscara ≥ 0,5, emparejamiento por score), y CarDD no anota todos los daños. En esas tres clases sirve para comparar modelos entre sí, no como medida absoluta.
- **El techo lo pone la detección guardada.** En `dent`, `scratch` y `crack`, que un daño no se detecte no significa que no exista: la visión solo verifica lo que PIIA1 propone.
- **No se puede medir con CarDD si la pieza y la severidad son correctas**, porque no trae esas etiquetas; hace falta revisar a mano una muestra.
- Los siniestros sintéticos de la empresa no tienen foto: evalúan los costes y la cobertura, no la cadena completa desde la imagen.
- Las evaluaciones que llaman al modelo de visión cuestan dinero: por defecto solo cuentan las llamadas que harían, y gastar requiere pedirlo de forma explícita.

## Criterios de aceptación

**Cómo leer la columna de verificación.** *Verificado*: el comando se ejecuta y pasa. *Parcial*: parte del criterio está verificada y se indica cuál. *Pendiente*: no hay verificación todavía, con el motivo o la Issue que la cubrirá. Los comandos se ejecutan desde `app/agentes/agente_multimodal/`; los que usan el export de 500 imágenes o el paquete de datos de la empresa se saltan con un aviso si no están en local.

### Nivel 1 — detección de PIIA1 (criterios heredados)

Se conservan como especificación del `Evaluator` de PIIA1; no son requisitos de ejecución de PIIA2, que no ejecuta SAM3. Ninguno tiene una prueba automática en el repositorio: su estado sale de leer el código de `app/ml/StrategyPipeline`.

| ID | Dado / Cuando | Resultado esperado | Verificación y estado |
|---|---|---|---|
| AC-001 | Una ejecución de evaluación. | Guarda el nombre y la versión de la estrategia, sus parámetros, la versión del conjunto de datos y la fecha de ejecución. | **Parcial.** `RunInfo` guarda `strategy_name`, `dataset_name`, `ann_path` y `config` (parámetros); no guarda la versión ni la fecha de ejecución. Sin prueba automática. |
| AC-002 | Una evaluación terminada. | Produce métricas globales y un desglose para cada categoría presente en la referencia o en las predicciones. | **Pendiente de prueba automática.** Implementado en `EvalOutput.summary` y `EvalOutput.per_class`. |
| AC-003 | El informe de una evaluación. | Incluye, como mínimo, calidad de segmentación o localización, falsos positivos por imagen y tiempo medio de inferencia. | **Pendiente de prueba automática.** Implementado en `SummaryMetrics`: `mask_ap_50_95`, `ap75`, `ap_small`, `fp_per_image` y `ms_per_image`. |
| AC-004 | Una evaluación determinista repetida con la misma entrada y configuración. | Produce los mismos resultados numéricos, salvo tolerancias documentadas. | **Pendiente.** No hay prueba ni tolerancias documentadas. |
| AC-005 | La comparación entre dos estrategias evaluadas con particiones o protocolos incompatibles. | La comparación se rechaza o lo señala. | **Pendiente.** No existe una función de comparación en `app/ml/StrategyPipeline`. |
| AC-006 | Una métrica agregada. | Permite localizar los resultados por imagen que contribuyen a ella y visualizar ejemplos de error. | **Pendiente de prueba automática.** Implementado en `EvalOutput.per_image` y `Evaluator.get_inspection()` ([`inspection.py`](../app/ml/StrategyPipeline/evaluation/inspection.py)). |
| AC-007 | Imágenes con condiciones adversas. | La evaluación de robustez identifica por separado cada condición y cuantifica su degradación respecto al conjunto limpio. | **Pendiente de prueba automática.** Implementado en `per_condition` y en las métricas `pclean`, `mpc` y `rpc`. |

### Nivel 2 — sistema PIIA2

| ID | Dado / Cuando | Resultado esperado | Verificación y estado |
|---|---|---|---|
| AC-008 | Las detecciones guardadas con `is_true_positive` y un modelo de visión. | `evaluar_vision.py` calcula, por clase y modelo, cuántos falsos positivos de PIIA1 rechaza la visión y cuántos aciertos reales descarta por error. Por defecto solo cuenta las llamadas que haría; gastar requiere `--ejecutar`. | **Parcial.** Con un modelo simulado, `python probar_evaluar_vision_stub.py` verifica la aritmética de las métricas, el recuento de llamadas y que la caché evita el coste. La medición con el modelo real está pendiente. |
| AC-009 | Las 500 imágenes exportadas. | `analizar_detecciones.py` calcula la precisión y el recall de PIIA1 por clase y umbral de score, y las llamadas que supone cada filtro previo. | **Parcial.** La cifra del filtro (18.507 detecciones → 3.712 candidatas) se verifica con `python probar_seleccion_stub.py`. Las curvas están medidas y documentadas en [`agente-confianza-hallazgos.md`](agente-confianza-hallazgos.md) y se reproducen con `python analizar_detecciones.py <carpeta del export>`. |
| AC-010 | Los siniestros sintéticos de la empresa (`split` val y test) con su coste facturado sin IVA. | Se mide el error de coste de la herramienta de la empresa con los daños reales (referencia ≈ 9 %), que es el suelo de error que hereda el Agente 2. | **Pendiente.** Depende del Agente 2 ([Issue #30](https://github.com/lvckss/piia2-26/issues/30)). |
| AC-011 | Las 25 preguntas de evaluación de la empresa. | Se mide en cuántas aparece la fuente esperada entre los k fragmentos que devuelve el RAG. | **Pendiente.** Depende del RAG ([Issue #32](https://github.com/lvckss/piia2-26/issues/32)); la métrica mínima la fija su plan. |
| AC-012 | Un informe generado a partir de la salida del Agente 2. | Todas las cifras en euros del informe coinciden con las de esa salida, y una comprobación automática lo verifica. | **Pendiente.** Depende del Agente 3 ([Issue #31](https://github.com/lvckss/piia2-26/issues/31)). |
| AC-013 | Una muestra de fotos de CarDD y la categoría de vehículo estimada para cada una. | Se documenta, por foto, la categoría estimada y la que juzga una persona, y la tasa de coincidencia. | **Aparcado.** La [Issue #28](https://github.com/lvckss/piia2-26/issues/28) está aparcada, así que este criterio no se evalúa en este ciclo; corresponde al criterio AC-011 de su planificación, que fijaba el umbral. |
