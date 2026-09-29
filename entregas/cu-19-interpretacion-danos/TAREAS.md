# Tareas — mejora de robustez del pipeline de detección (PIIA-1)

Detalle completo, contexto y criterios de aceptación de cada punto en
[`specs/mejora-robustez-tipos-vehiculo.md`](specs/mejora-robustez-tipos-vehiculo.md).

Todas las tareas quedan asignadas a Lucía.

> [!NOTE]
> **Actualización 29/09/2026: la instrumentación por `vehicle_type` (tarea 1
> y tarea 7 de abajo) se construyó y se revirtió por completo.** CarDD no
> trae esa etiqueta de fábrica; se había escrito un clasificador zero-shot
> con CLIP para generarla (`label_vehicle_types.py`), pero nunca llegó a
> correrse sobre el dataset real. Mantener `vehicle_type`/`per_vehicle` en el
> pipeline sin ningún dato real detrás — solo reportando siempre `"unknown"`
> — era complejidad sin validar y sin plan real de validarla, así que se optó
> por quitarla en vez de dejarla a medias. El umbral por clase de daño (tarea
> 3, sí calibrado con datos reales) es independiente de esto y se mantiene
> intacto. Se deja esta nota en vez de borrar el historial de abajo para que
> quede constancia de qué se intentó y por qué se descartó.

## Medición e infraestructura de evaluación

- [x] ~~1a-1d. Campo `vehicle_type` + dimensión `per_vehicle` en el
      `Evaluator` + `CarddLoader(vehicle_types_path=...)` +
      `label_vehicle_types.py`~~ — **revertido el 29/09/2026**, ver nota de
      arriba.
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
      **Calibrado con datos reales el 29/09/2026** (BaselineStrategy, 150-200
      imágenes de `val` en Colab): `lamp_broken`/`glass_shatter`/`tire_flat`
      funcionan bien a threshold≈0.3-0.6. Para `dent`/`scratch`/`crack` el
      barrido completo (0.1 a 0.85) **no encontró ningún threshold con
      precisión y recall aceptables a la vez** — mejor caso `dent` a 0.70:
      11.5% precisión, 6.6% recall; a 0.85 las tres caen a 0%/0%. Conclusión:
      no es un problema de calibración de threshold, ver decisión de alcance
      más abajo.

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
      **Probado con datos reales el 29/09/2026:** 3 variantes de prompt para
      `crack` sobre 150 imágenes de `val` (BaselineStrategy). Ninguna mejoró
      la original: `v2` (más específica, "rigid part") se quedó en 0%
      precisión y 0% recall — dejó de detectar cualquier crack real; `v3`
      (con negación "not a paint scratch") perdió casi todo el recall (4.1%
      vs 32.7% de la original) sin ganar precisión utilizable. Lección: los
      modelos zero-shot tipo SAM3/CLIP manejan mal la negación en el prompt.
      Se mantiene el prompt original; ver decisión de alcance más abajo.
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

- [x] ~~7. Infraestructura de recalibración por tipo de vehículo
      (`slice_size_by_vehicle_type`/`overlap_ratio_by_vehicle_type` en
      `SahiStrategy`, `perturbation_scale_by_vehicle_type` en
      `GeometricEnsembleStrategy`)~~ — **revertido el 29/09/2026** junto con
      la tarea 1, ver nota de arriba: dependía de `vehicle_type`, que ya no
      existe en el pipeline.

## Decisión de alcance para PIIA2 (actualizado 29/09/2026)

Primera versión de esta decisión (excluir `dent`/`scratch`/`crack` del
informe) revisada: la precisión bruta a threshold=0.3 de `lamp_broken`
(18.6%), `glass_shatter` (15.3%) y `tire_flat` (19.0%) tampoco era buena, y
su threshold de `confirmed` (0.6) se había asumido sin comprobar con un
barrido real. No es coherente excluir 3 clases sin verificar antes las otras
3 con el mismo rigor.

**Decisión final: ninguna clase se excluye.** Las 6 pasan por el mismo
esquema `confirmed`/`needs_review`, con un threshold de `confirmed` por
clase calibrado con datos — no con una lista de exclusión fija. El barrido
de thresholds se extendió a las 6 clases (antes solo cubría
`dent`/`scratch`/`crack`); pendiente correr esa celda en Colab y fijar los
valores finales de `CATEGORY_REVIEW_THRESHOLD`. Detalle y
`classify_confidence(...)` en
[`specs/agente-confianza-hallazgos.md`](specs/agente-confianza-hallazgos.md).

Vías para reincorporar `dent`/`scratch`/`crack` más adelante (ninguna es un
ajuste de threshold): extender CLIP + Tip-Adapter (base ya lista para `dent`
en la tarea 5), prompts basados en exemplars en vez de texto puro, o
fine-tuning.
