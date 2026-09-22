from collections import defaultdict
from typing import Any

import pandas as pd

from ml.StrategyPipeline.schemas import ImageEvalRecord, RobustnessMetricsOutput
from ml.StrategyPipeline.evaluation.metrics.coco_metrics import compute_coco_metrics
from ml.StrategyPipeline.evaluation.metrics.error_metrics import compute_error_metrics

def compute_robustness_metrics(
    records: list[ImageEvalRecord],
    category_map: dict[int, str],
    error_iou_threshold: float = 0.50,
    error_matching_policy: str = "score_greedy",
    base_metric_name: str = "mask_ap_50_95",
) -> RobustnessMetricsOutput:
    if not records:
        raise ValueError("compute_robustness_metrics requiere al menos un ImageEvalRecord.")

    if base_metric_name not in {"mask_ap_50_95", "ap75", "ap_small"}:
        raise ValueError(
            "base_metric_name debe ser 'mask_ap_50_95', 'ap75' o 'ap_small'"
        )

    clean_records = [record for record in records if record.is_clean]
    corrupted_groups = _group_corrupted_records(records)

    rows: list[dict[str, Any]] = []
    corrupted_scores: list[float] = []

    pclean = None

    if clean_records:
        clean_coco_out = compute_coco_metrics(
            records=clean_records,
            category_map=category_map,
        )
        clean_error_out = compute_error_metrics(
            records=clean_records,
            iou_threshold=error_iou_threshold,
            matching_policy=error_matching_policy,
        )

        pclean = _select_base_metric(clean_coco_out, base_metric_name)

        rows.append(
            {
                "corruption": "clean",
                "severity": 0,
                "num_images": len(clean_records),
                "mask_ap_50_95": clean_coco_out.mask_ap_50_95,
                "ap75": clean_coco_out.ap75,
                "ap_small": clean_coco_out.ap_small,
                "fp_per_image": clean_error_out.fp_per_image,
            }
        )

    for (corruption, severity), group_records in sorted(corrupted_groups.items()):
        coco_out = compute_coco_metrics(
            records=group_records,
            category_map=category_map,
        )

        error_out = compute_error_metrics(
            records=group_records,
            iou_threshold=error_iou_threshold,
            matching_policy=error_matching_policy,
        )

        rows.append(
            {
                "corruption": corruption,
                "severity": severity,
                "num_images": len(group_records),
                "mask_ap_50_95": coco_out.mask_ap_50_95,
                "ap75": coco_out.ap75,
                "ap_small": coco_out.ap_small,
                "fp_per_image": error_out.fp_per_image,
            }
        )

        base_metric_value = _select_base_metric(coco_out, base_metric_name)
        if base_metric_value is not None:
            corrupted_scores.append(base_metric_value)

    per_condition = pd.DataFrame(rows)
    if not per_condition.empty:
        per_condition = per_condition.sort_values(
            by=["corruption", "severity"]
        ).reset_index(drop=True)

    mpc = (
        float(sum(corrupted_scores) / len(corrupted_scores))
        if corrupted_scores
        else None
    )

    rpc = None
    if pclean is not None and pclean > 0 and mpc is not None:
        rpc = float(mpc / pclean)

    return RobustnessMetricsOutput(
        pclean=pclean,
        mpc=mpc,
        rpc=rpc,
        per_condition=per_condition,
    )

def _group_corrupted_records(
    records: list[ImageEvalRecord],
) -> dict[tuple[str, int], list[ImageEvalRecord]]:
    grouped: dict[tuple[str, int], list[ImageEvalRecord]] = defaultdict(list)

    for record in records:
        if record.is_clean:
            continue

        if record.corruption is None or record.severity is None:
            raise ValueError(
                f"Record corrupto inválido: image_id={record.image_id} no tiene "
                "corruption o severity definidos."
            )

        grouped[(record.corruption, int(record.severity))].append(record)

    return dict(grouped)

def _select_base_metric(coco_out, base_metric_name: str) -> float | None:
    if base_metric_name == "mask_ap_50_95":
        return coco_out.mask_ap_50_95
    if base_metric_name == "ap75":
        return coco_out.ap75
    if base_metric_name == "ap_small":
        return coco_out.ap_small

    raise ValueError(f"base_metric_name no soportado: {base_metric_name}")