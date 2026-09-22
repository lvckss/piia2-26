# Guia rapida del pipeline ML

Objetivo: evaluar imagenes sin escribir helpers cada vez.

> [!TIP]
> Si estas en un notebook y empiezas a escribir funciones para calcular AP, FP, FN, tiempos o plots, para. Eso ya lo hace el pipeline.

La forma correcta es siempre esta:

```text
CarddLoader -> Strategy -> Evaluator -> Output + Inspection
```

- `CarddLoader`: carga imagenes y anotaciones.
- `Strategy`: predice mascaras.
- `Evaluator`: calcula metricas.
- `Inspection`: busca errores y dibuja casos.

> [!NOTE]
> El notebook solo deberia orquestar: crear dataset, crear estrategia, lanzar evaluator y mirar resultados.

## Uso minimo

```python
from pathlib import Path

from ml.StrategyPipeline.data.loader import CarddLoader
from ml.StrategyPipeline.evaluation.evaluator import Evaluator
from ml.StrategyPipeline.schemas import RunInfo
from ml.StrategyPipeline.strategies.baseline import BaselineStrategy
from ml.StrategyPipeline.strategies.components.sam3_backend import (
    ExemplarRef,
    PromptSpec,
)
```

```python
ROOT = Path("/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app")
DATA = ROOT / "bd" / "rawdata"
SAM3 = ROOT.parent.parent / "models" / "facebook_sam3"

CATEGORY_MAP = {
    1: "dent",
    2: "scratch",
    3: "crack",
    4: "glass shatter",
    5: "lamp broken",
    6: "tire flat",
}

PROMPT_MAP = {
    1: "a visible dent on the metal body of a car",
    2: "a visible scratch on the painted surface of a car",
    3: "a visible crack on a car part or surface",
    4: "shattered or broken car window glass",
    5: "a broken or damaged car headlamp or tail lamp",
    6: "a flat or deflated car tire",
}
```

```python
dataset = CarddLoader(
    ann_path=str(DATA / "instances_all.json"),
    img_dir=str(DATA / "images"),
    load_image=False,
)

strategy = BaselineStrategy(
    model_path=str(SAM3),
    category_map=CATEGORY_MAP,
    prompt_map=PROMPT_MAP,
    score_threshold=0.85,
    mask_threshold=0.5,
    prompt_batch_size=6,
)
```

> [!TIP]
> Usa `load_image=False` en runs largas. Consume menos memoria y la estrategia carga cada imagen cuando la necesita.

## Sistema de prompts

Ahora `prompt_map` ya no está limitado a `str`.

El backend nuevo acepta un `prompt_map` de tipo:

```python
dict[int, PromptValue]
```

Donde cada valor puede ser:

- `str`
- `PromptSpec`
- `list[str | PromptSpec]`

> [!IMPORTANT]
> Cada clase puede tener como máximo un prompt con texto.
> Eso incluye `str`, `PromptSpec(mode="text")` y `PromptSpec(mode="hybrid")`.
> Si quieres combinar texto y exemplars, usa un único `PromptSpec.hybrid_prompt(...)`.

Esto funciona igual para `BaselineStrategy`, `SahiStrategy` y `GeometricEnsembleStrategy`.

> [!IMPORTANT]
> El sistema de prompts es agnóstico a la strategy.
> La strategy decide si trabaja con imagen completa, slices o refinamiento geométrico.
> El backend decide cómo lanzar SAM3 para cada prompt.

## Prompt texto simple

Esto sigue funcionando igual que antes:

```python
PROMPT_MAP = {
    1: "a visible dent on the metal body of a car",
    2: "a visible scratch on the painted surface of a car",
    3: "a visible crack on a car part or surface",
    4: "shattered or broken car window glass",
    5: "a broken or damaged car headlamp or tail lamp",
    6: "a flat or deflated car tire",
}
```

En esta ruta:

- `BaselineStrategy` ejecuta varios prompts sobre una misma imagen.
- `SahiStrategy` ejecuta un mismo prompt sobre imagen completa o varios slices.
- el backend usa `transformers.Sam3Model` + `transformers.Sam3Processor`.
- los prompts de texto sí aprovechan batching real.

## Una sola entrada de texto por clase

