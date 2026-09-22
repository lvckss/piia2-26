import sql from '../bd/bd';
import { type ImageWithLabels, ImageWithLabelsSchema } from '../models/Image';
import { type ImageWithInstances, ImageWithInstancesSchema } from '../models/ImageWithInstances';

type Split = "train" | "val" | "test";
type DamageCategory =
    | "dent"
    | "scratch"
    | "crack"
    | "glass shatter"
    | "lamp broken"
    | "tire flat";

type ShootingAngle = "front" | "rear" | "side" | "inside" | "NaN";
type CoverageFilter = "ambos" | "todo" | "parcial";

export type ImagesFilters = {
    limit: number;
    cursor?: number | null;

    split?: Split[];
    damageCategories?: DamageCategory[];

    minInstances?: number | null;
    maxInstances?: number | null;

    minCategories?: number | null;
    maxCategories?: number | null;

    minArea?: number | null;
    maxArea?: number | null;

    complete?: CoverageFilter;

    shootingAngle?: ShootingAngle[];
    vehicleColor?: string[];
};

export type ImagesVirtual = {
    items: ImageWithLabels[];
    nextCursor: number | null;
};

export const getImagesPage = async (
    rawFilters: ImagesFilters
): Promise<ImagesVirtual> => {
    const limit = rawFilters.limit;
    const cursor = rawFilters.cursor ?? null;

    const split = rawFilters.split ?? [];
    const damageCategories = rawFilters.damageCategories ?? [];
    const shootingAngle = rawFilters.shootingAngle ?? [];
    const vehicleColor = rawFilters.vehicleColor ?? [];

    const minInstances = rawFilters.minInstances ?? null;
    const maxInstances = rawFilters.maxInstances ?? null;
    const minCategories = rawFilters.minCategories ?? null;
    const maxCategories = rawFilters.maxCategories ?? null;
    const minArea = rawFilters.minArea ?? null;
    const maxArea = rawFilters.maxArea ?? null;

    const complete = rawFilters.complete ?? "ambos";

    const hasInstanceFilters =
        damageCategories.length > 0 ||
        minArea != null ||
        maxArea != null;

    const rows = await sql`
        WITH paged_images AS (
            SELECT i.*
            FROM imagenes i
            WHERE
                (${split.length > 0 ? sql`i.split IN ${sql(split)}` : sql`TRUE`})
                AND (${minInstances != null ? sql`i.numero_instancias >= ${minInstances}` : sql`TRUE`})
                AND (${maxInstances != null ? sql`i.numero_instancias <= ${maxInstances}` : sql`TRUE`})
                AND (${minCategories != null ? sql`i.numero_categorias >= ${minCategories}` : sql`TRUE`})
                AND (${maxCategories != null ? sql`i.numero_categorias <= ${maxCategories}` : sql`TRUE`})

                AND (${
                    complete === "todo"
                        ? sql`i.cobertura IN ('complete', 'completa', 'full')`
                        : complete === "parcial"
                            ? sql`COALESCE(i.cobertura, '') NOT IN ('complete', 'completa', 'full')`
                            : sql`TRUE`
                })

                AND (${shootingAngle.length > 0 ? sql`i.angulo_fotografia IN ${sql(shootingAngle)}` : sql`TRUE`})
                AND (${vehicleColor.length > 0 ? sql`i.color_vehiculo IN ${sql(vehicleColor)}` : sql`TRUE`})

                AND (${
                    hasInstanceFilters
                        ? sql`
                            EXISTS (
                                SELECT 1
                                FROM instancias ins
                                JOIN etiquetas e
                                    ON e.id = ins.categoria_id
                                WHERE ins.imagen_id = i.id
                                  ${damageCategories.length > 0 ? sql`AND e.nombre IN ${sql(damageCategories)}` : sql``}
                                  ${minArea != null ? sql`AND ins.area_pct >= ${minArea}` : sql``}
                                  ${maxArea != null ? sql`AND ins.area_pct <= ${maxArea}` : sql``}
                            )
                        `
                        : sql`TRUE`
                })

                AND (${cursor != null ? sql`i.id > ${cursor}` : sql`TRUE`})
            ORDER BY i.id ASC
            LIMIT ${limit + 1}
        )
        SELECT
            pi.*,
            lbl.labels
        FROM paged_images pi
        LEFT JOIN LATERAL (
            SELECT COALESCE(
                array_agg(x.nombre ORDER BY x.nombre),
                ARRAY[]::text[]
            ) AS labels
            FROM (
                SELECT DISTINCT e.nombre
                FROM instancias ins
                JOIN etiquetas e
                    ON e.id = ins.categoria_id
                WHERE ins.imagen_id = pi.id
            ) AS x
        ) AS lbl ON TRUE
        ORDER BY pi.id ASC
    `;

    const parsedRows = rows.map((row: any) => ImageWithLabelsSchema.parse(row));

    const hasMore = parsedRows.length > limit;
    const items = hasMore ? parsedRows.slice(0, limit) : parsedRows;
    const lastItem = items.at(-1);

    return {
        items,
        nextCursor: hasMore && lastItem?.id != null ? lastItem.id : null,
    };
};

export const getImageByID = async (
  id: number
): Promise<ImageWithInstances | null> => {
  const rows = await sql`
    SELECT
      i.*,

      COALESCE(lbl.labels, ARRAY[]::text[]) AS labels,

      COALESCE(inst.instances, '[]'::json) AS instances

    FROM imagenes i

    LEFT JOIN LATERAL (
      SELECT COALESCE(
        array_agg(x.nombre ORDER BY x.nombre),
        ARRAY[]::text[]
      ) AS labels
      FROM (
        SELECT DISTINCT e.nombre
        FROM instancias ins
        JOIN etiquetas e
          ON e.id = ins.categoria_id
        WHERE ins.imagen_id = i.id
      ) AS x
    ) AS lbl ON TRUE

    LEFT JOIN LATERAL (
      SELECT json_agg(
        json_build_object(
          'id', ins.id,
          'categoria_id', ins.categoria_id,
          'categoria_nombre', e.nombre,
          'segmentacion', ins.segmentacion,
          'area', ins.area,
          'area_pct', ins.area_pct,
          'bbox_x', ins.bbox_x,
          'bbox_y', ins.bbox_y,
          'bbox_width', ins.bbox_width,
          'bbox_height', ins.bbox_height
        )
        ORDER BY ins.id
      ) AS instances
      FROM instancias ins
      JOIN etiquetas e
        ON e.id = ins.categoria_id
      WHERE ins.imagen_id = i.id
    ) AS inst ON TRUE

    WHERE i.id = ${id}
    LIMIT 1
  `;

  if (rows.length === 0) return null;

  return ImageWithInstancesSchema.parse(rows[0]);
};