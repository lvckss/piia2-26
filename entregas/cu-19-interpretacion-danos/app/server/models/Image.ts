import { z } from "zod";

export const ImageSchema = z.object({
  id: z.number().int().positive(),
  id_externo: z.number().int(),
  file_name: z.string().max(255),
  split: z.enum(["train", "test", "val"]),
  ruta_imagen: z.string(),
  ruta_thumbnail: z.string().nullable().optional(),
  width: z.number().int(),
  height: z.number().int(),
  file_size_kb: z.number().optional().nullable(),
  numero_instancias: z.number().int().default(0),
  numero_categorias: z.number().int().default(0),
  angulo_fotografia: z.string().max(50).optional().nullable(),
  cobertura: z.string().max(50).optional().nullable(),
  color_vehiculo: z.string().max(50).optional().nullable(),
  observaciones: z.string().optional().nullable(),
});

export const ImageWithLabelsSchema = ImageSchema.extend({
    labels: z.array(z.string()).default([]),
});

export const createImageSchema = ImageSchema.omit({ id: true });
export type PostImage = z.infer<typeof createImageSchema>;
export type Image = z.infer<typeof ImageSchema>;
export type ImageWithLabels = z.infer<typeof ImageWithLabelsSchema>;