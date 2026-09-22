from __future__ import annotations

import base64
from io import BytesIO

import numpy as np
from PIL import Image, ImageDraw

from ml.api.schemas.response import VisualizationPayload
from ml.StrategyPipeline.schemas import StrategyResult


# paleta simple para distinguir instancias cuando hay varias.
_COLORS: list[tuple[int, int, int]] = [
    (230, 57, 70),
    (29, 185, 84),
    (69, 123, 157),
    (244, 162, 97),
    (131, 56, 236),
    (255, 183, 3),
]


def build_visualization_payload(
    *,
    image: Image.Image,
    result: StrategyResult,
    category_map: dict[int, str],
    image_format: str,
) -> VisualizationPayload:
    # trabajamos en rgba para mezclar overlays con transparencia.
    rgba_image = image.convert("RGBA")
    overlay_rgba = np.zeros((rgba_image.height, rgba_image.width, 4), dtype=np.uint8)

    for index, prediction in enumerate(result.predictions):
        # pintamos cada máscara en una capa separada del lienzo base.
        color = _COLORS[index % len(_COLORS)]
        mask = np.asarray(prediction.mask, dtype=bool)
        overlay_rgba[mask] = (*color, 90)

    # unimos la imagen base con la capa de máscaras.
    overlay_image = Image.fromarray(overlay_rgba, mode="RGBA")
    composed = Image.alpha_composite(rgba_image, overlay_image)
    draw = ImageDraw.Draw(composed)

    for index, prediction in enumerate(result.predictions):
        # además de la máscara, dibujamos bbox y score para lectura rápida.
        color = _COLORS[index % len(_COLORS)]
        label = category_map.get(
            prediction.category_id,
            str(prediction.category_id),
        )

        x, y, width, height = prediction.bbox
        x1 = float(x)
        y1 = float(y)
        x2 = float(x + width)
        y2 = float(y + height)

        draw.rectangle(
            [x1, y1, x2, y2],
            outline=color,
            width=3,
        )

        text = f"{label} {prediction.score:.2f}"
        text_x = max(0.0, x1)
        text_y = max(0.0, y1 - 18.0)
        draw.text(
            (text_x, text_y),
            text,
            fill=color,
        )

    # serializamos la imagen final a bytes para luego codificarla en base64.
    output_buffer = BytesIO()
    normalized_format = image_format.upper()
    mime_type = "image/png" if normalized_format == "PNG" else "image/jpeg"

    final_image = composed
    if normalized_format == "JPEG":
        # jpeg no soporta alpha, así que quitamos el canal transparente.
        final_image = composed.convert("RGB")

    final_image.save(output_buffer, format=normalized_format)

    return VisualizationPayload(
        mime_type=mime_type,
        image_base64=base64.b64encode(output_buffer.getvalue()).decode("ascii"),
    )
