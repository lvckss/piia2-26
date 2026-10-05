# PIIA2 — arquitectura multiagente y reparto final

Este documento es el punto de partida para los 3: describe el sistema
completo, el contrato de datos entre piezas y quién hace qué. Las guías de
cada agente (`agente2-recuperacion-guia-victor.md`,
`agente3-informe-guia-lucas.md`) dan el detalle paso a paso, pero antes de
leerlas, lee este.

> **Versión 2 (reunión con la empresa).** Sustituye a la primera versión. Lo
> que cambia: la empresa nos entregó un paquete de datos con una herramienta
> de costes ya hecha, pólizas y legislación para el RAG; usamos la API de
> OpenAI (no Anthropic); el modelo de visión debe dar una segunda opinión
> sobre cada detección (para limpiar falsos positivos) y además decidir qué
> pieza del coche está dañada y con qué severidad. El informe, de momento, en
> markdown.

## Qué construir

Un sistema de 3 agentes que, a partir de la salida de detección de daños de
PIIA-1 (CU-19) y de los datos del siniestro, genere un informe de peritaje
automático con el coste de reparación, la cobertura de la póliza y la
indemnización estimada:

```text
Foto -> PIIA-1 (SAM3, ya construido) -> detecciones (clase, caja, score)
                                              |
                                              v
                    Agente 1 — Analista de daños (multimodal)
                    mira la foto con un modelo de visión y, por cada
                    detección: ¿es un daño real? ¿qué pieza? ¿qué severidad?
                    + decide la confianza (confirmed / needs_review)
                                              |
                                              v
                    Agente 2 — Costes, cobertura y normativa
                    (a) tool de costes de la empresa -> presupuesto
                    (b) cobertura, pérdida total e indemnización según póliza
                    (c) RAG sobre pólizas y legislación -> citas
                                              |
                                              v
                    Agente 3 — Redactor
                    informe de peritaje en markdown (cifras exactas
                    de los agentes anteriores, nunca inventadas)
```

## Qué trae ya hecho el paquete de la empresa

`piia2_paquete_datos.zip` (extraerlo en la raíz del repo como
`piia2_paquete_datos/`; está en `.gitignore`, cada uno lo extrae en su copia).
Su `README.md` describe todos los ficheros; lo que nos importa:

| Pieza | Para qué sirve |
|---|---|
| `scripts/estimar_coste.py` | Tool **determinista** de costes: `estimar_coste(vehiculo_id, danos, region, tipo_taller, acabado, tipo_pieza)` con `danos = [{clase, pieza_id, severidad}]` → líneas de presupuesto, desglose, IVA 21 %, `arrastres_posibles`. También `valor_venal(...)` y `perdida_total(...)`. |
| `data/piezas.csv`, `reglas_dano.csv` | Catálogo de 35 piezas y 45 reglas (clase CarDD × tipo de zona × severidad → acción de reparación). |
| `data/vehiculos.csv` | 27 modelos (marca, segmento, factor de precio, ADAS). |
| `data/polizas.csv` + `docs/polizas_sinteticas/*.md` | 4 pólizas ficticias (parámetros y condiciones en texto). |
| `docs/legal/*.txt` | 7 textos legales **reales** (BOE, EUR-Lex) para el RAG. |
| `data/preguntas_evaluacion.csv` | 25 preguntas con respuesta y fuente esperadas, para evaluar el RAG. |
| `data/siniestros_sinteticos.csv` | 1.200 siniestros sintéticos con coste facturado (`split` train/val/test) para evaluar la parte de costes. |

**Todo lo que no es legislación es sintético.** Sirve para prototipar, no para
estimar costes reales (la empresa lo avisa).

**Lo que la empresa deja explícitamente a nuestro cargo:** CarDD no da piezas
ni severidad, así que traducir *visión → pieza + severidad* es trabajo del
equipo. Esa traducción es lo que hace el Agente 1.

## Por qué esta arquitectura

