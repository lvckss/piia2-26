from __future__ import annotations

import argparse
import json
import shutil
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SelectedExemplar:
    image_id: int
    annotation_id: int
    image_file_name: str
    copied_image_name: str
    bbox_xywh: list[float]
    area: float
    width: int
    height: int


def find_project_root() -> Path:
    # buscamos la raiz real del proyecto para que el script funcione desde cualquier cwd
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "bd" / "rawdata").exists() and (parent / "ml").exists():
            return parent

    raise RuntimeError("No se pudo encontrar la raiz del proyecto desde el script.")


def parse_args() -> argparse.Namespace:
    project_root = find_project_root()

    parser = argparse.ArgumentParser(
        description=(
            "Crea un support set de image exemplars a partir de instances_all.json "
            "copiando las imagenes originales y generando un manifest.json con bbox."
        )
    )
    parser.add_argument(
        "--ann-path",
        type=Path,
        default=project_root / "bd" / "rawdata" / "instances_all.json",
    )
    parser.add_argument(
        "--img-dir",
        type=Path,
        default=project_root / "bd" / "rawdata" / "images",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=project_root / "ml" / "config" / "image_exemplars",
    )
    parser.add_argument(
        "--category",
        required=True,
        help="category_id o nombre exacto de la categoria, por ejemplo 6 o 'tire flat'.",
    )
    parser.add_argument(
        "--image-ids",
        nargs="+",
        type=int,
        required=True,
        help="lista de image_id que se quieren convertir en exemplars.",
    )
    parser.add_argument(
        "--mode",
        choices=["exemplar", "hybrid"],
        default="hybrid",
        help="modo que se guardara en el manifest.",
    )
    parser.add_argument(
        "--text",
        default=None,
        help="texto del prompt si el manifest va en modo hybrid. por defecto usa el nombre de la categoria.",
    )
    parser.add_argument(
        "--multi-ann-policy",
        choices=["largest", "first", "error"],
        default="largest",
        help="que hacer si una imagen tiene varias anotaciones de la misma clase.",
    )
    parser.add_argument(
        "--folder-name",
        default=None,
        help="nombre manual de la carpeta destino. por defecto usa <category_id>_<category_name>.",
    )
    parser.add_argument(
        "--manifest-name",
        default="manifest.json",
    )
    return parser.parse_args()


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower().strip()
    cleaned = []
    previous_was_sep = False

    for char in normalized:
        if char.isalnum():
            cleaned.append(char)
            previous_was_sep = False
            continue

        if not previous_was_sep:
            cleaned.append("_")
            previous_was_sep = True

    return "".join(cleaned).strip("_") or "category"


def load_coco_dict(ann_path: Path) -> dict[str, Any]:
    if not ann_path.exists():
        raise FileNotFoundError(f"No existe el archivo de anotaciones: {ann_path}")

    with ann_path.open(encoding="utf-8") as annotations_file:
        data = json.load(annotations_file)

    required_keys = {"images", "annotations", "categories"}
    missing_keys = sorted(required_keys - set(data))
    if missing_keys:
        raise ValueError(
            "El json de anotaciones no tiene el formato esperado. "
            f"Faltan claves: {missing_keys}"
        )

    return data


def resolve_category(
    category_arg: str,
    categories: list[dict[str, Any]],
) -> tuple[int, str]:
    # aceptamos tanto category_id como nombre de categoria
    categories_by_id = {
        int(category["id"]): str(category["name"])
        for category in categories
    }
    categories_by_name = {
        str(category["name"]).strip().lower(): int(category["id"])
        for category in categories
    }

    if category_arg.isdigit():
        category_id = int(category_arg)
        if category_id not in categories_by_id:
            raise KeyError(f"category_id no existe en categories: {category_id}")
        return category_id, categories_by_id[category_id]

    normalized_name = category_arg.strip().lower()
    if normalized_name not in categories_by_name:
        raise KeyError(f"category_name no existe en categories: {category_arg!r}")

    category_id = categories_by_name[normalized_name]
    return category_id, categories_by_id[category_id]


def resolve_image_path(img_dir: Path, file_name: str) -> Path:
    clean_name = file_name.lstrip("./")
    candidates = [
        img_dir / clean_name,
        img_dir / "images" / clean_name,
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        f"No se encontro la imagen {file_name!r}. "
        f"Se busco en: {', '.join(str(candidate) for candidate in candidates)}"
    )


def select_annotation(
    *,
    image_id: int,
    category_id: int,
    annotations_by_image_id: dict[int, list[dict[str, Any]]],
    multi_ann_policy: str,
) -> dict[str, Any]:
    # para image exemplars necesitamos quedarnos con una sola bbox por imagen
    candidates = [
        ann
        for ann in annotations_by_image_id.get(image_id, [])
        if int(ann["category_id"]) == category_id
    ]

    if not candidates:
        raise ValueError(
            "La imagen pedida no tiene anotaciones para la categoria seleccionada. "
            f"image_id={image_id}, category_id={category_id}"
        )

    if len(candidates) == 1:
        return candidates[0]

    ordered = sorted(
        candidates,
        key=lambda ann: (
            -float(ann.get("area", 0.0)),
            int(ann["id"]),
        ),
    )

    if multi_ann_policy == "largest":
        # por defecto nos quedamos con la instancia mas grande de esa clase
        return ordered[0]

    if multi_ann_policy == "first":
        return sorted(candidates, key=lambda ann: int(ann["id"]))[0]

    raise ValueError(
        "La imagen tiene varias anotaciones para la categoria y la politica actual es error. "
        f"image_id={image_id}, category_id={category_id}, annotation_ids="
        f"{[int(ann['id']) for ann in ordered]}"
    )


