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

# Calibrados en la Issue #44 (ver "Restricciones"); se recalibran si cambia la estrategia, el prompt, el juez o el dataset.
CATEGORY_REVIEW_THRESHOLD = {
    "dent": 0.3, "scratch": 0.3, "crack": 0.3,
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
score, se puede relajar. La calibración de la Issue #44 lo hace en `dent`,
`scratch` y `crack`: su umbral es 0,3 y, como PIIA-1 no entrega detecciones
por debajo de 0,3, en esas clases decide la visión (con pieza y regla de
coste) y el score ya no frena nunca. En `lamp broken`, `glass shatter` y
`tire flat` el score sigue frenando desde 0,6.

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

- **Los falsos positivos no son duplicados** (quitar duplicados baja las
  detecciones solo de 18.507 a 17.263), **pero tampoco son todos falsas
  alarmas.** Al mirar a mano casos que el modelo de visión confirmaba y CarDD
  marcaba como falso positivo en `dent`/`scratch`/`crack`, había daño real en
  la caja (por ejemplo, una grieta en la esquina de un paragolpes que CarDD no
  anota): CarDD no anota todos los daños, y el criterio de IoU de máscara ≥ 0,5
  es muy estricto para cajas pequeñas o sueltas. Por eso `is_true_positive`
  **infravalora a la visión en esas tres clases**. Es una vara razonable en
  `glass shatter`, `lamp broken` y `tire flat`; en las otras tres, comparar
  modelos con ella sirve solo en términos relativos, y medir de verdad exige
  revisar a mano una muestra de detecciones.
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

Los datos de PIIA-1 lo confirman: con las 500 imágenes exportadas, la
precisión bruta a threshold 0,3 es baja en **todas** las clases (`glass shatter`
14,9 %, `lamp broken` 12,5 %, `tire flat` 8,2 %, `dent` 2,8 %, `scratch` 3,4 %
y `crack` 0,9 %; ver la tabla de «Filtro previo»), y en `dent`/`scratch`/`crack`
ningún threshold da a la vez una precisión y un recall aceptables. Por eso no se excluye ninguna clase
(todas necesitan el mismo rigor), y por eso la empresa recomendó usar un LLM
con visión como segunda opinión: dado el recorte y la caja, comprobar si hay
consenso con la detección y así limpiar falsos positivos.

La tercera condición existe porque la tool de costes no falla cuando no hay
regla para una combinación (por ejemplo `dent` sobre un parabrisas): devuelve
coste 0 con una línea de aviso. Un hallazgo así "confirmado" saldría en el
informe con coste 0 €, sin que nadie lo note.

## Alcance

- **Incluido:** el filtro previo de detecciones por clase
  ([`seleccion.py`](../app/agentes/agente_multimodal/seleccion.py)); el nivel de
  confianza solo por score (`classify_confidence`); el nivel final que combina
  score, veredicto de visión y posibilidad de presupuestar (`decidir_tier`); el
  registro de lo que el filtro descarta.
- **Fuera de alcance:** detectar daños (PIIA-1); la consulta al modelo de visión
  y la validación de su respuesta, que se especifican en
  [`interpretacion-danos-imagen.md`](interpretacion-danos-imagen.md); calcular
  costes (Agente 2) y redactar el informe (Agente 3), que consumen el nivel de
  confianza; calibrar los umbrales con el modelo real, que se hizo en la
  [Issue #44](https://github.com/lvckss/piia2-26/issues/44) (AC-006).

## Restricciones y supuestos

- Esta capa vive en el Agente 1 de PIIA2, no en PIIA-1: no cambia ninguna
  predicción, solo decide cómo se usa cada una aguas abajo.
- **Criterio de los umbrales `CATEGORY_REVIEW_THRESHOLD`** (Issue #44, plan
  v1.4, decisión D-6). Para cada clase se elige el valor más bajo de la rejilla
  (0,3 a 0,9) para el que, entre los hallazgos que la visión confirma con pieza
  y regla de coste y tienen score ≥ umbral, el límite inferior del intervalo de
  Wilson al 95 % de la proporción de **daño real** es al menos el 95 %, con al
  menos 5 casos decididos; si ningún valor lo alcanza, se mantiene el actual. El
  daño real lo establece un modelo juez (`gpt-6.1-terra`, esfuerzo `high`, prompt
  `abe617f3`) sobre el recorte y la clase de la caja; son etiquetas de un modelo,
  no verdad humana. Con las 500 imágenes (1.558 candidatos) salen `dent`,
  `scratch` y `crack` a 0,3 (daño real del 100 %, 98,9 % y 99,4 %; límites
  inferiores de 98,7 %, 97,6 % y 97,9 %; con la revisión humana de sus `dudo`,
  98,7 %, 98,2 % y 98,4 %, y los mismos umbrales). `lamp broken`, `glass shatter` y
  `tire flat` se quedan en 0,6 **porque ningún valor de la rejilla llega al
  mínimo** (con 0,6, límites inferiores de 81,2 %, 90,3 % y 86,5 %; el mejor valor
  de la rejilla, 82,5 % con 0,8, 94,3 % con 0,9 y 90,1 % con 0,9): su 0,6 **no
  está demostrado**, es el valor de partida que se conserva. Los hallazgos firmes
  de las 500 imágenes pasan de 799 a 1.531. Se recalibra si cambia la
  estrategia, el prompt, el juez o el dataset.
  `python tabla_umbrales.py --criterio …` lo reproduce (ver el README del agente).
- **Lo que la tabla de umbrales no mide ni demuestra.** (1) *La clase de la
  caja:* en `dent` y `crack` un hallazgo firme tiene daño real casi siempre (100 %
  y 99 % según el juez), pero la clase de la caja solo es correcta en el 60 % y el
  66 %; el resto es daño de otro tipo. Como la regla de coste se elige por clase,
  zona y severidad (`reglas_dano.csv`), el coste puede corresponder a otra
  operación; el umbral no lo corrige, así que lo revisa una persona. (2) *Los
  `dudo`* del juez y los hallazgos sin etiqueta quedan fuera del denominador; si
  todos los `dudo` fueran `no`, ninguna clase llegaría al 95 %. (3) *Validación del
  juez:* una sola persona y 60 etiquetas, todas de `dent`, `scratch` y `crack`
  (49 comparables sin `dudo`: acuerdo exacto del 84 %, 41 de 49, IC 71-91 %; «hay
  daño» 49 de 49; kappa 0,34, que no es interpretable porque no hay ningún `no`
  humano). Las 60 primeras etiquetas se hicieron con el score y la respuesta de la
  IA a la vista. **De los `no` del juez solo 4 se han contrastado con una persona
  (la revisión de los `dudo` y `no`: 2 `si`, 1 `no` y 1 `dudo`), y en `lamp
  broken`, `glass shatter` y `tire flat` no hay ninguna etiqueta humana**: sus
  umbrales, que no cambian, descansan solo en el juez. Las etiquetas están en
  `agente_multimodal/etiquetas/`. (4) *Pieza y severidad* no se
  miden aquí (CarDD no trae esas etiquetas). (5) *Correlación:* el juez y el modelo
  de visión pueden fallar parecido si son de la misma familia; esta validación no
  lo descarta. (6) *`is_true_positive` infravalora a la visión* en `dent`,
  `scratch` y `crack`: de los 1.134 candidatos de esas clases que PIIA-1 daba por
  fallo, el juez ve daño real en 1.037 (99,2 % de los 1.045 decididos), y en las
  60 etiquetas humanas, 52 de 52 decididos eran daño real (43 `si`, 9 `otra`, 0
  `no`, 8 `dudo`); por eso la medida de la precisión se hace con las etiquetas del
  juez y no con `is_true_positive`. (7) *Un solo modelo de visión* (`gpt-6-luna`):
  los umbrales son de ese modelo y se repiten si cambia.
- Si una clase pasa por verificación CLIP + Tip-Adapter, su umbral puede
  bajar, porque ya tiene una capa de verificación adicional.
- El veredicto del modelo se **valida**: un `pieza_id` que no esté en el
  catálogo, o un `veredicto`/`severidad` fuera de los valores permitidos, se
  descarta (el hallazgo queda `incierto` o sin pieza), nunca se acepta tal cual.
- **No se puede medir si la pieza y la severidad que da el modelo son
  correctas:** CarDD no trae esas etiquetas. Eso requiere revisar a mano una
  muestra; `is_true_positive` solo mide si la detección de PIIA-1 acertó.
- `needs_review` no significa "se descarta": significa que el informe lo debe
  presentar como pendiente de confirmación, nunca como hecho.

## Acceptance Criteria

**Cómo leer la columna de verificación.** *Verificado*: el comando se ejecuta y
pasa. *Parcial*: parte del criterio está verificada y se indica cuál.
*Pendiente*: no hay verificación todavía, con el motivo o la Issue que la
cubrirá. Los comandos se ejecutan desde `app/agentes/agente_multimodal/`; los
que usan el export de 500 imágenes o el paquete de datos de la empresa se saltan
con un aviso si no están en local. Los criterios AC-001 a AC-007 son los siete
criterios originales, con el mismo orden.

| ID | Dado / Cuando | Resultado esperado | Verificación y estado |
|---|---|---|---|
| AC-001 | Cualquier hallazgo que el Agente 1 entrega al agente de costes. | Tiene `confidence_tier` con valor `confirmed` o `needs_review` antes de presupuestarse. | `python probar_agente1_stub.py` comprueba los niveles de los tres hallazgos de un ejemplo. **Verificado.** |
| AC-002 | Un hallazgo con score, veredicto de visión, pieza y regla de coste. | Es `confirmed` solo si el score pasa el umbral de su clase, la visión lo confirma, hay pieza y existe regla de coste; cualquier otra combinación es `needs_review`. | `python probar_vision_stub.py` (`probar_decidir_tier`: las 7 combinaciones y, para cada clase, el valor justo por encima y por debajo de su umbral: 0,30 y 0,29 en `dent`, `scratch` y `crack`; 0,60 y 0,59 en las otras tres). **Verificado.** |
| AC-003 | Un informe con hallazgos `confirmed` y `needs_review`. | Cada `confirmed` aparece solo bajo «Daños confirmados». Cada `needs_review` incluido en el escenario `con_pendientes` aparece solo bajo «Daños pendientes de revisión», con todos sus motivos, y los que quedan fuera del coste aparecen solo bajo «Detecciones no incluidas en el coste», con su motivo. Ningún `needs_review` aparece bajo «Daños confirmados». Lo comprueba [`specs/31-informe-peritaje.md#AC-002`](31-informe-peritaje.md). | **Pendiente.** Depende del Agente 3 ([Issue #31](https://github.com/lvckss/piia2-26/issues/31)). |
| AC-004 | El Agente 2 presupuesta los hallazgos. | Calcula el coste total solo con los `confirmed` y, por separado, con los pendientes presupuestables, para que quien lea sepa cuánto de la estimación es firme y cuánto provisional. | **Pendiente.** Depende del Agente 2 ([Issue #30](https://github.com/lvckss/piia2-26/issues/30)). El ejemplo [`agente2_salida.json`](../app/agentes/ejemplos_contrato/agente2_salida.json) muestra los dos escenarios. |
| AC-005 | Los umbrales de revisión por clase. | Están definidos en un único sitio, `CATEGORY_REVIEW_THRESHOLD` de [`confianza.py`](../app/agentes/agente_multimodal/confianza.py), sin repetirse en otros módulos. | `git grep -n "CATEGORY_REVIEW_THRESHOLD" -- "*.py"`: la definición y la lectura de `decidir_tier` están solo en `confianza.py`; `tabla_umbrales.py` la lee para calibrar y reproducir la tabla, y el resto son comentarios. `UMBRALES_DE_PARTIDA` de `etiquetado.py` son los valores anteriores a la calibración (0,7 y 0,6), solo para reproducir las muestras de etiquetado y la tabla antes y después, y no los lee ninguna decisión de nivel. **Verificado.** |
| AC-006 | La tabla de umbrales por clase, antes de darla por definitiva. | Cada uno de los 6 umbrales tiene detrás la curva medida de precisión y recall con las detecciones etiquetadas. | **Verificado** ([Issue #44](https://github.com/lvckss/piia2-26/issues/44)). `python evaluar_vision.py --modelos gpt-6-luna --n-imagenes 500 --max-llamadas 4000 --salida <carpeta> --ejecutar` sobre las 500 imágenes: 3.712 filas, 0 llamadas facturadas desde la caché y una segunda ejecución con el mismo resultado, con la precisión y el recall de `confirmed` por clase y umbral (con `is_true_positive`). `python tabla_umbrales.py --salidas <salida_agente1_500> --etiquetas etiquetas/etiquetas_juez.csv --criterio` da, con las etiquetas del juez, la precisión por clase y umbral y los 6 valores; `python probar_tabla_umbrales_stub.py` lo comprueba con datos sintéticos y, con los datos reales, que lo aplicado en `confianza.py` es lo que sale del criterio. **Límite:** en `lamp broken`, `glass shatter` y `tire flat` ningún valor llega al mínimo y se mantiene 0,6, que no está demostrado (ver «Restricciones y supuestos»). |
| AC-007 | Las detecciones etiquetadas con `is_true_positive` como verdad. | Se mide la segunda opinión: cuántos falsos positivos rechaza cada modelo de visión y cuántos aciertos reales descarta por error. | **Verificado para un modelo** (`gpt-6-luna`, [Issue #44](https://github.com/lvckss/piia2-26/issues/44)). `python probar_evaluar_vision_stub.py` verifica la herramienta con un modelo simulado, y la medición real sobre las 500 imágenes (comando de AC-006) da que la visión rechaza entre el 10 % (`scratch`) y el 93 % (`tire flat`) de los falsos positivos de PIIA-1 y descarta entre el 0 % y el 9 % de sus aciertos. `is_true_positive` como verdad infravalora a la visión en `dent`, `scratch` y `crack` (ver «Restricciones y supuestos»). Comparar otros modelos queda fuera de alcance. |
| AC-008 | Las 500 imágenes exportadas (18.507 detecciones) y el filtro previo de `seleccion.py`. | Quedan 3.712 candidatas (el 20 %): `glass shatter` con score ≥ 0,5 y las 2 mejores por imagen en las demás clases. Se conserva al menos el 97 % del recall de PIIA-1 en `glass shatter`, el 99 % en `tire flat` y el 93 % en `lamp broken`. | `python probar_seleccion_stub.py` (`probar_export_real`). **Verificado** con el export presente. |
