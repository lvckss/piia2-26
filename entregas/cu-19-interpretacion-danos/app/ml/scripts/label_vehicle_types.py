from __future__ import annotations

import argparse
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import torch
from PIL import Image
from pycocotools.coco import COCO
from transformers import CLIPModel, CLIPProcessor
from transformers.utils import logging as hf_logging

hf_logging.set_verbosity_error()
hf_logging.disable_progress_bar()


# etiquetas por defecto: cubren los tipos de carroceria mas distintos entre si
# a nivel visual para que el zero-shot de CLIP tenga menos ambiguedad al elegir
DEFAULT_VEHICLE_TYPES: list[str] = [
    "sedan car",
    "suv",
    "pickup truck",
    "van or minivan",
    "motorcycle",
    "bus or truck",
]

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Etiqueta cada imagen de un dataset COCO con un tipo de vehiculo "
            "usando clasificacion zero-shot de CLIP, y guarda el resultado en "
            "un json plano {image_id: vehicle_type} listo para "
            "CarddLoader(vehicle_types_path=...)."
        )
    )
    parser.add_argument(
        "--ann-path",
        required=True,
        type=Path,
        help="ruta al json de anotaciones COCO (instances_all.json, instances_train.json, ...).",
    )
    parser.add_argument(
        "--img-dir",
        required=True,
        type=Path,
        help="carpeta con las imagenes referenciadas en el json de anotaciones.",
    )
    parser.add_argument(
        "--output-path",
        required=True,
        type=Path,
        help="ruta donde escribir el json de salida {image_id: vehicle_type}.",
    )
    parser.add_argument(
        "--vehicle-types",
        nargs="+",
        default=DEFAULT_VEHICLE_TYPES,
        help="lista de tipos de vehiculo candidatos para el zero-shot.",
    )
    parser.add_argument(
        "--clip-model-name",
        default="openai/clip-vit-base-patch32",
        help="modelo CLIP a usar, mismo default que RoiVerifierConfig.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="numero de imagenes por batch al clasificar.",
    )
    parser.add_argument(
        "--device",
        default=None,
        help="cuda o cpu; por defecto usa cuda si esta disponible.",
    )
    return parser.parse_args()


def load_image_entries(ann_path: Path, img_dir: Path) -> list[tuple[int, Path]]:
    # reutiliza el mismo criterio de resolucion de rutas que CarddLoader._resolve_image_path
    with io.StringIO() as buffer, redirect_stdout(buffer):
        coco = COCO(str(ann_path))

    entries: list[tuple[int, Path]] = []
    for image_id in sorted(coco.getImgIds()):
        image_info = coco.loadImgs([image_id])[0]
        image_path = resolve_image_path(img_dir, image_info["file_name"])
        entries.append((int(image_id), image_path))

    return entries


def resolve_image_path(img_dir: Path, file_name: str) -> Path:
    clean_name = file_name.lstrip("./")
    candidates = [img_dir / clean_name, img_dir / "images" / clean_name]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        f"No se encontro la imagen '{file_name}'. Se comprobo en: "
        + ", ".join(str(path) for path in candidates)
    )


def build_text_embeddings(
    model: CLIPModel,
    processor: CLIPProcessor,
    vehicle_types: list[str],
    device: str,
) -> torch.Tensor:
    prompts = [f"a photo of a {vehicle_type}" for vehicle_type in vehicle_types]

    inputs = processor(text=prompts, return_tensors="pt", padding=True)
    inputs = {key: value.to(device) for key, value in inputs.items() if torch.is_tensor(value)}

    with torch.no_grad():
        text_embeddings = model.get_text_features(**inputs)

    return torch.nn.functional.normalize(text_embeddings, dim=-1)


def classify_batch(
    model: CLIPModel,
    processor: CLIPProcessor,
    images: list[Image.Image],
    text_embeddings: torch.Tensor,
    vehicle_types: list[str],
    device: str,
) -> list[str]:
    inputs = processor(images=images, return_tensors="pt")
    inputs = {key: value.to(device) for key, value in inputs.items() if torch.is_tensor(value)}

    with torch.no_grad():
        image_embeddings = model.get_image_features(**inputs)

    image_embeddings = torch.nn.functional.normalize(image_embeddings, dim=-1)
    similarities = image_embeddings @ text_embeddings.T
    best_indices = similarities.argmax(dim=-1).tolist()

    return [vehicle_types[index] for index in best_indices]


def main() -> None:
    args = parse_args()
    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")

    print(f"[carga] modelo CLIP={args.clip_model_name} device={device}")
    model = CLIPModel.from_pretrained(args.clip_model_name).to(device)
    processor = CLIPProcessor.from_pretrained(args.clip_model_name)
    model.eval()

    text_embeddings = build_text_embeddings(model, processor, args.vehicle_types, device)

    print(f"[dataset] cargando anotaciones desde {args.ann_path}")
    entries = load_image_entries(args.ann_path, args.img_dir)
    print(f"[dataset] {len(entries)} imagenes a etiquetar")

    results: dict[int, str] = {}

    for start in range(0, len(entries), args.batch_size):
        batch_entries = entries[start : start + args.batch_size]
        batch_images = [
            Image.open(image_path).convert("RGB") for _, image_path in batch_entries
        ]

        batch_labels = classify_batch(
            model=model,
            processor=processor,
            images=batch_images,
            text_embeddings=text_embeddings,
            vehicle_types=args.vehicle_types,
            device=device,
        )

        for (image_id, _), label in zip(batch_entries, batch_labels):
            results[image_id] = label

        for image in batch_images:
            image.close()

        print(f"[progreso] {min(start + args.batch_size, len(entries))}/{len(entries)}")

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[guardado] {args.output_path}")


if __name__ == "__main__":
    main()
