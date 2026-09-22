# CU-19 — Código de la aplicación

Código base de la aplicación de interpretación y segmentación de daños en
vehículos. Esta carpeta contiene la base técnica heredada de PIIA1 sobre la que
se continuará desarrollando CU-19.

## Estructura

```text
app/
  server/                 # api bun + hono
  frontend/               # cliente react + vite
  bd/                     # datos, scripts de carga y schema sql
  ml/StrategyPipeline/    # dataloader, strategies, evaluator e inspection
  ml/api/                 # api FastAPI de inferencia
  ml/scripts/             # scripts de preparación y evaluación
  notes/                  # notas de diseño del pipeline
```

## Backend

```bash
bun install
bun run dev
```

El servidor arranca desde:

```text
server/index.ts
```

Rutas principales:

```text
/images
/instances
/sam3
```

## Frontend

```bash
cd frontend
bun install
bun run dev
```

Para build:

```bash
bun run build
```

## Pipeline ML

El pipeline de evaluación sigue esta forma:

```text
CarddDataset -> StrategyModule -> Evaluator -> EvalOutput
```

Piezas principales:

```text
ml/StrategyPipeline/data/loader.py
ml/StrategyPipeline/strategies/base.py
ml/StrategyPipeline/strategies/baseline.py
ml/StrategyPipeline/evaluation/evaluator.py
ml/StrategyPipeline/evaluation/inspection.py
```

Las métricas están separadas por familia:

```text
ml/StrategyPipeline/evaluation/metrics/coco_metrics.py
ml/StrategyPipeline/evaluation/metrics/error_metrics.py
ml/StrategyPipeline/evaluation/metrics/robustness_metrics.py
ml/StrategyPipeline/evaluation/metrics/runtime_metrics.py
```

Salida típica:

```python
for sample in dataset:
    result = strategy.run(sample)
    evaluator.add(sample, result)

output = evaluator.finalize()
inspection = evaluator.get_inspection()
```

`output` contiene las métricas serializables. `inspection` se usa para revisar casos concretos y plottear ground truth frente a predicciones.

Guía operativa detallada:

```text
ml/README_EVALUACION.md
```

## Datos y modelos externos

Los datasets, pesos de SAM3, caches de Tip-Adapter, imágenes de soporte y
resultados de experimentos no se incluyen en este repositorio. Deben montarse o
configurarse externamente mediante las variables y rutas documentadas por la
API ML.

```text
ML_API_MODEL_PATH=/ruta/al/modelo/facebook_sam3
ML_API_FLAT_TIRE_CACHE_PATH=/ruta/al/cache/flat_tire/cache.pt
ML_API_BROKEN_LAMP_CACHE_PATH=/ruta/al/cache/broken_lamp/cache.pt
```

Para evaluar el pipeline, el loader espera un dataset CARDD con sus imágenes y
anotaciones COCO. Esos datos deben permanecer fuera del commit por su tamaño y
por las restricciones de distribución.

## Artefactos

Los notebooks suelen escribir resultados en:

```text
ml/notebooks/results/
```

Ejemplos:

```text
output.json          # métricas finales
inspection.joblib    # objeto de inspección para otra sesión de jupyter
```

## Notas

Documentación de diseño:

```text
notes/ml-pipeline-architecture.md
notes/strategy-module.md
```
