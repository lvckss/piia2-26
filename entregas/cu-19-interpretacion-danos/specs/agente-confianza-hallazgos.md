# Niveles de confianza de los hallazgos para el Agente 1 (PIIA2)

## Qué construir

Se construirá una capa de clasificación que, antes de que cualquier hallazgo
de daño llegue al agente redactor del informe, lo etiquete como `confirmed`
o `needs_review` según la clase de daño y el `score` que produjo PIIA-1. Los
hallazgos `needs_review` no se afirman en el informe con la misma seguridad
que los `confirmed`: se muestran como pendientes de verificación humana, o se
excluyen del cálculo de coste agregado.

El umbral de revisión no es un único número global: depende de la clase de
daño. Pero no todas las clases se resuelven subiendo o bajando un threshold —
algunas se **excluyen directamente** del informe automático (ver "Por qué").

Referencia inicial (a recalibrar con más evidencia, no un valor cerrado):

```python
from typing import Literal

ConfidenceTier = Literal["confirmed", "needs_review", "excluded"]

# clases con una curva precision/recall utilizable (barrido de thresholds,
# 29/09/2026, BaselineStrategy, 150 imagenes de val): listón normal.
CATEGORY_REVIEW_THRESHOLD: dict[str, float] = {
    "lamp broken": 0.6,
    "glass shatter": 0.6,
    "tire flat": 0.6,
}

# clases sin ningun threshold utilizable: el barrido (0.1 a 0.85) no encontro
# un solo punto con precision Y recall aceptables a la vez. Mejor caso real:
# dent a threshold=0.70 -> 11.5% precision, 6.6% recall; crack nunca supera
# 2% de precision en todo el barrido. A threshold=0.85 las tres caen a 0%
# precision y 0% recall (no producen ninguna deteccion). Subir el threshold
# no arregla esto — reescribir el prompt de texto tampoco (ver TAREAS.md,
# prueba de 3 variantes de prompt para `crack`, todas peores que la original
# o directamente sin recall). Por eso se excluyen del informe automatico en
# vez de intentar filtrarlas por score.
EXCLUDED_CATEGORIES = {"dent", "scratch", "crack"}

DEFAULT_REVIEW_THRESHOLD = 0.8  # categoria desconocida y no excluida -> conservador


def classify_confidence(category_name: str, score: float) -> ConfidenceTier:
    if category_name in EXCLUDED_CATEGORIES:
        return "excluded"
    threshold = CATEGORY_REVIEW_THRESHOLD.get(category_name, DEFAULT_REVIEW_THRESHOLD)
    return "confirmed" if score >= threshold else "needs_review"
```

## Por qué

Un falso positivo y un falso negativo no cuestan lo mismo dentro de un
informe de peritaje. Si el Agente 1 trata la salida de PIIA-1 como verdad
absoluta, un falso positivo con score alto se convierte en una afirmación
económica falsa presentada con autoridad ("sustitución de neumático, 120€")
en un documento que se supone objetivo — mucho peor que omitir un daño real.

La primera versión de este spec (28/09/2026) asumía que `dent`/`scratch`
tenían "solo" un problema de recall (aciertan poco, pero lo que dicen es
razonable) y que subir el threshold arreglaría `tire_flat`/`crack`. El
barrido de thresholds del 29/09/2026 (0.1 a 0.85, sobre 150 imágenes)
descartó esa hipótesis: **`dent` y `scratch` tienen el mismo problema de
precisión que `crack`**, no solo de recall. En ningún punto del barrido
`dent`, `scratch` o `crack` alcanzan una precisión y un recall aceptables a
la vez — el mejor caso (`dent` a threshold=0.70) sigue siendo 88.5% de falsos
positivos. Tampoco lo arregla reescribir el prompt de texto: se probaron 3
variantes para `crack` y las 2 alternativas a la original perdieron casi todo
el recall sin ganar precisión utilizable.

Por eso el diseño ya no es "threshold distinto por clase para todo": las
clases sin una curva precision/recall utilizable (`dent`, `scratch`,
`crack`) se **excluyen** del informe automático en vez de intentar filtrarlas
por score — no hay ningún score que las salve. Las que sí tienen una curva
razonable (`lamp_broken`, `glass_shatter`, `tire_flat`) siguen el esquema
`confirmed`/`needs_review` original. Esto imita a un perito real que, ante
una fuente de información poco fiable para cierto tipo de daño, prefiere no
mencionarlo en vez de arriesgarse a afirmar algo falso.

## Restricciones y supuestos

- Esta capa vive en el Agente 1 (interpretación de daños) de PIIA2, no en el
  pipeline de PIIA-1: no cambia ninguna predicción, solo decide cómo se usa
  cada una aguas abajo.
- `excluded` es una decisión de alcance de PIIA2, no un fallo oculto: el
  sistema informa con fiabilidad sobre `lamp_broken`/`glass_shatter`/
  `tire_flat`, y `dent`/`scratch`/`crack` quedan fuera del informe automático
  hasta que haya una mejora real de detección (exemplars, fine-tuning, o
  extender CLIP + Tip-Adapter — ya hay una base para `dent` en
  `ml/scripts/export_dent_roi_crops.py`). No es un umbral que se pueda subir
  para "arreglarlo": el barrido ya cubrió ese espacio y no hay un punto bueno.
- `EXCLUDED_CATEGORIES`/`CATEGORY_REVIEW_THRESHOLD` se calibraron con
  `BaselineStrategy` sobre 150-200 imágenes de `val`. Si la estrategia, el
  prompt o el dataset cambian, hay que rehacer el barrido antes de dar por
  buena esta tabla.
- Si una clase pasa por verificación CLIP + Tip-Adapter, su umbral de
  revisión puede bajar (o una clase `excluded` podría reincorporarse) porque
  ya tiene una capa adicional de verificación antes de llegar aquí.
- `needs_review` no significa "se descarta": significa que el informe lo debe
  presentar como pendiente de confirmación, nunca como hecho consumado.
  `excluded` sí significa que no llega al informe en absoluto.

## Criterios de aceptación

1. Todo hallazgo que llega al agente redactor tiene un `confidence_tier`
   (`confirmed`, `needs_review` o `excluded`) asignado antes de redactarse.
2. Los hallazgos `excluded` no aparecen en el informe ni se usan para el
   coste agregado; los `needs_review` aparecen, pero nunca con la misma
   redacción que los `confirmed` (deben distinguirse explícitamente).
3. El coste total agregado del informe puede calcularse solo con los
   hallazgos `confirmed`, y por separado con todos los no excluidos, para que
   quien lo lea sepa cuánto de la estimación es firme y cuánto es provisional.
4. Los umbrales y la lista de exclusión están centralizados en un único punto
   (`CATEGORY_REVIEW_THRESHOLD` / `EXCLUDED_CATEGORIES`), no repartidos por el
   código del agente, para poder recalibrarlos según la evidencia sin tocar
   la lógica del agente.