```python
PROMPT_MAP = {
    5: "a broken or damaged car headlamp or tail lamp",
}
```

Regla:

- cada categoría puede tener solo un texto
- si intentas meter dos textos para la misma categoría, el backend lanza `StrategyContractError`
- si quieres texto + support visual, usa `PromptSpec.hybrid_prompt(...)`
- si quieres varios exemplars, mételos dentro del mismo `PromptSpec`

Ejemplo correcto de texto + exemplars en una sola definición:

```python
PROMPT_MAP = {
    6: PromptSpec.hybrid_prompt(
        "a flat car tire",
        [
            ExemplarRef("ml/config/exemplars/tire_flat/flat_001.jpg"),
            ExemplarRef("ml/config/exemplars/tire_flat/flat_002.jpg"),
        ],
        name="flat_tire_hybrid",
    ),
}
```

## PromptSpec

`PromptSpec` permite describir prompts más ricos:

- `mode="text"`: solo texto
- `mode="exemplar"`: solo image exemplars
- `mode="hybrid"`: texto + image exemplars

`ExemplarRef` representa una imagen exemplar y, opcionalmente, una caja `xywh` dentro de esa imagen.

Ejemplo de prompt híbrido:

```python
PROMPT_MAP = {
    6: PromptSpec.hybrid_prompt(
        "a flat car tire",
        [
            ExemplarRef("ml/config/exemplars/tire_flat/flat_001.jpg"),
            ExemplarRef("ml/config/exemplars/tire_flat/flat_002.jpg"),
        ],
        name="flat_tire_hybrid",
    ),
}
```

Ejemplo de prompt exemplar puro:

```python
PROMPT_MAP = {
    6: PromptSpec.exemplar_prompt(
        [
            ExemplarRef("ml/config/exemplars/tire_flat/flat_001.jpg"),
            ExemplarRef("ml/config/exemplars/tire_flat/flat_002.jpg"),
        ],
        name="flat_tire_visual_only",
    ),
}
```

Ejemplo con caja dentro del exemplar:

```python
PROMPT_MAP = {
    6: PromptSpec.hybrid_prompt(
        "a flat car tire",
        [
            ExemplarRef(
                "ml/config/exemplars/tire_flat/example_scene.jpg",
                bbox_xywh=(120, 80, 260, 220),
            ),
        ],
        name="flat_tire_roi",
    ),
}
```

## Usar una carpeta de exemplars

Si tienes una carpeta con imágenes support, puedes usar el helper:

```python
PROMPT_MAP = {
    6: PromptSpec.from_exemplar_dir(
        "ml/config/exemplars/tire_flat",
        text="a flat car tire",
        name="flat_tire_dir",
    ),
}
```

Eso usa todas las imágenes válidas de esa carpeta como exemplars:

- `.jpg`
- `.jpeg`
- `.png`
- `.webp`
- `.bmp`

> [!NOTE]
> `PromptSpec.from_exemplar_dir(...)` usa todas las imágenes del directorio.
> No hace muestreo ni ranking automático.

Si dentro de esa carpeta existe `manifest.json`, el helper usa el manifest automáticamente.

## Usar un manifest directamente

Si exportaste exemplars con el script de `ml/scripts`, ya puedes cargarlos sin escribir los `ExemplarRef(...)` a mano:

```python
PROMPT_MAP = {
    6: PromptSpec.from_manifest(
        "ml/config/image_exemplars/6_tire_flat/manifest.json"
    ),
}
```

También puedes construir un `prompt_map` entero desde varios manifests:

```python
from ml.StrategyPipeline.strategies.components.sam3_backend import (
    prompt_map_from_manifests,
)

PROMPT_MAP = prompt_map_from_manifests(
    "ml/config/image_exemplars/1_dent/manifest.json",
    "ml/config/image_exemplars/3_crack/manifest.json",
    "ml/config/image_exemplars/6_tire_flat/manifest.json",
)
```

> [!TIP]
> `PromptSpec.from_manifest(...)` acepta overrides opcionales de `text`, `mode` y `name`.
> `PromptSpec.from_exemplar_dir(...)` también usa el manifest si lo encuentra en la carpeta.

## Usar un solo exemplar por clase

Si quieres una versión rápida de `1-shot`, puedes quedarte con un único exemplar del `manifest.json`.

