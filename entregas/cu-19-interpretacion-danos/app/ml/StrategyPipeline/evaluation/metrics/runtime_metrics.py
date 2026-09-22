import pandas as pd
from ml.StrategyPipeline.schemas import ImageEvalRecord, RuntimeMetricsOutput

def compute_runtime_metrics(
    records: list[ImageEvalRecord],
    ) -> RuntimeMetricsOutput:
    rows = []
    vram_values: list[float] = []

    for record in records:
        rows.append(
            {
                "image_id": record.image_id,
                "inference_ms": record.inference_ms,
                "peak_vram_mb": record.peak_vram_mb,
            }
        )

        if record.peak_vram_mb is not None:
            vram_values.append(record.peak_vram_mb)

    per_image = pd.DataFrame(rows).sort_values("image_id").reset_index(drop=True)

    ms_per_image = float(per_image["inference_ms"].mean()) if not per_image.empty else 0.0
    peak_vram_mb = max(vram_values) if vram_values else None

    return RuntimeMetricsOutput(
        ms_per_image=ms_per_image,
        peak_vram_mb=peak_vram_mb,
        per_image=per_image,
    )