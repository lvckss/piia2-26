import pandas as pd

from collections import defaultdict
from typing import Literal

from ml.StrategyPipeline.schemas import ErrorMetricsOutput, ImageEvalRecord, GroundTruthInstance, InstancePrediction

MatchingPolicy = Literal["score_greedy", "iou_greedy"]

def compute_error_metrics(
    records: list[ImageEvalRecord],
    iou_threshold: float = 0.50,
    matching_policy: str = "score_greedy",
) -> ErrorMetricsOutput:
    """Computa métricas de error (FP por imagen promedio) a partir de los registros de evaluación. Devuelve un ErrorMetricsOutput con los resultados."""

    if matching_policy not in {"score_greedy", "iou_greedy"}:
        raise ValueError(f"matching_policy debe ser 'score_greedy' o 'iou_greedy' | '{matching_policy}'")

    rows = []
    total_fp = 0

    class_totals: dict[int, dict[str, int]] = defaultdict(
        lambda: {
            "tp_iou50": 0,
            "fp_iou50": 0,
            "fn_iou50": 0,
        }
    )

    for record in records:
        tp, fp, fn, per_class_counts = _count_errors(
            record,
            iou_threshold=iou_threshold,
            matching_policy=matching_policy,
        )

        rows.append(
            {
                "image_id": record.image_id,
                "tp_iou50": tp,
                "fp_iou50": fp,
                "fn_iou50": fn,
            }
        )

        total_fp += fp

        for category_id, counts in per_class_counts.items():
            class_totals[category_id]["tp_iou50"] += counts["tp_iou50"]
            class_totals[category_id]["fp_iou50"] += counts["fp_iou50"]
            class_totals[category_id]["fn_iou50"] += counts["fn_iou50"]

    per_image = pd.DataFrame(rows).sort_values("image_id").reset_index(drop=True)
    fp_per_image = total_fp / len(records) if records else 0.0 # media de falsos positivos por imagen

    class_rows = []

    for category_id, counts in sorted(class_totals.items()):
        class_rows.append(
            {
                "category_id": category_id,
                "tp_iou50": counts["tp_iou50"],
                "fp_iou50": counts["fp_iou50"],
                "fn_iou50": counts["fn_iou50"],
                "fp_per_image": (
                    counts["fp_iou50"] / len(records) if records else 0.0
                ),
            }
        )

    per_class = pd.DataFrame(
        class_rows,
        columns=["category_id", "tp_iou50", "fp_iou50", "fn_iou50", "fp_per_image"],
    )

    return ErrorMetricsOutput(
        fp_per_image=fp_per_image,
        per_image=per_image,
        per_class=per_class,
    )

def _count_errors(
    record: ImageEvalRecord,
    iou_threshold: float,
    matching_policy: MatchingPolicy,
) -> tuple[int, int, int, dict[int, dict[str, int]]]:
    """Devuelve el conteo de TP, FP, FN para una imagen dada, según el matching_policy especificado."""

    gt_by_class = _group_gt_by_class(record.gt_instances)
    pred_by_class = _group_pred_by_class(record.pred_instances)

    all_category_ids = sorted(set(gt_by_class) | set(pred_by_class))

    total_fp = 0
    total_tp = 0
    total_fn = 0

    per_class_counts: dict[int, dict[str, int]] = {}

    for category_id in all_category_ids:
        gt_instances = gt_by_class.get(category_id, [])
        pred_instances = pred_by_class.get(category_id, [])

        tp, fp, fn = _match_single_class(
            gt_instances,
            pred_instances,
            iou_threshold=iou_threshold,
            matching_policy=matching_policy,
        )

        total_tp += tp
        total_fp += fp
        total_fn += fn

        per_class_counts[category_id] = {
            "tp_iou50": tp,
            "fp_iou50": fp,
            "fn_iou50": fn,
        }

    return total_tp, total_fp, total_fn, per_class_counts

