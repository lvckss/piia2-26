from typing import Any

import io
from contextlib import redirect_stdout

from ml.StrategyPipeline.schemas import (
    CocoMetricsOutput,
    ImageEvalRecord,
)

from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval
from pycocotools import mask as mask_utils

import pandas as pd
import numpy as np

def compute_coco_metrics(
    records: list[ImageEvalRecord],
    category_map: dict[int, str],
) -> CocoMetricsOutput:
    """Computa métricas COCO (AP50, AP75, AP) a partir de los registros de evaluación. Devuelve un CocoMetricsOutput con los resultados."""

    if not records:
        raise ValueError("compute_coco_metrics requiere al menos un ImageEvalRecord.")

    coco_gt_dict = _build_gt_coco_dict(records, category_map)
    coco_pred_results = _build_pred_coco_results(records)

    coco_gt = _load_coco_gt(coco_gt_dict)
    coco_dt = _load_coco_dt(coco_gt, coco_pred_results)

    coco_eval = _run_coco_eval(
        coco_gt=coco_gt,
        coco_dt=coco_dt,
        imgs_ids=[record.image_id for record in records],
        cat_ids=sorted(category_map),
    )

    mask_ap_50_95, ap75, ap_small = _extract_global_metrics(coco_eval)
    per_class = _build_per_class_df(coco_eval, category_map)

    return CocoMetricsOutput(
        mask_ap_50_95=mask_ap_50_95,
        ap75=ap75,
        ap_small=ap_small,
        per_class=per_class,
        raw={"coco_eval": coco_eval},
    )


def _build_gt_coco_dict(
    records: list[ImageEvalRecord],
    category_map: dict[int, str],
) -> dict:
    """Construye un diccionario de anotaciones en formato COCO a partir de los registros de evaluación. De esta forma este diccionario puede ser usado para computar métricas COCO con pycocotools"""

    images: list[dict[str, Any]] = []
    annotations: list[dict[str, Any]] = []

    for record in records:
        images.append(
            {
                "id": record.image_id,
                "width": int(record.width),
                "height": int(record.height),
            }
        )

        for gt in record.gt_instances:
            annotations.append(
                {
                    "id": int(gt.annotation_id),
                    "image_id": record.image_id,
                    "category_id": int(gt.category_id),
                    "segmentation": _encode_mask_to_rle(gt.mask),
                    "bbox": [float(x) for x in gt.bbox],
                    "area": float(gt.area),
                    "iscrowd": 0,
                }
            )

    categories = [
        {
            "id": int(category_id),
            "name": category_name,
            "supercategory": "damage",
        }
        for category_id, category_name in sorted(category_map.items())
    ]

    """De esta forma el diccionario cumple con el formato esperado por pycocotools para las anotacionesde ground truth."""
    return {
        "info": {},
        "licenses": [],
        "images": images,
        "annotations": annotations,
        "categories": categories,
    }

def _build_pred_coco_results(
    records: list[ImageEvalRecord],
) -> list[dict[str, Any]]:
    """Construye una lista de predicciones en formato COCO a partir de los registros de evaluación. De esta forma esta lista puede ser usada para computar métricas COCO con pycocotools"""

    results: list[dict[str, Any]] = []

    for record in records:
        for pred in record.pred_instances:
            results.append(
                {
                    "image_id": record.image_id,
                    "category_id": int(pred.category_id),
                    "segmentation": _encode_mask_to_rle(pred.mask),
                    "bbox": [float(x) for x in pred.bbox],
                    "score": float(pred.score),
                }
            )

    """De esta forma la lista cumple con el formato esperado por pycocotools para las predicciones."""
    return results

def _load_coco_gt(coco_gt_dict: dict[str, Any]) -> COCO:
    """Carga un diccionario de anotaciones en formato COCO en una instancia de COCO de pycocotools."""

    coco_gt = COCO()
    coco_gt.dataset = coco_gt_dict
    # redirigimos la salida a un buffer para evitar que se imprima en consola
    with io.StringIO() as buffer, redirect_stdout(buffer):
          coco_gt.createIndex()
    return coco_gt

def _load_coco_dt(coco_gt: COCO, coco_pred_results: list[dict[str, Any]]) -> COCO:
    """Carga una lista de predicciones en formato COCO en una instancia de COCO de pycocotools. Si la lista de predicciones está vacía, devuelve una instancia de COCO "vacía" con las mismas imágenes y categorías que coco_gt pero sin anotaciones."""

    if coco_pred_results:
        # redirigimos la salida a un buffer para evitar que se imprima en consola
        with io.StringIO() as buffer, redirect_stdout(buffer):
            return coco_gt.loadRes(coco_pred_results) # loadRes ya valida que los image_id y category_id de las predicciones existan en coco_gt, y lanza un error si no es así
    # Si no hay predicciones, igualmente necesitamos una instancia de COCO para poder computar las métricas, pero  loadRes no acepta una lista vacía. Entonces creamos una instancia de COCO "vacía" con las mismas imágenes y categorías que coco_gt pero sin anotaciones.
    coco_dt = COCO()
    coco_dt.dataset = {
        "info": dict(coco_gt.dataset.get("info", {})),
        "licenses": list(coco_gt.dataset.get("licenses", [])),
        "images": list(coco_gt.dataset.get("images", [])),
        "categories": list(coco_gt.dataset.get("categories", [])),
        "annotations": [],
    }
    coco_dt.createIndex()
    return coco_dt

