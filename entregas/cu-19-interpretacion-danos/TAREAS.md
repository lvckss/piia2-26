# Tareas — mejora de robustez por tipo de vehículo

Detalle completo, contexto y criterios de aceptación de cada punto en
[`specs/mejora-robustez-tipos-vehiculo.md`](specs/mejora-robustez-tipos-vehiculo.md).

Todas las tareas quedan asignadas a Lucía.

## Medición e infraestructura de evaluación

- [x] 1a. Campo `vehicle_type` en `ImageSample`/`SampleRef`/`ImageEvalRecord`,
      propagado por `StrategyModule.run()`, validado en
      `validate_evaluator_input`, y visible en `per_image`.
- [x] 1b. Dimensión `per_vehicle` en el `Evaluator`
      (`ml/StrategyPipeline/evaluation/metrics/vehicle_metrics.py`), mismo
      patrón que `per_condition`. Sin etiquetar, las imágenes quedan visibles
      como `"unknown"` en vez de desaparecer del desglose.
- [x] 1c. `CarddLoader(vehicle_types_path=...)` para leer el mapeo
      `image_id -> vehicle_type` desde un json externo.
- [ ] 1d. Script `ml/scripts/label_vehicle_types.py` (zero-shot con CLIP)
      escrito y listo, pero **pendiente de ejecutar sobre el dataset real**:
      esto requiere el CarDD descargado + un entorno con `torch`/
      `transformers`, que no están disponibles en este equipo. Ejecutar donde
      esté montado el dataset:
      ```bash
      python ml/scripts/label_vehicle_types.py \
        --ann-path bd/rawdata/instances_all.json \
        --img-dir bd/rawdata/images \
        --output-path ml/config/vehicle_types.json
      ```
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
