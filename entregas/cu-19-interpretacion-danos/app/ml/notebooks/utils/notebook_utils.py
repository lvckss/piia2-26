import json
import math
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from ml.StrategyPipeline.schemas import RunInfo
from ml.StrategyPipeline.evaluation.evaluator import Evaluator

from ml.StrategyPipeline.strategies.baseline import BaselineStrategy
from ml.StrategyPipeline.strategies.geom_ensemble import GeometricEnsembleStrategy
from ml.StrategyPipeline.strategies.sahi import SahiStrategy
from ml.StrategyPipeline.strategies.components.sam3_backend import (
    ExemplarRef,
    PromptSpec,
)


DEFAULT_CATEGORY_MAP = {
    1: "dent",
    2: "scratch",
    3: "crack",
    4: "glass shatter",
    5: "lamp broken",
    6: "tire flat",
}


def run_and_plot_image(
    image_id: int,
    dataloader,
    strategy,
    *,
    run_name: str | None = None,
    alpha: float = 0.18,
    with_boxes: bool = False,
    show_scores: bool = True,
    show_labels: bool = False,
    with_legend: bool = True,
    edge_alpha: float = 0.90,
    edge_linewidth: float = 2.5,
    label_group_iou_threshold: float = 0.50,
    figsize: tuple[int, int] = (14, 6),
    return_output: bool = False,
):
    # carga la imagen por id
    sample = dataloader.get_by_image_id(image_id)

    # ejecuta la strategy sobre esa imagen
    result = strategy.run(sample)

    strategy_name = result.strategy_name
    effective_run_name = run_name or f"{strategy_name}_image_{image_id}"

    evaluator = Evaluator(
        RunInfo(
            run_name=effective_run_name,
            strategy_name=strategy_name,
            dataset_name=dataloader.dataset_name,
            ann_path=str(dataloader.ann_path),
        ),
        category_map=strategy.category_map,
    )

    # añade la predicción al evaluator y recalcula métricas
    evaluator.add(sample, result)
    output = evaluator.finalize()

    # usa el inspector del evaluator para pintar gt vs predicciones
    inspector = evaluator.get_inspection()
    inspector.plot(
        image_id,
        alpha=alpha,
        with_boxes=with_boxes,
        show_scores=show_scores,
        show_labels=show_labels,
        with_legend=with_legend,
        edge_alpha=edge_alpha,
        edge_linewidth=edge_linewidth,
        label_group_iou_threshold=label_group_iou_threshold,
        figsize=figsize,
    )

    # devuelve también el output si necesitas inspeccionar métricas o registros
    if return_output:
        return inspector, output

    # devuelve el inspector para reutilizarlo después, por ejemplo en grad cam
    return inspector


