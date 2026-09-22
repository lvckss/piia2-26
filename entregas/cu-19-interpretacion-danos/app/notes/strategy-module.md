# Notas de arquitectura: StrategyModule

## Objetivo

El `StrategyModule` es la pieza del pipeline que convierte una muestra del dataset en una predicción normalizada lista para evaluar.

Su contrato es:

```text
ImageSample -> StrategyResult
```

La idea es que cualquier estrategia futura:

- baseline por prompts
- SAHI
- TTA geométrico
- ensembles

pueda enchufarse al mismo `Evaluator` sin cambiar el evaluador.

## Posición en el pipeline

```text
CarddDataset -> StrategyModule.run(sample) -> StrategyResult -> Evaluator.add(sample, result)
```

Semántica:

- `CarddDataset` entrega un `ImageSample`
- la estrategia corre su lógica de inferencia
- la estrategia devuelve un `StrategyResult`
- el `Evaluator` compara ese resultado con el GT contenido en `ImageSample`

## Contrato de entrada y salida

### Entrada

La entrada pública del strategy es `ImageSample`, definido en `ml/schemas.py`.

Contiene:

- `image_id`
- `image_path`
- `image`
- `width`, `height`
- `split`
- `gt_instances`
- `corruption`, `severity`, `is_clean`

La estrategia no debería usar `gt_instances` para evaluar; el GT pertenece al evaluador.

Excepción:

- una estrategia de sanity check tipo `bbox_gt` podría usar GT como prompt, pero no sería una baseline justa para reportar resultados finales.

### Salida

La salida pública del strategy es `StrategyResult`, definido en `ml/schemas.py`.

Contiene:

- `strategy_name`
- `sample: SampleRef`
- `predictions: list[InstancePrediction]`
- `runtime: RuntimeStats`

Reglas:

- siempre es por imagen
- no contiene GT
- no contiene métricas
- debe contener la predicción final consolidada de la estrategia

## Clase base recomendada

La clase base no debería implementar la estrategia concreta. Debería implementar solo el marco común:

- validación ligera del `sample`
- medición de tiempo
- medición de VRAM pico
- construcción de `SampleRef`
- empaquetado en `StrategyResult`

La forma conceptual es esta:

```python
class StrategyModule(ABC):
    def __init__(self, strategy_name: str, category_map: dict[int, str]) -> None:
        ...

    def run(self, sample: ImageSample) -> StrategyResult:
        ...

    @abstractmethod
    def _predict_instances(self, sample: ImageSample) -> list[InstancePrediction]:
        ...
```

## Por qué `run()` debería vivir en la base

Si cada estrategia implementa su propio `run()`, todas acaban duplicando:

- construcción de `SampleRef`
- cronometraje
- medición de VRAM
- empaquetado en `StrategyResult`

Eso genera ruido y más puntos de inconsistencia.

La regla recomendada es:

- `run()` vive en la base
- `_predict_instances()` vive en la subclase

## Qué debe hacer `run()`

`run()` debería seguir siempre este flujo:

1. validar el `ImageSample`
2. resetear el pico de VRAM si aplica
3. empezar a medir tiempo
4. llamar a `_predict_instances(sample)`
5. parar el cronómetro
6. leer el pico de VRAM
7. construir `SampleRef`
8. devolver `StrategyResult`

Forma conceptual:

```python
def run(self, sample: ImageSample) -> StrategyResult:
    self._validate_sample(sample)

    self._reset_peak_vram_stats_if_needed()
    start = time.perf_counter()

    predictions = self._predict_instances(sample)

    elapsed_ms = (time.perf_counter() - start) * 1000.0
    peak_vram_mb = self._get_peak_vram_mb()

    return StrategyResult(
        strategy_name=self.strategy_name,
        sample=self._build_sample_ref(sample),
        predictions=predictions,
        runtime=RuntimeStats(
            inference_ms=elapsed_ms,
            peak_vram_mb=peak_vram_mb,
        ),
    )
```

Opcionalmente, `run()` puede validar que la subclase haya devuelto realmente una `list[InstancePrediction]`.

## Helpers razonables en la base

### `_build_sample_ref(sample)`

Construye `SampleRef` a partir del `ImageSample`.

Esto evita repetir siempre:

- `image_id`
- `width`
- `height`
- `split`
- `corruption`
- `severity`
- `is_clean`

### `_validate_sample(sample)`

Validación ligera de entrada.

No sustituye al validador del `Evaluator`.

Comprobaciones razonables:

- `image_id` válido
- `width > 0` y `height > 0`
- `split` no vacío
- si `sample.image` está cargada, que su shape coincida con `height` y `width`

### `_load_image_if_needed(sample)`