El enunciado de PIIA2 pide (1) un sistema **multiagente**, (2) **multimodal**,
(3) que parta de la salida de PIIA-1, (4) que recupere información de una
**BBDD vectorial** y (5) que genere un **informe agregado**. Cada agente cubre
un punto, y el orden Agente 1 → 2 → 3 es también el de dependencia.

"Multimodal" no es decorativo: el Agente 1 no se limita a leer el JSON de
PIIA-1; mira la foto (entera, con la caja marcada, y el recorte) para decidir
si el daño existe y sobre qué pieza está. Eso es justo la "segunda opinión"
que propuso la empresa para limpiar falsos positivos, y es necesario porque
PIIA-1 tiene baja precisión en todas las clases (en `dent`, `scratch` y
`crack` especialmente; ver `agente-confianza-hallazgos.md`).

## Entrada del siniestro (no la produce ningún agente)

La tool de costes necesita saber el coche, el taller y la póliza. Esos datos
son **entrada del sistema**, como en un parte real, y no se deducen de la
foto (las fotos de CarDD son coches cualesquiera, casi ninguno está en el
catálogo de 27 modelos):

```json
{
  "vehiculo_id": "V05",
  "region": "Madrid",
  "tipo_taller": "multimarca",
  "acabado": "metalizado",
  "tipo_pieza": "oem",
  "poliza_id": "P-TR-FR300",
  "rol": "propio",
  "edad_anios": 3,
  "km": 42000
}
```

Valores válidos: `vehiculo_id` de `vehiculos.csv`; `region` y `tipo_taller` de
`tarifas.csv`; `acabado` ∈ `solido | metalizado | perlado_tricapa`;
`tipo_pieza` ∈ `oem | aftermarket`; `rol` ∈ `propio | tercero_perjudicado`
(con `tercero_perjudicado`, `poliza_id` va vacío). Ejemplo completo en
`app/agentes/ejemplos_contrato/contexto_siniestro.json`.

> No confundir con el `vehicle_type` (sedán, SUV...) que se quitó de PIIA-1:
> aquello era una etiqueta inventada por nosotros; esto es un dato de entrada
> real de la tool de la empresa.

## Contrato de datos entre piezas

Si cada uno programa contra esto, las piezas encajan sin necesidad de
coordinarse en directo. Los ejemplos reales (con cifras calculadas por la tool
de la empresa) están en `app/agentes/ejemplos_contrato/`.

### PIIA-1 → Agente 1

Un JSON por imagen con las detecciones (`image_id`, `image_path`,
`image_width`, `image_height`, `predictions[]` con `instance_index`,
`damage_class`, `score`, `bbox_xywh`...). Se genera **una sola vez en Colab**
para ~500 imágenes de `val`/`test` (notebook
`app/agentes/agente_multimodal/colab/exportar_detecciones.ipynb`) y desde ahí
nadie necesita cargar SAM3. Cada detección va marcada con `is_true_positive`
contra las anotaciones reales de CarDD, lo que permite **medir** la segunda
opinión del modelo de visión.

### Agente 1 → Agente 2 y Agente 3

Un *hallazgo* (finding) por cada detección de PIIA-1. Ninguna se descarta en
esta capa; lo que no se confirma queda como `needs_review`:

```json
{
  "image_id": 160,
  "findings": [
    {
      "finding_id": "160-1",
      "category": "lamp broken",
      "clase_tool": "lamp_broken",
      "score": 0.91,
      "score_tier": "confirmed",
      "confidence_tier": "confirmed",
      "bbox_xywh": [700.0, 40.0, 250.0, 200.0],
      "vision_verdict": "confirmado",
      "pieza_id": "FARO_DEL_D",
      "severidad": "grave",
      "regla_coste_aplicable": true,
      "vision_description": "Faro delantero derecho roto, carcasa fragmentada.",
      "crop_image_path": "crops/160_lamp_broken_1.jpg"
    }
  ]
}
```