Ejemplo: coger el primer exemplar de cada manifest y convertirlo en un `PromptSpec` híbrido de una sola imagen.

```python
import json
from pathlib import Path

from ml.StrategyPipeline.strategies.components.sam3_backend import (
    ExemplarRef,
    PromptSpec,
)


def one_shot_from_manifest(manifest_path):
    manifest_path = Path(manifest_path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    exemplar = data["exemplars"][0]

    return PromptSpec.hybrid_prompt(
        data["text"],
        [
            ExemplarRef(
                str((manifest_path.parent / exemplar["image"]).resolve()),
                bbox_xywh=tuple(exemplar["bbox_xywh"]),
            )
        ],
        name=f'{data["category_name"]}_1shot',
    )
```

```python
PROMPT_MAP = {
    1: one_shot_from_manifest(ROOT / "ml/config/image_exemplars/1_dent/manifest.json"),
    3: one_shot_from_manifest(ROOT / "ml/config/image_exemplars/3_crack/manifest.json"),
}
```

> [!TIP]
> Si prefieres control total, puedes construir ese `PromptSpec.hybrid_prompt(...)` a mano con un solo `ExemplarRef(...)`.

## Cómo se ejecuta internamente

Hay tres rutas internas:

### 1. prompt solo texto

- usa el backend de `transformers`
- permite batching real
- es la ruta más barata y más rápida

### 2. prompt con exemplars

- usa el backend nativo del paquete `sam3`
- cose todos los exemplars y el target en una sola imagen compuesta
- construye una caja positiva por cada exemplar
- opcionalmente añade también el texto si el modo es `hybrid`
- filtra las detecciones para quedarse solo con las que caen en la parte target
- aplica un nms final entre máscaras para quitar duplicados entre exemplars

> [!WARNING]
> La ruta con exemplars no tiene el mismo batching que la ruta de texto.
> Si metes muchos exemplars, el coste sube porque el composite se hace más ancho y la inferencia pesa más.

### 3. prompt texto + ensemble geométrico

- genera una predicción seed usando texto normal
- convierte cada seed en una caja `xywh`
- crea varias perturbaciones geométricas de esa caja
- relanza SAM3 con el mismo texto y `input_boxes`
- fusiona las máscaras por voto por píxel
- se queda solo con las regiones que alcanzan el consenso configurado

> [!NOTE]
> El ensemble geométrico solo afecta a prompts de texto.
> Si una categoría usa exemplars o hybrid, esa parte sigue yendo por su ruta normal.

## Requisitos para exemplars

Los prompts de texto funcionan con el stack actual de `transformers`.

Los prompts con exemplars requieren además el paquete nativo `sam3` instalado en el entorno activo.

Si no está instalado:

- las strategies con prompts solo texto seguirán funcionando
- fallará solo cuando intentes usar un prompt con exemplars

## Qué guarda cada predicción

El backend añade metadata útil a cada predicción:

- `sam3_backend`
- `prompt_name`
- `prompt_mode`
- `sam3_prompt`
- `exemplar_paths`
- `exemplar_count`
- `exemplar_bboxes_xywh`

Y si la predicción viene de exemplars, además:

- `sam3_exemplar_prompt_boxes_xywh`
- `sam3_target_box_xyxy`

Y si el prompt tenía un solo exemplar, además:

- `exemplar_image_path`
- `exemplar_bbox_xywh`

Esto sirve para inspección, debug y explainability.

Si la predicción viene de ensemble geométrico, además se guarda:

- `sam3_seed_score`
- `sam3_seed_bbox_xywh`
- `ensemble_num_perturbations`
- `ensemble_perturbation_scale`
- `ensemble_consensus_threshold`
- `ensemble_min_votes`
- `ensemble_max_votes`

## Relación con las strategies

La api del prompt es la misma en las tres strategies principales.

La diferencia está en cómo se usa:

- `BaselineStrategy`: una imagen, muchos prompts
- `SahiStrategy`: un prompt, una imagen completa o muchos slices
- `GeometricEnsembleStrategy`: una imagen, varios prompts, y refinamiento por cajas perturbadas en los prompts de texto

En todos los casos:

- el backend decide si un prompt va por texto o por exemplars
- la strategy sigue siendo responsable de colocar la máscara final en coordenadas globales
- el `Evaluator` no cambia

## Relación con Tip-Adapter

Si una categoría usa `RoiVerificationManager`:

- las propuestas iniciales para esa categoría siguen usando prompts de texto genéricos
- luego `Tip-Adapter` decide positive vs negative sobre las roi candidatas

Es decir:

- image exemplars y tip-adapter son cosas distintas
- se pueden usar en el mismo proyecto
- pero tip-adapter sigue trabajando sobre roi candidates, no sobre el sistema de prompts general
- si usas `GeometricEnsembleStrategy`, primero se hace el consenso geométrico y luego se verifica la roi final con CLIP + tip-adapter

## GeometricEnsembleStrategy

Si quieres una variante más robusta para prompts de texto, puedes usar `GeometricEnsembleStrategy`.

La idea es:

- SAM3 encuentra una seed inicial con texto
- esa seed se perturba varias veces como caja geométrica
- SAM3 vuelve a inferir guiado por esas cajas
- la máscara final sale de una votación por píxel

Ejemplo:

```python
from ml.StrategyPipeline.strategies.geom_ensemble import (
    GeometricEnsembleStrategy,
)

strategy = GeometricEnsembleStrategy(
    model_path=str(SAM3),
    category_map=CATEGORY_MAP,
    prompt_map=PROMPT_MAP,
    score_threshold=0.3,
    mask_threshold=0.5,
    num_perturbations=5,
    perturbation_scale=0.05,
    consensus_threshold=0.6,
    random_seed=42,
)
```

Parámetros importantes:

- `num_perturbations`: cuántas cajas perturbadas se generan por seed
- `perturbation_scale`: cuánto ruido geométrico se mete en posición y tamaño
- `consensus_threshold`: fracción mínima de votos por píxel para aceptar la región

> [!TIP]
> Si el prompt de texto ya es estable, empieza con `num_perturbations=5` y `consensus_threshold=0.6`.
> Si ves demasiado ruido, sube `consensus_threshold`.

## Recomendaciones prácticas

- empieza con texto simple
- afina un único prompt de texto antes de meter exemplars
- si necesitas texto + support visual, usa un `PromptSpec.hybrid_prompt(...)`
- usa exemplars solo en clases donde el texto se quede corto
- si un exemplar contiene mucho fondo, pásale `bbox_xywh`
- no metas decenas de exemplars sin necesidad
- guarda en `RunInfo.config` qué prompts, carpetas de exemplars o nombres de prompt has usado

## Evaluar una imagen

```python
sample = dataset.get_by_image_id(928)

evaluator = Evaluator(
    RunInfo(
        run_name="debug_one_image",
        strategy_name=strategy.strategy_name,
        dataset_name=dataset.dataset_name,
        ann_path=str(dataset.ann_path),
    ),
    category_map=CATEGORY_MAP,
)

evaluator.add(sample, strategy.run(sample))

output = evaluator.finalize()
inspection = evaluator.get_inspection()
```

```python
output.summary
inspection.plot(928)
```

> [!NOTE]
> Esta receta de una imagen sirve para debug rapido. No necesitas otro flujo especial.

## Evaluar todo

```python
evaluator = Evaluator(
    RunInfo(
        run_name="sam3_baseline_v1",
        strategy_name=strategy.strategy_name,
        dataset_name=dataset.dataset_name,
        ann_path=str(dataset.ann_path),
        config={
            "score_threshold": 0.85,
            "mask_threshold": 0.5,
            "prompt_batch_size": 6,
        },
    ),
    category_map=CATEGORY_MAP,
)

for sample in dataset:
    evaluator.add(sample, strategy.run(sample))

output = evaluator.finalize()
inspection = evaluator.get_inspection()
```

Guardar:

```python
run_dir = ROOT / "ml" / "notebooks" / "results" / "sam3_baseline_v1"
run_dir.mkdir(parents=True, exist_ok=True)

(run_dir / "output.json").write_text(
    output.to_json(include_run_info=True),
    encoding="utf-8",
)

output.per_image.to_csv(run_dir / "per_image.csv", index=False)
output.per_class.to_csv(run_dir / "per_class.csv", index=False)
output.per_condition.to_csv(run_dir / "per_condition.csv", index=False)
```

