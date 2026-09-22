# Nota de diseño: verificación ROI con CLIP + Tip-Adapter en BaselineStrategy

## Objetivo

El pipeline baseline actual tiene dificultades para diferenciar entre objetos dañados y objetos sanos de la misma familia, especialmente:

- `tire flat` frente a ruedas sanas
- `lamp broken` frente a faros sanos

La propuesta es añadir una verificación por ROI usando CLIP + Tip-Adapter, pero sin crear una strategy completamente nueva todavía. Se considera una extensión incremental de `BaselineStrategy`.

## Decisión

La implementación debe vivir dentro de `BaselineStrategy` como una rama opcional activada por configuración.

No se debe mover esta lógica al `Evaluator`.

Razón:

- El `Evaluator` debe seguir recibiendo únicamente `StrategyResult` con `InstancePrediction`.
- CLIP + Tip-Adapter forma parte de la inferencia y normalización de predicciones.
- Mantener el evaluador intacto permite comparar baseline pura, baseline con verificador, SAHI, TTA u otras estrategias sin tocar las métricas.

## Interfaz recomendada

Evitar flags demasiado específicos como:

```python
use_tire_tip_adapter=True
```

Eso escala mal cuando se añadan faros u otras clases.

Preferir un flag general y una configuración por categoría:

```python
strategy = BaselineStrategy(
    model_path=SAM3_PATH,
    category_map=CATEGORY_MAP,
    prompt_map=PROMPT_MAP,
    score_threshold=0.85,
    mask_threshold=0.5,
    prompt_batch_size=6,
    enable_roi_verification=True,
    roi_verifier_configs={
        6: tire_flat_verifier_config,
        5: lamp_broken_verifier_config,
    },
)
```

Semántica:

- `enable_roi_verification=False`
  Mantiene el comportamiento actual exacto.

- `enable_roi_verification=True`
  Para cada categoría:
  - si la categoría tiene config en `roi_verifier_configs`, se usa la rama ROI + CLIP/Tip-Adapter
  - si no tiene config, se usa la baseline actual por prompt de clase

## Cambio de nombre de strategy

Cuando la verificación ROI esté activa, el `strategy_name` no debería ser el mismo que en la baseline pura.

Recomendación:

```text
baseline_prompt
baseline_prompt_roi_verified
```

Esto evita que los resultados queden mezclados o parezca que pertenecen a la baseline original.

## Flujo de inferencia

Para categorías no verificadas:

```text
prompt de daño -> SAM3 -> InstancePrediction
```

Para categorías verificadas:

```text
prompt genérico del objeto -> SAM3 propone ROIs -> crop con margen -> CLIP embedding -> Tip-Adapter -> decisión positive/negative -> InstancePrediction si pasa el threshold
```

Ejemplo para ruedas:

```text
"a visible car tire" -> SAM3 propone ruedas -> CLIP/Tip-Adapter decide flat vs healthy
```

Ejemplo para faros:

```text
"a car headlight" / "a car tail light" -> SAM3 propone faros -> CLIP/Tip-Adapter decide broken vs healthy
```

## Configuración por categoría

Una config razonable para cada verificador debería contener:

```python
{
    "target_category_id": 6,
    "positive_label": "flat",
    "negative_label": "healthy",
    "proposal_prompts": [
        "a visible car tire",
        "a car wheel",
        "a vehicle wheel",
    ],
    "positive_text_prompts": [
        "a flat deflated car tire",
        "a car tire with no air",
    ],
    "negative_text_prompts": [
        "a normal inflated car tire",
        "a healthy car wheel",
    ],
    "cache_path": "ml/artifacts/tip_adapter/tire_flat/cache.pt",
    "alpha": 1.0,
    "beta": 5.0,
    "threshold": 0.5,
    "crop_padding_frac": 0.25,
    "max_proposals_per_image": 2,
}
```

Para faros rotos:

```python
{
    "target_category_id": 5,
    "positive_label": "broken_lamp",
    "negative_label": "healthy_lamp",
    "proposal_prompts": [
        "a car headlight",
        "a car tail light",
        "a vehicle lamp",
    ],
    "positive_text_prompts": [
        "a broken car headlight",
        "a damaged car tail light",
    ],
    "negative_text_prompts": [
        "a normal car headlight",
        "an intact car tail light",
    ],
    "cache_path": "ml/artifacts/tip_adapter/lamp_broken/cache.pt",
    "alpha": 1.0,
    "beta": 5.0,
    "threshold": 0.5,
    "crop_padding_frac": 0.25,
    "max_proposals_per_image": 2,
}
```

Los valores de `alpha`, `beta` y `threshold` deben calibrarse con `val`, no con `test`.

## Componente reutilizable

Aunque la activación viva en `BaselineStrategy`, conviene que la lógica de CLIP + Tip-Adapter no quede mezclada directamente con todo el código de SAM3.

Recomendación de estructura:

```text
ml/StrategyPipeline/strategies/
  baseline_strategy.py
  components/
    clip_tip_adapter.py
```

`baseline_strategy.py` decidiría cuándo llamar al verificador.

`clip_tip_adapter.py` contendría la lógica reusable:

- cargar CLIP
- cargar cache key-value
- generar embedding del crop
- calcular logits zero-shot CLIP
- calcular logits del cache Tip-Adapter
- combinar scores
- devolver decisión y score calibrado

## Cache key-value

El cache de Tip-Adapter debería construirse con crops curados.

Para ruedas:

```text
positive: crops de ruedas pinchadas
negative: crops de ruedas sanas
```

Para faros:

```text
positive: crops de faros rotos
negative: crops de faros sanos
```

Los artefactos no deberían depender del notebook para producción. Ubicación sugerida:

```text
ml/artifacts/tip_adapter/
  tire_flat/
    cache.pt
    metadata.json
  lamp_broken/
    cache.pt
    metadata.json
```

El `metadata.json` debería incluir:

- modelo CLIP usado
- fecha o versión del cache
- número de crops positivos y negativos
- prompts usados
- normalización aplicada
- `alpha`, `beta` recomendados
- threshold recomendado

## Score final

El output debe seguir siendo `InstancePrediction`.

Para categorías verificadas:

```python
InstancePrediction(
    category_id=target_category_id,
    score=final_score,
    mask=proposal_mask,
    bbox=proposal_bbox,
    area=proposal_area,
)
```

`final_score` debe ser continuo para que COCO AP pueda ordenar predicciones.

Una opción razonable:

```text
final_score = sam3_proposal_score * p_positive
```

o una combinación calibrada similar.

No usar únicamente un booleano positive/negative como score.

## Datos de entrenamiento y validación

Para construir el cache:

- usar `train`
- calibrar thresholds con `val`
- reportar resultado final con `test`

Aunque no se reentrenen pesos, el ajuste de prompts, thresholds, crops, `alpha` y `beta` cuenta como tuning.

## Resumen

La decisión recomendada es:

- mantener `BaselineStrategy` como strategy principal
- añadir `enable_roi_verification`
- añadir `roi_verifier_configs` por categoría
- implementar CLIP + Tip-Adapter como componente reusable
- dejar el `Evaluator` intacto
- cambiar `strategy_name` cuando el verificador esté activo
- guardar caches y metadata fuera de notebooks
