# Niveles de confianza de los hallazgos para el Agente 1 (PIIA2)

## Qué construir

Una capa que, antes de que un hallazgo de daño llegue a los agentes de costes
y de informe, lo etiquete como `confirmed` o `needs_review` combinando tres
fuentes de evidencia:

1. el **score de PIIA-1** frente a un umbral propio de cada clase,
2. la **segunda opinión de un modelo de visión** (¿hay de verdad un daño de
   esa clase en la zona marcada?),
3. que se pueda **presupuestar**: el modelo ha identificado la pieza y la
   tool de costes tiene una regla para esa clase + pieza + severidad.

`confirmed` exige las tres. Todo lo demás es `needs_review`: el informe lo
presenta como pendiente de verificación y no como un hecho.

**Ninguna clase se excluye del informe por diseño, y ninguna detección se
descarta en esta capa.** Lo que la visión rechaza queda como `needs_review`
con `vision_verdict = "rechazado"` (el informe lo muestra aparte y fuera del
coste).

Implementado en `app/agentes/agente_multimodal/confianza.py`:

```python
ConfidenceTier = Literal["confirmed", "needs_review"]

# PENDIENTE de calibrar (ver "Restricciones"): placeholders, no resultados medidos.
CATEGORY_REVIEW_THRESHOLD = {
    "dent": 0.7, "scratch": 0.7, "crack": 0.7,
    "lamp broken": 0.6, "glass shatter": 0.6, "tire flat": 0.6,
}
DEFAULT_REVIEW_THRESHOLD = 0.8  # clase desconocida -> conservador


def classify_confidence(category_name, score) -> ConfidenceTier:
    """Primer filtro, solo por score."""


def decidir_tier(category_name, score, vision_verdict, pieza_id, regla_coste_aplicable):
    """Tier final: 'confirmed' solo si el score pasa su umbral, la visión
    dice 'confirmado' y hay pieza con regla de coste; si no, 'needs_review'."""
```

La visión **no rescata scores bajos**: un hallazgo por debajo de su umbral
sigue siendo `needs_review` aunque el modelo lo confirme. Es una decisión
conservadora; si las medidas muestran que la visión es más fiable que el
score, se puede relajar.

## Filtro previo: qué detecciones llegan al modelo de visión

Antes de nada, no todas las detecciones se mandan al modelo (cada llamada
cuesta). Con las **500 imágenes** exportadas de Colab (`val`/`test`, SAM3
baseline, score ≥ 0,3; acierto = IoU de máscara ≥ 0,5 con la anotación real) se
midió cuánto sirve cada filtro. Reproducible con
`agente_multimodal/analizar_detecciones.py`.

| Clase | Recall de PIIA-1 | Precisión | Detecciones | Qué filtro separa |
|---|---:|---:|---:|---|
| `glass shatter` | 97,4 % | 14,9 % | 505 | El score **sí**: a ≥ 0,8 → 67 % de precisión con 93,5 % de recall |
| `lamp broken` | 97,5 % | 12,5 % | 625 | El score casi no (a ≥ 0,8: 25 %); top-2 por imagen → 94 % de recall |
| `tire flat` | 100 % | 8,2 % | 497 | El score casi no (a ≥ 0,8: 16 %); top-2 por imagen → 100 % de recall |
| `dent` | 32,3 % | 2,8 % | 3.356 | Ninguno (techo de SAM3) |
| `scratch` | 35,4 % | 3,4 % | 4.831 | Ninguno (techo de SAM3) |
| `crack` | 65,3 % | 0,9 % | 8.693 | Ninguno (techo de SAM3) |

Hallazgos que condicionan el diseño:

- **Los falsos positivos son falsas alarmas reales**, no duplicados ni cajas
  desplazadas: quitar duplicados baja las detecciones solo de 18.507 a
  17.263, y solo el 8 % de las de `dent`, el 10 % de `scratch` y el 2 % de
  `crack` caen sobre un daño real de su clase. Por eso `is_true_positive` es
  una vara justa para medir al modelo de visión.
- **El techo lo pone SAM3, no la visión.** En `dent`/`scratch`/`crack`, ni
  siquiera quedándose con las 5 mejores por imagen y clase se recupera más
  del 26 %, 25 % y 48 %. La visión solo verifica lo que SAM3 propone: un daño
  que SAM3 no marca no aparecerá en el informe. Limitación a declarar.

