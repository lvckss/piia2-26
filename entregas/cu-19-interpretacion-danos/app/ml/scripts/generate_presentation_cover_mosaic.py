from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ANN_PATH = ROOT / "bd" / "rawdata" / "instances_all.json"
DEFAULT_IMAGE_DIR = ROOT / "bd" / "rawdata" / "images"
DEFAULT_OUTPUT_DIR = ROOT / "ml" / "presentation_assets"

DEFAULT_WIDTH = 3840
DEFAULT_HEIGHT = 2160

BACKGROUND_COLOR = (9, 13, 20)
GLOBAL_TINT = (8, 14, 30, 54)
CENTER_BAND = (6, 8, 14, 108)
EDGE_VIGNETTE = (0, 0, 0, 120)

CATEGORY_COLORS = {
    1: (239, 71, 111),   # dent
    2: (255, 209, 102),  # scratch
    3: (6, 214, 160),    # crack
    4: (17, 138, 178),   # glass shatter
    5: (131, 56, 236),   # lamp broken
    6: (138, 201, 38),   # tire flat
}


@dataclass(frozen=True)
class GridSpec:
    columns: int
    rows: int
    cell_width: int
    cell_height: int
    grid_width: int
    grid_height: int
    crop_left: int
    crop_top: int


@dataclass(frozen=True)
class JustifiedPlacement:
    image_record: dict
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class JustifiedLayout:
    placements: list[JustifiedPlacement]
    content_height: int
    row_count: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="genera un mosaico 16:9 con todas las imagenes del dataset y sus anotaciones",
    )
    parser.add_argument(
        "--ann-path",
        type=Path,
        default=DEFAULT_ANN_PATH,
        help="ruta al json de anotaciones en formato coco",
    )
    parser.add_argument(
        "--image-dir",
        type=Path,
        default=DEFAULT_IMAGE_DIR,
        help="directorio donde viven las imagenes originales",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="directorio donde se guardan los fondos generados",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=DEFAULT_WIDTH,
        help="ancho del fondo final",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=DEFAULT_HEIGHT,
        help="alto del fondo final",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260509,
        help="semilla para mezclar el orden de las imagenes manteniendo reproducibilidad",
    )
    parser.add_argument(
        "--margin",
        type=int,
        default=2,
        help="margen interior de cada celda para que se lea el mosaico",
    )
    parser.add_argument(
        "--layout",
        choices=["justified", "grid"],
        default="justified",
        help="tipo de mosaico. justified conserva el aspect ratio completo",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.width <= 0 or args.height <= 0:
        raise ValueError("width y height deben ser > 0")

    if args.margin < 0:
        raise ValueError("margin no puede ser negativo")

    with args.ann_path.open("r", encoding="utf-8") as annotation_file:
        coco = json.load(annotation_file)

    images = coco["images"]
    annotations = coco["annotations"]

    if not images:
        raise ValueError("no hay imagenes en el json de anotaciones")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    annotations_by_image = group_annotations_by_image(annotations)
    image_records = list(images)

    rng = random.Random(args.seed)
    image_records.sort(key=lambda item: int(item["id"]))
    rng.shuffle(image_records)

    if args.layout == "justified":
        raw_output = render_justified_mosaic(
            image_records=image_records,
            annotations_by_image=annotations_by_image,
            image_dir=args.image_dir,
            target_width=args.width,
            target_height=args.height,
            gap=args.margin,
        )
    else:
        raw_output = render_grid_mosaic(
            image_records=image_records,
            annotations_by_image=annotations_by_image,
            image_dir=args.image_dir,
            target_width=args.width,
            target_height=args.height,
            margin=args.margin,
        )

    styled_output = apply_cover_styling(raw_output)

    raw_png_path = (
        args.output_dir
        / f"dataset_mosaic_{args.layout}_raw_{args.width}x{args.height}.png"
    )
    cover_png_path = (
        args.output_dir
        / f"dataset_mosaic_{args.layout}_cover_{args.width}x{args.height}.png"
    )
    cover_jpg_path = (
        args.output_dir
        / f"dataset_mosaic_{args.layout}_cover_{args.width}x{args.height}.jpg"
    )

    raw_output.save(raw_png_path, format="PNG")
    styled_output.save(cover_png_path, format="PNG")
    styled_output.convert("RGB").save(cover_jpg_path, format="JPEG", quality=92)

    print(f"[mosaic] guardado raw:   {raw_png_path}")
    print(f"[mosaic] guardado cover: {cover_png_path}")
    print(f"[mosaic] guardado jpg:   {cover_jpg_path}")


def group_annotations_by_image(
    annotations: list[dict],
) -> dict[int, list[dict]]:
    grouped: dict[int, list[dict]] = defaultdict(list)

    for annotation in annotations:
        grouped[int(annotation["image_id"])].append(annotation)

    return dict(grouped)


def render_justified_mosaic(
    *,
    image_records: list[dict],
    annotations_by_image: dict[int, list[dict]],
    image_dir: Path,
    target_width: int,
    target_height: int,
    gap: int,
) -> Image.Image:
    layout = choose_justified_layout(
        image_records=image_records,
        target_width=target_width,
        target_height=target_height,
        gap=gap,
    )

    canvas = Image.new("RGB", (target_width, target_height), BACKGROUND_COLOR)
    y_offset = max(0, (target_height - layout.content_height) // 2)
    total = len(layout.placements)

    for index, placement in enumerate(layout.placements, start=1):
        if index == 1 or index % 200 == 0 or index == total:
            print(f"[mosaic] procesadas {index}/{total} imagenes")

        tile = render_fit_tile(
            image_record=placement.image_record,
            annotations=annotations_by_image.get(
                int(placement.image_record["id"]),
                [],
            ),
            image_dir=image_dir,
            target_width=placement.width,
            target_height=placement.height,
        )
        canvas.paste(tile, (placement.x, placement.y + y_offset))

    return canvas


def choose_justified_layout(
    *,
    image_records: list[dict],
    target_width: int,
    target_height: int,
    gap: int,
) -> JustifiedLayout:
    low = 8.0
    high = 120.0
    best_layout: JustifiedLayout | None = None

    for _ in range(20):
        mid = (low + high) / 2.0
        layout = build_justified_layout(
            image_records=image_records,
            target_width=target_width,
            base_row_height=mid,
            gap=gap,
        )

        if layout.content_height <= target_height:
            best_layout = layout
            low = mid
        else:
            high = mid

    if best_layout is None:
        best_layout = build_justified_layout(
            image_records=image_records,
            target_width=target_width,
            base_row_height=low,
            gap=gap,
        )

    print(
        "[mosaic] justified "
        f"rows={best_layout.row_count} | "
        f"content_height={best_layout.content_height}px"
    )

    return best_layout


def build_justified_layout(
    *,
    image_records: list[dict],
    target_width: int,
    base_row_height: float,
    gap: int,
) -> JustifiedLayout:
    rows: list[list[dict]] = []
    current_row: list[dict] = []
    current_aspect_sum = 0.0

    for image_record in image_records:
        aspect_ratio = float(image_record["width"]) / float(image_record["height"])

        if not current_row:
            current_row.append(image_record)
            current_aspect_sum = aspect_ratio
            continue

        current_width = current_aspect_sum * base_row_height + gap * (len(current_row) - 1)
        projected_width = (current_aspect_sum + aspect_ratio) * base_row_height + gap * len(current_row)

        if projected_width < target_width:
            current_row.append(image_record)
            current_aspect_sum += aspect_ratio
            continue

        if abs(projected_width - target_width) <= abs(current_width - target_width):
            current_row.append(image_record)
            rows.append(list(current_row))
            current_row = []
            current_aspect_sum = 0.0
            continue

        rows.append(list(current_row))
        current_row = [image_record]
        current_aspect_sum = aspect_ratio

    if current_row:
        rows.append(list(current_row))

    placements: list[JustifiedPlacement] = []
    cursor_y = 0

    for row in rows:
        row_aspects = [
            float(item["width"]) / float(item["height"])
            for item in row
        ]
        row_gap_total = gap * (len(row) - 1)
        usable_row_width = max(1, target_width - row_gap_total)
        row_aspect_sum = sum(row_aspects)
        row_height_float = usable_row_width / row_aspect_sum
        row_height = max(1, int(round(row_height_float)))

        width_floats = [
            usable_row_width * (aspect / row_aspect_sum)
            for aspect in row_aspects
        ]
        widths = [int(math.floor(width)) for width in width_floats]
        missing_pixels = usable_row_width - sum(widths)

        fractional_order = sorted(
            range(len(widths)),
            key=lambda index: width_floats[index] - widths[index],
            reverse=True,
        )

        for index in fractional_order[:missing_pixels]:
            widths[index] += 1

        cursor_x = 0
        for image_record, tile_width in zip(row, widths):
            placements.append(
                JustifiedPlacement(
                    image_record=image_record,
                    x=cursor_x,
                    y=cursor_y,
                    width=max(1, tile_width),
                    height=row_height,
                )
            )
            cursor_x += tile_width + gap

        cursor_y += row_height + gap

    content_height = max(0, cursor_y - gap)

    return JustifiedLayout(
        placements=placements,
        content_height=content_height,
        row_count=len(rows),
    )


def render_grid_mosaic(
    *,
    image_records: list[dict],
    annotations_by_image: dict[int, list[dict]],
    image_dir: Path,
    target_width: int,
    target_height: int,
    margin: int,
) -> Image.Image:
    grid = choose_grid(
        num_items=len(image_records),
        target_width=target_width,
        target_height=target_height,
    )

    canvas = Image.new("RGB", (grid.grid_width, grid.grid_height), BACKGROUND_COLOR)

    total = len(image_records)
    for index, image_record in enumerate(image_records, start=1):
        if index == 1 or index % 200 == 0 or index == total:
            print(f"[mosaic] procesadas {index}/{total} imagenes")

        tile = render_cover_crop_tile(
            image_record=image_record,
            annotations=annotations_by_image.get(int(image_record["id"]), []),
            image_dir=image_dir,
            cell_width=grid.cell_width,
            cell_height=grid.cell_height,
            margin=margin,
        )

        cell_x = ((index - 1) % grid.columns) * grid.cell_width
        cell_y = ((index - 1) // grid.columns) * grid.cell_height
        canvas.paste(tile, (cell_x, cell_y))

    return canvas.crop(
        (
            grid.crop_left,
            grid.crop_top,
            grid.crop_left + target_width,
            grid.crop_top + target_height,
        )
    )


def choose_grid(
    *,
    num_items: int,
    target_width: int,
    target_height: int,
) -> GridSpec:
    best_spec: GridSpec | None = None
    best_score: tuple[float, int, int, float] | None = None

    target_aspect = target_width / target_height
    ideal_columns = math.sqrt(num_items * target_aspect)
    min_columns = max(1, int(ideal_columns * 0.60))
    max_columns = max(min_columns, int(ideal_columns * 1.40) + 1)

    for columns in range(min_columns, max_columns + 1):
        rows = math.ceil(num_items / columns)
        cell_width = math.ceil(target_width / columns)
        cell_height = math.ceil(target_height / rows)

        grid_width = columns * cell_width
        grid_height = rows * cell_height

        if grid_width < target_width or grid_height < target_height:
            continue

        crop_left = max(0, (grid_width - target_width) // 2)
        crop_top = max(0, (grid_height - target_height) // 2)

        cell_ratio = cell_width / cell_height
        cell_area = cell_width * cell_height
        ideal_cell_area = (target_width * target_height) / num_items

        # priorizamos celdas visualmente equilibradas.
        score = (
            abs(cell_ratio - 1.0),
            abs(cell_area - ideal_cell_area),
            (grid_width - target_width) + (grid_height - target_height),
            abs(columns * target_height - rows * target_width),
        )

        spec = GridSpec(
            columns=columns,
            rows=rows,
            cell_width=cell_width,
            cell_height=cell_height,
            grid_width=grid_width,
            grid_height=grid_height,
            crop_left=crop_left,
            crop_top=crop_top,
        )
        if best_score is None or score < best_score:
            best_score = score
            best_spec = spec

    if best_spec is None:
        raise ValueError("no se pudo encontrar una malla valida para el mosaico")

    print(
        "[mosaic] grid "
        f"{best_spec.columns}x{best_spec.rows} | "
        f"cell={best_spec.cell_width}x{best_spec.cell_height} | "
        f"grid={best_spec.grid_width}x{best_spec.grid_height}"
    )

    return best_spec


def render_cover_crop_tile(
    *,
    image_record: dict,
    annotations: list[dict],
    image_dir: Path,
    cell_width: int,
    cell_height: int,
    margin: int,
) -> Image.Image:
    tile = Image.new("RGB", (cell_width, cell_height), BACKGROUND_COLOR)

    inner_width = max(1, cell_width - 2 * margin)
    inner_height = max(1, cell_height - 2 * margin)

    image_path = image_dir / Path(str(image_record["file_name"])).name

    with Image.open(image_path) as opened_image:
        image = opened_image.convert("RGB")

    transform = build_cover_transform(
        src_width=image.width,
        src_height=image.height,
        target_width=inner_width,
        target_height=inner_height,
    )

    fitted_image = image.resize(
        (transform["resized_width"], transform["resized_height"]),
        Image.Resampling.LANCZOS,
    ).crop(
        (
            transform["crop_left"],
            transform["crop_top"],
            transform["crop_left"] + inner_width,
            transform["crop_top"] + inner_height,
        )
    )

    # rebajamos un poco color y brillo para que las anotaciones destaquen mas.
    fitted_image = ImageEnhance.Color(fitted_image).enhance(0.92)
    fitted_image = ImageEnhance.Brightness(fitted_image).enhance(0.88)
    fitted_image = ImageEnhance.Contrast(fitted_image).enhance(1.08)

    annotated_image = draw_annotations(
        base_image=fitted_image,
        annotations=annotations,
        transform=transform,
        target_width=inner_width,
        target_height=inner_height,
    )

    tile.paste(annotated_image, (margin, margin))

    return tile


def render_fit_tile(
    *,
    image_record: dict,
    annotations: list[dict],
    image_dir: Path,
    target_width: int,
    target_height: int,
) -> Image.Image:
    tile = Image.new("RGB", (target_width, target_height), BACKGROUND_COLOR)

    image_path = image_dir / Path(str(image_record["file_name"])).name

    with Image.open(image_path) as opened_image:
        image = opened_image.convert("RGB")

    transform = build_fit_transform(
        src_width=image.width,
        src_height=image.height,
        target_width=target_width,
        target_height=target_height,
    )

    fitted_image = image.resize(
        (transform["resized_width"], transform["resized_height"]),
        Image.Resampling.LANCZOS,
    )

    tile.paste(
        fitted_image,
        (transform["paste_x"], transform["paste_y"]),
    )

    tile = ImageEnhance.Color(tile).enhance(0.92)
    tile = ImageEnhance.Brightness(tile).enhance(0.88)
    tile = ImageEnhance.Contrast(tile).enhance(1.08)

    return draw_annotations(
        base_image=tile,
        annotations=annotations,
        transform=transform,
        target_width=target_width,
        target_height=target_height,
    )


def build_cover_transform(
    *,
    src_width: int,
    src_height: int,
    target_width: int,
    target_height: int,
) -> dict[str, float | int]:
    scale = max(target_width / src_width, target_height / src_height)
    resized_width = max(1, int(round(src_width * scale)))
    resized_height = max(1, int(round(src_height * scale)))

    crop_left = max(0, int(round((resized_width - target_width) / 2)))
    crop_top = max(0, int(round((resized_height - target_height) / 2)))

    return {
        "scale": scale,
        "scale_x": scale,
        "scale_y": scale,
        "resized_width": resized_width,
        "resized_height": resized_height,
        "crop_left": crop_left,
        "crop_top": crop_top,
        "offset_x": -crop_left,
        "offset_y": -crop_top,
    }


def build_fit_transform(
    *,
    src_width: int,
    src_height: int,
    target_width: int,
    target_height: int,
) -> dict[str, float | int]:
    scale = min(target_width / src_width, target_height / src_height)
    resized_width = max(1, int(round(src_width * scale)))
    resized_height = max(1, int(round(src_height * scale)))

    paste_x = max(0, (target_width - resized_width) // 2)
    paste_y = max(0, (target_height - resized_height) // 2)

    return {
        "scale": scale,
        "scale_x": scale,
        "scale_y": scale,
        "resized_width": resized_width,
        "resized_height": resized_height,
        "paste_x": paste_x,
        "paste_y": paste_y,
        "offset_x": paste_x,
        "offset_y": paste_y,
    }


def draw_annotations(
    *,
    base_image: Image.Image,
    annotations: list[dict],
    transform: dict[str, float | int],
    target_width: int,
    target_height: int,
) -> Image.Image:
    composed = base_image.convert("RGBA")
    overlay = Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay, "RGBA")
    line_draw = ImageDraw.Draw(composed, "RGBA")

    scale_x = float(transform["scale_x"])
    scale_y = float(transform["scale_y"])
    offset_x = float(transform["offset_x"])
    offset_y = float(transform["offset_y"])

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
                    point_x = float(raw_x) * scale_x + offset_x
                    point_y = float(raw_y) * scale_y + offset_y
                    points.append((point_x, point_y))

                overlay_draw.polygon(
                    points,
                    fill=(*color, 76),
                    outline=(*color, 196),
                )

        bbox = annotation.get("bbox")
        if isinstance(bbox, list) and len(bbox) == 4:
            x, y, width, height = bbox
            x1 = float(x) * scale_x + offset_x
            y1 = float(y) * scale_y + offset_y
            x2 = float(x + width) * scale_x + offset_x
            y2 = float(y + height) * scale_y + offset_y

            line_draw.rectangle(
                (x1, y1, x2, y2),
                outline=(*color, 208),
                width=1,
            )

    composed = Image.alpha_composite(composed, overlay)
    return composed.convert("RGB")


def apply_cover_styling(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")

    # unificamos la paleta con una dominante azul muy suave.
    tint = Image.new("RGBA", rgba.size, GLOBAL_TINT)
    rgba = Image.alpha_composite(rgba, tint)

    # esta banda central deja una zona mas amable para poner titulo encima.
    band = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    band_draw = ImageDraw.Draw(band, "RGBA")
    width, height = rgba.size
    band_top = int(height * 0.24)
    band_bottom = int(height * 0.76)
    band_draw.rounded_rectangle(
        (int(width * 0.07), band_top, int(width * 0.93), band_bottom),
        radius=int(height * 0.06),
        fill=CENTER_BAND,
    )
    band = band.filter(ImageFilter.GaussianBlur(radius=max(24, height // 28)))
    rgba = Image.alpha_composite(rgba, band)

    # viñeta suave para que los bordes no compitan tanto con el texto.
    vignette_mask = build_vignette_mask(width=width, height=height)
    vignette = Image.new("RGBA", rgba.size, EDGE_VIGNETTE)
    vignette.putalpha(vignette_mask)
    rgba = Image.alpha_composite(rgba, vignette)

    return rgba.convert("RGB")


def build_vignette_mask(*, width: int, height: int) -> Image.Image:
    center = Image.new("L", (int(width * 0.82), int(height * 0.82)), 0)

    mask = Image.new("L", (width, height), 255)
    center_x = (width - center.width) // 2
    center_y = (height - center.height) // 2
    mask.paste(center, (center_x, center_y))
    mask = mask.filter(ImageFilter.GaussianBlur(radius=max(60, width // 20)))

    return mask


if __name__ == "__main__":
    main()
