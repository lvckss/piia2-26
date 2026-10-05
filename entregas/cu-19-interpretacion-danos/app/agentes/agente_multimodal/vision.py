from __future__ import annotations

import base64
import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any

from PIL import Image

from catalogo import Catalogo, clase_a_tool, combinacion_valida, lista_piezas_para_prompt
from confianza import decidir_tier
from recorte import imagen_con_caja

VEREDICTOS = ("confirmado", "rechazado", "incierto")
SEVERIDADES = ("leve", "moderado", "grave")

PROMPT_TEMPLATE = """\
Eres un perito de danos de vehiculos. Un sistema automatico de deteccion ha marcado, con el rectangulo rojo de la primera imagen, un posible dano de tipo '{categoria}'. La segunda imagen es un recorte ampliado de esa zona.

Responde SOLO con un objeto JSON con estas claves:
- "veredicto": "confirmado" si en la zona marcada hay de verdad un dano de ese tipo, "rechazado" si no lo hay (falso positivo), "incierto" si no se puede asegurar.
- "pieza_id": la pieza danada, elegida EXACTAMENTE de esta lista (null si el veredicto es "rechazado"):
{piezas}
- "severidad": "leve", "moderado" o "grave" (null si el veredicto es "rechazado").
- "descripcion": 1-2 frases en espanol sobre lo que ves.

Para el lado (izquierdo/derecho) y delantero/trasero fijate en la imagen completa; izquierdo y derecho son los del vehiculo, no los de la foto. Si no puedes distinguir la pieza con seguridad, responde "incierto" en vez de adivinar."""


def _jpeg_base64(imagen: Image.Image) -> str:
    buffer = io.BytesIO()
    imagen.convert("RGB").save(buffer, format="JPEG", quality=90)
    return base64.standard_b64encode(buffer.getvalue()).decode("utf-8")


def _extraer_json(texto: str) -> dict[str, Any]:
    """Lee el JSON de la respuesta aunque venga envuelto en ```json ... ```.
    Si no hay JSON valido devuelve {} (el hallazgo quedara como `incierto`)."""
    for candidato in (texto, *re.findall(r"\{.*\}", texto, flags=re.DOTALL)):
        try:
            datos = json.loads(candidato)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(datos, dict):
            return datos
    return {}


def parsear_respuesta(texto: str, catalogo: Catalogo, clase_tool: str) -> dict[str, Any]:
    """Convierte la respuesta del modelo en los campos del hallazgo,
    validandola: un veredicto, pieza o severidad fuera de lo permitido no se
    acepta (el modelo puede inventarse un `pieza_id`)."""
    datos = _extraer_json(texto)

    veredicto = datos.get("veredicto")
    if veredicto not in VEREDICTOS:
        veredicto = "incierto"

    pieza_id = datos.get("pieza_id")
    if pieza_id not in catalogo.piezas:
        pieza_id = None

    severidad = datos.get("severidad")
    if severidad not in SEVERIDADES:
        severidad = None

    if veredicto == "rechazado":
        pieza_id, severidad = None, None

    regla = (
        combinacion_valida(catalogo, clase_tool, pieza_id, severidad)
        if pieza_id and severidad
        else None
    )

    return {
        "vision_verdict": veredicto,
        "pieza_id": pieza_id,
        "severidad": severidad,
        "regla_coste_aplicable": regla,
        "vision_description": str(datos.get("descripcion") or "").strip(),
    }


def analizar_hallazgo(
    client: Any,
    modelo: str,
    imagen: Image.Image,
    finding: dict[str, Any],
    catalogo: Catalogo,
    cache_dir: str | Path | None = None,
    uso: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Segunda opinion de un modelo con vision sobre un hallazgo de PIIA-1.

    `client` es un cliente de OpenAI (o uno falso en las pruebas). Si se pasa
    `cache_dir`, la respuesta se guarda por (modelo, prompt, imagenes) y no se
    vuelve a pagar la misma consulta. Si se pasa `uso`, se le suman las
    llamadas y los tokens realmente facturados (lo que sale de la cache no
    cuenta): claves `llamadas`, `prompt_tokens` y `completion_tokens`.
    """
    prompt = PROMPT_TEMPLATE.format(
        categoria=finding["category"], piezas=lista_piezas_para_prompt(catalogo)
    )
    contexto_b64 = _jpeg_base64(imagen_con_caja(imagen, finding["bbox_xywh"]))
    with Image.open(finding["crop_image_path"]) as recorte:
        recorte_b64 = _jpeg_base64(recorte)

    ruta_cache = None
    if cache_dir is not None:
        clave = hashlib.sha256(
            "|".join((modelo, prompt, contexto_b64, recorte_b64)).encode("utf-8")
        ).hexdigest()
        ruta_cache = Path(cache_dir) / f"{clave}.json"
        if ruta_cache.exists():
            texto = json.loads(ruta_cache.read_text(encoding="utf-8"))["respuesta"]
            return parsear_respuesta(texto, catalogo, clase_a_tool(finding["category"]))

    respuesta = client.chat.completions.create(
        model=modelo,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{contexto_b64}"}},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{recorte_b64}"}},
                ],
            }
        ],
        response_format={"type": "json_object"},
    )
    texto = respuesta.choices[0].message.content or ""

    if uso is not None:
        tokens = getattr(respuesta, "usage", None)
        uso["llamadas"] = uso.get("llamadas", 0) + 1
        uso["prompt_tokens"] = uso.get("prompt_tokens", 0) + int(getattr(tokens, "prompt_tokens", 0) or 0)
        uso["completion_tokens"] = uso.get("completion_tokens", 0) + int(getattr(tokens, "completion_tokens", 0) or 0)

    if ruta_cache is not None:
        ruta_cache.parent.mkdir(parents=True, exist_ok=True)
        ruta_cache.write_text(
            json.dumps({"modelo": modelo, "respuesta": texto}, ensure_ascii=False),
            encoding="utf-8",
        )

    return parsear_respuesta(texto, catalogo, clase_a_tool(finding["category"]))


def enriquecer_con_vision(
    hallazgos: dict[str, Any],
    client: Any,
    modelo: str,
    imagen_path: str | Path,
    catalogo: Catalogo,
    cache_dir: str | Path | None = None,
) -> None:
    """Rellena veredicto, pieza, severidad y descripcion de cada finding, y
    recalcula su `confidence_tier` con `decidir_tier`, in-place. Requiere que
    `generar_recortes` ya se haya ejecutado (necesita `crop_image_path`)."""
    with Image.open(imagen_path) as imagen:
        imagen.load()
        for finding in hallazgos["findings"]:
            finding.update(analizar_hallazgo(client, modelo, imagen, finding, catalogo, cache_dir))
            finding["confidence_tier"] = decidir_tier(
                finding["category"],
                finding["score"],
                finding["vision_verdict"],
                finding["pieza_id"],
                finding["regla_coste_aplicable"],
            )
