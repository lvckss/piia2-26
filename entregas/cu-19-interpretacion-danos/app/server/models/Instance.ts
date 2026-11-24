import { z } from "zod";

const PolygonSchema = z
  .array(z.number())
  .min(6) // mínimo 3 puntos
  .refine((coords) => coords.length % 2 === 0, {
    message: "Las coordenadas de la segmentación tienen que ir en pares (x,y)",
  });

export const InstanceSchema = z.object({
  id: z.number().int().positive().optional(),
  //imagen_id: z.number().int(),
  categoria_id: z.number().int(),

  // COCO segmentation: lista de polígonos
  // [[x1,y1,x2,y2,...], [...]]
  segmentacion: z.array(PolygonSchema),

  area: z.number().nonnegative(),
  area_pct: z.coerce.number().min(0).max(100),

  bbox_x: z.number(),
  bbox_y: z.number(),
  bbox_width: z.number().nonnegative(),
  bbox_height: z.number().nonnegative(),
});

export const createInstanceSchema = InstanceSchema.omit({ id: true });
export type PostInstance = z.infer<typeof createInstanceSchema>;
export type Instance = z.infer<typeof InstanceSchema>;