from __future__ import annotations

from ml.api.schemas.response import BoundingBox, DamageAssessmentItem
from ml.StrategyPipeline.schemas import StrategyResult


def map_strategy_result_to_response(
    *,
    result: StrategyResult,
    category_map: dict[int, str],
) -> list[DamageAssessmentItem]:
    # convertimos la salida interna del pipeline al contrato público de la api.
    items: list[DamageAssessmentItem] = []

    # ordenamos por score para que la respuesta ya salga en orden útil.
    ordered_predictions = sorted(
        result.predictions,
        key=lambda prediction: prediction.score,
        reverse=True,
    )

    for prediction in ordered_predictions:
        # la bbox ya viene en xywh desde el pipeline.
        x, y, width, height = prediction.bbox
        items.append(
            DamageAssessmentItem(
                damage_class=category_map.get(
                    prediction.category_id,
                    str(prediction.category_id),
                ),
                bbox=BoundingBox(
                    x=float(x),
                    y=float(y),
                    width=float(width),
                    height=float(height),
                ),
                area=float(prediction.area),
                score=float(prediction.score),
            )
        )

    return items
