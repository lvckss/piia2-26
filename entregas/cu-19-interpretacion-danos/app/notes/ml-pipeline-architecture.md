# Notas de arquitectura: pipeline ML, schemas y contratos entre módulos

## Objetivo

El objetivo del pipeline es evaluar distintas estrategias para aumentar la robustez de SAM3 sin reentrenamiento, por ejemplo:

- baseline
- SAHI
- TTA geométrico
- ensembles

La idea es que todas las estrategias sean intercambiables y que el evaluador sea común para todas.

## Flujo general

```text
Data Loader -> Strategy Module -> Evaluator
```

Semántica de cada bloque:

- `Data Loader`
  Devuelve una muestra por imagen con su GT y metadata.

- `Strategy Module`
  Recibe un `ImageSample` y devuelve un `StrategyResult` para esa imagen.

- `Evaluator`
  Acumula muchos `StrategyResult` y escupe un único `EvalOutput` por run.

## Estructura de carpetas recomendada

```text
ml/
  schemas.py
  data/
    loader.py
  strategies/
    base.py
    baseline.py
    sahi.py
    tta_geom.py
  evaluation/
    evaluator.py
    coco_metrics.py
    robustness.py
  notebooks/
```

Regla práctica:

- `ml/notebooks/` sirve para experimentar y orquestar.
- La lógica reutilizable no debería vivir en el notebook.

## Schemas

Los schemas viven en `ml/schemas.py` y son el contrato único entre módulos.

### Output del Data Loader

```python
@dataclass(frozen=True)
class GroundTruthInstance:
    annotation_id: int
    category_id: int
    mask: np.ndarray
    bbox: tuple[float, float, float, float]
    area: float


@dataclass(frozen=True)
class ImageSample:
    image_id: int
    image_path: str
    image: np.ndarray | None
    width: int
    height: int
    split: str
    gt_instances: list[GroundTruthInstance]
    corruption: str | None = None
    severity: int | None = None
    is_clean: bool = True
```

Interpretación:

- `ImageSample` representa una imagen concreta.
- Incluye GT porque el pipeline está pensado para evaluación.
- `image` puede ir cargada o no, según `load_image=True/False`.

### Output del Strategy Module

```python
@dataclass(frozen=True)
class SampleRef:
    image_id: int
    width: int
    height: int
    split: str
    corruption: str | None = None
    severity: int | None = None
    is_clean: bool = True


@dataclass(frozen=True)
class InstancePrediction:
    category_id: int
    score: float
    mask: np.ndarray
    bbox: tuple[float, float, float, float]
    area: float


@dataclass(frozen=True)
class RuntimeStats:
    inference_ms: float
    peak_vram_mb: float | None


@dataclass(frozen=True)
class StrategyResult:
    strategy_name: str
    sample: SampleRef
    predictions: list[InstancePrediction]
    runtime: RuntimeStats
```

Interpretación:

- `StrategyResult` es siempre por imagen.
- No contiene GT.
- No contiene métricas.
- Debe contener la predicción final de la estrategia para esa imagen.

## Data Loader

La clase actual es `CarddDataset` en `ml/data/loader.py`.

### Responsabilidad

- leer COCO
- resolver la ruta de la imagen
- cargar anotaciones GT
- construir `ImageSample`

### Comportamiento actual decidido

- El dataset físico canónico de imágenes será `bd/rawdata/images/`.
- Las carpetas `train/`, `val/` y `test/` se pueden eliminar como almacenamiento físico.
- La separación `train/val/test` se mantiene como concepto lógico.

### Decisión sobre `split`

El constructor de `CarddDataset` ya no recibe `split`.

El split se resuelve automáticamente:

- si `ann_path` es `instances_train.json` -> split `train`
- si `ann_path` es `instances_val.json` -> split `val`
- si `ann_path` es `instances_test.json` -> split `test`
- si `ann_path` es `instances_all.json` -> split por imagen inferido cruzando `image_id` con `instances_train.json`, `instances_val.json` y `instances_test.json`

Esto evita inconsistencias del tipo:

- cargar `instances_all.json`
- pero etiquetar todas las muestras como `train`

### Resolución de rutas de imagen

El loader limpia `file_name` del COCO, por ejemplo `./000012.jpg`, y busca la imagen en:

1. `img_dir / file_name`
2. `img_dir / "images" / file_name`

Así puede usarse de dos formas:

```python
CarddDataset(
    ann_path="bd/rawdata/instances_test.json",
    img_dir="bd/rawdata/images",
    load_image=True,
)
```

o:

```python
CarddDataset(
    ann_path="bd/rawdata/instances_test.json",
    img_dir="bd/rawdata",
    load_image=True,
)
```

### Iteración

El dataset implementa:

- `__len__`
- `__getitem__`
- `__iter__`

Uso típico:

```python
for sample in dataset:
    ...
```

o:

```python
sample = dataset[0]
```

## Strategy Module

Cada estrategia debe implementar la misma interfaz conceptual:

```python
result = strategy.run(sample)
```

donde:

- `sample` es un `ImageSample`
- `result` es un `StrategyResult`

### Reglas para las estrategias

- Todas deben devolver la misma estructura.
- La estrategia debe hacerse responsable de su propia lógica interna.
- El evaluador no debería saber si la predicción viene de baseline, SAHI o TTA.

Ejemplos:

- `BaselineStrategy`
  corre la inferencia directa y devuelve predicciones finales.

- `SAHIStrategy`
  corta en tiles, infiere, remapea a coordenadas globales, fusiona y devuelve predicciones finales.

- `GeometricTTAStrategy`
  aplica augmentations, deshace transforms, fusiona y devuelve predicciones finales.

Importante:

- SAHI y TTA no deben devolver estados intermedios al evaluador.
- El evaluador solo debe ver la salida final ya consolidada.

## Evaluator

El evaluador trabaja a nivel de run completo.

### Entrada conceptual

Recibe:

- muchos `ImageSample`
- muchos `StrategyResult`
- metadata del run

API conceptual:

```python
evaluator = Evaluator(run_info)

for sample in dataset:
    result = strategy.run(sample)
    evaluator.add(sample, result)

eval_output = evaluator.finalize()
```

### Salida conceptual

El `Evaluator` no escupe un resultado por imagen, sino un objeto final por run:

```python
EvalOutput
```

Con esta forma conceptual:

```python
{
    "run_info": ...,
    "summary": ...,
    "per_class": ...,
    "per_condition": ...,
    "per_image": ...,
}
```

### Qué debería contener

`summary`

- `mask_ap_50_95`
- `ap75`
- `ap_small`
- `fp_per_image`
- `pclean`
- `mpc`
- `rpc`
- `ms_per_image`
- `peak_vram_mb`

`per_class`

- una fila por clase
- AP por clase

`per_condition`

- una fila por condición
- `clean`, corrupción y severidad

`per_image`

- una fila por imagen
- TP, FP, FN, latencia, VRAM

## Significado de las métricas

- `mask AP@[.50:.95]`
  métrica global principal de segmentación por instancia

- `AP75`
  versión más estricta del AP

- `AP_S`
  AP para objetos pequeños

- `AP por clase`
  AP separado por tipo de daño

- `FP/image`
  media de falsos positivos por imagen

- `Pclean`
  rendimiento en limpio

- `mPC`
  rendimiento medio bajo corrupción

- `rPC`
  fracción de rendimiento conservado bajo corrupción

- `ms/img`
  latencia media por imagen

- `VRAM pico`
  máximo uso de memoria GPU en el run

## Sobre train, val y test sin reentrenamiento

Aunque no haya reentrenamiento, sigue teniendo sentido mantener:

- `val` para tomar decisiones de diseño
- `test` para reportar resultado final

Porque en la práctica sí vais a ajustar cosas:

- prompts
- thresholds
- top-k
- SAHI
- TTA
- fusión de predicciones

Eso también es tuning, aunque no haya aprendizaje de pesos.

La separación que no aporta tanto es la duplicación física de imágenes en carpetas separadas.

## Importación desde notebooks

Para usar módulos de `ml/` desde un notebook, se añade la raíz del proyecto al `sys.path`.

Primera celda recomendada:

```python
import sys
from pathlib import Path

ROOT = Path.cwd().resolve()
while not (ROOT / "ml").exists():
    if ROOT.parent == ROOT:
        raise RuntimeError("No se encontró la raíz del proyecto")
    ROOT = ROOT.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
```

Después:

```python
from ml.data.loader import CarddDataset
```

## Estado actual

Ya están resueltos estos puntos:

- `ml/schemas.py` define los contratos base
- `ml/data/loader.py` usa import relativo correcto
- `CarddDataset` resuelve imágenes en `images/`
- `CarddDataset` ya no recibe `split`
- `instances_all.json` infiere el split por imagen automáticamente

## Siguiente paso natural

Implementar la interfaz base de `StrategyModule` y el esqueleto de `Evaluator`, para que el pipeline completo quede así:

```text
ImageSample -> StrategyResult -> EvalOutput
```
