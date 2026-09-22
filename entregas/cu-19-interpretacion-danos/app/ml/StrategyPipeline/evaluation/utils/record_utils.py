from ml.StrategyPipeline.schemas import GroundTruthInstance, InstancePrediction, ImageEvalRecord
import numpy as np
import pandas as pd

def copy_gt_instance(gt: GroundTruthInstance) -> GroundTruthInstance:
    x, y, w, h = gt.bbox
    return GroundTruthInstance(
        annotation_id=int(gt.annotation_id),
        category_id=int(gt.category_id),
        mask=np.array(gt.mask, copy=True),
        bbox=(float(x), float(y), float(w), float(h)),
        area=float(gt.area),
    )

def copy_prediction(pred: InstancePrediction) -> InstancePrediction:
    x, y, w, h = pred.bbox
    return InstancePrediction(
        category_id=int(pred.category_id),
        score=float(pred.score),
        mask=np.array(pred.mask, copy=True),
        bbox=(float(x), float(y), float(w), float(h)),
        area=float(pred.area),
        metadata=dict(pred.metadata),
    )

def build_per_image_base(records: list[ImageEvalRecord]) -> pd.DataFrame:
    rows = []
    for record in records:
        rows.append(
            {
                "image_id": record.image_id,
                "split": record.split,
                "corruption": record.corruption,
                "severity": record.severity,
                "is_clean": record.is_clean,
                "num_gt": len(record.gt_instances),
                "num_pred": len(record.pred_instances),
            }
        )
    return pd.DataFrame(rows)
