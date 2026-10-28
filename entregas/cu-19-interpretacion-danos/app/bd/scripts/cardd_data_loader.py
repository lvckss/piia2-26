import pandas as pd
from pathlib import Path
import json
from typing import Any


def load_xlsx_metadata(xlsx_path: str | Path) -> dict[int, dict]:
    """
    Función que lee image_info.xlsx y devuelve un diccionario:
    {
        id_externo: {
            "id_externo": ...,
            "file_name": ...,
            "width": ...,
            "height": ...,
            "file_size_kb": ...,
            "numero_instancias": ...,
            "numero_categorias": ...,
            "angulo_fotografia": ...,
            "cobertura": ...,
            "color_vehiculo": ...,
            "observaciones": None,
        }
    }
    """
    xlsx_path = Path(xlsx_path)

    df = pd.read_excel(xlsx_path)

    # Renombramos exactamente las columnas del Excel a nombres adaptados a nuestro schema de psql
    df = df.rename(
        columns={
            "id": "id_externo",
            "file_name": "file_name",
            "width": "width",
            "height": "height",
            "file_size (KB)": "file_size_kb",
            "#instances": "numero_instancias",
            "#categories": "numero_categorias",
            "shooting angle": "angulo_fotografia",
            "complete or partial ": "cobertura",
            "color": "color_vehiculo",
        }
    )

    # Convertimos NaN a None para que se inserten como NULL en la base de datos
    df = df.where(pd.notnull(df), None)

    # Aseguramos tipos razonables
    numeric_cols = [
        "id_externo",
        "width",
        "height",
        "numero_instancias",
        "numero_categorias",
    ]
    for col in numeric_cols:
        df[col] = df[col].apply(lambda x: int(x) if x is not None else None)

    df["file_size_kb"] = df["file_size_kb"].apply(
        lambda x: float(x) if x is not None else None
    )

    # Construimos diccionario indexado por id_externo
    metadata_by_id: dict[int, dict] = {}

    for row in df.to_dict(orient="records"):
        metadata_by_id[row["id_externo"]] = {
            "id_externo": row["id_externo"],
            "file_name": row["file_name"],
            "width": row["width"],
            "height": row["height"],
            "file_size_kb": row["file_size_kb"],
            "numero_instancias": row["numero_instancias"],
            "numero_categorias": row["numero_categorias"],
            "angulo_fotografia": row["angulo_fotografia"],
            "cobertura": row["cobertura"],
            "color_vehiculo": row["color_vehiculo"],
            "observaciones": None,
        }

    return metadata_by_id