def build_manifest(
    *,
    selected_exemplars: list[SelectedExemplar],
    category_id: int,
    category_name: str,
    mode: str,
    text: str | None,
    ann_path: Path,
    img_dir: Path,
    multi_ann_policy: str,
) -> dict[str, Any]:
    manifest = {
        "category_id": category_id,
        "category_name": category_name,
        "mode": mode,
        "text": text,
        "source": {
            "ann_path": str(ann_path),
            "img_dir": str(img_dir),
            "multi_ann_policy": multi_ann_policy,
        },
        "exemplars": [
            {
                "image": exemplar.copied_image_name,
                "image_id": exemplar.image_id,
                "annotation_id": exemplar.annotation_id,
                "bbox_xywh": exemplar.bbox_xywh,
                "area": exemplar.area,
                "width": exemplar.width,
                "height": exemplar.height,
                "source_file_name": exemplar.image_file_name,
            }
            for exemplar in selected_exemplars
        ],
    }

    return manifest


def main() -> None:
    args = parse_args()
    data = load_coco_dict(args.ann_path)

    category_id, category_name = resolve_category(
        args.category,
        data["categories"],
    )

    images_by_id = {
        int(image["id"]): image
        for image in data["images"]
    }

    annotations_by_image_id: dict[int, list[dict[str, Any]]] = {}
    for annotation in data["annotations"]:
        image_id = int(annotation["image_id"])
        annotations_by_image_id.setdefault(image_id, []).append(annotation)

    folder_name = args.folder_name or f"{category_id}_{slugify(category_name)}"
    output_dir = args.output_root / folder_name
    output_dir.mkdir(parents=True, exist_ok=True)

    # en hybrid dejamos un texto minimo para que el manifest ya sea util sin tocarlo
    prompt_text = args.text
    if args.mode == "hybrid" and not prompt_text:
        prompt_text = category_name
    if args.mode == "exemplar":
        prompt_text = None

    selected_exemplars: list[SelectedExemplar] = []
    seen_image_ids: set[int] = set()

    for image_id in args.image_ids:
        if image_id in seen_image_ids:
            raise ValueError(f"image_id repetido en --image-ids: {image_id}")
        seen_image_ids.add(image_id)

        if image_id not in images_by_id:
            raise KeyError(f"image_id no existe en images: {image_id}")

        image_info = images_by_id[image_id]
        annotation = select_annotation(
            image_id=image_id,
            category_id=category_id,
            annotations_by_image_id=annotations_by_image_id,
            multi_ann_policy=args.multi_ann_policy,
        )

        image_path = resolve_image_path(args.img_dir, str(image_info["file_name"]))
        copied_image_name = Path(str(image_info["file_name"]).lstrip("./")).name
        # copiamos la imagen original completa y dejamos la bbox en el manifest
        shutil.copy2(image_path, output_dir / copied_image_name)

        selected_exemplars.append(
            SelectedExemplar(
                image_id=image_id,
                annotation_id=int(annotation["id"]),
                image_file_name=str(image_info["file_name"]),
                copied_image_name=copied_image_name,
                bbox_xywh=[
                    float(value)
                    for value in annotation["bbox"]
                ],
                area=float(annotation.get("area", 0.0)),
                width=int(image_info["width"]),
                height=int(image_info["height"]),
            )
        )

    manifest = build_manifest(
        selected_exemplars=selected_exemplars,
        category_id=category_id,
        category_name=category_name,
        mode=args.mode,
        text=prompt_text,
        ann_path=args.ann_path,
        img_dir=args.img_dir,
        multi_ann_policy=args.multi_ann_policy,
    )

    manifest_path = output_dir / args.manifest_name
    # el manifest queda listo para usarse como support set y para trazabilidad
    with manifest_path.open("w", encoding="utf-8") as manifest_file:
        json.dump(
            manifest,
            manifest_file,
            ensure_ascii=False,
            indent=2,
        )
        manifest_file.write("\n")

    print(f"categoria: {category_id} | {category_name}")
    print(f"output_dir: {output_dir}")
    print(f"manifest: {manifest_path}")
    print(f"num_exemplars: {len(selected_exemplars)}")
    for exemplar in selected_exemplars:
        print(
            " - "
            f"image_id={exemplar.image_id} "
            f"annotation_id={exemplar.annotation_id} "
            f"image={exemplar.copied_image_name} "
            f"bbox_xywh={exemplar.bbox_xywh}"
        )


if __name__ == "__main__":
    main()
