"""
conda run --no-capture-output -n sam3 python ml/config/tip_adapter/generate_cropped_embeddings.py \
    --local-files-only \
    --output-path ml/config/tip_adapter/flat_tire/cropped_embeddings_001/cache.pt \
    --metadata-path ml/config/tip_adapter/flat_tire/cropped_embeddings_001/cache_metadata.json
"""
# script vibecodeado para generar un cache de embeddings CLIP a partir de crops de ruedas pinchadas y sanas, para usar con tip-adapter

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_CLIP_MODEL_NAME = "openai/clip-vit-base-patch32"


def script_dir() -> Path:
    return Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    default_root = script_dir() / "flat_tire" / "wheel_roi_crops"

    parser = argparse.ArgumentParser(
        description=(
            "genera el cache key-value de tip-adapter a partir de crops "
            "positive/negative ya separados en carpetas"
        )
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=default_root,
        help="carpeta con subcarpetas de clase positive y negative",
    )
    parser.add_argument(
        "--positive-dir-name",
        default="flat",
        help="nombre de la subcarpeta que representa la clase positive",
    )
    parser.add_argument(
        "--negative-dir-name",
        default="healthy",
        help="nombre de la subcarpeta que representa la clase negative",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=script_dir() / "flat_tire" / "cache.pt",
        help="ruta donde se guardará el cache .pt",
    )
    parser.add_argument(
        "--metadata-path",
        type=Path,
        default=script_dir() / "flat_tire" / "cache_metadata.json",
        help="ruta donde se guardará metadata legible del cache",
    )
    parser.add_argument(
        "--clip-model-name",
        default=DEFAULT_CLIP_MODEL_NAME,
        help="modelo CLIP usado para generar los embeddings",
    )
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--device", default=None)
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        help="usa solo pesos ya disponibles en local",
    )
    return parser.parse_args()


def collect_image_paths(folder: Path) -> list[Path]:
    if not folder.exists():
        raise FileNotFoundError(f"no existe la carpeta: {folder}")

    if not folder.is_dir():
        raise NotADirectoryError(f"no es una carpeta: {folder}")

    return sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def load_runtime_dependencies() -> tuple[Any, Any, Any, Any]:
    # estos imports viven aquí para que --help funcione aunque no se esté en el env sam3
    import torch
    from PIL import Image
    from torch.nn import functional as F
    from tqdm.auto import tqdm
    from transformers import CLIPModel, CLIPProcessor

    return torch, Image, F, tqdm, CLIPModel, CLIPProcessor


def load_rgb_images(image_paths: list[Path], image_module: Any) -> list[Any]:
    images = []

    for image_path in image_paths:
        with image_module.open(image_path) as image_file:
            images.append(image_file.convert("RGB"))

    return images


def extract_pooled_features(model_output: Any, torch_module: Any) -> Any:
    # transformers 5 puede devolver un output con pooler_output en lugar de un tensor
    if torch_module.is_tensor(model_output):
        return model_output

    if hasattr(model_output, "pooler_output") and model_output.pooler_output is not None:
        return model_output.pooler_output

    if isinstance(model_output, (tuple, list)):
        if len(model_output) > 1 and torch_module.is_tensor(model_output[1]):
            return model_output[1]

        if len(model_output) > 0 and torch_module.is_tensor(model_output[0]):
            return model_output[0]

    raise TypeError(
        "CLIP devolvió un output sin tensor de features usable. "
        f"tipo recibido={type(model_output)!r}"
    )


def encode_images(
    *,
    image_paths: list[Path],
    model: Any,
    processor: Any,
    torch_module: Any,
    functional_module: Any,
    image_module: Any,
    tqdm_module: Any,
    batch_size: int,
    device: str,
) -> Any:
    all_features = []

    for start in tqdm_module(
        range(0, len(image_paths), batch_size),
        desc="generando embeddings",
    ):
        batch_paths = image_paths[start : start + batch_size]
        images = load_rgb_images(batch_paths, image_module)

        inputs = processor(
            images=images,
            return_tensors="pt",
        )

        inputs = {
            key: value.to(device)
            for key, value in inputs.items()
            if torch_module.is_tensor(value)
        }

        with torch_module.no_grad():
            output = model.get_image_features(**inputs)
            features = extract_pooled_features(output, torch_module)

        all_features.append(functional_module.normalize(features, dim=-1).cpu())

    return torch_module.cat(all_features, dim=0)


