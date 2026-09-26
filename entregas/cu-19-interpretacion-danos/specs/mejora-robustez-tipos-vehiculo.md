# Mejora de robustez entre tipos de vehículo

## Qué construir

Se instrumentará y refactorizará el pipeline de detección de daños (SAM3 +
estrategias baseline/SAHI/geometric ensemble) para poder medir y corregir la
inconsistencia de métricas observada entre distintos tipos de vehículo. El
trabajo incluye:

- una dimensión de evaluación por tipo de vehículo dentro del `Evaluator`,
  análoga a la ya existente por condición adversa;
- una única fuente de configuración para los umbrales de score y de máscara,
  compartida por las tres estrategias;
- umbrales de score calibrados por clase de daño en lugar de un único umbral
  global;
- un conjunto de prompts de texto por clase, sin dependencia de un valor de
  respaldo poco descriptivo;
- una configuración CLIP + Tip-Adapter propia para clases adicionales, más
  allá de las dos que ya la tienen;
- una decisión explícita, documentada e implementada, sobre la compatibilidad
  entre exemplars y ensemble geométrico;
- una recalibración de los parámetros de SAHI y del ensemble geométrico en
  función del tipo de vehículo, una vez disponible esa dimensión de
  evaluación.

## Por qué

El equipo observa que la detección funciona bien en algunos vehículos y baja
notablemente en otros, pero el pipeline actual no registra el tipo de
vehículo en ningún punto: ni en las anotaciones, ni en el loader, ni en las
métricas del evaluador. Sin esa dimensión no es posible confirmar la causa
del problema ni verificar si un cambio realmente lo mejora, solo se puede
inspeccionar caso a caso.

Además, varias piezas del pipeline explican por qué el comportamiento podría
variar entre vehículos: los mismos parámetros de umbral tienen valores
distintos según el archivo donde se definen, lo que hace que comparar
estrategias entre sí no sea fiable si no se homogenizan antes; los prompts de
texto están redactados asumiendo turismos convencionales; y solo dos de las
seis clases de daño cuentan con verificación visual adicional (CLIP +
Tip-Adapter), dejando el resto expuesto directamente al umbral crudo de SAM3.

## Restricciones y supuestos

- No se reentrenará SAM3; los cambios se limitan a configuración, prompts,
  calibración de umbrales y a la capa de estrategias/evaluación.
- El etiquetado de tipo de vehículo puede obtenerse mediante un clasificador
  zero-shot (por ejemplo CLIP) y no requiere anotación manual del dataset
  completo.
- Cualquier ajuste de umbral, prompt o hiperparámetro de Tip-Adapter se
  calibrará con el split `val`; el split `test` solo se usará para reportar
  el resultado final, siguiendo la convención ya establecida en el pipeline.
- La unificación de umbrales no debe romper la compatibilidad de las
  notebooks y scripts existentes que instancian las estrategias directamente.
- Los cambios en `Evaluator` deben mantener el contrato actual
  (`StrategyResult` → métricas) sin que las estrategias devuelvan información
  de evaluación.
- La recalibración por tipo de vehículo depende de que la dimensión de
  evaluación correspondiente esté disponible; no se abordará antes de esa
  instrumentación.

## Criterios de aceptación

1. El `Evaluator` produce un desglose de métricas por tipo de vehículo,
   comparable en formato al desglose existente por condición adversa.
2. Las tres estrategias (baseline, SAHI, ensemble geométrico) leen
   `score_threshold` y `mask_threshold` de una única fuente de
   configuración; no existen valores por defecto distintos entre ellas para
   el mismo parámetro.
3. Cada clase de daño puede evaluarse con un umbral de score propio, y el
   informe de evaluación permite comparar el resultado antes y después de
   calibrar por clase.
4. Ninguna estrategia puede quedar, por omisión, ejecutando un prompt de
   texto igual al nombre desnudo de la categoría; el prompt usado en cada
   predicción queda registrado en la metadata de la predicción.
5. Cada clase de daño cuenta con al menos una variante de prompt de texto
   adicional a la original, y el proceso de selección de la mejor variante
   queda documentado con los resultados de `val`.
6. Al menos una clase adicional a `tire_flat` y `lamp_broken` cuenta con
   verificación CLIP + Tip-Adapter configurada y con su propio cache
   calibrado.
7. Queda documentado y reflejado en el código si el ensemble geométrico
   soporta prompts con exemplars/hybrid o si se mantiene limitado a prompts
   de texto; no queda como comportamiento implícito no documentado.
8. Los parámetros de slicing de SAHI y de perturbación del ensemble
   geométrico cuentan con al menos una configuración alternativa evaluada por
   tipo de vehículo, con resultados registrados en la dimensión `per_vehicle`.

## Reparto de trabajo propuesto

**Persona A — Medición e infraestructura de evaluación**

- Instrumentar `vehicle_type` (clasificación + campo en `ImageSample`/loader
  + dimensión `per_vehicle` en el `Evaluator`).
- Unificar `score_threshold`/`mask_threshold` en una única fuente de
  configuración.
- Calibrar el umbral de score por clase de daño.

**Persona B — Prompts y verificación visual**

- Eliminar el fallback de prompt silencioso y diseñar variantes de texto por
  clase.
- Extender CLIP + Tip-Adapter a clases adicionales (empezando por `dent`).
- Decidir e implementar/documentar la relación entre exemplars y ensemble
  geométrico.

**Conjunto, al cierre**

- Recalibrar `slice_size`/`overlap_ratio` (SAHI) y `perturbation_scale`
  (ensemble geométrico) por tipo de vehículo, una vez disponible esa
  dimensión de evaluación.
