# Niveles de confianza de los hallazgos para el Agente 1 (PIIA2)

## Qué construir

Se construirá una capa de clasificación que, antes de que cualquier hallazgo
de daño llegue al agente redactor del informe, lo etiquete como `confirmed`
o `needs_review` según la clase de daño y el `score` que produjo PIIA-1. Los
hallazgos `needs_review` no se afirman en el informe con la misma seguridad
que los `confirmed`: se muestran como pendientes de verificación humana, o se
excluyen del cálculo de coste agregado.

**Ninguna clase se excluye del informe por diseño.** Todas las clases de daño
pasan por el mismo esquema `confirmed`/`needs_review` — lo que cambia por
clase es el threshold de `confirmed`, calibrado con datos reales.

```python
from typing import Literal

ConfidenceTier = Literal["confirmed", "needs_review"]

# PENDIENTE de calibrar con el barrido de thresholds extendido a las 6 clases
# (antes solo se habia probado dent/scratch/crack; ver "Por que"). Estos
# valores son un placeholder, no los uses hasta que el barrido de las 6
# clases este corrido y confirmado.
CATEGORY_REVIEW_THRESHOLD: dict[str, float] = {
    "dent": 0.7,
    "scratch": 0.7,
    "crack": 0.7,
    "lamp broken": 0.6,
    "glass shatter": 0.6,
    "tire flat": 0.6,
}
DEFAULT_REVIEW_THRESHOLD = 0.8  # categoria desconocida -> conservador


def classify_confidence(category_name: str, score: float) -> ConfidenceTier:
    threshold = CATEGORY_REVIEW_THRESHOLD.get(category_name, DEFAULT_REVIEW_THRESHOLD)
    return "confirmed" if score >= threshold else "needs_review"
```

## Por qué

Un falso positivo y un falso negativo no cuestan lo mismo dentro de un
informe de peritaje. Si el Agente 1 trata la salida de PIIA-1 como verdad
absoluta, un falso positivo con score alto se convierte en una afirmación
económica falsa presentada con autoridad ("sustitución de neumático, 120€")
en un documento que se supone objetivo — mucho peor que omitir un daño real.

La versión anterior de este spec (29/09/2026, primera revisión) proponía
excluir `dent`/`scratch`/`crack` del informe por completo, basándose en que
el barrido de thresholds (0.1 a 0.85) no encontró ningún punto con precisión
y recall aceptables a la vez para esas 3 clases. Revisando los mismos datos
con más cuidado, la precisión bruta a threshold=0.3 de las otras 3 clases
tampoco era buena (`glass_shatter` 15.3%, `lamp_broken` 18.6%, `tire_flat`
19.0% — del mismo orden que las "malas"), y ese threshold=0.6 que se les
había asignado nunca se comprobó con un barrido real, se asumió porque el AP
y el `fp_per_image` agregados parecían razonables. No es coherente excluir
3 clases sin comprobar antes si las otras 3 de verdad se sostienen.

Por eso el diseño cambia: **sin exclusiones**, todo pasa por
`confirmed`/`needs_review` con un threshold por clase calibrado con el mismo
rigor para las 6. Si al final del barrido extendido alguna clase resulta no
tener ningún threshold razonable (como parecía ser el caso de `crack`), el
resultado práctico puede ser un threshold tan alto que casi nunca confirme
nada — pero es una consecuencia de los datos, no una lista de exclusión
codificada de antemano.

## Restricciones y supuestos

- Esta capa vive en el Agente 1 (interpretación de daños) de PIIA2, no en el
  pipeline de PIIA-1: no cambia ninguna predicción, solo decide cómo se usa
  cada una aguas abajo.
- **`CATEGORY_REVIEW_THRESHOLD` de arriba es un placeholder.** Antes de
  usarlo en el Agente 1 de verdad, hay que correr el barrido de thresholds
  extendido a las 6 clases (celda del notebook `quick_check_...ipynb`,
  sección "Barrido de score_threshold para las 6 clases") y sustituir estos
  valores por los que salgan de ahí.
- Se calibra con `BaselineStrategy` sobre 150-200 imágenes de `val`. Si la
  estrategia, el prompt o el dataset cambian, hay que rehacer el barrido
  antes de dar por buena la tabla.
- Si una clase pasa por verificación CLIP + Tip-Adapter, su umbral de
  revisión puede bajar, porque ya tiene una capa adicional de verificación
  antes de llegar aquí.
- `needs_review` no significa "se descarta": significa que el informe lo debe
  presentar como pendiente de confirmación, nunca como hecho consumado.

## Criterios de aceptación

1. Todo hallazgo que llega al agente redactor tiene un `confidence_tier`
   (`confirmed` o `needs_review`) asignado antes de redactarse.
2. Los hallazgos `needs_review` nunca aparecen en el informe con la misma
   redacción que los `confirmed` (deben distinguirse explícitamente).
3. El coste total agregado del informe puede calcularse solo con los
   hallazgos `confirmed`, y por separado con todos, para que quien lo lea
   sepa cuánto de la estimación es firme y cuánto es provisional.
4. Los umbrales por clase están centralizados en un único punto
   (`CATEGORY_REVIEW_THRESHOLD`), no repartidos por el código del agente,
   para poder recalibrarlos según la evidencia sin tocar la lógica del
   agente.
5. `CATEGORY_REVIEW_THRESHOLD` refleja el resultado del barrido de las 6
   clases, no valores asumidos — antes de cerrar esta spec como definitiva,
   los 6 valores deben tener un barrido real detrás.
