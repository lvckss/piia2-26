"""Prueba el Agente 1 de punta a punta (agente1.analizar_imagen) sin API Key
real: usa el cliente falso de probar_vision_stub.py y una imagen sintetica.
Comprueba que el JSON final cumple el contrato Agente 1 -> Agente 2/3."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from PIL import Image

from agente1 import analizar_imagen
from probar_vision_stub import MINI_CATALOGO, ClienteFalso

CAMPOS_FINDING = {
    "finding_id",
    "category",
    "clase_tool",
    "score",
    "score_tier",
    "confidence_tier",
    "bbox_xywh",
    "vision_verdict",
    "pieza_id",
    "severidad",
    "regla_coste_aplicable",
    "vision_description",
    "crop_image_path",
}


def main() -> None:
    ejemplo_path = Path(__file__).parent / "ejemplos" / "ejemplo_3_mixto_dificil.json"
    deteccion = json.loads(ejemplo_path.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        foto_falsa = tmp_dir / "foto.jpg"
        Image.new("RGB", (deteccion["image_width"], deteccion["image_height"]), "gray").save(
            foto_falsa
        )
        salida = tmp_dir / "salida" / "hallazgos.json"

        resultado = analizar_imagen(
            ejemplo_path,
            ClienteFalso(),
            tmp_dir / "crops",
            modelo="modelo-falso",
            image_path=foto_falsa,
            output_path=salida,
            catalogo=MINI_CATALOGO,
        )

        guardado = json.loads(salida.read_text(encoding="utf-8"))
        assert guardado == resultado, "el JSON guardado no coincide con el devuelto"

        for finding in resultado["findings"]:
            assert Path(finding["crop_image_path"]).exists(), "falta el recorte en disco"

    assert set(resultado) == {"image_id", "findings"}
    assert resultado["image_id"] == 160
    assert len(resultado["findings"]) == 3
    for finding in resultado["findings"]:
        assert set(finding) == CAMPOS_FINDING, f"campos inesperados: {set(finding) ^ CAMPOS_FINDING}"
        assert finding["vision_verdict"] in ("confirmado", "rechazado", "incierto")
        assert finding["vision_description"], "vision_description vacio"
        assert finding["clase_tool"] == finding["category"].replace(" ", "_")

    tiers = [f["confidence_tier"] for f in resultado["findings"]]
    assert tiers == ["confirmed", "needs_review", "needs_review"], tiers

    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    print("\nTodo ok: el JSON final cumple el contrato Agente 1 -> Agente 2/3.")


if __name__ == "__main__":
    main()
