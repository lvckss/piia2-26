from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from hallazgos import cargar_detecciones, construir_hallazgos
from recorte import generar_recortes
from vision import enriquecer_con_vision


def crear_cliente_anthropic() -> Any:
    """Crea el cliente real de Anthropic con la API Key de la variable de
    entorno ANTHROPIC_API_KEY. Se importa `anthropic` aqui dentro para que el
    resto del modulo funcione sin el paquete instalado (por ejemplo, en las
    pruebas con cliente falso)."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "Falta la variable de entorno ANTHROPIC_API_KEY (la API Key del caso)."
        )

    import anthropic

    return anthropic.Anthropic()


def analizar_imagen(
    deteccion_path: str | Path,
    client: Any,
    crops_dir: str | Path,
    image_path: str | Path | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Ejecuta el Agente 1 completo sobre la salida de PIIA-1 de una imagen y
    devuelve el JSON del contrato Agente 1 -> Agente 2/3
    (`specs/piia2-arquitectura-multiagente.md`).

    `image_path` sustituye al `image_path` del JSON de PIIA-1 cuando la foto
    esta en otra ruta (por ejemplo, el CarDD montado en Colab). Si se pasa
    `output_path`, el resultado tambien se guarda ahi como JSON.
    """
    deteccion = cargar_detecciones(deteccion_path)
    if image_path is not None:
        deteccion["image_path"] = str(image_path)

    hallazgos = construir_hallazgos(deteccion)
    generar_recortes(deteccion, hallazgos, crops_dir)
    enriquecer_con_vision(hallazgos, client)

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(hallazgos, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return hallazgos


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Agente 1: analista de danos (multimodal)")
    parser.add_argument("deteccion", help="JSON de PIIA-1 de una imagen")
    parser.add_argument("--imagen", help="ruta real de la foto, si no es la del JSON")
    parser.add_argument("--crops-dir", default="crops", help="donde guardar los recortes")
    parser.add_argument("--salida", help="donde guardar el JSON de hallazgos")
    args = parser.parse_args()

    resultado = analizar_imagen(
        args.deteccion,
        crear_cliente_anthropic(),
        args.crops_dir,
        image_path=args.imagen,
        output_path=args.salida,
    )
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
