from __future__ import annotations

import argparse
import gc
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw

from ml.api.core.paths import paths
from ml.api.core.settings import settings
from ml.StrategyPipeline.schemas import ImageSample, StrategyResult
from ml.StrategyPipeline.strategies.baseline import BaselineStrategy
from ml.StrategyPipeline.strategies.components.clip_tip_adapter import (
    RoiVerifierConfig,
    simple_roi_verifier_config,
)
from ml.StrategyPipeline.strategies.geom_ensemble import GeometricEnsembleStrategy
from ml.StrategyPipeline.strategies.sahi import SahiStrategy


@dataclass(frozen=True)
class VariantSpec:
    # describe qué strategy concreta vamos a cargar para esta corrida.
    strategy_key: str
    enable_roi_verification: bool = False


VARIANT_SPECS: dict[str, VariantSpec] = {
    "baseline": VariantSpec(strategy_key="baseline"),
    "sahi": VariantSpec(strategy_key="sahi"),
    "sahi_clip": VariantSpec(
        strategy_key="sahi",
        enable_roi_verification=True,
    ),
    "geom_ensemble": VariantSpec(strategy_key="geom_ensemble"),
    "geom_ensemble_clip": VariantSpec(
        strategy_key="geom_ensemble",
        enable_roi_verification=True,
    ),
}


# paleta simple para distinguir instancias sin depender de notebooks.
COLORS: list[tuple[int, int, int]] = [
    (230, 57, 70),
    (29, 185, 84),
    (69, 123, 157),
    (244, 162, 97),
    (131, 56, 236),
    (255, 183, 3),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "ejecuta una sola strategy sobre una imagen robusta y guarda una "
            "visualización con máscaras, cajas y etiquetas."
        )
    )
    parser.add_argument(
        "--variant",
        required=True,
        choices=sorted(VARIANT_SPECS),
        help="variant a ejecutar.",
    )
    parser.add_argument(
        "--image-path",
        required=True,
        type=Path,
        help="ruta a la imagen de entrada.",
    )
    parser.add_argument(
        "--condition",
        required=True,
        help="nombre de la condición robusta, por ejemplo rain o night.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=(
            paths.ml_root
            / "notebooks"
            / "results"
            / "robust_single_image"
        ),
        help="carpeta base donde se guardarán png y json.",
    )
    return parser.parse_args()


def load_image_sample(
    image_path: Path,
    *,
    condition: str,
) -> tuple[Image.Image, ImageSample]:
    # cargamos la imagen una sola vez y construimos el sample a mano.
    resolved_image_path = image_path.expanduser().resolve()
    if not resolved_image_path.exists():
        raise FileNotFoundError(f"No existe la imagen: {resolved_image_path}")

    with Image.open(resolved_image_path) as image_file:
        image = image_file.convert("RGB")

    image_np = np.asarray(image)
    image_id = int(resolved_image_path.stem) if resolved_image_path.stem.isdigit() else 0
    height, width = image_np.shape[:2]

    sample = ImageSample(
        image_id=image_id,
        image_path=str(resolved_image_path),
        image=image_np,
        width=width,
        height=height,
        split="robust_inference",
        gt_instances=[],
        corruption=condition,
        severity=None,
        is_clean=False,
    )

    return image, sample


def build_roi_verifier_configs() -> list[RoiVerifierConfig]:
    # solo hay verificación roi para tire flat y lamp broken.
    configs: list[RoiVerifierConfig] = []

    if paths.flat_tire_cache_path.exists():
        configs.append(
            simple_roi_verifier_config(
                target_category_id=6,
                proposal_prompt="a visible car tire",
                cache_path=str(paths.flat_tire_cache_path),
                positive_label="flat car tire",
                negative_label="healthy car tire",
            )
        )

    if paths.broken_lamp_cache_path.exists():
        configs.append(
            simple_roi_verifier_config(
                target_category_id=5,
                proposal_prompt="a visible car headlamp or tail lamp",
                cache_path=str(paths.broken_lamp_cache_path),
                positive_label="broken car lamp",
                negative_label="healthy car lamp",
            )
        )

    if not configs:
        raise FileNotFoundError(
            "no se encontraron caches para roi verification y la variant clip los necesita."
        )

    return configs


def build_strategy(variant: str):
    # construimos exactamente una strategy para este proceso.
    spec = VARIANT_SPECS[variant]
    roi_verifier_configs = (
        build_roi_verifier_configs()
        if spec.enable_roi_verification
        else None
    )

    common_kwargs = {
        "model_path": str(paths.sam3_model_path),
        "category_map": settings.category_map,
        "prompt_map": settings.prompt_map,
        "score_threshold": settings.score_threshold,
        "mask_threshold": settings.mask_threshold,
        "device": settings.device,
        "enable_roi_verification": spec.enable_roi_verification,
        "roi_verifier_configs": roi_verifier_configs,
    }

    if spec.strategy_key == "baseline":
        return BaselineStrategy(
            **common_kwargs,
            prompt_batch_size=settings.prompt_batch_size,
        )

    if spec.strategy_key == "sahi":
        return SahiStrategy(**common_kwargs)

    if spec.strategy_key == "geom_ensemble":
        return GeometricEnsembleStrategy(**common_kwargs)

    raise ValueError(f"variant no soportada: {variant}")