def one_shot_from_manifest(manifest_path):
    manifest_path = Path(manifest_path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    ex = data["exemplars"][0]

    return PromptSpec.hybrid_prompt(
        data["text"],
        [
            ExemplarRef(
                str((manifest_path.parent / ex["image"]).resolve()),
                bbox_xywh=tuple(ex["bbox_xywh"]),
            )
        ],
        name=f'{data["category_name"]}_1shot',
    )


def compare_single_exemplars_for_image(
    *,
    strategy_name: str,
    image_id: int,
    category_name: str,
    dataloader,
    model_path: str | Path,
    category_map: dict[int, str] | None = None,
    manifests_root: str | Path | None = None,
    manifest_path: str | Path | None = None,
    strategy_kwargs: dict[str, Any] | None = None,
    mode: str | None = None,
    columns: int = 3,
    alpha: float = 0.28,
    gt_alpha: float = 0.18,
    exemplar_inset_size: float = 0.34,
    figsize: tuple[int, int] | None = None,
    return_results: bool = False,
):
    # corre la misma imagen una vez por exemplar y lo pinta todo en un grid para comparar rápido
    category_map = dict(DEFAULT_CATEGORY_MAP if category_map is None else category_map)
    strategy_kwargs = dict(strategy_kwargs or {})

    if strategy_kwargs.get("enable_roi_verification"):
        raise ValueError(
            "compare_single_exemplars_for_image está pensado para comparar exemplars. "
            "No actives enable_roi_verification aquí."
        )

    sample = dataloader.get_by_image_id(image_id)
    image = np.asarray(_load_rgb_image(sample.image_path))

    target_category_id, target_category_name = _resolve_category_name(
        category_name=category_name,
        category_map=category_map,
    )

    resolved_manifest_path = _resolve_exemplar_manifest_path(
        category_id=target_category_id,
        category_name=target_category_name,
        manifests_root=manifests_root,
        manifest_path=manifest_path,
    )

    manifest_data = _load_json(resolved_manifest_path)
    prompt_specs, exemplar_refs = _build_single_exemplar_prompt_specs(
        manifest_path=resolved_manifest_path,
        manifest_data=manifest_data,
        mode=mode,
    )

    if not prompt_specs:
        raise ValueError(f"No hay exemplars en {resolved_manifest_path}")

    strategy = _build_single_class_strategy(
        strategy_name=strategy_name,
        model_path=str(model_path),
        category_id=target_category_id,
        category_name=target_category_name,
        first_prompt_spec=prompt_specs[0],
        strategy_kwargs=strategy_kwargs,
    )

    gt_masks = [
        np.asarray(gt.mask, dtype=bool)
        for gt in sample.gt_instances
        if int(gt.category_id) == target_category_id
    ]

    results = []
    for exemplar_index, (prompt_spec, exemplar_ref) in enumerate(
        zip(prompt_specs, exemplar_refs),
        start=1,
    ):
        # reutilizamos la misma strategy para no recargar el modelo en cada exemplar
        strategy.prompt_map = {target_category_id: prompt_spec}
        result = strategy.run(sample)

        pred_masks = [
            np.asarray(pred.mask, dtype=bool)
            for pred in result.predictions
            if int(pred.category_id) == target_category_id
        ]
        pred_scores = [
            float(pred.score)
            for pred in result.predictions
            if int(pred.category_id) == target_category_id
        ]

        results.append(
            {
                "exemplar_index": exemplar_index,
                "exemplar_ref": exemplar_ref,
                "prompt_spec": prompt_spec,
                "result": result,
                "pred_masks": pred_masks,
                "pred_scores": pred_scores,
                "best_score": max(pred_scores) if pred_scores else None,
                "best_iou": _best_iou_between_sets(gt_masks, pred_masks),
            }
        )

    _plot_single_exemplar_comparison_grid(
        image=image,
        gt_masks=gt_masks,
        results=results,
        category_name=target_category_name,
        image_id=image_id,
        columns=columns,
        alpha=alpha,
        gt_alpha=gt_alpha,
        exemplar_inset_size=exemplar_inset_size,
        figsize=figsize,
    )

    if return_results:
        return results

    return results


def _build_single_class_strategy(
    *,
    strategy_name: str,
    model_path: str,
    category_id: int,
    category_name: str,
    first_prompt_spec: PromptSpec,
    strategy_kwargs: dict[str, Any],
):
    # instanciamos la strategy una sola vez y luego cambiamos el prompt_map en memoria
    strategy_alias = _normalize_strategy_name(strategy_name)
    single_category_map = {category_id: category_name}
    base_kwargs = {
        "model_path": model_path,
        "category_map": single_category_map,
        "prompt_map": {category_id: first_prompt_spec},
    }
    base_kwargs.update(strategy_kwargs)

    if strategy_alias == "baseline":
        return BaselineStrategy(**base_kwargs)

    if strategy_alias == "sahi":
        return SahiStrategy(**base_kwargs)

    if strategy_alias == "ensemble":
        return GeometricEnsembleStrategy(**base_kwargs)

    raise ValueError(
        "strategy_name debe ser 'baseline', 'sahi' o 'ensemble'. "
        f"Recibido: {strategy_name!r}"
    )


def _normalize_strategy_name(strategy_name: str) -> str:
    normalized = strategy_name.strip().lower().replace("-", "_")

    if normalized in {"baseline", "baseline_prompt"}:
        return "baseline"

    if normalized in {"sahi", "sahi_prompt"}:
        return "sahi"

    if normalized in {
        "ensemble",
        "geom_ensemble",
        "geometric_ensemble",
        "geometric_ensemble_prompt",
    }:
        return "ensemble"

    return normalized


def _resolve_category_name(
    *,
    category_name: str,
    category_map: dict[int, str],
) -> tuple[int, str]:
    # aceptamos el nombre real de la clase y también variantes con underscores
    normalized_target = _normalize_label(category_name)

    for category_id, candidate_name in category_map.items():
        if _normalize_label(candidate_name) == normalized_target:
            return int(category_id), str(candidate_name)

    raise KeyError(
        f"No se pudo resolver la clase {category_name!r} dentro de category_map."
    )


def _resolve_exemplar_manifest_path(
    *,
    category_id: int,
    category_name: str,
    manifests_root: str | Path | None,
    manifest_path: str | Path | None,
) -> Path:
    if manifest_path is not None:
        resolved_path = Path(manifest_path).expanduser().resolve()
        if not resolved_path.exists():
            raise FileNotFoundError(f"No existe manifest_path: {resolved_path}")
        return resolved_path

    resolved_root = _resolve_project_root() / "ml" / "config" / "image_exemplars"
    if manifests_root is not None:
        resolved_root = Path(manifests_root).expanduser().resolve()

    if not resolved_root.exists():
        raise FileNotFoundError(f"No existe manifests_root: {resolved_root}")

    preferred_folder_names = [
        f"{category_id}_{_slugify(category_name)}_selected",
        f"{category_id}_{_slugify(category_name)}",
    ]

    for folder_name in preferred_folder_names:
        candidate_path = resolved_root / folder_name / "manifest.json"
        if candidate_path.exists():
            return candidate_path

    matching_manifests = []
    for candidate_path in sorted(resolved_root.glob("*/manifest.json")):
        data = _load_json(candidate_path)
        if int(data.get("category_id", -1)) != category_id:
            continue

        if _normalize_label(str(data.get("category_name", ""))) != _normalize_label(category_name):
            continue

        matching_manifests.append(candidate_path)

    if len(matching_manifests) == 1:
        return matching_manifests[0]

    if len(matching_manifests) > 1:
        selected_matches = [
            path
            for path in matching_manifests
            if path.parent.name.endswith("_selected")
        ]
        if len(selected_matches) == 1:
            return selected_matches[0]

        raise ValueError(
            "Hay varios manifests para esa clase. "
            "Pasa manifest_path explícitamente. "
            f"Opciones: {[str(path) for path in matching_manifests]}"
        )

    raise FileNotFoundError(
        f"No se encontró ningún manifest de image exemplars para {category_name!r} "
        f"en {resolved_root}"
    )


def _build_single_exemplar_prompt_specs(
    *,
    manifest_path: Path,
    manifest_data: dict[str, Any],
    mode: str | None,
) -> tuple[list[PromptSpec], list[ExemplarRef]]:
    raw_exemplars = manifest_data.get("exemplars", [])
    if not isinstance(raw_exemplars, list) or not raw_exemplars:
        raise ValueError(
            f"El manifest no contiene exemplars válidos: {manifest_path}"
        )

    effective_text = manifest_data.get("text")
    effective_mode = mode or manifest_data.get("mode") or (
        "hybrid" if effective_text else "exemplar"
    )

    if effective_mode not in {"hybrid", "exemplar"}:
        raise ValueError(
            "compare_single_exemplars_for_image solo soporta mode='hybrid' o 'exemplar'. "
            f"Recibido: {effective_mode!r}"
        )

    prompt_specs: list[PromptSpec] = []
    exemplar_refs: list[ExemplarRef] = []

    for exemplar_index, exemplar_item in enumerate(raw_exemplars, start=1):
        image_value = exemplar_item.get("image") or exemplar_item.get("image_path")
        if not image_value:
            raise ValueError(
                f"Exemplar inválido en {manifest_path}: falta image o image_path"
            )

        bbox_xywh = exemplar_item.get("bbox_xywh")
        exemplar_ref = ExemplarRef(
            image_path=str((manifest_path.parent / str(image_value)).resolve()),
            bbox_xywh=tuple(bbox_xywh) if bbox_xywh is not None else None,
        )
        exemplar_refs.append(exemplar_ref)

        prompt_name = f"{manifest_data.get('category_name', 'category')}_exemplar_{exemplar_index:02d}"

        if effective_mode == "hybrid":
            if not effective_text:
                raise ValueError(
                    f"El manifest {manifest_path} no tiene text y se pidió mode='hybrid'."
                )
            prompt_specs.append(
                PromptSpec.hybrid_prompt(
                    effective_text,
                    [exemplar_ref],
                    name=prompt_name,
                )
            )
            continue

        prompt_specs.append(
            PromptSpec.exemplar_prompt(
                [exemplar_ref],
                name=prompt_name,
            )
        )

    return prompt_specs, exemplar_refs


def _plot_single_exemplar_comparison_grid(
    *,
    image: np.ndarray,
    gt_masks: list[np.ndarray],
    results: list[dict[str, Any]],
    category_name: str,
    image_id: int,
    columns: int,
    alpha: float,
    gt_alpha: float,
    exemplar_inset_size: float,
    figsize: tuple[int, int] | None,
) -> None:
    num_items = len(results)
    if num_items == 0:
        raise ValueError("No hay resultados para dibujar.")

    columns = max(1, int(columns))
    rows = int(math.ceil(num_items / columns))

    if figsize is None:
        figsize = (columns * 5, rows * 5)

    fig, axes = plt.subplots(rows, columns, figsize=figsize)
    axes = np.atleast_1d(axes).ravel()

    for ax, item in zip(axes, results):
        ax.imshow(image)
        ax.axis("off")

        _draw_mask_set(ax=ax, masks=gt_masks, color=(0.10, 0.85, 0.25), alpha=gt_alpha)
        _draw_mask_set(ax=ax, masks=item["pred_masks"], color=(0.95, 0.15, 0.15), alpha=alpha)

        best_score = item["best_score"]
        best_iou = item["best_iou"]
        exemplar_name = Path(item["exemplar_ref"].image_path).name

        ax.set_title(
            f"{exemplar_name}\n"
            f"preds={len(item['pred_masks'])} | "
            f"best_score={_format_metric(best_score)} | "
            f"best_iou={_format_metric(best_iou)}",
            fontsize=10,
        )

        inset_ax = ax.inset_axes(
            [
                1.0 - exemplar_inset_size - 0.02,
                0.02,
                exemplar_inset_size,
                exemplar_inset_size,
            ]
        )
        inset_ax.imshow(_load_exemplar_preview(item["exemplar_ref"]))
        inset_ax.set_xticks([])
        inset_ax.set_yticks([])
        for spine in inset_ax.spines.values():
            spine.set_edgecolor("white")
            spine.set_linewidth(1.5)

    for ax in axes[num_items:]:
        ax.axis("off")

    fig.suptitle(
        f"image exemplars | image_id={image_id} | class={category_name}",
        fontsize=14,
    )
    plt.tight_layout()
    plt.show()


def _draw_mask_set(
    *,
    ax,
    masks: list[np.ndarray],
    color: tuple[float, float, float],
    alpha: float,
) -> None:
    for mask in masks:
        mask = np.asarray(mask, dtype=bool)
        if not mask.any():
            continue

        overlay = np.zeros((*mask.shape, 4), dtype=float)
        overlay[mask] = (*color, alpha)
        ax.imshow(overlay)
        ax.contour(
            mask.astype(float),
            levels=[0.5],
            colors=[color],
            linewidths=2.0,
        )


def _best_iou_between_sets(
    gt_masks: list[np.ndarray],
    pred_masks: list[np.ndarray],
) -> float | None:
    if not gt_masks or not pred_masks:
        return None

    best_iou = 0.0
    for gt_mask in gt_masks:
        for pred_mask in pred_masks:
            iou = _mask_iou(gt_mask, pred_mask)
            if iou > best_iou:
                best_iou = iou

    return float(best_iou)


def _mask_iou(mask_a: np.ndarray, mask_b: np.ndarray) -> float:
    mask_a = np.asarray(mask_a, dtype=bool)
    mask_b = np.asarray(mask_b, dtype=bool)

    intersection = np.logical_and(mask_a, mask_b).sum()
    union = np.logical_or(mask_a, mask_b).sum()

    if union == 0:
        return 0.0

    return float(intersection / union)


def _load_exemplar_preview(exemplar_ref: ExemplarRef) -> np.ndarray:
    # enseñamos la roi del exemplar si existe bbox; si no, enseñamos la imagen completa
    with Image.open(exemplar_ref.image_path) as image_file:
        image = image_file.convert("RGB")

    if exemplar_ref.bbox_xywh is None:
        return np.asarray(image)

    x, y, width, height = exemplar_ref.bbox_xywh
    pad_x = width * 0.10
    pad_y = height * 0.10

    x1 = max(0, int(np.floor(x - pad_x)))
    y1 = max(0, int(np.floor(y - pad_y)))
    x2 = min(image.width, int(np.ceil(x + width + pad_x)))
    y2 = min(image.height, int(np.ceil(y + height + pad_y)))

    if x2 <= x1 or y2 <= y1:
        return np.asarray(image)

    return np.asarray(image.crop((x1, y1, x2, y2)))


def _load_rgb_image(image_path: str | Path) -> Image.Image:
    with Image.open(image_path) as image_file:
        return image_file.convert("RGB")


def _resolve_project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "bd" / "rawdata").exists() and (parent / "ml").exists():
            return parent

    raise RuntimeError("No se pudo encontrar la raiz del proyecto desde notebook_utils.py.")


def _load_json(json_path: str | Path) -> dict[str, Any]:
    path = Path(json_path).expanduser().resolve()
    with path.open(encoding="utf-8") as json_file:
        data = json.load(json_file)

    if not isinstance(data, dict):
        raise ValueError(f"Se esperaba un objeto json en {path}")

    return data


def _normalize_label(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", " ").split())


def _slugify(value: str) -> str:
    return _normalize_label(value).replace(" ", "_")


def _format_metric(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{float(value):.3f}"
