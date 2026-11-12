from __future__ import annotations

import base64
import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any, Callable

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


# Issue #54, slice 3 (plan v1.1: https://github.com/lvckss/piia2-26/issues/54#issuecomment-6806386857).
# AC-005: a veces el modelo devuelve un JSON valido cuya descripcion lleva alfabetos ajenos (CJK, indios, cirilico...)
# o restos de su razonamiento en ingles; una descripcion asi no se acepta tal cual.
_ALFABETOS_AJENOS = re.compile(
    r"[Ѐ-ԯ֐-႟Ⴀ-ᇿ⺀-꓏가-힯豈-﫿︰-﹏＀-￯�]"
)
_RESTOS_DE_RAZONAMIENTO = re.compile(r"\b(Wait|Actually|Let me|Need ensure|Need to|malformed)\b")
DESCRIPCION_DESCARTADA = "Descripcion descartada: la respuesta del modelo no era valida."

# AC-013: una descripcion que situa el dano en otro vehiculo o en el fondo no puede quedar `confirmado`.
_OTRO_VEHICULO = re.compile(
    r"\b(otro|segundo)\s+(veh[ií]culo|coche|autom[oó]vil)\b"
    r"|\b(veh[ií]culo|coche|autom[oó]vil)(\s+\w+){0,2}\s+(del|al|de)\s+fondo\b",
    re.IGNORECASE,
)


def descripcion_corrupta(texto: str) -> bool:
    """True si la descripcion lleva alfabetos ajenos al español o restos de razonamiento del modelo."""
    return bool(_ALFABETOS_AJENOS.search(texto) or _RESTOS_DE_RAZONAMIENTO.search(texto))


def descripcion_de_otro_vehiculo(texto: str) -> bool:
    """True si la descripcion dice que la zona es de otro vehiculo o del vehiculo del fondo."""
    return bool(_OTRO_VEHICULO.search(texto))


def respuesta_sin_basura(texto: str) -> bool:
    """False si la respuesta es un JSON valido con una descripcion corrupta (AC-005); el resto, incluido lo que
    no es JSON (que ya queda `incierto`), se considera una respuesta utilizable."""
    datos = _extraer_json(texto)
    return not descripcion_corrupta(str(datos.get("descripcion") or ""))


def parsear_respuesta(texto: str, catalogo: Catalogo, clase_tool: str) -> dict[str, Any]:
    """Convierte la respuesta del modelo en los campos del hallazgo,
    validandola: un veredicto, pieza o severidad fuera de lo permitido no se
    acepta (el modelo puede inventarse un `pieza_id`)."""
    datos = _extraer_json(texto)

    descripcion = str(datos.get("descripcion") or "").strip()
    if descripcion_corrupta(descripcion):
        return {
            "vision_verdict": "incierto",
            "pieza_id": None,
            "severidad": None,
            "regla_coste_aplicable": None,
            "vision_description": DESCRIPCION_DESCARTADA,
        }

    veredicto = datos.get("veredicto")
    if veredicto not in VEREDICTOS:
        veredicto = "incierto"
    if veredicto == "confirmado" and descripcion_de_otro_vehiculo(descripcion):
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


def consultar_modelo(
    client: Any,
    modelo: str,
    prompt: str,
    imagenes_b64: tuple[str, ...],
    cache_dir: str | Path | None = None,
    uso: dict[str, int] | None = None,
    valida: Callable[[str], bool] | None = None,
) -> str:
    """Una consulta al modelo de vision con `prompt` e `imagenes_b64` (JPEG en base64) y devuelve el texto de
    la respuesta. Con `cache_dir`, la respuesta se guarda por (modelo, prompt, imagenes) en
    `<sha256>.json` y no se vuelve a pagar la misma consulta; la clave es `sha256("|".join((modelo, prompt,
    *imagenes)))`. Si se pasa `uso`, se le suman las llamadas y los tokens realmente facturados (lo que sale
    de la cache no cuenta): claves `llamadas`, `prompt_tokens` y `completion_tokens`. Si se pasa `valida`, una
    respuesta guardada que no la cumpla se descarta y se vuelve a consultar, y una respuesta nueva que no la
    cumpla no se guarda (Issue #54, AC-006)."""
    ruta_cache = None
    if cache_dir is not None:
        clave = hashlib.sha256("|".join((modelo, prompt, *imagenes_b64)).encode("utf-8")).hexdigest()
        ruta_cache = Path(cache_dir) / f"{clave}.json"
        if ruta_cache.exists():
            guardada = json.loads(ruta_cache.read_text(encoding="utf-8"))["respuesta"]
            if valida is None or valida(guardada):
                return guardada

    respuesta = client.chat.completions.create(
        model=modelo,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    *({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}} for b64 in imagenes_b64),
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

    if ruta_cache is not None and (valida is None or valida(texto)):
        ruta_cache.parent.mkdir(parents=True, exist_ok=True)
        ruta_cache.write_text(
            json.dumps({"modelo": modelo, "respuesta": texto}, ensure_ascii=False),
            encoding="utf-8",
        )
    return texto


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

    texto = consultar_modelo(client, modelo, prompt, (contexto_b64, recorte_b64), cache_dir, uso, respuesta_sin_basura)
    if not respuesta_sin_basura(texto):
        # descripcion corrupta: una sola repeticion (la corrupta no se guarda en la cache); si persiste, queda `incierto`
        texto = consultar_modelo(client, modelo, prompt, (contexto_b64, recorte_b64), cache_dir, uso, respuesta_sin_basura)
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
