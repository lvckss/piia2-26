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
- [x] 2. Unificar `score_threshold`/`mask_threshold` en una única fuente de
      configuración. `mask_threshold` ya era 0.5 en todos los sitios; el
      divergente era `score_threshold` (baseline 0.3, sahi 0.8, geom_ensemble
      0.3, settings.py 0.6). Ahora los tres viven en
      `ml/StrategyPipeline/strategies/components/defaults.py`
      (`DEFAULT_SCORE_THRESHOLD=0.6`, `DEFAULT_MASK_THRESHOLD=0.5`), y
      `baseline.py`/`sahi.py`/`geom_ensemble.py`/`ml/api/core/settings.py` lo
      usan como default compartido. Sigue siendo posible pasar un valor
      distinto de forma explícita (ej. el ejemplo de `GeometricEnsembleStrategy`
      con `score_threshold=0.3` en `README_EVALUACION.md` sigue siendo válido),
      lo que ya no ocurre es que "no decir nada" dé un número distinto según
      la estrategia.
- [x] 3. Umbral de score por clase de daño: `baseline.py`/`sahi.py`/
      `geom_ensemble.py` aceptan `score_threshold_map={category_id: umbral}`
      en el constructor (o `strategy.set_score_threshold_map({...})` sin
      recargar sam3), resuelto por el helper compartido
      `resolve_score_threshold_map` (`strategies/components/defaults.py`).
      SAM3 se configura internamente con el umbral más permisivo de todas las
      categorías, y cada categoría se filtra después con su propio umbral (o
      con `score_threshold` si no tiene uno propio) — sin usar el mapa, el
      comportamiento es idéntico al de antes.
      **Pendiente real:** decidir los valores por clase mirando
      `output.per_class` sobre el dataset real (necesita la tarea 1 y una
      máquina con el CarDD + GPU montados, no disponibles aquí).

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