def render_prediction_image(
    *,
    image: Image.Image,
    result: StrategyResult,
    category_map: dict[int, str],
) -> Image.Image:
    # dibujamos máscaras, cajas y una etiqueta por instancia detectada.
    rgba_image = image.convert("RGBA")
    overlay_rgba = np.zeros((rgba_image.height, rgba_image.width, 4), dtype=np.uint8)
    sorted_predictions = sorted(
        result.predictions,
        key=lambda prediction: prediction.score,
        reverse=True,
    )

    for index, prediction in enumerate(sorted_predictions):
        color = COLORS[index % len(COLORS)]
        mask = np.asarray(prediction.mask, dtype=bool)
        overlay_rgba[mask] = (*color, 90)

    overlay_image = Image.fromarray(overlay_rgba, mode="RGBA")
    composed = Image.alpha_composite(rgba_image, overlay_image)
    draw = ImageDraw.Draw(composed)

    for index, prediction in enumerate(sorted_predictions):
        color = COLORS[index % len(COLORS)]
        label = category_map.get(
            prediction.category_id,
            str(prediction.category_id),
        )

        x, y, width, height = prediction.bbox
        x1 = float(x)
        y1 = float(y)
        x2 = float(x + width)
        y2 = float(y + height)

        draw.rectangle(
            [x1, y1, x2, y2],
            outline=color,
            width=3,
        )

        # usamos un índice visible para que se entienda qué instancia es cada una.
        text = f"#{index + 1} {label} {prediction.score:.2f}"
        text_bbox = draw.textbbox((x1, y1), text)
        text_x = max(0.0, x1)
        text_y = max(0.0, y1 - ((text_bbox[3] - text_bbox[1]) + 6.0))
        background_bbox = draw.textbbox((text_x, text_y), text)

        draw.rectangle(
            [
                background_bbox[0] - 3,
                background_bbox[1] - 2,
                background_bbox[2] + 3,
                background_bbox[3] + 2,
            ],
            fill=(0, 0, 0, 180),
        )
        draw.text(
            (text_x, text_y),
            text,
            fill=color,
        )

    return composed.convert("RGB")


def build_json_summary(
    *,
    variant: str,
    image_path: Path,
    result: StrategyResult,
    category_map: dict[int, str],
) -> dict:
    predictions = sorted(
        result.predictions,
        key=lambda prediction: prediction.score,
        reverse=True,
    )

    return {
        "variant": variant,
        "strategy_name": result.strategy_name,
        "image_path": str(image_path),
        "num_predictions": len(predictions),
        "runtime": {
            "inference_ms": result.runtime.inference_ms,
            "peak_vram_mb": result.runtime.peak_vram_mb,
        },
        "predictions": [
            {
                "instance_index": index + 1,
                "damage_class": category_map.get(
                    prediction.category_id,
                    str(prediction.category_id),
                ),
                "category_id": int(prediction.category_id),
                "score": float(prediction.score),
                "bbox_xywh": [float(value) for value in prediction.bbox],
                "area": float(prediction.area),
            }
            for index, prediction in enumerate(predictions)
        ],
    }


def ensure_model_exists() -> None:
    if not paths.sam3_model_path.exists():
        raise FileNotFoundError(
            f"No existe el modelo SAM3 en: {paths.sam3_model_path}"
        )


def main() -> None:
    args = parse_args()
    ensure_model_exists()

    image, sample = load_image_sample(
        args.image_path,
        condition=args.condition,
    )

    variant_output_dir = (
        args.output_dir
        / sample.image_path.split("/")[-1].replace(".jpg", "")
        / args.condition
    )
    variant_output_dir.mkdir(parents=True, exist_ok=True)

    strategy = None
    try:
        print(f"[inicio] cargando variant={args.variant}")
        strategy = build_strategy(args.variant)

        print(f"[inferencia] ejecutando strategy_name={strategy.strategy_name}")
        result = strategy.run(sample)
        print(
            "[ok] "
            f"predicciones={len(result.predictions)} "
            f"inference_ms={result.runtime.inference_ms:.2f} "
            f"peak_vram_mb={result.runtime.peak_vram_mb}"
        )

        rendered_image = render_prediction_image(
            image=image,
            result=result,
            category_map=strategy.category_map,
        )
        image_output_path = variant_output_dir / f"{args.variant}.png"
        rendered_image.save(image_output_path)

        summary = build_json_summary(
            variant=args.variant,
            image_path=args.image_path.expanduser().resolve(),
            result=result,
            category_map=strategy.category_map,
        )
        json_output_path = variant_output_dir / f"{args.variant}.json"
        json_output_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print(f"[guardado] {image_output_path}")
        print(f"[guardado] {json_output_path}")
    finally:
        # intentamos liberar lo máximo posible antes de salir.
        del strategy
        gc.collect()

        if torch.cuda.is_available():
            torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