| Campo | Significado |
|---|---|
| `category` / `clase_tool` | Clase de PIIA-1 (`lamp broken`) y su nombre para la tool de costes (`lamp_broken`). |
| `score_tier` | Tier solo por el score de PIIA-1 (umbral por clase). |
| `vision_verdict` | `confirmado` · `rechazado` (falso positivo) · `incierto`. |
| `pieza_id`, `severidad` | Pieza del catálogo (`piezas.csv`) y `leve`/`moderado`/`grave`; `null` si el veredicto es `rechazado`. Validados contra el catálogo: una pieza inventada por el modelo se descarta. |
| `regla_coste_aplicable` | `true` si `reglas_dano.csv` tiene regla para (clase, zona de la pieza, severidad). **Si es `false`, la tool de costes no calcula nada** y solo devuelve una línea de aviso, así que ese daño no se puede presupuestar. |
| `confidence_tier` | **Final**: `confirmed` solo si el score pasa el umbral de su clase, la visión confirma **y** hay pieza con regla de coste. Si no, `needs_review`. |

### Agente 2 → Agente 3

Por siniestro, dos escenarios de coste (con los hallazgos `confirmed` solo, y
añadiendo los pendientes que sí se pueden presupuestar), más lo que quedó
fuera y los extractos de normativa que sirven de justificación:

```json
{
  "image_id": 160,
  "contexto": { "...": "el contexto del siniestro de arriba" },
  "valor_venal_eur": 17491.54,
  "umbral_perdida_total": 0.75,
  "escenarios": {
    "confirmados": {
      "hallazgos_incluidos": ["160-1", "160-4"],
      "estimacion": { "desglose": {}, "subtotal_sin_iva_eur": 1019.46, "iva_eur": 214.09, "total_con_iva_eur": 1233.55, "lineas": [], "arrastres_posibles": [] },
      "cobertura": { "cubierto": true, "motivo": "Daños propios por colisión", "franquicia_eur": 300.0, "perdida_total": false, "indemnizacion_estimada_eur": 933.55 }
    },
    "con_pendientes": { "...": "misma forma" }
  },
  "hallazgos_fuera_del_coste": [ { "finding_id": "160-2", "motivo": "rechazado_por_vision" } ],
  "normativa": [ { "tema": "pérdida total", "extracto": "5.1 Habrá pérdida total cuando...", "fuente": "docs/polizas_sinteticas/P-TR-FR300.md#5. Pérdida total" } ]
}
```

`estimacion` es, tal cual, la salida de `estimar_coste` (incluye `lineas` y
`arrastres_posibles`). Los motivos de `hallazgos_fuera_del_coste` son
`rechazado_por_vision`, `sin_pieza_o_severidad` y `sin_regla_de_coste`. Los
`arrastres_posibles` son daños asociados probables (radiador, airbag...) que
**no** entran en el coste: el informe los muestra aparte como posibles.

### Agente 3 → salida final

Informe de peritaje en **markdown** (el PDF, sobre todo con imágenes, es
complejo: la empresa dijo que se vea más adelante).

## Decisiones tomadas y pendientes

| Tema | Estado |
|---|---|
| Proveedor y modelos | **Decidido por la empresa:** API de OpenAI con la clave que nos dieron (solo en variable de entorno `OPENAI_API_KEY`, **nunca** en el repo ni en el chat). Recomiendan un modelo concreto, pero piden probar varios y comparar si compensa el esfuerzo. El id del modelo va en `OPENAI_MODEL` o en el parámetro `modelo`; usad el id exacto que figure en la cuenta. |
| Presupuesto | La empresa dice que 50-100 € está bien y no restringe. Aun así: cache de respuestas (`cache_dir` en el Agente 1), comparar modelos solo con 30-50 imágenes, y el modelo elegido con el resto. |
| Veredicto de visión | **Asumido (confirmar):** no descarta nada; un rechazo deja el hallazgo como `needs_review` con `vision_verdict = rechazado`, y el informe lo muestra aparte, fuera del coste. Alternativa: sacarlo del informe. |
| `vehiculo_id` | **Asumido (confirmar):** dato de entrada del siniestro, no deducido por el LLM. |
| Framework | La empresa trabaja con **Google ADK** y lo recomienda. La tool de la empresa ya trae un ejemplo (`scripts/ejemplo_tool.py`: funciones Python normales pasadas como `tools=[...]` a un `Agent`), **sin probar** con la librería. Plan: toda la lógica son funciones Python normales, testeables sin red; se envuelven en agentes de ADK al final. Antes de comprometerse, hacer una prueba mínima de ADK con un modelo de OpenAI (probablemente vía un adaptador tipo LiteLLM; **comprobarlo en su documentación**). |
| Formato del informe | Markdown ahora; PDF más adelante, solo si sobra tiempo. |
| Reparador con API (puente a un taller real) | Opcional según la empresa; solo si no complica. |