Si `sample.image is None`, carga la imagen desde `sample.image_path`.

Esto desacopla la estrategia de `load_image=True` en el dataset.

### `_reset_peak_vram_stats_if_needed()`

Si hay CUDA:

- `torch.cuda.reset_peak_memory_stats()`

### `_get_peak_vram_mb()`

Si hay CUDA:

- `torch.cuda.max_memory_allocated() / (1024 ** 2)`

Si no hay CUDA:

- `None`

## Qué no debería hacer la clase base

La clase base no debería:

- cargar lógica específica de SAM3 por sí sola
- conocer prompts concretos
- saber nada de SAHI
- saber nada de TTA
- hacer matching
- calcular métricas
- usar GT para evaluar

Su trabajo es solo estructurar la ejecución común de cualquier strategy.

## Baseline recomendado para cerrar el pipeline

La primera estrategia razonable para probar el pipeline completo es una baseline por prompts:

```text
BaselinePromptStrategy
```

No una baseline con cajas GT.

Razones:

- es más coherente con zero-shot
- no le regala localización al modelo
- es comparable luego con SAHI o TTA

## Cómo debe funcionar `BaselinePromptStrategy`

Para cada imagen:

1. cargar la imagen si hace falta
2. recorrer las clases del proyecto
3. para cada clase, construir o recuperar su prompt
4. correr SAM3 sobre la imagen completa con ese prompt
5. recoger todas las máscaras predichas para ese prompt
6. convertir cada máscara en `InstancePrediction`
7. agregar todas las predicciones de todos los prompts
8. devolverlas a través de `run()`

## Configuración esperable de `BaselinePromptStrategy`

Parámetros razonables:

- `model_path`
- `category_map`
- `prompt_map` opcional
- `score_threshold`
- `mask_threshold`
- `top_k` opcional
- `device` opcional

### `category_map`

Mapea:

```python
{
    1: "dent",
    2: "scratch",
    3: "crack",
}
```

### `prompt_map`

Permite desacoplar el texto real del prompt de la etiqueta interna:

```python
{
    1: "dent",
    2: "car scratch",
    3: "crack on vehicle surface",
}
```

Si no se proporciona, se puede usar `category_map` como fallback.

## Qué debe devolver `_predict_instances()` en la baseline por prompts

Debe devolver una lista plana de `InstancePrediction`.

Ejemplo conceptual:

```python
[
    InstancePrediction(category_id=1, ...),
    InstancePrediction(category_id=1, ...),
    InstancePrediction(category_id=2, ...),
    InstancePrediction(category_id=3, ...),
]
```

Reglas:

- una imagen puede generar cero, una o varias instancias por prompt
- no se debería colapsar todo a una única máscara por clase
- el `Evaluator` ya se encargará del matching posterior

## Qué debe contener cada `InstancePrediction`

- `category_id`
- `score`
- `mask`
- `bbox`
- `area`

Recomendación:

- usar la máscara como fuente de verdad
- derivar `bbox` de la máscara
- derivar `area` como suma de píxeles de la máscara

## Semántica del runtime

El runtime de una imagen debe incluir toda la estrategia aplicada a esa imagen.

En la baseline por prompts eso significa:

- si hay 6 clases y se hace una inferencia por prompt, `inference_ms` debe incluir las 6 inferencias

No debe medirse solo un prompt aislado.

Lo mismo con `peak_vram_mb`:

- es el pico de memoria GPU durante toda la ejecución de esa imagen

## Relación con el Evaluator

El `Evaluator` no debería saber si el `StrategyResult` viene de:

- `BaselinePromptStrategy`
- `SAHIStrategy`
- `GeometricTTAStrategy`

Solo debería ver:

- `sample`
- `StrategyResult`

Por eso la normalización de la salida debe hacerse dentro de la strategy.

## Estructura recomendada de archivos

```text
ml/
  strategies/
    __init__.py
    base.py
    baseline_prompt.py
```

Más adelante:

```text
    sahi.py
    tta_geom.py
```

## Uso esperado

Ejemplo de flujo:

```python
dataset = CarddDataset(...)
strategy = BaselinePromptStrategy(...)
evaluator = Evaluator(run_info=...)

for sample in dataset:
    result = strategy.run(sample)
    evaluator.add(sample, result)

eval_output = evaluator.finalize()
```

## Resumen

La abstracción correcta para strategies es:

- entrada pública: `ImageSample`
- salida pública: `StrategyResult`
- `run()` común en la clase base
- `_predict_instances()` específico en cada subclase

Con esto, el pipeline queda modular:

- el dataset es común
- las estrategias son intercambiables
- el evaluador permanece fijo
