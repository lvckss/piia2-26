# Salidas reales del Agente 1 (lote de 30 imágenes)

Las 30 salidas **reales** del Agente 1 sobre fotos de CarDD (`val` y `test`), para que el Agente 2 y el Agente 3 se prueben con datos que salen de ejecutar el sistema y no solo con el ejemplo escrito a mano (`../agente1_salida.json`). Las generó [`generar_lote.py`](../../agente_multimodal/generar_lote.py) (Issue #43) con el modelo `gpt-6-luna` el 2026-10-17: 30 imágenes elegidas con semilla 42 y al menos 3 aciertos de PIIA-1 por clase. En total hay 234 hallazgos: 94 `confirmed` y 140 `needs_review`. Los niveles (`score_tier` y `confidence_tier`) se calcularon el 2026-10-17 con los umbrales de partida (entonces eran 48 `confirmed` y 186 `needs_review`) y se recalcularon el 2026-10-31 con los calibrados en la Issue #44 (`dent`, `scratch` y `crack` a 0,3; el resto sigue en 0,6); lo demás de cada hallazgo no cambió. Desde la Issue #28 cada salida lleva además `vehiculo`, la categoría del coche que propone el modelo.

Un fichero por imagen, con el `image_id` de seis cifras (`001236.json`). Seis para empezar, por los casos límite que cubren:

| Fichero | Imagen | Hallazgos | `confirmed` | Qué sirve para probar |
|---|---|---|---|---|
| [`001236.json`](001236.json) | 1236 | 9 | 5 | Es la más completa: cuatro clases firmes (`crack`, `dent`, `lamp broken`, `tire flat`) y dos daños graves. |
| [`000341.json`](000341.json) | 341 | 5 | 4 | Pequeña y de coste alto: tres hallazgos graves sobre el mismo parabrisas (dos `glass shatter` y un `crack`) y una grieta leve en el capó. |
| [`000381.json`](000381.json) | 381 | 9 | 3 | Tiene un `incierto`, un hallazgo sin regla de coste y `dent` y `scratch` sobre la misma pieza: las ramas de «no se puede presupuestar». |
| [`000082.json`](000082.json) | 82 | 10 | 4 | El mismo golpe con varias clases: `crack` y dos `scratch` sobre el paragolpes trasero. |
| [`001245.json`](001245.json) | 1245 | 9 | 4 | Cuatro hallazgos firmes (`crack`, `dent` y dos `scratch`, con score de 0,40 a 0,55) sobre el mismo paragolpes trasero, que con los umbrales de partida quedaban todos pendientes. Incluye una `lamp broken` rechazada por la IA aunque PIIA1 acertó (`1245-1`). |
| [`003478.json`](003478.json) | 3478 | 5 | 0 | Ningún hallazgo firme: todo queda pendiente (cuatro rechazados por la IA y un `scratch` confirmado sin regla de coste). |

Qué hay y qué no:

- Tienen el formato del contrato Agente 1 → Agente 2 y 3 ([`piia2-arquitectura-multiagente.md`](../../../../docs/piia2-arquitectura-multiagente.md)) y pasan `validar_salida_agente1`.
- **`vehiculo`** (Issue #28) se añadió el 2026-10-29 con una consulta de categoría por imagen (`gpt-6-luna`) y es lo único que cambió en estos JSON desde el 2026-10-17: los hallazgos son los del lote original. Hoy la caché no los reproduce (los recortes se guardan con otra codificación JPEG y las respuestas del modelo varían), así que volver a ejecutar el Agente 1 sobre estas fotos daría otros hallazgos. Reparto de categorías: 11 `desconocido` (9 primeros planos o vistas parciales en los que no se distingue el tipo, un camión y una camioneta pickup, que el catálogo no incluye), 10 `C`, 3 `B`, 3 `SUV-C` y 3 `FURG`. Confianza declarada: 13 `baja`, 15 `media` y 2 `alta`. Una persona no las ha revisado una a una.
- **No hay fotos ni recortes.** `crop_image_path` es relativo a la carpeta del lote (`crops/...`) y esos recortes no están en el repositorio; el Agente 2 y el Agente 3 no los necesitan.
- **No traen datos del siniestro** (vehículo, taller, póliza): para probar el Agente 2 hay que combinarlas con un contexto de prueba, por ejemplo `../contexto_siniestro.json`.
- Los textos de `vision_description` son salida del modelo; una persona no los ha revisado uno a uno.
- El lote se eligió para cubrir las seis clases con aciertos de PIIA-1, así que el reparto entre `confirmed` y `needs_review` no es representativo ni es una evaluación del sistema.
- Para regenerarlas hacen falta el export de PIIA-1, las fotos de CarDD y la clave de la empresa (ver el README de `agente_multimodal`); la caché de respuestas evita volver a pagar las consultas ya hechas. Regenerarlas hoy daría hallazgos distintos a los versionados (ver `vehiculo` arriba).