def load_coco_json(
    json_path: str | Path,
    split: str,
    xlsx_metadata_by_id: dict[int, dict],
    thumbnails_dirname: str = "thumbnails",
) -> dict[str, Any]:
    """
    Lee un JSON COCO de CarDD y devuelve:
    {
        "etiquetas": { id_externo_categoria: { ... } },
        "imagenes": { id_externo_imagen: { ... } },
        "instancias": [ { ... }, ... ],
    }

    Parámetros
    ----------
    json_path:
        Ruta al JSON
    split:
        Uno de: 'train', 'test', 'val'
    xlsx_metadata_by_id:
        Diccionario devuelto por load_xlsx_metadata(...)
    thumbnails_dirname:
        Nombre del directorio relativo para thumbnails, si quieres predecir rutas.
        Si no tienes thumbnails aún, puedes dejar ruta_thumbnail = None abajo.
    """
    json_path = Path(json_path)

    if split not in {"train", "test", "val"}:
        raise ValueError(f"split inválido: {split}")

    with open(json_path, "r", encoding="utf-8") as f:
        coco = json.load(f)

    # -------------------------------------------------------------------------
    # 1. Etiquetas / categorías
    # -------------------------------------------------------------------------
    etiquetas_by_external_id: dict[int, dict] = {}

    for category in coco.get("categories", []):
        category_id = int(category["id"])
        etiquetas_by_external_id[category_id] = {
            "id_externo": category_id,
            "nombre": category["name"],
        }

    # -------------------------------------------------------------------------
    # 2. Imágenes
    # -------------------------------------------------------------------------
    imagenes_by_external_id: dict[int, dict] = {}

    for image in coco.get("images", []):
        image_id = int(image["id"])
        file_name = image["file_name"]

        # Añadimos los metadatos del Excel
        xlsx_row = xlsx_metadata_by_id.get(image_id)

        # Si el Excel tiene info, la usamos como fuente principal
        # Si no, hacemos fallback al JSON
        if xlsx_row:
            width = xlsx_row["width"]
            height = xlsx_row["height"]
            resolved_file_name = xlsx_row["file_name"]
        else:
            width = int(image["width"])
            height = int(image["height"])
            resolved_file_name = file_name
            # ESTO NUNCA SE EJECUTA!!!!

        imagenes_by_external_id[image_id] = {
            "id_externo": image_id,
            "file_name": xlsx_row["file_name"] if xlsx_row else file_name,
            "split": split,
            # Ruta relativa a la imagen física
            "ruta_imagen": f"{split}/fullsize/{resolved_file_name}",
            # Si todavía no tienes thumbnails generados, puedes poner None
            # (stem le quita la extensión 00001.jpg -> 00001)
            "ruta_thumbnail": f"{split}/{thumbnails_dirname}/{Path(resolved_file_name).stem}.webp",
            "width": width,
            "height": height,
            "file_size_kb": xlsx_row["file_size_kb"] if xlsx_row else None,
            "numero_instancias": xlsx_row["numero_instancias"] if xlsx_row else 0,
            "numero_categorias": xlsx_row["numero_categorias"] if xlsx_row else 0,
            "angulo_fotografia": xlsx_row["angulo_fotografia"] if xlsx_row else None,
            "cobertura": xlsx_row["cobertura"] if xlsx_row else None,
            "color_vehiculo": xlsx_row["color_vehiculo"] if xlsx_row else None,
            "observaciones": xlsx_row["observaciones"] if xlsx_row else None,
        }

    # -------------------------------------------------------------------------
    # 3. Instancias / anotaciones
    # -------------------------------------------------------------------------
    instancias: list[dict] = []

    # array de anotaciones
    for annotation in coco.get("annotations", []):
        # en caso de que falte bbox, ponemos None (aunque idealmente no debería faltar)
        bbox = annotation.get("bbox", [None, None, None, None])
        print(annotation["id"])

        instancias.append(
            {
                "imagen_id_externo": int(annotation["image_id"]),
                "categoria_id_externo": int(annotation["category_id"]),
                # PostgreSQL JSONB: luego esto lo podrás insertar como JSON
                "segmentacion": annotation.get("segmentation", []),
                "area": float(annotation["area"]),
                "bbox_x": float(bbox[0]) if bbox[0] is not None else None,
                "bbox_y": float(bbox[1]) if bbox[1] is not None else None,
                "bbox_width": float(bbox[2]) if bbox[2] is not None else None,
                "bbox_height": float(bbox[3]) if bbox[3] is not None else None,
            }
        )

    return {
        "etiquetas": etiquetas_by_external_id,
        "imagenes": imagenes_by_external_id,
        "instancias": instancias,
    }

def load_all_coco_jsons(
    xlsx_metadata_by_id: dict[int, dict],
) -> dict[str, Any]:
    """
    Carga:
      - instances_train.json
      - instances_test.json
      - instances_val.json

    y devuelve todo unificado:
    {
        "etiquetas": { ... },
        "imagenes": { ... },
        "instancias": [ ... ]
    }
    """

    split_to_json = {
        "train": "./rawdata/instances_train.json",
        "test": "./rawdata/instances_test.json",
        "val": "./rawdata/instances_val.json",
    }

    all_etiquetas: dict[int, dict] = {}
    all_imagenes: dict[int, dict] = {}
    all_instancias: list[dict] = []

    for split, json_path in split_to_json.items():
        parsed = load_coco_json(
            json_path=json_path,
            split=split,
            xlsx_metadata_by_id=xlsx_metadata_by_id,
        )

        # Categorías: vienen repetidas en los 3 JSON, así que deduplicamos por id_externo
        for category_id, category_row in parsed["etiquetas"].items():
            existing = all_etiquetas.get(category_id)
            if existing is None:
                all_etiquetas[category_id] = category_row
            elif existing["nombre"] != category_row["nombre"]:
                raise ValueError(
                    f"Conflicto en categoría {category_id}: "
                    f"{existing['nombre']} != {category_row['nombre']}"
                )

        # Imágenes
        for image_id, image_row in parsed["imagenes"].items():
            if image_id in all_imagenes:
                raise ValueError(f"Imagen duplicada con id_externo={image_id}")
            all_imagenes[image_id] = image_row

        # Instancias
        all_instancias.extend(parsed["instancias"])

    return {
        "etiquetas": all_etiquetas,
        "imagenes": all_imagenes,
        "instancias": all_instancias,
    }



# función principal que se llamará desde otro script para cargar todo el dataset de CarDD a la base de datos
def build_cardd_dataset(rawdata_dir: str | Path) -> dict[str, Any]:
    xlsx_metadata = load_xlsx_metadata(Path(rawdata_dir) / "image_info.xlsx")
    return load_all_coco_jsons(xlsx_metadata)