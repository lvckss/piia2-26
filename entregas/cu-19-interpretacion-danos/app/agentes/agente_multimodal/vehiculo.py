"""Categoria del vehiculo a partir de la foto (Issue #28, ADR 0001, `specs/28-categoria-vehiculo.md`).

El Agente 1 pregunta una vez por imagen a que categoria del catalogo de la empresa pertenece el coche y
propone un coche de referencia para presupuestar. Es una propuesta orientativa: la persona usuaria la
confirma o corrige en la web (#34). La respuesta del modelo se valida y nunca se acepta tal cual.
"""

from __future__ import annotations

from typing import Any

from PIL import Image

from vision import _extraer_json, _jpeg_base64

# Los 8 segmentos del catalogo de vehiculos de la empresa (campo `segmento` de `vehiculos.csv`)
CATEGORIAS = ("A", "B", "C", "SUV-B", "SUV-C", "FURG", "C-PREMIUM", "D-PREMIUM")
DESCONOCIDO = "desconocido"
CONFIANZAS = ("alta", "media", "baja")

# Coche de referencia de cada categoria (ids de `vehiculos.csv`, paquete de la empresa): el del segmento cuyo
# `factor_precio_pieza` esta mas cerca de la media del segmento (a igualdad, el de menor id). `desconocido` no
# tiene coche de referencia: la persona usuaria elige en la web. AC-004 comprueba esta tabla contra el CSV.
REFERENCIA = {
    "A": "V24",  # Fiat 500
    "B": "V07",  # Renault Clio
    "C": "V02",  # SEAT Leon
    "SUV-B": "V08",  # Renault Captur
    "SUV-C": "V11",  # Peugeot 3008
    "FURG": "V09",  # Renault Kangoo
    "C-PREMIUM": "V26",  # Mercedes-Benz Clase A
    "D-PREMIUM": "V25",  # BMW Serie 3
}

PROMPT_VEHICULO = """\
Eres un perito de vehiculos. La imagen es la foto de un vehiculo danado. Indica a que categoria pertenece el vehiculo, para poder presupuestar su reparacion con un coche de referencia.

Responde SOLO con un objeto JSON con estas claves:
- "categoria": una de estas, elegida EXACTAMENTE:
  - "A": utilitario muy pequeno (por ejemplo Fiat 500).
  - "B": utilitario (por ejemplo Ibiza, Polo, Clio, 208, C3, Sandero, Yaris, Corsa).
  - "C": compacto (por ejemplo Leon, Golf, C4, Corolla, Focus).
  - "SUV-B": SUV pequeno (por ejemplo Arona, Captur, Duster).
  - "SUV-C": SUV mediano (por ejemplo Tiguan, 3008, RAV4, Tucson, Sportage).
  - "FURG": furgoneta pequena de reparto (por ejemplo Kangoo, Transit Connect).
  - "C-PREMIUM": compacto premium (por ejemplo Mercedes Clase A, Audi A3).
  - "D-PREMIUM": berlina premium (por ejemplo BMW Serie 3).
  - "desconocido": si no distingues el tipo de vehiculo o no es ninguno de los anteriores (por ejemplo un camion, un autobus o una moto).
- "confianza": "alta", "media" o "baja".
- "descripcion": una frase en espanol con el tipo de vehiculo y, solo si lo reconoces con seguridad, la marca y el modelo.

No indiques matriculas, personas ni propietarios, aunque se vean en la foto. Si no puedes distinguir la categoria con seguridad, responde "desconocido" en vez de adivinar."""


def parsear_respuesta_vehiculo(texto: str) -> dict[str, str]:
    """Convierte la respuesta del modelo en `categoria`, `confianza` y `descripcion`, validandola: una categoria
    fuera de la lista (o una respuesta que no es JSON, sin `categoria` o vacia) es `desconocido` con confianza
    `baja`; una confianza fuera de alta/media/baja, o `alta` con `desconocido`, pasa a `baja`."""
    datos = _extraer_json(texto)
    categoria = datos.get("categoria")
    confianza = datos.get("confianza")
    if not isinstance(categoria, str) or categoria not in (*CATEGORIAS, DESCONOCIDO):
        categoria, confianza = DESCONOCIDO, "baja"
    elif confianza not in CONFIANZAS or (categoria == DESCONOCIDO and confianza == "alta"):
        confianza = "baja"
    return {
        "categoria": categoria,
        "confianza": confianza,
        "descripcion": str(datos.get("descripcion") or "").strip(),
    }


def consultar_vehiculo(client: Any, modelo: str, imagen: Image.Image) -> dict[str, Any]:
    """Pregunta al modelo de vision la categoria del vehiculo de la foto y devuelve el objeto `vehiculo` del
    contrato del Agente 1: exactamente `categoria`, `vehiculo_id_referencia`, `confianza`, `descripcion` y
    `modelo`. Si el proveedor falla, la excepcion llega al llamante (no se inventa un `desconocido`)."""
    respuesta = client.chat.completions.create(
        model=modelo,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT_VEHICULO},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{_jpeg_base64(imagen)}"}},
                ],
            }
        ],
        response_format={"type": "json_object"},
    )
    datos = parsear_respuesta_vehiculo(respuesta.choices[0].message.content or "")
    return {
        "categoria": datos["categoria"],
        "vehiculo_id_referencia": REFERENCIA.get(datos["categoria"]),
        "confianza": datos["confianza"],
        "descripcion": datos["descripcion"],
        "modelo": modelo,
    }
