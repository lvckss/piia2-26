# Tareas — mejora de robustez por tipo de vehículo

Detalle completo, contexto y criterios de aceptación de cada punto en
[`specs/mejora-robustez-tipos-vehiculo.md`](specs/mejora-robustez-tipos-vehiculo.md).

Todas las tareas quedan asignadas a Lucía.

## Medición e infraestructura de evaluación

- [ ] 1. Instrumentar `vehicle_type`: clasificador zero-shot (ej. CLIP) para
      etiquetar el dataset, campo `vehicle_type` en `ImageSample`/loader, y
      dimensión `per_vehicle` en el `Evaluator` (mismo patrón que
      `per_condition`).
- [ ] 2. Unificar `score_threshold`/`mask_threshold` en una única fuente de
      configuración (`ml/api/core/settings.py`), eliminando los defaults
      divergentes de `baseline.py`, `sahi.py` y `geom_ensemble.py`.
- [ ] 3. Calibrar el umbral de score por clase de daño, apoyándose en
      `output.per_class` del `Evaluator`.

## Prompts y verificación visual

- [ ] 4. Eliminar el fallback de prompt silencioso (`prompt_map or
      category_map`) y diseñar al menos una variante de texto adicional por
      clase.
- [ ] 5. Extender CLIP + Tip-Adapter a clases adicionales, empezando por
      `dent`.
- [ ] 6. Decidir e implementar/documentar la relación entre exemplars y
      ensemble geométrico (hoy son mutuamente excluyentes por
      `_is_text_only_prompt`).

## Al cierre (depende de la tarea 1)

- [ ] 7. Recalibrar `slice_size`/`overlap_ratio` (SAHI) y
      `perturbation_scale` (ensemble geométrico) por tipo de vehículo.