def build_cache_values(
    *,
    positive_count: int,
    negative_count: int,
    torch_module: Any,
) -> Any:
    # columna 0 -> positive, columna 1 -> negative
    positive_values = torch_module.tensor(
        [[1.0, 0.0]] * positive_count,
        dtype=torch_module.float32,
    )
    negative_values = torch_module.tensor(
        [[0.0, 1.0]] * negative_count,
        dtype=torch_module.float32,
    )
    return torch_module.cat([positive_values, negative_values], dim=0)


def write_metadata(
    *,
    metadata_path: Path,
    cache_path: Path,
    input_dir: Path,
    clip_model_name: str,
    positive_dir_name: str,
    negative_dir_name: str,
    positive_paths: list[Path],
    negative_paths: list[Path],
    embedding_dim: int,
) -> None:
    metadata = {
        "clip_model_name": clip_model_name,
        "cache_path": str(cache_path.resolve()),
        "input_dir": str(input_dir.resolve()),
        "positive_dir_name": positive_dir_name,
        "negative_dir_name": negative_dir_name,
        "positive_count": len(positive_paths),
        "negative_count": len(negative_paths),
        "total_count": len(positive_paths) + len(negative_paths),
        "embedding_dim": embedding_dim,
        "cache_keys": "[num_examples, embedding_dim]",
        "cache_values": "[num_examples, 2], columnas: positive, negative",
        "positive_files": [path.name for path in positive_paths],
        "negative_files": [path.name for path in negative_paths],
    }

    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()

    if args.batch_size <= 0:
        raise ValueError("batch-size debe ser > 0.")

    if args.local_files_only:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    torch, Image, F, tqdm, CLIPModel, CLIPProcessor = load_runtime_dependencies()
    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")

    positive_dir = args.input_dir / args.positive_dir_name
    negative_dir = args.input_dir / args.negative_dir_name

    positive_paths = collect_image_paths(positive_dir)
    negative_paths = collect_image_paths(negative_dir)

    if not positive_paths:
        raise ValueError(f"no hay imágenes en la carpeta positive: {positive_dir}")

    if not negative_paths:
        raise ValueError(f"no hay imágenes en la carpeta negative: {negative_dir}")

    image_paths = positive_paths + negative_paths

    print(f"modelo CLIP: {args.clip_model_name}")
    print(f"device: {device}")
    print(f"positive: {len(positive_paths)} imágenes ({positive_dir})")
    print(f"negative: {len(negative_paths)} imágenes ({negative_dir})")

    model = CLIPModel.from_pretrained(
        args.clip_model_name,
        local_files_only=args.local_files_only,
    ).to(device)
    processor = CLIPProcessor.from_pretrained(
        args.clip_model_name,
        local_files_only=args.local_files_only,
    )
    model.eval()

    cache_keys = encode_images(
        image_paths=image_paths,
        model=model,
        processor=processor,
        torch_module=torch,
        functional_module=F,
        image_module=Image,
        tqdm_module=tqdm,
        batch_size=args.batch_size,
        device=device,
    )
    cache_values = build_cache_values(
        positive_count=len(positive_paths),
        negative_count=len(negative_paths),
        torch_module=torch,
    )

    cache = {
        "cache_keys": cache_keys,
        "cache_values": cache_values,
        "clip_model_name": args.clip_model_name,
        "positive_label": args.positive_dir_name,
        "negative_label": args.negative_dir_name,
        "image_paths": [str(path.resolve()) for path in image_paths],
        "labels": (
            [args.positive_dir_name] * len(positive_paths)
            + [args.negative_dir_name] * len(negative_paths)
        ),
    }

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(cache, args.output_path)

    write_metadata(
        metadata_path=args.metadata_path,
        cache_path=args.output_path,
        input_dir=args.input_dir,
        clip_model_name=args.clip_model_name,
        positive_dir_name=args.positive_dir_name,
        negative_dir_name=args.negative_dir_name,
        positive_paths=positive_paths,
        negative_paths=negative_paths,
        embedding_dim=int(cache_keys.shape[1]),
    )

    print(f"cache_keys: {tuple(cache_keys.shape)}")
    print(f"cache_values: {tuple(cache_values.shape)}")
    print(f"cache guardado en: {args.output_path}")
    print(f"metadata guardada en: {args.metadata_path}")


if __name__ == "__main__":
    main()