Filtro adoptado (`seleccion.py`, `FILTRO_PREVIO`): `glass shatter` con
score ≥ 0,5; en el resto de clases las 2 mejores por imagen y clase. **3.712
llamadas para 500 imágenes en vez de 18.507** (un 80 % menos), con 97 % de
recall en `glass shatter`, 94 % en `lamp broken` y 100 % en `tire flat` sobre lo
que PIIA-1 encontraba. Subir de 2 a 3 en `dent` costaría 337 llamadas más por
+4 puntos de recall: no compensa. Los valores de *k* se eligieron mirando estas
mismas imágenes, así que son algo optimistas; basta para una decisión gruesa.

Las detecciones que no pasan el filtro **no se descartan en silencio**: quedan
contadas por clase en `resumen_filtro_previo`.

## Por qué

Un falso positivo y un falso negativo no cuestan lo mismo dentro de un
informe de peritaje. Si el sistema trata la salida de PIIA-1 como verdad
absoluta, un falso positivo con score alto se convierte en una afirmación
económica falsa presentada con autoridad ("sustitución de neumático, 120 €")
en un documento que se supone objetivo, mucho peor que omitir un daño real.

Los datos de PIIA-1 lo confirman: la precisión bruta a threshold 0,3 es baja
en **todas** las clases (`glass_shatter` 15,3 %, `lamp_broken` 18,6 %,
`tire_flat` 19,0 %; y `dent`/`scratch`/`crack` peor, sin ningún threshold con
precisión y recall aceptables a la vez). Por eso no se excluye ninguna clase
(todas necesitan el mismo rigor), y por eso la empresa recomendó usar un LLM
con visión como segunda opinión: dado el recorte y la caja, comprobar si hay
consenso con la detección y así limpiar falsos positivos.

La tercera condición existe porque la tool de costes no falla cuando no hay
regla para una combinación (por ejemplo `dent` sobre un parabrisas): devuelve
coste 0 con una línea de aviso. Un hallazgo así "confirmado" saldría en el
informe con coste 0 €, sin que nadie lo note.

## Restricciones y supuestos

- Esta capa vive en el Agente 1 de PIIA2, no en PIIA-1: no cambia ninguna
  predicción, solo decide cómo se usa cada una aguas abajo.
- **`CATEGORY_REVIEW_THRESHOLD` siguen siendo placeholders, y los datos dicen
  que no valen tal cual.** Con los 0,7 actuales de `dent`/`scratch`/`crack`, el
  score ≥ 0,7 solo conserva el 4 %, 10 % y 30 % del recall de PIIA-1, porque el
  score casi no separa en esas clases; en `glass shatter` 0,6 se queda corto
  (a ≥ 0,8 la precisión sube de 36 % a 67 %). Pero **no se fijan sin medir a la
  visión**: si el modelo acierta, conviene exigir menos score y dejar que decida
  él; si no, el score es la única barrera. `agente_multimodal/evaluar_vision.py`
  calcula, para cada clase y cada umbral, la precisión y el recall de
  `confirmed` con y sin visión, y es lo que decide los 6 valores finales. Se
  recalibra si cambia la estrategia, el prompt o el dataset.
- Si una clase pasa por verificación CLIP + Tip-Adapter, su umbral puede
  bajar, porque ya tiene una capa de verificación adicional.
- El veredicto del modelo se **valida**: un `pieza_id` que no esté en el
  catálogo, o un `veredicto`/`severidad` fuera de los valores permitidos, se
  descarta (el hallazgo queda `incierto` o sin pieza), nunca se acepta tal cual.
- `needs_review` no significa "se descarta": significa que el informe lo debe
  presentar como pendiente de confirmación, nunca como hecho.

## Criterios de aceptación

1. Todo hallazgo que llega al agente de costes tiene `confidence_tier`
   (`confirmed` o `needs_review`) asignado antes de presupuestarse.
2. Un hallazgo es `confirmed` solo si pasan las tres condiciones (se prueba en
   `probar_vision_stub.py::probar_decidir_tier`).
3. Los hallazgos `needs_review` nunca aparecen en el informe con la misma
   redacción que los `confirmed`.
4. El coste total puede calcularse solo con los hallazgos `confirmed` y, por
   separado, con los pendientes presupuestables, para que quien lea sepa cuánto
   de la estimación es firme y cuánto provisional.
5. Los umbrales por clase están centralizados (`CATEGORY_REVIEW_THRESHOLD`),
   no repartidos por el código.
6. Antes de dar la tabla por definitiva, los 6 umbrales tienen detrás la curva
   medida con las detecciones etiquetadas.
7. Se mide la segunda opinión: con `is_true_positive` como verdad, cuántos
   falsos positivos rechaza cada modelo de visión y cuántos aciertos reales
   descarta por error.