> [!IMPORTANT]
> Crea un `Evaluator` nuevo para cada run. No reutilices el mismo evaluator entre configuraciones distintas.

## Que mirar

```python
output.summary
```

Lo importante:

- `mask_ap_50_95`: metrica principal.
- `ap75`: AP mas estricto.
- `fp_per_image`: falsos positivos medios.
- `ms_per_image`: tiempo medio.
- `peak_vram_mb`: pico de VRAM.

> [!TIP]
> Para decidir si una run mejora, mira primero `mask_ap_50_95`, `fp_per_image` y `per_class`. Luego inspecciona imagenes malas con `inspection`.

```python
output.per_class
```

Sirve para ver que clase falla.

```python
output.per_image
```

Sirve para encontrar imagenes malas.

```python
output.per_condition
```

Sirve para ver robustez por corrupcion/severidad.

## Inspeccionar errores

Peores FP:

```python
worst_fp = (
    inspection.search()
    .sort_values("fp_iou50", ascending=False)
    .head(20)
)
```

Peores FN:

```python
worst_fn = (
    inspection.search()
    .sort_values("fn_iou50", ascending=False)
    .head(20)
)
```

Dibujar:

```python
image_id = int(worst_fp.iloc[0]["image_id"])
inspection.plot(image_id)
```

Ver predicciones y GT:

```python
item = inspection.get(image_id)
item.record.gt_instances
item.record.pred_instances
item.metrics
```

## Tip-Adapter en una frase

Usalo solo si SAM3 encuentra el objeto, pero confunde sano vs danado.

Ejemplo: detecta una rueda, pero no sabe si esta pinchada.

> [!WARNING]
> No actives Tip-Adapter por defecto para todo. Usalo solo en clases donde haya confusion clara entre objeto sano y objeto danado.

Funciona igual con:

- `BaselineStrategy`
- `SahiStrategy`
- `GeometricEnsembleStrategy`

```python
from ml.StrategyPipeline.strategies.components.clip_tip_adapter import RoiVerifierConfig

tire_flat_config = RoiVerifierConfig(
    target_category_id=6,
    positive_label="tire flat",
    negative_label="healthy tire",
    proposal_prompts=["a visible car tire"],
    positive_text_prompts=["a flat deflated car tire", "a car tire with no air"],
    negative_text_prompts=["a normal inflated car tire", "a healthy car tire"],
    cache_path=str(ROOT / "ml/config/tip_adapter/flat_tire/cropped_embeddings_001/cache.pt"),
    alpha=2.0,
    beta=50.0,
    threshold=0.5,
    crop_padding_frac=0.25,
    max_proposals_per_image=6,
)

strategy = BaselineStrategy(
    model_path=str(SAM3),
    category_map=CATEGORY_MAP,
    prompt_map=PROMPT_MAP,
    score_threshold=0.85,
    mask_threshold=0.5,
    prompt_batch_size=6,
    enable_roi_verification=True,
    roi_verifier_configs=[tire_flat_config],
)
```

Si no quieres escribir el `RoiVerifierConfig` completo, usa el helper corto:

```python
from ml.StrategyPipeline.strategies.components.clip_tip_adapter import (
    simple_roi_verifier_config,
)

tire_flat_config = simple_roi_verifier_config(
    target_category_id=6,
    proposal_prompt="a visible car tire",
    cache_path=str(ROOT / "ml/config/tip_adapter/flat_tire/cropped_embeddings_001/cache.pt"),
    positive_label="flat car tire",
    negative_label="healthy car tire",
)
```

```python
lamp_config = simple_roi_verifier_config(
    target_category_id=5,
    proposal_prompt="a visible car headlamp or tail lamp",
    cache_path=str(ROOT / "ml/config/tip_adapter/broken_lamp/cropped_embeddings_001/cache.pt"),
    positive_label="broken car lamp",
    negative_label="healthy car lamp",
)
```

Ese helper:

- mete `proposal_prompts=[proposal_prompt]`
- intenta leer `clip_model_name` desde `cache_metadata.json`
- genera prompts de texto básicos si no los pasas a mano
- deja los hiperparámetros de tip-adapter con defaults razonables

Si quieres, puedes usar también el classmethod equivalente:

