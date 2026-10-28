from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    import numpy as np
    import torch
    from PIL import Image
    from pycocotools.coco import COCO
    from tqdm.auto import tqdm
    from transformers import Sam3Model, Sam3Processor


# mismo patron que export_lamp_roi_crops.py (que a su vez viene de
# export_wheel_roi_crops.py, ver su comentario "REUTILIZAR ESTO PARA LOS
# FAROS"): dent no tiene un "objeto sano" tan claro como una rueda o un faro,
# asi que el rol de "healthy" lo hace un panel de carroceria sin dano, y las
# propuestas sam3 para healthy usan prompts genericos de panel en vez de un
# prompt de dent.
DENT_CATEGORY_ID = 1

DEFAULT_PANEL_PROMPTS = [
    "a car door panel",
    "a car fender panel",
    "a car hood or trunk panel",
    "a car body panel",
]


def load_runtime_dependencies() -> None:
    global COCO, Image, Sam3Model, Sam3Processor, np, torch, tqdm

    try:
        import numpy as np
        import torch
        from PIL import Image
        from pycocotools.coco import COCO
        from tqdm.auto import tqdm
        import transformers.utils as transformers_utils
        import transformers.utils.import_utils as transformers_import_utils
        from transformers.utils import logging as hf_logging
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing Python dependency for dent ROI export: "
            f"{exc.name}. Run this script from the ML/Jupyter environment "
            "that has numpy, torch, transformers, pillow, pycocotools and tqdm."
        ) from exc

    # el env local de sam3 tiene dependencias opcionales rotas para rutas que aqui no usamos
    for name, replacement in {
        "is_sklearn_available": lambda: False,
        "is_scipy_available": lambda: False,
        "is_accelerate_available": lambda min_version="1.1.0": False,
    }.items():
        original = getattr(transformers_import_utils, name)
        original.cache_clear()
        setattr(transformers_import_utils, name, replacement)
        setattr(transformers_utils, name, replacement)

    from transformers import Sam3Model, Sam3Processor

    hf_logging.disable_progress_bar()


@dataclass(frozen=True)
class Sam3Proposal:
    prompt: str
    score: float
    mask: Any
    bbox_xyxy: tuple[int, int, int, int]
    mask_area: int


def find_project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "bd" / "rawdata").exists() and (parent / "ml").exists():
            return parent
    raise RuntimeError("Could not find project root from script location.")


def default_model_path(project_root: Path) -> Path:
    env_path = os.environ.get("SAM3_PATH")
    if env_path:
        return Path(env_path)

    candidates = [
        project_root.parent.parent / "models" / "facebook_sam3",
        project_root / "models" / "facebook_sam3",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]


def parse_args() -> argparse.Namespace:
    project_root = find_project_root()

    parser = argparse.ArgumentParser(
        description=(
            "Export dent ROI crops for a dent/healthy support set. "
            "Dent crops use dent GT boxes by default; healthy crops use SAM3 "
            "panel proposals sobre imagenes sin dano en ese panel."
        )
    )
    parser.add_argument(
        "--ann-path",
        type=Path,
        default=project_root / "bd" / "rawdata" / "instances_all.json",
    )
    parser.add_argument(
        "--img-dir",
        type=Path,
        default=project_root / "bd" / "rawdata" / "images",
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=default_model_path(project_root),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_root / "ml" / "config" / "tip_adapter" / "dent" / "dent_roi_crops",
    )
    parser.add_argument(
        "--dent-ids",
        nargs="*",
        type=int,
        default=[],
        help="image ids con dents. si dent-source=gt, se recortan por bbox GT.",
    )
    parser.add_argument(
        "--dent-manifest",
        type=Path,
        default=None,
        help="manifest.json de image exemplars de dent para reutilizar sus image_id.",
    )
    parser.add_argument(
        "--healthy-ids",
        nargs="*",
        type=int,
        default=[],
        help="image ids con paneles sanos sobre los que SAM3 propondra roi.",
    )
    parser.add_argument(
        "--dent-source",
        choices=["gt", "sam3"],
        default="gt",
        help="usar bbox GT para dent o usar propuestas SAM3.",
    )
    parser.add_argument(
        "--panel-prompts",
        nargs="+",
        default=DEFAULT_PANEL_PROMPTS,
        help="prompts usados por SAM3 para encontrar paneles de carroceria sanos.",
    )
    parser.add_argument("--score-threshold", type=float, default=0.50)
    parser.add_argument("--mask-threshold", type=float, default=0.50)
    parser.add_argument("--nms-iou-threshold", type=float, default=0.70)
    parser.add_argument("--max-crops-per-image", type=int, default=2)
    parser.add_argument("--padding-frac", type=float, default=0.25)
    parser.add_argument(
        "--min-mask-area",
        type=int,
        default=500,
        help="area minima de mascara para no quedarnos con ruido pequeno.",
    )
    parser.add_argument(
        "--max-mask-area-frac",
        type=float,
        default=0.70,
        help="fraccion maxima del area total de la imagen para evitar mascaras gigantes.",
    )
    parser.add_argument("--device", default=None)
    parser.add_argument("--manifest-name", default="manifest.csv")
    return parser.parse_args()


