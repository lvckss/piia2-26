from __future__ import annotations

from io import BytesIO

import numpy as np
from PIL import Image

from ml.StrategyPipeline.schemas import ImageSample


def load_upload_as_rgb_image(file_bytes: bytes) -> Image.Image:
    # normalizamos cualquier upload a rgb antes de inferir.
    return Image.open(BytesIO(file_bytes)).convert("RGB")


def build_image_sample(
    *,
    image: Image.Image,
    filename: str | None,
) -> ImageSample:
    # la strategy trabaja con numpy, así que convertimos la imagen aquí.
    image_np = np.asarray(image.convert("RGB"))
    height, width = image_np.shape[:2]

    # la imagen subida no existe en disco, así que dejamos una pseudo-ruta estable.
    safe_filename = filename or "upload_image"

    return ImageSample(
        # no tenemos dataset ni ground truth; solo inferencia online.
        image_id=0,
        image_path=f"uploaded://{safe_filename}",
        image=image_np,
        width=width,
        height=height,
        split="inference",
        gt_instances=[],
        corruption=None,
        severity=None,
        is_clean=True,
    )