## Evaluación (cómo sabremos que funciona)

| Qué | Cómo |
|---|---|
| Segunda opinión de visión (Agente 1) | Con las ~500 detecciones etiquetadas (`is_true_positive`): ¿cuántos falsos positivos rechaza la visión y cuántos aciertos reales descarta por error? Misma muestra de 30-50 imágenes para cada modelo → tabla de comparación de modelos (precisión del filtro vs. coste en €). |
| Costes (Agente 2) | Con los siniestros sintéticos (`split` val/test): llamar a la tool con los daños reales da un error (MAPE) de ≈ 9 % contra `coste_facturado_sin_iva_eur`; es el suelo. Ojo: esos siniestros **no tienen foto**, así que sirven para evaluar la parte de costes y cobertura, no la cadena completa desde la imagen. |
| RAG (Agente 2) | Las 25 preguntas de `preguntas_evaluacion.csv`: ¿aparece la fuente esperada entre los k fragmentos recuperados? |
| Informe (Agente 3) | Revisión automática de que **todas** las cifras en euros del informe coinciden con las de la salida del Agente 2. |

## Restricciones y supuestos

- Cada agente se puede desarrollar y probar por separado con los ejemplos de
  `app/agentes/ejemplos_contrato/`, sin esperar a los otros dos.
- Los datos de piezas, precios, tiempos y pólizas son sintéticos; solo la
  legislación es real. Los informes deben llevar el aviso de que no sustituyen
  una valoración pericial.
- El paquete de la empresa y el dataset CarDD **no se suben a git** (están en
  `.gitignore`).
- La clave de la API nunca se escribe en ficheros del repo.

## Criterios de aceptación

1. Dada la salida de PIIA-1 sobre una imagen y los datos del siniestro, el
   sistema produce un informe con: hallazgos (pieza y severidad), coste
   desglosado, cobertura/indemnización y fuentes normativas.
2. El informe distingue visiblemente entre hallazgos `confirmed`,
   `needs_review` y los rechazados por la visión, y da el coste de dos formas
   (solo confirmados y con pendientes).
3. Cada agente se ejecuta y se prueba de forma aislada con los ejemplos del
   contrato.
4. El Agente 1 usa la imagen (no solo el JSON de PIIA-1): si se quita la
   visión, deja de decidir pieza, severidad y confirmación.
5. Hay una comparación con números de al menos dos modelos de visión y una
   evaluación del RAG con las 25 preguntas.

## Reparto final

| Agente | Quién | Cuándo | Guía |
|---|---|---|---|
| Agente 1 — Analista de daños (multimodal) + integración general y ADK | Lucía | Ya | `app/agentes/agente_multimodal/README.md` |
| Agente 2 — Costes, cobertura y RAG | Víctor | Ya | [`agente2-recuperacion-guia-victor.md`](agente2-recuperacion-guia-victor.md) |
| Agente 3 — Redactor del informe | Lucas | Se incorpora en ~1 semana | [`agente3-informe-guia-lucas.md`](agente3-informe-guia-lucas.md) |

Lucía coordina la integración final de las 3 piezas.