def load_manifest_image_ids(manifest_path: Path) -> list[int]:
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    with manifest_path.open(encoding="utf-8") as file:
        data = json.load(file)

    exemplars = data.get("exemplars", [])
    image_ids = []
    for exemplar in exemplars:
        image_id = exemplar.get("image_id")
        if image_id is None:
            continue
        image_ids.append(int(image_id))

    return image_ids


def merge_unique_ids(*groups: list[int]) -> list[int]:
    seen: set[int] = set()
    merged: list[int] = []

    for group in groups:
        for image_id in group:
            if image_id in seen:
                continue
            seen.add(image_id)
            merged.append(image_id)

    return merged


def resolve_image_path(img_dir: Path, file_name: str) -> Path:
    clean_name = file_name.lstrip("./")
    candidates = [
        img_dir / clean_name,
        img_dir / "images" / clean_name,
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        f"Image {file_name!r} not found. Checked: "
        + ", ".join(str(candidate) for candidate in candidates)
    )


def load_image(coco: COCO, image_id: int, img_dir: Path) -> tuple[dict[str, Any], Path, Image.Image]:
    image_info = coco.loadImgs([image_id])
    if not image_info:
        raise KeyError(f"image_id not found in COCO annotations: {image_id}")

    info = image_info[0]
    image_path = resolve_image_path(img_dir, info["file_name"])
    with Image.open(image_path) as image_file:
        image = image_file.convert("RGB")
    return info, image_path, image


def expand_bbox_xyxy(
    bbox_xyxy: tuple[float, float, float, float],
    image_width: int,
    image_height: int,
    padding_frac: float,
) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = bbox_xyxy
    width = max(0.0, x1 - x0)
    height = max(0.0, y1 - y0)
    pad_x = width * padding_frac
    pad_y = height * padding_frac

    return (
        max(0, int(np.floor(x0 - pad_x))),
        max(0, int(np.floor(y0 - pad_y))),
        min(image_width, int(np.ceil(x1 + pad_x))),
        min(image_height, int(np.ceil(y1 + pad_y))),
    )


