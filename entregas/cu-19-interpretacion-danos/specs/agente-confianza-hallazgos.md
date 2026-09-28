# Niveles de confianza de los hallazgos para el Agente 1 (PIIA2)

## Qué construir

Se construirá una capa de clasificación que, antes de que cualquier hallazgo
de daño llegue al agente redactor del informe, lo etiquete como `confirmed`
o `needs_review` según la clase de daño y el `score` que produjo PIIA-1. Los
hallazgos `needs_review` no se afirman en el informe con la misma seguridad
que los `confirmed`: se muestran como pendientes de verificación humana, o se
excluyen del cálculo de coste agregado.

El umbral de revisión no es un único número global: depende de la clase de
daño, porque las clases no fallan todas de la misma forma (ver "Por qué").

Referencia inicial (a recalibrar con evidencia real, no un valor cerrado):

```python
from typing import Literal

ConfidenceTier = Literal["confirmed", "needs_review"]

# fiabilidad conocida por clase, basada en la inspeccion visual sobre SAHI/
# baseline en piia2-26 (ver TAREAS.md, tarea de "inspeccion visual"):
# - lamp_broken / glass_shatter: clases fiables, listón normal.
# - tire_flat / crack: problema de PRECISION conocido — disparan con score
#   alto sobre partes sanas (rueda inflada, arañazo confundido con grieta).
#   Necesitan un listón mas alto porque un falso positivo con score alto se
#   afirmaria en el informe como si fuera cierto.
# - dent / scratch: problema de RECALL, no de precision — lo poco que
#   detectan suele ser razonable, así que no hace falta subirles el listón.
CATEGORY_REVIEW_THRESHOLD: dict[str, float] = {
    "lamp broken": 0.6,
    "glass shatter": 0.6,
    "tire flat": 0.9,
    "crack": 0.9,
    "dent": 0.6,
    "scratch": 0.6,
}
DEFAULT_REVIEW_THRESHOLD = 0.8  # categoria desconocida -> conservador


def classify_confidence(category_name: str, score: float) -> ConfidenceTier:
    threshold = CATEGORY_REVIEW_THRESHOLD.get(category_name, DEFAULT_REVIEW_THRESHOLD)
    return "confirmed" if score >= threshold else "needs_review"
```

## Por qué

Un falso positivo y un falso negativo no cuestan lo mismo dentro de un
informe de peritaje. Si el Agente 1 trata la salida de PIIA-1 como verdad
absoluta:

- Un falso positivo con score alto (por ejemplo `tire_flat` disparando sobre
  una rueda sana, o `crack` confundiendo un arañazo con una grieta — ambos
  observados en la inspección visual del 28/09/2026) se convertiría en una
  afirmación económica falsa presentada con autoridad ("sustitución de
  neumático, 120€") en un documento que se supone objetivo.
- Un falso negativo (por ejemplo `dent`/`scratch` con recall bajo) simplemente
  omite un daño real del informe — un fallo más defendible que inventar un
  coste que no corresponde.

Por eso el umbral de revisión no debe ser el mismo para todas las clases: las
que tienen un problema de **precisión conocido** (falsos positivos con score
alto) necesitan un listón más exigente que las que solo tienen un problema de
**recall** (aciertan poco, pero cuando aciertan es razonable). Esto imita el
comportamiento de un perito real, que distingue entre lo que puede firmar y
lo que necesita revisar antes de firmarlo, en vez de exigir que PIIA-1 tenga
accuracy perfecta antes de que PIIA2 pueda arrancar.

## Restricciones y supuestos

- Esta capa vive en el Agente 1 (interpretación de daños) de PIIA2, no en el
  pipeline de PIIA-1: no cambia ninguna predicción, solo decide cómo se usa
  cada una aguas abajo.
- Los valores de `CATEGORY_REVIEW_THRESHOLD` son un punto de partida basado en
  observación cualitativa (9 imágenes inspeccionadas), no en una calibración
  formal con `val`. Deben revisarse en cuanto haya una evaluación con más
  imágenes y, cuando esté disponible, con el desglose `output.per_class` real.
- Si una clase pasa por verificación CLIP + Tip-Adapter (ver
  `entregas/cu-19-interpretacion-danos/app/ml/StrategyPipeline/strategies/components/clip_tip_adapter.py`),
  su umbral de revisión puede bajar, porque ya tiene una capa adicional de
  verificación antes de llegar aquí.
- `needs_review` no significa "se descarta": significa que el informe lo debe
  presentar como pendiente de confirmación, nunca como hecho consumado.

## Criterios de aceptación

1. Todo hallazgo que llega al agente redactor tiene un `confidence_tier`
   (`confirmed` o `needs_review`) asignado antes de redactarse.
2. Los hallazgos `needs_review` nunca aparecen en el informe con la misma
   redacción que los `confirmed` (deben distinguirse explícitamente, por
   ejemplo con una sección aparte o una anotación visible).
3. El coste total agregado del informe puede calcularse solo con los
   hallazgos `confirmed`, y por separado con todos, para que quien lo lea
   sepa cuánto de la estimación es firme y cuánto es provisional.
4. Los umbrales por clase están centralizados en un único punto
   (`CATEGORY_REVIEW_THRESHOLD`), no repartidos por el código del agente, para
   poder recalibrarlos según la evidencia sin tocar la lógica del agente.
