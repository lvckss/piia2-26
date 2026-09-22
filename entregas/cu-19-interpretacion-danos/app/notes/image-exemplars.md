# Nota práctica: exportar image exemplars desde `instances_all.json`

## Objetivo

Tener una forma rápida de construir support sets de `image exemplars` a partir del dataset ya anotado:

- leer `bd/rawdata/instances_all.json`
- escoger una categoría
- pasar una lista de `image_id`
- copiar las imágenes originales a `ml/config/image_exemplars/...`
- generar un `manifest.json` con la `bbox_xywh` correcta para cada exemplar

Esto evita tener que montar los `ExemplarRef(...)` a mano cada vez.

## Script

El script está en:

```text
ml/scripts/export_image_exemplars_from_instances.py
```

Usa solo `stdlib`, así que no depende de `pycocotools`.

## Dataset de entrada

Se apoya en:

```text
bd/rawdata/instances_all.json
bd/rawdata/images/
```

`instances_all.json` está en formato tipo COCO:

- `images`
- `annotations`
- `categories`

Para cada `image_id` pedido, el script busca una anotación de la categoría objetivo y usa su `bbox`.

## Qué genera

Por defecto crea una carpeta dentro de:

```text
ml/config/image_exemplars/
```

El nombre por defecto es:

```text
<category_id>_<category_name_slug>
```

Ejemplo:

```text
ml/config/image_exemplars/6_tire_flat/
```

Dentro deja:

- las imágenes originales copiadas
- `manifest.json`

## Formato del `manifest.json`

El manifest guarda:

- `category_id`
- `category_name`
- `mode`
- `text`
- `source`
- `exemplars`

Cada exemplar guarda:

- `image`
- `image_id`
- `annotation_id`
- `bbox_xywh`
- `area`
- `width`
- `height`
- `source_file_name`

Ejemplo simplificado:

```json
{
  "category_id": 6,
  "category_name": "tire flat",
  "mode": "hybrid",
  "text": "tire flat",
  "exemplars": [
    {
      "image": "000012.jpg",
      "image_id": 12,
      "annotation_id": 1,
      "bbox_xywh": [32.61, 221.06, 331.72, 332.82]
    }
  ]
}
```

## Selección de bbox

Una imagen puede tener varias anotaciones de la misma clase.

Para `image exemplars` necesitamos quedarnos con una sola `bbox` por imagen.

El script soporta tres políticas:

- `largest`
  Usa la instancia con más `area`. Es la opción por defecto.
- `first`
  Usa la anotación con menor `annotation_id`.
- `error`
  Falla si hay más de una instancia de esa clase en la imagen.

## Uso típico

Ejemplo para `tire flat`:

```bash
python ml/scripts/export_image_exemplars_from_instances.py \
  --category 6 \
  --image-ids 12 57 237 353 712
```

También se puede pasar el nombre de la categoría:

```bash
python ml/scripts/export_image_exemplars_from_instances.py \
  --category "tire flat" \
  --image-ids 12 57 237 353 712
```

## Flags útiles

- `--mode exemplar`
  Guarda el manifest como prompt visual puro.

- `--mode hybrid`
  Guarda el manifest como prompt mixto texto + exemplars.

- `--text "a flat car tire"`
  Sobrescribe el texto que se guarda en el manifest.

- `--folder-name tire_flat_support_v1`
  Fuerza el nombre de la carpeta de salida.

- `--output-root ...`
  Cambia la raíz de salida.

- `--multi-ann-policy error`
  Obliga a revisar a mano las imágenes ambiguas.

## Ejemplos

Prompt híbrido:

```bash
python ml/scripts/export_image_exemplars_from_instances.py \
  --category 6 \
  --image-ids 12 57 237 353 712 \
  --mode hybrid \
  --text "a flat car tire"
```

Prompt visual puro:

```bash
python ml/scripts/export_image_exemplars_from_instances.py \
  --category "lamp broken" \
  --image-ids 40 82 106 152 214 \
  --mode exemplar
```

## Relación con el backend actual

El backend de prompts ya soporta:

- `PromptSpec`
- `ExemplarRef`
- `bbox_xywh`
- varios exemplars en una sola inferencia por `PromptSpec`

Lo que este script resuelve es la parte de preparación del support set.

Ahora mismo el manifest queda listo para:

- trazabilidad
- reutilización
- no perder qué `bbox` salió de qué anotación

Ahora sí existe carga directa desde manifest:

- `PromptSpec.from_manifest(...)`
- `prompt_map_from_manifests(...)`
- `PromptSpec.from_exemplar_dir(...)` usa `manifest.json` automáticamente si está presente

Ejemplo mínimo:

```python
from ml.StrategyPipeline.strategies.components.sam3_backend import PromptSpec

PROMPT_MAP = {
    6: PromptSpec.from_manifest(
        "ml/config/image_exemplars/6_tire_flat/manifest.json"
    ),
}
```

Ejemplo para varias clases:

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

## Recomendación práctica

Para cada clase:

- escoger 5 imágenes buenas
- revisar si cada imagen tiene una sola instancia clara
- exportarlas con este script
- dejar la carpeta en `ml/config/image_exemplars/<categoria>/`

Ejemplo de estructura:

```text
ml/config/image_exemplars/
  1_dent/
    manifest.json
    000023.jpg
    000033.jpg
    ...
  6_tire_flat/
    manifest.json
    000012.jpg
    000057.jpg
    ...
```

## Verificación rápida

Si quieres revisar qué va a salir antes de integrarlo en un prompt:

1. abrir el `manifest.json`
2. comprobar `image_id`, `annotation_id` y `bbox_xywh`
3. confirmar que la caja apunta al objeto correcto y no a otra instancia de la misma clase

Si una imagen no es limpia como exemplar, lo correcto es cambiar el `image_id`, no intentar arreglarlo después en la strategy.