```python
tire_flat_config = RoiVerifierConfig.simple(
    target_category_id=6,
    proposal_prompt="a visible car tire",
    cache_path=str(ROOT / "ml/config/tip_adapter/flat_tire/cropped_embeddings_001/cache.pt"),
    positive_label="flat car tire",
    negative_label="healthy car tire",
)
```

> [!TIP]
> Si el `cache_metadata.json` solo tiene nombres de carpeta tipo `flat`, `healthy` o `broken`, suele ser mejor pasar `positive_label` y `negative_label` manualmente para que los prompts automáticos sean más naturales.

Para crear el cache:

```bash
conda run --no-capture-output -n sam3 python ml/config/tip_adapter/generate_cropped_embeddings.py \
  --local-files-only \
  --input-dir ml/config/tip_adapter/flat_tire/wheel_roi_crops \
  --positive-dir-name flat \
  --negative-dir-name healthy \
  --output-path ml/config/tip_adapter/flat_tire/cropped_embeddings_001/cache.pt \
  --metadata-path ml/config/tip_adapter/flat_tire/cropped_embeddings_001/cache_metadata.json
```

> [!IMPORTANT]
> Si cambias crops, modelo CLIP o etiquetas positive/negative, regenera el cache.

## Crear una estrategia nueva

No crees una funcion nueva de evaluacion.

Crea una clase que herede de `StrategyModule` y solo implementa `_predict_instances()`.

> [!NOTE]
> `StrategyModule` ya mide tiempo, VRAM, valida el formato y empaqueta el resultado.

```python
from ml.StrategyPipeline.schemas import ImageSample, InstancePrediction
from ml.StrategyPipeline.strategies.base import StrategyModule


class MyStrategy(StrategyModule):
    def __init__(self, category_map: dict[int, str]) -> None:
        super().__init__("my_strategy", category_map)

    def _predict_instances(self, sample: ImageSample) -> list[InstancePrediction]:
        predictions = []
        return predictions
```

Cada prediccion debe ser un `InstancePrediction` con:

- `category_id`
- `score` entre `0` y `1`
- `mask` booleana con shape `(height, width)`
- `bbox` en formato `xywh`
- `area`

La estrategia predice. El evaluator evalua.

> [!IMPORTANT]
> La estrategia nunca debe devolver metricas. Solo predicciones finales.

## Reglas importantes

> [!IMPORTANT]
> - Usa un `Evaluator` nuevo por run.
> - En `RunInfo`, usa `strategy_name=strategy.strategy_name`.
> - Guarda siempre `output.to_json(include_run_info=True)`.
> - Mete thresholds, prompts y caches en `RunInfo.config`.

> [!WARNING]
> - No repitas `image_id` dentro del mismo evaluator.
> - No calcules AP, FP, FN o tiempos a mano.
> - No uses GT dentro de una estrategia real.
> - Si una mascara viene de crop/tile, remapeala al tamano original antes de devolverla.

> [!TIP]
> Ajusta prompts y thresholds con `val`. Reporta `test` solo cuando la configuracion este cerrada.

## Errores tipicos

> [!WARNING]
> `StrategyResult no pertenece al strategy del run`
>
> `RunInfo.strategy_name` esta mal. Usa `strategy.strategy_name`.

> [!WARNING]
> `La imagen ya fue anadida al evaluator`
>
> Estas reutilizando evaluator o repitiendo imagen. Crea otro evaluator.

> [!WARNING]
> `Mascara con shape invalido`
>
> La mascara no mide `(sample.height, sample.width)`.

> [!WARNING]
> `category_id desconocido`
>
> La clase no esta en `CATEGORY_MAP`.

## Resumen

```python
dataset = CarddLoader(...)
strategy = BaselineStrategy(...)
evaluator = Evaluator(...)

for sample in dataset:
    evaluator.add(sample, strategy.run(sample))

output = evaluator.finalize()
inspection = evaluator.get_inspection()
```

Si necesitas algo mas, probablemente es una nueva `Strategy`, una nueva metrica dentro del `Evaluator`, o una config mejor.

> [!IMPORTANT]
> El pipeline es el contrato. Si algo no encaja, primero piensa si debe ser una `Strategy`, una metrica del `Evaluator` o una config.
