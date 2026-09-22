import os
import psycopg
from psycopg.types.json import Jsonb
from typing import Any


def insert_etiquetas(conn: psycopg.Connection, etiquetas: dict[int, dict]) -> dict[str, int]:
    """
    Inserta etiquetas por nombre y devuelve un mapa:
    {
        "dent": 1,
        "scratch": 2,
        ...
    }
    """
    rows = [(row["nombre"],) for row in etiquetas.values()]

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO etiquetas (nombre)
            VALUES (%s)
            ON CONFLICT (nombre) DO NOTHING
            """,
            rows,
        )

        cur.execute("SELECT id, nombre FROM etiquetas")
        nombre_to_id = {nombre: id_ for id_, nombre in cur.fetchall()}

    return nombre_to_id


def insert_imagenes(conn: psycopg.Connection, imagenes: dict[int, dict]) -> dict[int, int]:
    """
    Inserta imágenes y devuelve un mapa:
    {
        id_externo: id_interno,
        ...
    }
    """
    rows = []
    for row in imagenes.values():
        rows.append(
            (
                row["id_externo"],
                row["file_name"],
                row["split"],
                row["ruta_imagen"],
                row["ruta_thumbnail"],
                row["width"],
                row["height"],
                row["file_size_kb"],
                row["numero_instancias"],
                row["numero_categorias"],
                row["angulo_fotografia"],
                row["cobertura"],
                row["color_vehiculo"],
                row["observaciones"],
            )
        )

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO imagenes (
                id_externo,
                file_name,
                split,
                ruta_imagen,
                ruta_thumbnail,
                width,
                height,
                file_size_kb,
                numero_instancias,
                numero_categorias,
                angulo_fotografia,
                cobertura,
                color_vehiculo,
                observaciones
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (id_externo) DO UPDATE SET
                file_name = EXCLUDED.file_name,
                split = EXCLUDED.split,
                ruta_imagen = EXCLUDED.ruta_imagen,
                ruta_thumbnail = EXCLUDED.ruta_thumbnail,
                width = EXCLUDED.width,
                height = EXCLUDED.height,
                file_size_kb = EXCLUDED.file_size_kb,
                numero_instancias = EXCLUDED.numero_instancias,
                numero_categorias = EXCLUDED.numero_categorias,
                angulo_fotografia = EXCLUDED.angulo_fotografia,
                cobertura = EXCLUDED.cobertura,
                color_vehiculo = EXCLUDED.color_vehiculo,
                observaciones = EXCLUDED.observaciones
            """,
            rows,
        )

        cur.execute("SELECT id, id_externo FROM imagenes")
        external_to_internal = {id_externo: id_ for id_, id_externo in cur.fetchall()}

    return external_to_internal


def compute_area_pct(area: float, width: int, height: int) -> float:
    if width <= 0 or height <= 0:
        raise ValueError(f"Dimensiones inválidas para calcular area_pct: width={width}, height={height}")

    return (float(area) / float(width * height)) * 100.0


def insert_instancias(
    conn: psycopg.Connection,
    instancias: list[dict],
    etiquetas_by_external_id: dict[int, dict],
    imagenes_by_external_id: dict[int, dict],
    nombre_to_categoria_id: dict[str, int],
    image_external_to_internal_id: dict[int, int],
) -> None:
    """
    Inserta instancias resolviendo:
    - imagen_id_externo -> imagen_id interno
    - categoria_id_externo -> nombre -> categoria_id interno
    - calcula area_pct = area / (width * height) * 100
    """
    rows = []

    for row in instancias:
        imagen_id_externo = row["imagen_id_externo"]

        imagen_id_interno = image_external_to_internal_id.get(imagen_id_externo)
        if imagen_id_interno is None:
            raise ValueError(
                f"No existe imagen interna para imagen_id_externo={imagen_id_externo}"
            )

        imagen_info = imagenes_by_external_id.get(imagen_id_externo)
        if imagen_info is None:
            raise ValueError(
                f"No existe metadata de imagen para imagen_id_externo={imagen_id_externo}"
            )

        width = imagen_info["width"]
        height = imagen_info["height"]
        area_pct = compute_area_pct(row["area"], width, height)

        categoria_externa = row["categoria_id_externo"]
        categoria_info = etiquetas_by_external_id.get(categoria_externa)
        if categoria_info is None:
            raise ValueError(
                f"No existe categoría externa {categoria_externa} en etiquetas_by_external_id"
            )

        categoria_nombre = categoria_info["nombre"]
        categoria_id_interno = nombre_to_categoria_id.get(categoria_nombre)
        if categoria_id_interno is None:
            raise ValueError(
                f"No existe categoría interna para nombre={categoria_nombre}"
            )

        rows.append(
            (
                imagen_id_interno,
                categoria_id_interno,
                Jsonb(row["segmentacion"]),
                row["area"],
                area_pct,
                row["bbox_x"],
                row["bbox_y"],
                row["bbox_width"],
                row["bbox_height"],
            )
        )

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO instancias (
                imagen_id,
                categoria_id,
                segmentacion,
                area,
                area_pct,
                bbox_x,
                bbox_y,
                bbox_width,
                bbox_height
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            rows,
        )


def import_dataset_to_postgres(dataset: dict[str, Any], database_url: str) -> None:
    """
    Importa todo el dataset a PostgreSQL.
    """
    with psycopg.connect(database_url) as conn:
        # Una transacción explícita: si algo falla, rollback completo.
        with conn.transaction():
            nombre_to_categoria_id = insert_etiquetas(conn, dataset["etiquetas"])
            image_external_to_internal_id = insert_imagenes(conn, dataset["imagenes"])
            insert_instancias(
                conn=conn,
                instancias=dataset["instancias"],
                etiquetas_by_external_id=dataset["etiquetas"],
                imagenes_by_external_id=dataset["imagenes"],
                nombre_to_categoria_id=nombre_to_categoria_id,
                image_external_to_internal_id=image_external_to_internal_id,
            )