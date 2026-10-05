from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

# Margen relativo (fraccion del ancho/alto del bbox) anadido por cada lado
# al recortar, para darle al modelo de vision contexto alrededor del bbox
# exacto de PIIA-1 en vez de un recorte justo al borde del dano.
MARGEN_RELATIVO = 0.15


def recortar_hallazgo(
    imagen: Image.Image, bbox_xywh: list[float], margen: float = MARGEN_RELATIVO
) -> Image.Image:
    """Recorta de `imagen` la region de `bbox_xywh`, ampliada `margen` por
    lado y recortada a los limites de la imagen."""
    x, y, w, h = bbox_xywh
    margen_x = w * margen
    margen_y = h * margen

    x0 = max(0, x - margen_x)
    y0 = max(0, y - margen_y)
    x1 = min(imagen.width, x + w + margen_x)
    y1 = min(imagen.height, y + h + margen_y)

    return imagen.crop((round(x0), round(y0), round(x1), round(y1)))


def generar_recortes(
    deteccion: dict[str, Any], hallazgos: dict[str, Any], output_dir: str | Path
) -> None:
    """Abre la imagen de `deteccion` una sola vez, recorta cada finding de
    `hallazgos` y guarda el resultado en `output_dir`. Rellena
    `crop_image_path` en cada finding, in-place."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    imagen = Image.open(deteccion["image_path"])
    image_id = deteccion["image_id"]

    for finding in hallazgos["findings"]:
        crop = recortar_hallazgo(imagen, finding["bbox_xywh"])
        instance_index = finding["finding_id"].split("-")[-1]
        categoria = finding["category"].replace(" ", "_")
        nombre = f"{image_id}_{categoria}_{instance_index}.jpg"
        crop_path = output_dir / nombre
        crop.convert("RGB").save(crop_path, quality=90)
        finding["crop_image_path"] = str(crop_path)


if __name__ == "__main__":
    import json
    import tempfile

    from hallazgos import cargar_detecciones, construir_hallazgos

    ejemplos_dir = Path(__file__).parent / "ejemplos"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        crops_dir = tmp_dir / "crops"

        print("=== Recortes sobre los 3 ejemplos (imagen sintetica) ===")
        for ejemplo_path in sorted(ejemplos_dir.glob("*.json")):
            deteccion = cargar_detecciones(ejemplo_path)

            # No tenemos las imagenes reales del CarDD en esta maquina (estan
            # en Colab), asi que generamos una imagen sintetica del mismo
            # tamano solo para poder ejercitar la logica de recorte de
            # verdad, sin depender del dataset.
            imagen_falsa = Image.new(
                "RGB", (deteccion["image_width"], deteccion["image_height"]), "gray"
            )
            fake_image_path = tmp_dir / f"{deteccion['image_id']}.jpg"
            imagen_falsa.save(fake_image_path)
            deteccion["image_path"] = str(fake_image_path)

            hallazgos = construir_hallazgos(deteccion)
            generar_recortes(deteccion, hallazgos, crops_dir)

            print(f"--- {ejemplo_path.name} ---")
            for finding in hallazgos["findings"]:
                with Image.open(finding["crop_image_path"]) as crop_img:
                    print(
                        f"  {finding['category']:15s} bbox={finding['bbox_xywh']} "
                        f"-> crop {crop_img.size} guardado en "
                        f"{Path(finding['crop_image_path']).name}"
                    )

        print("\n=== Caso limite: bbox pegado al borde (0,0) ===")
        imagen_borde = Image.new("RGB", (300, 300), "gray")
        crop_borde = recortar_hallazgo(imagen_borde, [0.0, 0.0, 50.0, 50.0])
        print(f"  bbox=[0,0,50,50] en imagen 300x300 -> crop {crop_borde.size}")
        assert crop_borde.size == (round(50 + 50 * MARGEN_RELATIVO), round(50 + 50 * MARGEN_RELATIVO))

        print("\n=== Caso limite: bbox pegado a la esquina opuesta ===")
        crop_borde2 = recortar_hallazgo(imagen_borde, [270.0, 270.0, 30.0, 30.0])
        print(f"  bbox=[270,270,30,30] en imagen 300x300 -> crop {crop_borde2.size}")
        # lado derecho/inferior recortado al borde (sin margen ahi), pero el
        # lado izquierdo/superior si conserva su margen -> no queda simetrico
        assert crop_borde2.size == (34, 34)

        print("\nTodo ok.")
