from collections import defaultdict
from typing import Any

import pandas as pd

from ml.StrategyPipeline.schemas import ImageEvalRecord, VehicleMetricsOutput
from ml.StrategyPipeline.evaluation.metrics.coco_metrics import compute_coco_metrics
from ml.StrategyPipeline.evaluation.metrics.error_metrics import compute_error_metrics

# etiqueta que se usa quando un record no tiene vehicle_type asignado (todavia no se ha etiquetado esa imagen)
UNKNOWN_VEHICLE_TYPE = "unknown"


def compute_vehicle_metrics(
    records: list[ImageEvalRecord],
    category_map: dict[int, str],
    error_iou_threshold: float = 0.50,
    error_matching_policy: str = "score_greedy",
) -> VehicleMetricsOutput:
    """Desglosa las mismas metricas de coco_metrics/error_metrics por vehicle_type.
    Sigue el mismo patron que compute_robustness_metrics, pero agrupando por
    tipo de vehiculo en lugar de por corruption/severity."""

    if not records:
        raise ValueError("compute_vehicle_metrics requiere al menos un ImageEvalRecord.")

    grouped_records = _group_records_by_vehicle(records)

    rows: list[dict[str, Any]] = []

    for vehicle_type, group_records in sorted(grouped_records.items()):
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
                "vehicle_type": vehicle_type,
                "num_images": len(group_records),
                "mask_ap_50_95": coco_out.mask_ap_50_95,
                "ap75": coco_out.ap75,
                "ap_small": coco_out.ap_small,
                "fp_per_image": error_out.fp_per_image,
            }
        )

    per_vehicle = pd.DataFrame(rows)
    if not per_vehicle.empty:
        per_vehicle = per_vehicle.sort_values(by=["vehicle_type"]).reset_index(drop=True)

    return VehicleMetricsOutput(per_vehicle=per_vehicle)


def _group_records_by_vehicle(
    records: list[ImageEvalRecord],
) -> dict[str, list[ImageEvalRecord]]:
    grouped: dict[str, list[ImageEvalRecord]] = defaultdict(list)

    for record in records:
        # las imagenes sin etiquetar quedan visibles bajo "unknown" en vez de desaparecer del desglose
        vehicle_type = record.vehicle_type or UNKNOWN_VEHICLE_TYPE
        grouped[vehicle_type].append(record)

    return dict(grouped)
