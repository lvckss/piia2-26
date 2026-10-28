from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ANN_PATH = ROOT / "bd" / "rawdata" / "instances_all.json"
DEFAULT_IMAGE_DIR = ROOT / "bd" / "rawdata" / "images"
DEFAULT_OUTPUT_DIR = ROOT / "ml" / "presentation_assets"

DEFAULT_COLUMNS = 5
DEFAULT_ROWS = 3
DEFAULT_TILE_WIDTH = 640
DEFAULT_GAP = 28
DEFAULT_SEED = 20260510

CATEGORY_COLORS = {
    1: (239, 71, 111),   # dent
    2: (255, 209, 102),  # scratch
    3: (6, 214, 160),    # crack
    4: (17, 138, 178),   # glass shatter
    5: (131, 56, 236),   # lamp broken
    6: (138, 201, 38),   # tire flat
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="genera un mosaico 3x5 de imagenes aleatorias del dataset, limpio y anotado",
    )
    parser.add_argument(
        "--ann-path",
        type=Path,
        default=DEFAULT_ANN_PATH,
        help="ruta al json coco",
    )
    parser.add_argument(
        "--image-dir",
        type=Path,
        default=DEFAULT_IMAGE_DIR,
        help="directorio de imagenes",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="directorio de salida",
    )
    parser.add_argument(
        "--columns",
        type=int,
        default=DEFAULT_COLUMNS,
        help="numero de columnas del mosaico",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=DEFAULT_ROWS,
        help="numero de filas del mosaico",
    )
    parser.add_argument(
        "--tile-width",
        type=int,
        default=DEFAULT_TILE_WIDTH,
        help="ancho de cada imagen dentro del mosaico",
    )
    parser.add_argument(
        "--gap",
        type=int,
        default=DEFAULT_GAP,
        help="padding blanco entre imagenes",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help="semilla reproducible",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.columns <= 0 or args.rows <= 0:
        raise ValueError("columns y rows deben ser > 0")

    if args.tile_width <= 0:
        raise ValueError("tile-width debe ser > 0")

    if args.gap < 0:
        raise ValueError("gap no puede ser negativo")

    with args.ann_path.open("r", encoding="utf-8") as annotation_file:
        coco = json.load(annotation_file)

    images = list(coco["images"])
    annotations_by_image = group_annotations_by_image(coco["annotations"])

    num_tiles = args.columns * args.rows
    if len(images) < num_tiles:
        raise ValueError("no hay suficientes imagenes para el mosaico pedido")

    rng = random.Random(args.seed)
    selected_images = rng.sample(images, num_tiles)

    sample_width = int(selected_images[0]["width"])
    sample_height = int(selected_images[0]["height"])
    tile_height = max(1, round(args.tile_width * sample_height / sample_width))

    clean_mosaic = build_mosaic(
        image_records=selected_images,
        annotations_by_image=annotations_by_image,
        image_dir=args.image_dir,
        columns=args.columns,
        rows=args.rows,
        tile_width=args.tile_width,
        tile_height=tile_height,
        gap=args.gap,
        draw_overlay=False,
    )

    annotated_mosaic = build_mosaic(
        image_records=selected_images,
        annotations_by_image=annotations_by_image,
        image_dir=args.image_dir,
        columns=args.columns,
        rows=args.rows,
        tile_width=args.tile_width,
        tile_height=tile_height,
        gap=args.gap,
        draw_overlay=True,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)

    stem = f"dataset_random_mosaic_{args.rows}x{args.columns}_seed_{args.seed}"
    clean_path = args.output_dir / f"{stem}_clean.png"
    annotated_path = args.output_dir / f"{stem}_annotated.png"
    selection_path = args.output_dir / f"{stem}_selection.json"

    clean_mosaic.save(clean_path, format="PNG")
    annotated_mosaic.save(annotated_path, format="PNG")

    selection_payload = {
        "seed": args.seed,
        "rows": args.rows,
        "columns": args.columns,
        "tile_width": args.tile_width,
        "tile_height": tile_height,
        "gap": args.gap,
        "images": [
            {
                "image_id": int(image_record["id"]),
                "file_name": Path(str(image_record["file_name"])).name,
                "width": int(image_record["width"]),
                "height": int(image_record["height"]),
                "num_annotations": len(
                    annotations_by_image.get(int(image_record["id"]), [])
                ),
            }
            for image_record in selected_images
        ],
    }
    selection_path.write_text(
        json.dumps(selection_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[mosaic] limpio:    {clean_path}")
    print(f"[mosaic] anotado:   {annotated_path}")
    print(f"[mosaic] selección: {selection_path}")


def group_annotations_by_image(
    annotations: list[dict],
) -> dict[int, list[dict]]:
    grouped: dict[int, list[dict]] = defaultdict(list)

    for annotation in annotations:
        grouped[int(annotation["image_id"])].append(annotation)

    return dict(grouped)


def build_mosaic(
    *,
    image_records: list[dict],
    annotations_by_image: dict[int, list[dict]],
    image_dir: Path,
    columns: int,
    rows: int,
    tile_width: int,
    tile_height: int,
    gap: int,
    draw_overlay: bool,
) -> Image.Image:
    mosaic_width = columns * tile_width + (columns + 1) * gap
    mosaic_height = rows * tile_height + (rows + 1) * gap

    canvas = Image.new("RGB", (mosaic_width, mosaic_height), (255, 255, 255))

    for index, image_record in enumerate(image_records):
        row = index // columns
        col = index % columns

        x = gap + col * (tile_width + gap)
        y = gap + row * (tile_height + gap)

        tile = render_tile(
            image_record=image_record,
            annotations=annotations_by_image.get(int(image_record["id"]), []),
            image_dir=image_dir,
            tile_width=tile_width,
            tile_height=tile_height,
            draw_overlay=draw_overlay,
        )
        canvas.paste(tile, (x, y))

    return canvas


def render_tile(
    *,
    image_record: dict,
    annotations: list[dict],
    image_dir: Path,
    tile_width: int,
    tile_height: int,
    draw_overlay: bool,
) -> Image.Image:
    image_path = image_dir / Path(str(image_record["file_name"])).name

    with Image.open(image_path) as opened_image:
        image = opened_image.convert("RGB")

    resized_image = image.resize((tile_width, tile_height), Image.Resampling.LANCZOS)

    if not draw_overlay:
        return resized_image

    scale_x = tile_width / float(image.width)
    scale_y = tile_height / float(image.height)

    return draw_annotations(
        base_image=resized_image,
        annotations=annotations,
        scale_x=scale_x,
        scale_y=scale_y,
    )


def draw_annotations(
    *,
    base_image: Image.Image,
    annotations: list[dict],
    scale_x: float,
    scale_y: float,
) -> Image.Image:
    composed = base_image.convert("RGBA")
    overlay = Image.new("RGBA", composed.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay, "RGBA")
    line_draw = ImageDraw.Draw(composed, "RGBA")

    for annotation in annotations:
        category_id = int(annotation["category_id"])
        color = CATEGORY_COLORS.get(category_id, (255, 255, 255))

        segmentation = annotation.get("segmentation") or []
        if isinstance(segmentation, list):
            for polygon in segmentation:
                if not polygon or len(polygon) < 6:
                    continue

                points = []
                for raw_x, raw_y in zip(polygon[0::2], polygon[1::2]):
                    points.append(
                        (
                            float(raw_x) * scale_x,
                            float(raw_y) * scale_y,
                        )
                    )

                overlay_draw.polygon(
                    points,
                    fill=(*color, 92),
                    outline=(*color, 220),
                )

        bbox = annotation.get("bbox")
        if isinstance(bbox, list) and len(bbox) == 4:
            x, y, width, height = bbox
            x1 = float(x) * scale_x
            y1 = float(y) * scale_y
            x2 = float(x + width) * scale_x
            y2 = float(y + height) * scale_y
            line_draw.rectangle(
                (x1, y1, x2, y2),
                outline=(*color, 255),
                width=2,
            )

    return Image.alpha_composite(composed, overlay).convert("RGB")


if __name__ == "__main__":
    main()
