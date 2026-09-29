# PIIA2 — arquitectura multiagente y reparto final

Este documento es el punto de partida para los 3: describe el sistema completo,
el contrato de datos entre piezas, y quién hace qué. Los otros dos documentos
(`agente2-recuperacion-guia-victor.md`, `agente3-informe-guia-lucas.md`) dan
el detalle paso a paso de cada pieza — pero antes de leerlos, lee este.

## Qué construir

Un sistema de 3 agentes que, a partir de la salida de detección de daños de
PIIA-1 (CU-19), genere un informe de peritaje automático:

```text
Imagen -> PIIA-1 (ya construido) -> detecciones de daño
                                            |
                                            v
                          Agente 1 — Analista de daños (multimodal)
                          lee las detecciones + mira la imagen recortada
                          con un modelo de vision, decide confianza
                                            |
                                            v
                          Agente 2 — Recuperación (RAG)
                          por cada hallazgo, busca en una base vectorial
                          el procedimiento de reparación + precio
                                            |
                                            v
                          Agente 3 — Redactor
                          junta todo en un informe de peritaje agregado
```

## Por qué esta arquitectura

El enunciado de PIIA2 pide explícitamente: (1) un sistema **multiagente**,
(2) **multimodal**, (3) que parta de la salida de PIIA-1, (4) que recupere
información de una **BBDD vectorial**, (5) que genere un **informe
agregado**. Los 3 agentes cubren cada uno un punto de esos, y el orden
Agente1 → Agente2 → Agente3 es también el orden de dependencia: el 3 necesita
que el 1 y el 2 ya tengan un formato de salida estable para poder agregar
algo.

"Multimodal" no es opcional ni decorativo: el Agente 1 no debe limitarse a
leer el JSON de PIIA-1 (categoría, máscara, score) — también debe mirar el
recorte de imagen de cada daño con un modelo con visión (Claude o GPT con
visión, usando la API Key de la infraestructura del caso). Esto añade una
segunda fuente de evidencia, útil sobre todo para las clases que PIIA-1 no
detecta con fiabilidad (ver `agente-confianza-hallazgos.md`: ninguna clase
se excluye, pero `dent`/`scratch`/`crack` tienen un threshold de `confirmed`
más exigente y dependen más de esta segunda fuente de evidencia).

## Contrato de datos entre agentes

Este es el contrato que hay que respetar — si cada uno programa contra esto,
las piezas encajan sin necesidad de coordinarse en directo todo el rato.

### PIIA-1 → Agente 1 (ya existe, no hay que construirlo)

Cada `InstancePrediction` que produce `strategy.run(sample)`
(`ml/StrategyPipeline/schemas.py`): `category_id`, `score`, `mask`, `bbox`,
`area`, `metadata`. Ver `ml/scripts/infer_robust_single_image.py` para un
ejemplo de cómo convertir esto a JSON (`build_json_summary`).

### Agente 1 → Agente 2 y Agente 3

Un "hallazgo" (finding) por cada detección de PIIA-1, con un
`confidence_tier` asignado (`confirmed` o `needs_review` — ninguna detección
se descarta en esta capa):

```json
{
  "image_id": 123,
  "findings": [
    {
      "finding_id": "123-1",
      "category": "lamp_broken",
      "score": 0.94,
      "confidence_tier": "confirmed",
      "bbox_xywh": [120, 80, 60, 40],
      "vision_description": "Faro delantero derecho roto, cristal fragmentado visible.",
      "crop_image_path": "crops/123_lamp_broken_1.jpg"
    }
  ]
}
```

### Agente 2 → Agente 3

Por cada `finding_id` que le llega, un procedimiento + precio recuperados:

```json
{
  "finding_id": "123-1",
  "repair_procedure": "Sustitución completa del conjunto óptico delantero derecho.",
  "estimated_price_eur": 180.0,
  "source_doc": "procedimientos_faros.md#faro-roto"
}
```

### Agente 3 → salida final

El informe agregado (markdown como mínimo; PDF si da tiempo), con: resumen
de daños confirmados vs. pendientes de revisión, coste total desglosado
(solo `confirmed` vs. incluyendo `needs_review`), y el detalle por hallazgo.

## Restricciones y supuestos

- Cada agente se puede desarrollar y probar por separado si se respeta el
  contrato JSON de arriba — no hace falta esperar a que los otros dos estén
  terminados para empezar a programar contra datos de ejemplo.
- Las 6 clases de daño llegan al Agente 2/3 (ninguna se excluye, ver
  `agente-confianza-hallazgos.md`). El Agente 2 necesita procedimiento +
  precio para las 6, no solo para 3.
- Infraestructura: Google Colab Pro + API Key (para el modelo de visión del
  Agente 1 y el LLM del Agente 3; el Agente 2 puede usar la misma API para
  generar embeddings, o un modelo local si prefiere no gastar cuota).
- Los datos de precios/procedimientos son sintéticos — no hace falta que sean
  reales, pero sí consistentes y con formato estructurado (para que el RAG
  tenga algo bueno que recuperar).

## Criterios de aceptación

1. Dada la salida de PIIA-1 sobre una imagen con al menos un daño de
   cualquiera de las 6 clases, el sistema completo produce un informe con al
   menos un hallazgo, su procedimiento de reparación y su precio estimado.
2. El informe distingue visiblemente entre hallazgos `confirmed` y
   `needs_review`.
3. Cada agente puede ejecutarse y probarse de forma aislada, pasándole datos
   de ejemplo con el formato de arriba, sin depender de que los otros dos
   agentes estén implementados.
4. El Agente 1 usa la imagen (no solo el JSON de PIIA-1) para al menos una
   parte de su decisión — si se quita esa parte, dejaría de ser multimodal.

## Reparto final

| Agente | Quién | Cuándo | Guía |
|---|---|---|---|
| Agente 1 — Analista de daños (multimodal) + integración general | Lucía | Ya | (trabaja directamente con Claude en este repo) |
| Agente 2 — Recuperación / RAG + tabla de precios | Víctor | Ya | [`agente2-recuperacion-guia-victor.md`](agente2-recuperacion-guia-victor.md) |
| Agente 3 — Redactor del informe | Lucas | Se incorpora en ~1 semana | [`agente3-informe-guia-lucas.md`](agente3-informe-guia-lucas.md) |

Lucía coordina la integración final de las 3 piezas.