def xywh_to_xyxy(
    bbox_xywh: list[float] | tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    x, y, width, height = bbox_xywh
    return float(x), float(y), float(x + width), float(y + height)


def mask_to_bbox_xyxy(mask: Any) -> tuple[int, int, int, int] | None:
    if torch.is_tensor(mask):
        ys, xs = torch.where(mask)
        if xs.numel() == 0:
            return None
        return (
            int(xs.min().item()),
            int(ys.min().item()),
            int(xs.max().item()) + 1,
            int(ys.max().item()) + 1,
        )

    ys, xs = np.where(mask)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def mask_iou(mask_a: Any, mask_b: Any) -> float:
    if torch.is_tensor(mask_a) or torch.is_tensor(mask_b):
        mask_a_tensor = torch.as_tensor(mask_a, dtype=torch.bool)
        mask_b_tensor = torch.as_tensor(mask_b, dtype=torch.bool)
        intersection = torch.logical_and(mask_a_tensor, mask_b_tensor).sum().item()
        union = torch.logical_or(mask_a_tensor, mask_b_tensor).sum().item()
    else:
        intersection = np.logical_and(mask_a, mask_b).sum()
        union = np.logical_or(mask_a, mask_b).sum()

    if union == 0:
        return 0.0
    return float(intersection / union)


def normalize_masks(masks: Any, image_height: int, image_width: int) -> Any:
    if masks is None:
        return torch.zeros((0, image_height, image_width), dtype=torch.bool)

    if torch.is_tensor(masks):
        mask_tensor = masks.detach().cpu()
    else:
        if len(masks) == 0:
            return torch.zeros((0, image_height, image_width), dtype=torch.bool)
        mask_tensor = torch.as_tensor(masks)

    if mask_tensor.numel() == 0:
        return torch.zeros((0, image_height, image_width), dtype=torch.bool)

    if mask_tensor.ndim == 2:
        mask_tensor = mask_tensor.unsqueeze(0)

    if tuple(mask_tensor.shape[1:]) != (image_height, image_width):
        raise ValueError(
            f"SAM3 returned masks with shape {tuple(mask_tensor.shape[1:])}, "
            f"expected {(image_height, image_width)}."
        )

    return mask_tensor.bool()


def normalize_scores(scores: Any) -> Any:
    if scores is None:
        return torch.zeros((0,), dtype=torch.float32)

    if torch.is_tensor(scores):
        return scores.detach().cpu().float()

    if len(scores) == 0:
        return torch.zeros((0,), dtype=torch.float32)

    return torch.as_tensor(scores, dtype=torch.float32)


def run_sam3_panel_proposals(
    *,
    model: Sam3Model,
    processor: Sam3Processor,
    image: Image.Image,
    prompts: list[str],
    device: str,
    score_threshold: float,
    mask_threshold: float,
    min_mask_area: int,
    max_mask_area_frac: float,
    nms_iou_threshold: float,
    max_crops_per_image: int,
) -> list[Sam3Proposal]:
    # lanzamos todos los prompts de panel a la vez y luego filtramos propuestas inviables
    inputs = processor(
        images=[image] * len(prompts),
        text=prompts,
        return_tensors="pt",
    )
    inputs = {
        key: (value.to(device) if torch.is_tensor(value) else value)
        for key, value in inputs.items()
    }

    with torch.no_grad():
        outputs = model(**inputs)

    results = processor.post_process_instance_segmentation(
        outputs,
        threshold=score_threshold,
        mask_threshold=mask_threshold,
        target_sizes=[(image.height, image.width)] * len(prompts),
    )

    image_area = image.height * image.width
    max_mask_area = int(image_area * max_mask_area_frac)
    proposals: list[Sam3Proposal] = []

    for prompt, result in zip(prompts, results):
        scores = normalize_scores(result.get("scores", []))
        masks = normalize_masks(result.get("masks", []), image.height, image.width)

        for score, mask in zip(scores, masks):
            mask_area = int(mask.sum().item())
            if mask_area < min_mask_area or mask_area > max_mask_area:
                continue

            bbox_xyxy = mask_to_bbox_xyxy(mask)
            if bbox_xyxy is None:
                continue

            proposals.append(
                Sam3Proposal(
                    prompt=prompt,
                    score=float(score.item()),
                    mask=mask,
                    bbox_xyxy=bbox_xyxy,
                    mask_area=mask_area,
                )
            )

    return nms_proposals(
        proposals,
        iou_threshold=nms_iou_threshold,
        max_crops=max_crops_per_image,
    )


def nms_proposals(
    proposals: list[Sam3Proposal],
    iou_threshold: float,
    max_crops: int,
) -> list[Sam3Proposal]:
    ordered = sorted(proposals, key=lambda proposal: proposal.score, reverse=True)
    kept: list[Sam3Proposal] = []

    for proposal in ordered:
        if any(mask_iou(proposal.mask, kept_proposal.mask) >= iou_threshold for kept_proposal in kept):
            continue
        kept.append(proposal)
        if len(kept) >= max_crops:
            break

    return kept


def save_crop(
    *,
    image: Image.Image,
    crop_path: Path,
    bbox_xyxy: tuple[int, int, int, int],
) -> None:
    crop_path.parent.mkdir(parents=True, exist_ok=True)
    image.crop(bbox_xyxy).save(crop_path, quality=95)


def build_crop_name(
    *,
    label: str,
    sequence_index: int,
) -> str:
    # misma nomenclatura simple que flat_tire/broken_lamp
    return f"{label}_{sequence_index:03d}.jpg"


def export_gt_dent_crops(
    *,
    coco: COCO,
    image_id: int,
    img_dir: Path,
    output_dir: Path,
    padding_frac: float,
    start_index: int,
) -> list[dict[str, Any]]:
    # para dent lo mejor es partir de la bbox GT
    info, image_path, image = load_image(coco, image_id, img_dir)
    ann_ids = coco.getAnnIds(imgIds=[image_id], catIds=[DENT_CATEGORY_ID])
    anns = coco.loadAnns(ann_ids)
    if not anns:
        raise ValueError(f"No dent GT annotation found for image_id={image_id}")

    rows: list[dict[str, Any]] = []
    for crop_index, ann in enumerate(anns):
        raw_bbox_xyxy = xywh_to_xyxy(ann["bbox"])
        crop_bbox = expand_bbox_xyxy(
            raw_bbox_xyxy,
            image_width=image.width,
            image_height=image.height,
            padding_frac=padding_frac,
        )
        crop_name = build_crop_name(
            label="dent",
            sequence_index=start_index + crop_index,
        )
        crop_path = output_dir / "dent" / crop_name
        save_crop(image=image, crop_path=crop_path, bbox_xyxy=crop_bbox)

        rows.append(
            manifest_row(
                image_id=image_id,
                label="dent",
                source="gt_dent",
                crop_index=crop_index,
                crop_path=crop_path,
                image_path=image_path,
                crop_bbox=crop_bbox,
                raw_bbox=raw_bbox_xyxy,
                prompt=None,
                score=None,
                annotation_id=int(ann["id"]),
                mask_area=float(ann.get("area", 0.0)),
                image_info=info,
            )
        )

    return rows


def export_sam3_crops(
    *,
    coco: COCO,
    image_id: int,
    img_dir: Path,
    output_dir: Path,
    label: str,
    model: Sam3Model,
    processor: Sam3Processor,
    prompts: list[str],
    device: str,
    score_threshold: float,
    mask_threshold: float,
    min_mask_area: int,
    max_mask_area_frac: float,
    nms_iou_threshold: float,
    max_crops_per_image: int,
    padding_frac: float,
    start_index: int,
) -> list[dict[str, Any]]:
    info, image_path, image = load_image(coco, image_id, img_dir)
    proposals = run_sam3_panel_proposals(
        model=model,
        processor=processor,
        image=image,
        prompts=prompts,
        device=device,
        score_threshold=score_threshold,
        mask_threshold=mask_threshold,
        min_mask_area=min_mask_area,
        max_mask_area_frac=max_mask_area_frac,
        nms_iou_threshold=nms_iou_threshold,
        max_crops_per_image=max_crops_per_image,
    )

    rows: list[dict[str, Any]] = []
    for crop_index, proposal in enumerate(proposals):
        crop_bbox = expand_bbox_xyxy(
            tuple(float(value) for value in proposal.bbox_xyxy),
            image_width=image.width,
            image_height=image.height,
            padding_frac=padding_frac,
        )
        crop_name = build_crop_name(
            label=label,
            sequence_index=start_index + crop_index,
        )
        crop_path = output_dir / label / crop_name
        save_crop(image=image, crop_path=crop_path, bbox_xyxy=crop_bbox)

        rows.append(
            manifest_row(
                image_id=image_id,
                label=label,
                source="sam3_panel",
                crop_index=crop_index,
                crop_path=crop_path,
                image_path=image_path,
                crop_bbox=crop_bbox,
                raw_bbox=tuple(float(value) for value in proposal.bbox_xyxy),
                prompt=proposal.prompt,
                score=proposal.score,
                annotation_id=None,
                mask_area=float(proposal.mask_area),
                image_info=info,
            )
        )

    if not rows:
        print(f"[warn] No SAM3 panel crops exported for image_id={image_id} ({label}).")

    return rows


def manifest_row(
    *,
    image_id: int,
    label: str,
    source: str,
    crop_index: int,
    crop_path: Path,
    image_path: Path,
    crop_bbox: tuple[int, int, int, int],
    raw_bbox: tuple[float, float, float, float],
    prompt: str | None,
    score: float | None,
    annotation_id: int | None,
    mask_area: float,
    image_info: dict[str, Any],
) -> dict[str, Any]:
    x0, y0, x1, y1 = crop_bbox
    raw_x0, raw_y0, raw_x1, raw_y1 = raw_bbox

    return {
        "image_id": image_id,
        "label": label,
        "source": source,
        "crop_index": crop_index,
        "crop_path": str(crop_path),
        "image_path": str(image_path),
        "file_name": image_info.get("file_name"),
        "annotation_id": annotation_id,
        "prompt": prompt,
        "sam3_score": score,
        "mask_area": mask_area,
        "crop_x0": x0,
        "crop_y0": y0,
        "crop_x1": x1,
        "crop_y1": y1,
        "crop_width": x1 - x0,
        "crop_height": y1 - y0,
        "raw_x0": raw_x0,
        "raw_y0": raw_y0,
        "raw_x1": raw_x1,
        "raw_y1": raw_y1,
        "image_width": image_info.get("width"),
        "image_height": image_info.get("height"),
    }


def load_sam3(
    model_path: Path,
    device: str,
) -> tuple[Sam3Model, Sam3Processor]:
    dtype = torch.float16 if device == "cuda" else torch.float32
    model = Sam3Model.from_pretrained(
        str(model_path),
        torch_dtype=dtype,
        local_files_only=True,
    ).to(device)
    processor = Sam3Processor.from_pretrained(
        str(model_path),
        local_files_only=True,
    )
    model.eval()
    return model, processor


def write_manifest(rows: list[dict[str, Any]], manifest_path: Path) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        manifest_path.write_text("", encoding="utf-8")
        return

    with manifest_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    load_runtime_dependencies()
    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")

    dent_ids = list(args.dent_ids)
    if args.dent_manifest is not None:
        dent_ids = merge_unique_ids(
            load_manifest_image_ids(args.dent_manifest),
            dent_ids,
        )

    healthy_ids = list(args.healthy_ids)

    if not dent_ids and not healthy_ids:
        raise SystemExit(
            "No image ids provided. Use --dent-ids, --dent-manifest and/or --healthy-ids."
        )

    coco = COCO(str(args.ann_path))
    args.output_dir.mkdir(parents=True, exist_ok=True)

    needs_sam3 = bool(healthy_ids) or args.dent_source == "sam3"
    model = None
    processor = None
    if needs_sam3:
        print(f"Loading SAM3 from {args.model_path} on {device}...")
        model, processor = load_sam3(args.model_path, device)

    rows: list[dict[str, Any]] = []
    dent_sequence_index = 1
    healthy_sequence_index = 1

    if dent_ids:
        print("Exporting dent crops...")
        for image_id in tqdm(dent_ids, desc="dent"):
            if args.dent_source == "gt":
                new_rows = export_gt_dent_crops(
                    coco=coco,
                    image_id=image_id,
                    img_dir=args.img_dir,
                    output_dir=args.output_dir,
                    padding_frac=args.padding_frac,
                    start_index=dent_sequence_index,
                )
                rows.extend(new_rows)
                dent_sequence_index += len(new_rows)
            else:
                assert model is not None and processor is not None
                new_rows = export_sam3_crops(
                    coco=coco,
                    image_id=image_id,
                    img_dir=args.img_dir,
                    output_dir=args.output_dir,
                    label="dent",
                    model=model,
                    processor=processor,
                    prompts=args.panel_prompts,
                    device=device,
                    score_threshold=args.score_threshold,
                    mask_threshold=args.mask_threshold,
                    min_mask_area=args.min_mask_area,
                    max_mask_area_frac=args.max_mask_area_frac,
                    nms_iou_threshold=args.nms_iou_threshold,
                    max_crops_per_image=args.max_crops_per_image,
                    padding_frac=args.padding_frac,
                    start_index=dent_sequence_index,
                )
                rows.extend(new_rows)
                dent_sequence_index += len(new_rows)

    if healthy_ids:
        print("Exporting healthy panel crops...")
        assert model is not None and processor is not None
        for image_id in tqdm(healthy_ids, desc="healthy"):
            new_rows = export_sam3_crops(
                coco=coco,
                image_id=image_id,
                img_dir=args.img_dir,
                output_dir=args.output_dir,
                label="healthy",
                model=model,
                processor=processor,
                prompts=args.panel_prompts,
                device=device,
                score_threshold=args.score_threshold,
                mask_threshold=args.mask_threshold,
                min_mask_area=args.min_mask_area,
                max_mask_area_frac=args.max_mask_area_frac,
                nms_iou_threshold=args.nms_iou_threshold,
                max_crops_per_image=args.max_crops_per_image,
                padding_frac=args.padding_frac,
                start_index=healthy_sequence_index,
            )
            rows.extend(new_rows)
            healthy_sequence_index += len(new_rows)

    manifest_path = args.output_dir / args.manifest_name
    write_manifest(rows, manifest_path)

    dent_count = sum(1 for row in rows if row["label"] == "dent")
    healthy_count = sum(1 for row in rows if row["label"] == "healthy")
    print(f"Done. dent={dent_count}, healthy={healthy_count}")
    print(f"Crops: {args.output_dir}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
