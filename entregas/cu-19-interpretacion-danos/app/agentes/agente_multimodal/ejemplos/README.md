# Ejemplos para desarrollar el Agente 1 sin Colab

3 JSON escritos a mano, con el mismo formato que produce
`ml/scripts/infer_robust_single_image.py` (`build_json_summary`), más
`image_id` y `vehicle_type` (que esa función todavía no incluye — falta
añadirlos ahí cuando generemos el lote real de imágenes).

| Fichero | Qué prueba |
|---|---|
| `ejemplo_1_faro_roto.json` | Caso simple: una detección, clase fiable, score alto → `confirmed`. |
| `ejemplo_2_cristal_y_rueda.json` | Dos detecciones de clases distintas, ambas fiables → las dos `confirmed`. |
| `ejemplo_3_mixto_dificil.json` | Fuerza los 2 tiers a la vez en la misma imagen: `lamp broken` score 0.91 (≥0.6) → `confirmed`; `tire flat` score 0.45 (<0.6) → `needs_review`; `dent` score 0.68 (<0.7, threshold más exigente por ser clase menos fiable) → también `needs_review`. Ninguna se excluye (ver `specs/agente-confianza-hallazgos.md`). |

Si `classify_confidence` está bien implementado, el ejemplo 3 debería
devolver 3 hallazgos: 1 `confirmed` y 2 `needs_review` — es el mejor para
comprobar que la lógica funciona antes de nada más.
