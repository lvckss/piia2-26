from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from catalogo import Catalogo, cargar_catalogo
from hallazgos import cargar_detecciones, construir_hallazgos
from recorte import generar_recortes
from vision import enriquecer_con_vision


def crear_cliente_openai() -> Any:
    """Crea el cliente real de OpenAI con la API Key de la variable de entorno
    OPENAI_API_KEY (la clave que da la empresa; nunca va en el repo). Se
    importa `openai` aqui dentro para que el resto del modulo funcione sin el
    paquete instalado (por ejemplo, en las pruebas con cliente falso)."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("Falta la variable de entorno OPENAI_API_KEY (la API Key del caso).")

    from openai import OpenAI

    # Sin brotli: con el paquete `brotli` (en realidad brotlipy) que trae algun
    # Anaconda, httpx2 revienta al leer respuestas `br` con un TypeError sobre
    # `output_buffer_limit`. gzip va bien. Ver agentes/README.md.
    # timeout corto: por defecto el SDK espera 10 min por llamada, y una que se
    # cuelga parece que el script esta parado
    return OpenAI(
        default_headers={"Accept-Encoding": "gzip, deflate"},
        timeout=120.0,
        max_retries=1,
    )


def resolver_modelo(modelo: str | None) -> str:
    modelo = modelo or os.environ.get("OPENAI_MODEL")
    if not modelo:
        raise RuntimeError(
            "Indica el modelo con el parametro `modelo` o la variable de entorno "
            "OPENAI_MODEL (el id exacto que figure en la cuenta de la empresa)."
        )
    return modelo


def analizar_imagen(
    deteccion_path: str | Path,
    client: Any,
    crops_dir: str | Path,
    modelo: str | None = None,
    image_path: str | Path | None = None,
    output_path: str | Path | None = None,
    catalogo: Catalogo | None = None,
    cache_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Ejecuta el Agente 1 completo sobre la salida de PIIA-1 de una imagen y
    devuelve el JSON del contrato Agente 1 -> Agente 2/3
    (`specs/piia2-arquitectura-multiagente.md`).

    `image_path` sustituye al `image_path` del JSON de PIIA-1 cuando la foto
    esta en otra ruta (por ejemplo, el CarDD montado en Colab). `catalogo`
    por defecto sale del paquete de datos de la empresa. `cache_dir` evita
    repetir (y pagar) llamadas identicas al modelo. Si se pasa `output_path`,
    el resultado tambien se guarda ahi como JSON.
    """
    modelo = resolver_modelo(modelo)
    catalogo = catalogo or cargar_catalogo()

    deteccion = cargar_detecciones(deteccion_path)
    if image_path is not None:
        deteccion["image_path"] = str(image_path)

    hallazgos = construir_hallazgos(deteccion)
    generar_recortes(deteccion, hallazgos, crops_dir)
    enriquecer_con_vision(
        hallazgos, client, modelo, deteccion["image_path"], catalogo, cache_dir=cache_dir
    )

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
    parser.add_argument("--modelo", help="id del modelo (o variable OPENAI_MODEL)")
    parser.add_argument("--crops-dir", default="crops", help="donde guardar los recortes")
    parser.add_argument("--cache-dir", help="carpeta de cache de respuestas del modelo")
    parser.add_argument("--salida", help="donde guardar el JSON de hallazgos")
    args = parser.parse_args()

    resultado = analizar_imagen(
        args.deteccion,
        crear_cliente_openai(),
        args.crops_dir,
        modelo=args.modelo,
        image_path=args.imagen,
        output_path=args.salida,
        cache_dir=args.cache_dir,
    )
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
