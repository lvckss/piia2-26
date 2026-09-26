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

- [x] 4. Fallback de prompt silencioso eliminado en dos capas: (1)
      `resolve_prompt_map` (`strategies/components/defaults.py`) sustituye
      `dict(prompt_map or category_map)` en las tres strategies — si falta
      una categoría, se rellena con `DEFAULT_PROMPT_MAP`, nunca con el nombre
      desnudo; si tampoco está ahí, falla con error claro. (2)
      `roi_verificator.get_prompts_for_category` ya no acepta
      `fallback_text=category_name`; `normalize_prompt_specs` ya no tiene
      parámetro de fallback en absoluto. De paso se eliminó la triplicación de
      `DEFAULT_CATEGORY_MAP`/`DEFAULT_PROMPT_MAP` que vivía por separado en
      `settings.py`, `evaluator.py` y `notebook_utils.py`.
      Variante de texto: `DEFAULT_PROMPT_MAP_V2` en el mismo módulo (usa
      "vehicle" en vez de "car" en las seis clases).
      **Pendiente real:** decidir si v2 (o alguna otra redacción) mejora
      `output.per_class` frente a v1 sobre `val` — necesita la máquina con el
      CarDD + GPU montados, no disponibles aquí.
- [x] 5. Extender CLIP + Tip-Adapter a `dent`. Añadido siguiendo exactamente
      el mismo patrón que `flat_tire`/`broken_lamp`:
      - [export_dent_roi_crops.py](../app/ml/scripts/export_dent_roi_crops.py)
        (mismo patrón que `export_lamp_roi_crops.py`, derivado a su vez de
        `export_wheel_roi_crops.py`). `dent` no tiene un "objeto sano" claro
        como una rueda o un faro, así que el rol de negativo lo hace un panel
        de carrocería sano, propuesto por SAM3 con prompts genéricos de panel
        en vez de un prompt de dent.
      - `dent_cache_path` añadido a `paths.py`/`settings.py` (con
        `ML_API_DENT_CACHE_PATH`), mismo patrón que `flat_tire`/`broken_lamp`.
      - `build_roi_verifier_configs()` en `infer_robust_single_image.py` ya
        activa el verificador de dent automáticamente si su cache existe.
      - Ejemplo de `RoiVerifierConfig` documentado en `README_EVALUACION.md`.
      **Pendiente real:** elegir a mano qué `image_id` del CarDD muestran un
      dent claro vs un panel sano (el script ya soporta pasarlos por
      `--dent-ids`/`--healthy-ids`), correr el script para generar los crops,
      generar el cache con `generate_cropped_embeddings.py`, y calibrar
      `alpha`/`beta`/`threshold` con `val` — todo esto necesita ver las
      imágenes reales y la máquina con GPU, no disponibles aquí.
- [x] 6. Relación exemplars ↔ ensemble geométrico: **decisión tomada** —
      se mantiene la limitación (el ensemble geométrico solo refina prompts de
      texto puro; extenderlo a exemplars requeriría poder pasarle una caja
      guía a `_predict_exemplar_prompt`, que hoy no la acepta — cambio de
      arquitectura no trivial y sin forma de validarlo sin GPU/dataset).
      Lo que cambia es que **ya no es silenciosa**:
      `GeometricEnsembleStrategy` ahora avisa con `UserWarning` en
      construcción si alguna categoría de `prompt_map` usa modo
      `exemplar`/`hybrid`, en vez de que sea descubrible solo leyendo el
      código o la metadata (`sam3_backend`) de cada predicción después de
      correr. Documentado también en `README_EVALUACION.md`.

## Al cierre (depende de la tarea 1)

- [ ] 7. Recalibrar `slice_size`/`overlap_ratio` (SAHI) y
      `perturbation_scale` (ensemble geométrico) por tipo de vehículo.