def _run_coco_eval(
    coco_gt: COCO,
    coco_dt: COCO,
    imgs_ids: list[int],
    cat_ids: list[int],
) -> COCOeval:
    """Ejecuta la evaluación COCO usando pycocotools y devuelve el objeto COCOeval con los resultados. Este objeto contiene las métricas globales y también permite extraer métricas por clase o por imagen si es necesario."""

    coco_eval = COCOeval(coco_gt, coco_dt, iouType="segm")
    coco_eval.params.imgIds = imgs_ids
    coco_eval.params.catIds = cat_ids

    # redirigimos la salida a un buffer para evitar que se imprima en consola
    with io.StringIO() as buffer, redirect_stdout(buffer):
        # Ejecutar la evaluación.
        # coco_eval.evaluate() calcula las correspondencias entre predicciones y ground truth,
        # coco_eval.accumulate() acumula los resultados para calcular las métricas,
        coco_eval.evaluate()
        coco_eval.accumulate()

        # coco_eval.summarize() imprime un resumen de las métricas en consola, pero no devuelve los valores.
        # Para obtener los valores de AP50, AP75 y AP, accedemos directamente a coco_eval.stats, que es un array con los resultados en el mismo orden que se imprimen en summarize().
        coco_eval.summarize()

    return coco_eval

def _extract_global_metrics(
    coco_eval: COCOeval,
) -> tuple[float | None, float | None, float | None]:
    """Extrae las métricas globales (AP50, AP75, AP) del objeto COCOeval. Si alguna métrica no está disponible, devuelve None en su lugar."""

    stats = getattr(coco_eval, "stats", None)
    if stats is None or len(stats) < 4:
        return None, None, None

    mask_ap_50_95 = _normalize_coco_stat(stats[0])
    ap75 = _normalize_coco_stat(stats[2])
    ap_small = _normalize_coco_stat(stats[3])

    return mask_ap_50_95, ap75, ap_small

def _build_per_class_df(
    coco_eval: COCOeval,
    category_map: dict[int, str],
) -> pd.DataFrame:
    precision = coco_eval.eval.get("precision")
    if precision is None:
        return pd.DataFrame(
            columns=["category_id", "category_name", "mask_ap_50_95", "ap75"]
        )

    area_index = _get_area_index(coco_eval, "all")
    max_det_index = _get_max_det_index(coco_eval, 100)
    iou75_index = _get_iou_threshold_index(coco_eval, 0.75)

    rows: list[dict[str, Any]] = []

    for class_index, category_id in enumerate(coco_eval.params.catIds):
        global_precision = precision[:, :, class_index, area_index, max_det_index]
        ap_all = _mean_valid_precision(global_precision)

        ap75_precision = precision[iou75_index, :, class_index, area_index, max_det_index]
        ap75 = _mean_valid_precision(ap75_precision)

        rows.append(
            {
                "category_id": int(category_id),
                "category_name": category_map.get(int(category_id), str(category_id)),
                "mask_ap_50_95": ap_all,
                "ap75": ap75,
            }
        )

    return pd.DataFrame(rows).sort_values("category_id").reset_index(drop=True)


# HELPERS

def _encode_mask_to_rle(mask: np.ndarray) -> dict[str, Any]:
    """Codifica una máscara binaria (numpy array 2D de bool) en formato RLE (Run-Length Encoding) usando pycocotools.
    El resultado es un diccionario con las claves "counts" y "size" que representa la máscara en formato RLE, que es el formato esperado por COCO para las segmentaciones."""
    encoded = mask_utils.encode(np.asfortranarray(mask.astype(np.uint8)))
    if isinstance(encoded["counts"], bytes):
        encoded["counts"] = encoded["counts"].decode("utf-8")
    return encoded

def _get_area_index(coco_eval: COCOeval, label: str) -> int:
    """Dado un objeto COCOeval y una etiqueta de área (por ejemplo "all", "small", "medium", "large"), devuelve el índice correspondiente en coco_eval.params.areaRngLbl. Lanza un error si no se encuentra la etiqueta."""
    for index, area_label in enumerate(coco_eval.params.areaRngLbl):
        if area_label == label:
            return index
    raise ValueError(f"No se encontró areaRngLbl={label!r} en COCOeval.")

def _get_max_det_index(coco_eval: COCOeval, max_det: int) -> int:
    """Dado un objeto COCOeval y un valor de maxDet (por ejemplo 1, 10, 100), devuelve el índice correspondiente en coco_eval.params.maxDets. Lanza un error si no se encuentra el valor."""
    for index, value in enumerate(coco_eval.params.maxDets):
        if value == max_det:
            return index
    raise ValueError(f"No se encontró maxDet={max_det} en COCOeval.")

def _get_iou_threshold_index(coco_eval: COCOeval, threshold: float) -> int:
      matches = np.where(np.isclose(coco_eval.params.iouThrs, threshold))[0]
      if len(matches) == 0:
          raise ValueError(f"No se encontró IoU={threshold} en COCOeval.")
      return int(matches[0])

def _mean_valid_precision(values: np.ndarray) -> float | None:
    valid = values[values > -1]
    if valid.size == 0:
        return None
    return float(valid.mean())

def _normalize_coco_stat(value: float) -> float | None:
    if value < 0:
        return None
    return float(value)