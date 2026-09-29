from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

MODEL = "claude-sonnet-5-5"

DESCRIPTION_PROMPT_TEMPLATE = (
    "Eres un perito de danos de vehiculos. Te muestro el recorte de una foto "
    "donde un sistema de deteccion automatica ha marcado un posible dano de "
    "tipo '{category}'. Describe en 1-2 frases, en espanol, lo que ves: que "
    "parte del vehiculo es, que tipo de dano parece y su severidad aparente. "
    "Si no ves ningun dano claro en la imagen, dilo explicitamente -- eso "
    "tambien es informacion util."
)


def _codificar_imagen(crop_path: Path) -> tuple[str, str]:
    media_type = "image/jpeg" if crop_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    data = base64.standard_b64encode(crop_path.read_bytes()).decode("utf-8")
    return media_type, data


def describir_dano(client: Any, crop_path: str | Path, category: str) -> str:
    """Llama a Claude con el recorte de imagen y devuelve una descripcion en
    lenguaje natural del dano.

    `client` se recibe como parametro (en vez de crearse aqui dentro) para
    poder probar esta funcion con un cliente falso sin llamar a la API real
    ni necesitar una API Key -- ver `probar_vision_stub.py`.
    """
    crop_path = Path(crop_path)
    media_type, data = _codificar_imagen(crop_path)

    respuesta = client.messages.create(
        model=MODEL,
        max_tokens=200,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": data},
                    },
                    {
                        "type": "text",
                        "text": DESCRIPTION_PROMPT_TEMPLATE.format(category=category),
                    },
                ],
            }
        ],
    )
    return respuesta.content[0].text.strip()


def enriquecer_con_vision(hallazgos: dict[str, Any], client: Any) -> None:
    """Rellena `vision_description` en cada finding de `hallazgos`,
    in-place. Requiere que `generar_recortes` ya se haya ejecutado antes
    (necesita `crop_image_path`)."""
    for finding in hallazgos["findings"]:
        finding["vision_description"] = describir_dano(
            client, finding["crop_image_path"], finding["category"]
        )
