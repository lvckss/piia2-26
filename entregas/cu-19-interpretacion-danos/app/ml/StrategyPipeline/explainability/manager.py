from pathlib import Path
from typing import Literal

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from ml.StrategyPipeline.explainability.sam3_grad_cam import (
    Sam3GradCamExplainer,
    Sam3GradCamResult,
)
from ml.StrategyPipeline.schemas import (
    ImageEvalRecord,
    InspectionItem,
    InstancePrediction,
    StrategyResult,
)
from ml.StrategyPipeline.strategies.base import StrategyContractError


PredictionSelectMode = Literal["best_score", "best_area"]


def find_prediction_by_category(
    result: StrategyResult,
    category_id: int,
    *,
    mode: PredictionSelectMode = "best_score",
) -> InstancePrediction:
    predictions = [
        prediction
        for prediction in result.predictions
        if prediction.category_id == category_id
    ]

    return _select_prediction(
        predictions=predictions,
        category_id=category_id,
        mode=mode,
    )


def find_prediction_by_category_record(
    record: ImageEvalRecord,
    category_id: int,
    *,
    mode: PredictionSelectMode = "best_score",
) -> InstancePrediction:
    predictions = [
        prediction
        for prediction in record.pred_instances
        if prediction.category_id == category_id
    ]

    return _select_prediction(
        predictions=predictions,
        category_id=category_id,
        mode=mode,
    )


def explain_prediction_by_category(
    *,
    inspector,
    image_id: int,
    category_id: int,
    strategy,
    mode: PredictionSelectMode = "best_score",
) -> Sam3GradCamResult:
    item = inspector.get(image_id)
    prediction = find_prediction_by_category_record(
        record=item.record,
        category_id=category_id,
        mode=mode,
    )

    explainer_backend = prediction.metadata.get("explainer_backend")
    if explainer_backend != "sam3":
        raise StrategyContractError(
            f"explainer no soportado para esta predicción: {explainer_backend!r}"
        )

    explainer = Sam3GradCamExplainer()
    return explainer.explain(
        record=item.record,
        strategy=strategy,
        prediction=prediction,
    )


def plot_grad_cam_by_category(
    *,
    inspector,
    image_id: int,
    category_id: int,
    strategy,
    mode: PredictionSelectMode = "best_score",
    alpha: float = 0.45,
    cmap: str = "jet",
    figsize: tuple[int, int] = (8, 6),
) -> Sam3GradCamResult:
    item = inspector.get(image_id)
    grad_cam_result = explain_prediction_by_category(
        inspector=inspector,
        image_id=image_id,
        category_id=category_id,
        strategy=strategy,
        mode=mode,
    )

    image = _load_record_image(item.record)

    plt.figure(figsize=figsize)
    plt.imshow(image)
    plt.imshow(
        grad_cam_result.heatmap,
        cmap=cmap,
        alpha=alpha,
        vmin=0.0,
        vmax=1.0,
    )
    plt.axis("off")
    plt.title(
        "grad-cam | "
        f"image_id={image_id} | "
        f"category_id={category_id} | "
        f"prompt={grad_cam_result.prompt!r} | "
        f"query={grad_cam_result.query_index} | "
        f"match_iou={grad_cam_result.matched_iou:.3f}"
    )
    plt.tight_layout()
    plt.show()

    return grad_cam_result


def _select_prediction(
    *,
    predictions: list[InstancePrediction],
    category_id: int,
    mode: PredictionSelectMode,
) -> InstancePrediction:
    if not predictions:
        raise ValueError(f"no hay predicciones para category_id={category_id}")

    if mode == "best_score":
        return max(predictions, key=lambda prediction: prediction.score)

    if mode == "best_area":
        return max(predictions, key=lambda prediction: prediction.area)

    raise ValueError(f"modo de selección no soportado: {mode}")


def _load_record_image(record: ImageEvalRecord) -> np.ndarray:
    with Image.open(Path(record.image_path)) as image_file:
        return np.asarray(image_file.convert("RGB"))