def _group_gt_by_class(
    instances: list[GroundTruthInstance],
) -> dict[int, list[GroundTruthInstance]]:
    grouped: dict[int, list[GroundTruthInstance]] = defaultdict(list)
    for instance in instances:
        grouped[instance.category_id].append(instance)
    return dict(grouped)

def _group_pred_by_class(
    instances: list[InstancePrediction],
) -> dict[int, list[InstancePrediction]]:
    grouped: dict[int, list[InstancePrediction]] = defaultdict(list)
    for instance in instances:
        grouped[instance.category_id].append(instance)
    return dict(grouped)

def _match_single_class(
    gt_instances: list[GroundTruthInstance],
    pred_instances: list[InstancePrediction],
    iou_threshold: float,
    matching_policy: MatchingPolicy,
) -> tuple[int, int, int]: # tp, fp, fn
    """Devuelve el conteo de TP, FP, FN para una clase dada, según el matching_policy especificado."""

    if not gt_instances and not pred_instances:
        return 0, 0, 0

    if not gt_instances:
        return 0, len(pred_instances), 0 # todo falsos positivos

    if not pred_instances:
        return 0, 0, len(gt_instances) # todo falsos negativos

    if matching_policy == "score_greedy":
        return _match_score_greedy(gt_instances, pred_instances, iou_threshold)

    if matching_policy == "iou_greedy":
        return _match_iou_greedy(gt_instances, pred_instances, iou_threshold)

def _match_score_greedy(
    gt_instances: list[GroundTruthInstance],
    pred_instances: list[InstancePrediction],
    iou_threshold: float,
) -> tuple[int, int, int]:
    """Algoritmo de matching greedy basado en score: se ordenan las predicciones por score descendente, y se asignan a la mejor coincidencia de GT disponible que supere el umbral de IoU."""

    ordered_preds = sorted(pred_instances, key=lambda pred: pred.score, reverse=True) # !!! ORDENAMOS POR SCORE
    used_gt: set[int] = set()

    tp = 0
    fp = 0

    for pred in ordered_preds:
        best_gt_idx = None
        best_iou = -1.0

        for gt_idx, gt in enumerate(gt_instances):
            if gt_idx in used_gt:
                continue

            iou = _mask_iou(gt.mask, pred.mask)
            if iou > best_iou:
                best_iou = iou
                best_gt_idx = gt_idx

        if best_gt_idx is not None and best_iou >= iou_threshold:
            used_gt.add(best_gt_idx)
            tp += 1
        else:
            fp += 1

    fn = len(gt_instances) - tp
    return tp, fp, fn

def _match_iou_greedy(
    gt_instances: list[GroundTruthInstance],
    pred_instances: list[InstancePrediction],
    iou_threshold: float,
) -> tuple[int, int, int]:
    """Algoritmo de matching greedy basado en IoU: se buscan primero las parejas GT-Pred con mayor IoU, se asignan si superan el umbral, y se repite hasta que no queden coincidencias válidas."""

    candidate_pairs: list[tuple[float, int, int]] = []

    for pred_idx, pred in enumerate(pred_instances):
        for gt_idx, gt in enumerate(gt_instances):
            iou = _mask_iou(gt.mask, pred.mask)
            if iou >= iou_threshold:
                candidate_pairs.append((iou, pred_idx, gt_idx))

    candidate_pairs.sort(reverse=True, key=lambda item: item[0])

    used_preds: set[int] = set()
    used_gt: set[int] = set()
    tp = 0

    for _, pred_idx, gt_idx in candidate_pairs:
        if pred_idx in used_preds or gt_idx in used_gt:
            continue

        used_preds.add(pred_idx)
        used_gt.add(gt_idx)
        tp += 1

    fp = len(pred_instances) - tp
    fn = len(gt_instances) - tp
    return tp, fp, fn

def _mask_iou(mask_a, mask_b) -> float:
    """Calcula el IoU entre dos máscaras booleanas."""

    intersection = (mask_a & mask_b).sum()
    union = (mask_a | mask_b).sum()

    if union == 0:
        return 0.0

    return float(intersection / union)
