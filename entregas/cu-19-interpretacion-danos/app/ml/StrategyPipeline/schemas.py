from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


# DATA LOADER -> STRATEGY MODULE


@dataclass(frozen=True)
class GroundTruthInstance:
    annotation_id: int
    category_id: int
    mask: np.ndarray
    bbox: tuple[float, float, float, float]
    area: float


@dataclass(frozen=True)
class ImageSample:
    image_id: int
    image_path: str
    image: np.ndarray | None
    width: int
    height: int
    split: str
    gt_instances: list[GroundTruthInstance]
    corruption: str | None = None
    severity: int | None = None
    is_clean: bool = True


# STRATEGY MODULE -> EVALUATOR

@dataclass(frozen=True)
class SampleRef:
    image_id: int
    width: int
    height: int
    split: str
    corruption: str | None = None
    severity: int | None = None
    is_clean: bool = True


@dataclass(frozen=True)
class InstancePrediction:
    category_id: int
    score: float
    mask: np.ndarray
    bbox: tuple[float, float, float, float]
    area: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeStats:
    inference_ms: float
    peak_vram_mb: float | None


@dataclass(frozen=True)
class StrategyResult:
    strategy_name: str
    sample: SampleRef
    predictions: list[InstancePrediction]
    runtime: RuntimeStats


# EVALUATOR CONFIG

@dataclass(frozen=True)
class RunInfo:
    run_name: str
    strategy_name: str
    dataset_name: str
    ann_path: str
    # config adicional que se quiera guardar sobre la run, por ejemplo hiperparámetros usados, etc
    # al final esto no afecta la evaluación pero puede ser útil para guardar toda esta info en el json de output final y tenerla a mano al analizar resultados
    config: dict[str, Any] = field(default_factory=dict)

    # método para convertir a dict, útil para serializar el output final incluyendo esta info en el json
    def to_dict(self) -> dict[str, Any]:
        return {
            "run_name": self.run_name,
            "strategy_name": self.strategy_name,
            "dataset_name": self.dataset_name,
            "ann_path": self.ann_path,
            "config": self.config,
        }

# EVALUATOR INTERNO

@dataclass(frozen=True)
class ImageEvalRecord:
    image_id: int
    image_path: str
    width: int
    height: int
    split: str
    corruption: str | None
    severity: int | None
    is_clean: bool
    gt_instances: list[GroundTruthInstance]
    pred_instances: list[InstancePrediction]
    inference_ms: float
    peak_vram_mb: float | None


# METRICS DATA TYPES

@dataclass(frozen=True)
class RuntimeMetricsOutput:
    ms_per_image: float
    peak_vram_mb: float | None
    per_image: pd.DataFrame

@dataclass(frozen=True)
class ErrorMetricsOutput:
    fp_per_image: float
    per_image: pd.DataFrame # columnas: image_id | tp_iou50 | fp_iou50 | fn_iou50
    per_class: pd.DataFrame # columnas: category_id | tp_iou50 | fp_iou50 | fn_iou50 | fp_per_image

@dataclass
class CocoMetricsOutput:
    mask_ap_50_95: float | None
    ap75: float | None
    ap_small: float | None
    per_class: pd.DataFrame # columnas: category_id | category_name | mask_ap_50_95 | ap75
    raw: dict[str, Any]

@dataclass(frozen=True)
class RobustnessMetricsOutput:
    pclean: float | None
    mpc: float | None
    rpc: float | None
    per_condition: pd.DataFrame # columnas: corruption | severity | num_images | mask_ap_50_95 | ap75 | ap_small | fp_per_image

# EVALUATOR -> OUTPUT FINAL

@dataclass(frozen=True)
class SummaryMetrics:
    mask_ap_50_95: float | None
    ap75: float | None
    ap_small: float | None
    fp_per_image: float
    pclean: float | None
    mpc: float | None
    rpc: float | None
    ms_per_image: float
    peak_vram_mb: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mask_ap_50_95": self.mask_ap_50_95,
            "ap75": self.ap75,
            "ap_small": self.ap_small,
            "fp_per_image": self.fp_per_image,
            "pclean": self.pclean,
            "mpc": self.mpc,
            "rpc": self.rpc,
            "ms_per_image": self.ms_per_image,
            "peak_vram_mb": self.peak_vram_mb,
        }


def _json_safe_value(value: Any) -> Any:
    # convierte valores no serializables o no válidos en json a tipos nativos
    if value is None:
        return None

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value

    if isinstance(value, np.bool_):
        return bool(value)

    if isinstance(value, np.integer):
        return int(value)

    if isinstance(value, np.floating):
        value = float(value)

    if isinstance(value, float):
        if not np.isfinite(value):
            return None
        return value

    if isinstance(value, int):
        return value

    if isinstance(value, dict):
        return {
            key: _json_safe_value(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            _json_safe_value(item)
            for item in value
        ]

    if isinstance(value, np.ndarray):
        return _json_safe_value(value.tolist())

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    return value


@dataclass(frozen=True)
class EvalOutput:
    run_info: RunInfo
    summary: SummaryMetrics
    per_class: pd.DataFrame
    per_condition: pd.DataFrame
    per_image: pd.DataFrame

    def to_dict(self, include_run_info: bool = False) -> dict[str, Any]:
        output = {
            "summary": self.summary.to_dict(),
            "per_class": self.per_class.to_dict(orient="records"),
            "per_condition": self.per_condition.to_dict(orient="records"),
            "per_image": self.per_image.to_dict(orient="records"),
        }

        if include_run_info:
            output["run_info"] = self.run_info.to_dict()

        return _json_safe_value(output)

    def to_json(self, include_run_info: bool = False, **json_kwargs: Any) -> str:
        effective_json_kwargs = {
            "ensure_ascii": False,
            "indent": 2,
            "allow_nan": False,
        }
        effective_json_kwargs.update(json_kwargs)
        return json.dumps(
            self.to_dict(include_run_info=include_run_info),
            **effective_json_kwargs,
        )

# INSPECTION TRAS EVALUACIÓN

@dataclass(frozen=True)
class InspectionItem:
    record: ImageEvalRecord
    metrics: dict[str, Any]
