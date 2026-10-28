# ml

## qué cubre

este documento describe la parte de `ml/` como librería y zona de trabajo de experimentación.

incluye:

- `StrategyPipeline`
- evaluación e inspección
- explainability
- fastapi de inferencia
- scripts auxiliares
- artefactos y resultados

## visión general

la carpeta `ml/` no es solo un modelo.

en la práctica agrupa cuatro capas distintas:

```text
ml/
  StrategyPipeline/   -> librería principal de inferencia y evaluación
  api/                -> fastapi que expone inferencia por http
  scripts/            -> utilidades auxiliares
  notebooks/          -> experimentación
```

además contiene:

- `config/` para artefactos auxiliares
- `presentation_assets/` para recursos visuales generados

## StrategyPipeline

### objetivo

`StrategyPipeline` es la librería central del proyecto para:

- cargar muestras
- ejecutar estrategias de inferencia
- evaluar resultados
- inspeccionar errores
- apoyar explainability

la forma conceptual del pipeline es:

```text
CarddLoader -> Strategy -> Evaluator -> Output + Inspection
```

referencia principal:

- [ml/README_EVALUACION.md](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/README_EVALUACION.md)

### módulos principales

```text
ml/StrategyPipeline/
  data/
  strategies/
  evaluation/
  explainability/
  schemas.py
```

### schemas

[schemas.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/StrategyPipeline/schemas.py) define los contratos de datos que conectan el pipeline.

tipos clave:

- `ImageSample`
- `GroundTruthInstance`
- `InstancePrediction`
- `StrategyResult`
- `RunInfo`
- `EvalOutput`
- `InspectionItem`

esto es importante porque gran parte del diseño del pipeline está guiado por contratos explícitos.

## carga de datos

el dataloader principal vive en:

- [data/loader.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/StrategyPipeline/data/loader.py)

su papel es convertir el dataset CARDD en `ImageSample` listos para inferencia y evaluación.

dataset esperado:

```text
bd/rawdata/
  images/
  instances_train.json
  instances_val.json
  instances_test.json
  instances_all.json
```

## strategies

### capa base

la abstracción base vive en:

- [strategies/base.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/StrategyPipeline/strategies/base.py)

esa clase fija el contrato que deben cumplir las estrategias.

### estrategias concretas

las implementaciones actuales son:

- [baseline.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/StrategyPipeline/strategies/baseline.py)
- [sahi.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/StrategyPipeline/strategies/sahi.py)
- [geom_ensemble.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/StrategyPipeline/strategies/geom_ensemble.py)

lectura rápida:

- `baseline`: inferencia directa sobre imagen completa
- `sahi`: slicing y consolidación de predicciones
- `geometric_ensemble`: perturbación/refinamiento geométrico con consenso

### componentes compartidos

los componentes técnicos más relevantes están en:

- [sam3_backend.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/StrategyPipeline/strategies/components/sam3_backend.py)
- [clip_tip_adapter.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/StrategyPipeline/strategies/components/clip_tip_adapter.py)
- [roi_verificator.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/StrategyPipeline/strategies/components/roi_verificator.py)

responsabilidades:

- `sam3_backend.py`: backend principal de prompts e inferencia SAM3
- `clip_tip_adapter.py`: verificación few-shot con CLIP + Tip-Adapter
- `roi_verificator.py`: filtrado o validación de propuestas por roi

## evaluación

### evaluator

el evaluador principal vive en:

- [evaluation/evaluator.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/StrategyPipeline/evaluation/evaluator.py)

su papel es:

- registrar `sample + result`
- validar contrato de entrada
- calcular métricas
- devolver `EvalOutput`
- construir un objeto `RunInspection`

### validación contractual

la parte de contrato vive en:

- [evaluation/utils/validators.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/StrategyPipeline/evaluation/utils/validators.py)

ahí se valida, entre otras cosas:

- consistencia de `strategy_name`
- alineación entre `sample` y `result.sample`
- shape de máscaras
- rango de scores
- categorías conocidas

### familias de métricas

las métricas están desacopladas por familia:

- [coco_metrics.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/StrategyPipeline/evaluation/metrics/coco_metrics.py)
- [error_metrics.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/StrategyPipeline/evaluation/metrics/error_metrics.py)
- [runtime_metrics.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/StrategyPipeline/evaluation/metrics/runtime_metrics.py)
- [robustness_metrics.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/StrategyPipeline/evaluation/metrics/robustness_metrics.py)

eso permite separar:

- precisión estilo coco
- tp/fp/fn y `fp_per_image`
- latencia y pico de vram
- degradación bajo corrupción/severidad

## inspección

la capa de inspección vive en:

- [evaluation/inspection.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/StrategyPipeline/evaluation/inspection.py)

`RunInspection` permite:

- recuperar datos por `image_id`
- filtrar por `split`, `corruption`, `severity`, `is_clean`
- dibujar ground truth frente a predicciones

esto está pensado para análisis posterior a la evaluación, no para servir producción.

## explainability

la parte de explainability está en:

- [explainability/manager.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/StrategyPipeline/explainability/manager.py)
- [explainability/sam3_grad_cam.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/StrategyPipeline/explainability/sam3_grad_cam.py)

su foco es generar herramientas de análisis visual sobre predicciones y regiones relevantes, no formar parte del camino principal de inferencia.

## fastapi dentro de `ml/`

además de la librería, `ml/` contiene una api en:

- [ml/api](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/api)

esa capa:

- reutiliza `StrategyPipeline`
- recibe una imagen
- construye un `ImageSample`
- ejecuta una strategy
- devuelve una respuesta json

la documentación específica de esa parte está en:

- [docs/api-docker.md](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/docs/api-docker.md)
- [ml/api/README.md](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/api/README.md)

## scripts

las utilidades de línea de comandos están en:

- [export_image_exemplars_from_instances.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/scripts/export_image_exemplars_from_instances.py)
- [export_lamp_roi_crops.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/scripts/export_lamp_roi_crops.py)
- [export_wheel_roi_crops.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/scripts/export_wheel_roi_crops.py)
- [infer_robust_single_image.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/scripts/infer_robust_single_image.py)
- [generate_presentation_cover_mosaic.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/scripts/generate_presentation_cover_mosaic.py)
- [generate_random_mosaic_3x5.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/scripts/generate_random_mosaic_3x5.py)

en la práctica hay tres familias:

- preparación de artefactos auxiliares
- inferencia o análisis puntual
- generación de assets visuales para presentación

## config y artefactos

`ml/config/` guarda artefactos auxiliares del pipeline.

dos bloques importantes:

- `ml/config/image_exemplars/`
- `ml/config/tip_adapter/`

ahí viven manifests, crops y caches que apoyan prompts híbridos o verificación roi.

## notebooks

la experimentación en jupyter vive en:

- `ml/notebooks/`

notebooks visibles:

- `pipeline.ipynb`
- `load_data.ipynb`
- `image_exemplars.ipynb`
- `clip_lamps.ipynb`

los resultados suelen guardarse en:

- `ml/notebooks/results/`

## presentation assets

`ml/presentation_assets/` ya se está usando para recursos gráficos del proyecto, por ejemplo:

- mosaicos del dataset
- variantes anotadas
- selecciones reproducibles en json

## cómo leer `ml/` sin perderte

si entras nuevo al módulo:

1. empieza por [ml/README_EVALUACION.md](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/README_EVALUACION.md)
2. sigue por [schemas.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/StrategyPipeline/schemas.py)
3. mira [loader.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/StrategyPipeline/data/loader.py)
4. revisa una strategy concreta
5. termina en [evaluator.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/StrategyPipeline/evaluation/evaluator.py) y [inspection.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/StrategyPipeline/evaluation/inspection.py)

## estado actual resumido

- `StrategyPipeline` es la librería central de ml del proyecto
- `ml/api` ya permite exponer inferencia por http
- `scripts/` y `config/` ya contienen utilidades y artefactos relevantes de soporte
- `notebooks/` sigue siendo la zona de experimentación y análisis manual
