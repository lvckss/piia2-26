from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from catalogo import clase_a_tool
from confianza import classify_confidence


def cargar_detecciones(json_path: str | Path) -> dict[str, Any]:
    """Lee el JSON de detecciones de PIIA-1 (formato `build_json_summary`
    + `image_id`, ver `ejemplos/README.md`; los de la exportacion de Colab
    traen ademas `is_true_positive`, que aqui se ignora)."""
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


def construir_hallazgos(deteccion: dict[str, Any]) -> dict[str, Any]:
    """Convierte las predicciones crudas de PIIA-1 en la lista de `findings`
    del contrato Agente 1 -> Agente 2/3
    (`specs/piia2-arquitectura-multiagente.md`).

    Aqui solo se aplica el filtro por score. `vision_verdict`, `pieza_id`,
    `severidad`, `regla_coste_aplicable`, `vision_description` y
    `crop_image_path` quedan en `None` hasta que se recorte la imagen y se
    llame al modelo de vision; entonces `confidence_tier` se recalcula con el
    veredicto (ver `vision.enriquecer_con_vision`).
    """
    image_id = deteccion["image_id"]
    findings = []
    for pred in deteccion["predictions"]:
        tier_por_score = classify_confidence(pred["damage_class"], pred["score"])
        findings.append(
            {
                "finding_id": f"{image_id}-{pred['instance_index']}",
                "category": pred["damage_class"],
                "clase_tool": clase_a_tool(pred["damage_class"]),
                "score": pred["score"],
                "score_tier": tier_por_score,
                "confidence_tier": tier_por_score,
                "bbox_xywh": pred["bbox_xywh"],
                "vision_verdict": None,
                "pieza_id": None,
                "severidad": None,
                "regla_coste_aplicable": None,
                "vision_description": None,
                "crop_image_path": None,
            }
        )
    return {
        "image_id": image_id,
        "findings": findings,
    }


if __name__ == "__main__":
    ejemplos_dir = Path(__file__).parent / "ejemplos"
    for ejemplo_path in sorted(ejemplos_dir.glob("*.json")):
        deteccion = cargar_detecciones(ejemplo_path)
        resultado = construir_hallazgos(deteccion)
        print(f"--- {ejemplo_path.name} ---")
        for finding in resultado["findings"]:
            print(
                f"  {finding['category']:15s} score={finding['score']:.2f} "
                f"-> {finding['score_tier']} (solo por score)"
            )
