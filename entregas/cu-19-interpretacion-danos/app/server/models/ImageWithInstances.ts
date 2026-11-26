import { z } from "zod";
import { InstanceSchema } from "./Instance";
import { ImageWithLabelsSchema } from "./Image";

export const InstanceWithCategorySchema = InstanceSchema.extend({
  id: z.number().int().positive(),
  categoria_nombre: z.string(),
});

export const ImageWithInstancesSchema = ImageWithLabelsSchema.extend({
  instances: z.array(InstanceWithCategorySchema).default([]),
});

export type ImageWithInstances = z.infer<typeof ImageWithInstancesSchema>;