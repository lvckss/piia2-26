# Salidas reales del Agente 1 (muestra)

Cinco salidas **reales** del Agente 1 sobre fotos de CarDD, para que el Agente 2 y el Agente 3 se prueben con datos que salen de ejecutar el sistema y no solo con el ejemplo escrito a mano (`../agente1_salida.json`). Las generó [`generar_lote.py`](../../agente_multimodal/generar_lote.py) (Issue #43) con el modelo `gpt-6-luna` el 2026-10-17, dentro de un lote de 30 imágenes, y se eligieron para cubrir casos distintos.

| Fichero | Imagen | Hallazgos | `confirmed` | Qué sirve para probar |
|---|---|---|---|---|
| [`001236.json`](001236.json) | 1236 | 9 | 4 | Es la más completa: cuatro clases firmes (`crack`, `dent`, `lamp broken`, `tire flat`) y dos daños graves. |
| [`000341.json`](000341.json) | 341 | 5 | 4 | Pequeña y de coste alto: tres hallazgos graves sobre el mismo parabrisas (dos `glass shatter` y un `crack`) y una grieta leve en el capó. |
| [`000381.json`](000381.json) | 381 | 9 | 2 | Tiene un `incierto`, un hallazgo sin regla de coste y `dent` y `scratch` sobre la misma pieza: las ramas de «no se puede presupuestar». |
| [`000082.json`](000082.json) | 82 | 10 | 3 | El mismo golpe con varias clases: `crack` y dos `scratch` sobre el paragolpes trasero. |
| [`001245.json`](001245.json) | 1245 | 9 | 0 | Ningún hallazgo firme: todo queda pendiente. Incluye una `lamp broken` rechazada por la IA aunque PIIA1 acertó (`1245-1`). |

Qué hay y qué no:

- Tienen el formato del contrato Agente 1 → Agente 2 y 3 ([`piia2-arquitectura-multiagente.md`](../../../../specs/piia2-arquitectura-multiagente.md)) y pasan `validar_salida_agente1`.
- **No hay fotos ni recortes.** `crop_image_path` es relativo a la carpeta del lote (`crops/...`) y esos recortes no están en el repositorio; el Agente 2 y el Agente 3 no los necesitan.
- **No traen datos del siniestro** (vehículo, taller, póliza): para probar el Agente 2 hay que combinarlas con un contexto de prueba, por ejemplo `../contexto_siniestro.json`.
- Los textos de `vision_description` son salida del modelo; una persona no los ha revisado uno a uno.
- El lote se eligió para cubrir las seis clases con aciertos de PIIA-1, así que el reparto entre `confirmed` y `needs_review` no es representativo ni es una evaluación del sistema.
