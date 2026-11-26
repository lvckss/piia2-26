import { z } from "zod";

export const splitValues = ["train", "val", "test"] as const;
export const damageCategoryValues = [
  "dent",
  "scratch",
  "crack",
  "glass shatter",
  "lamp broken",
  "tire flat",
] as const;

export const shootingAngleValues = [
  "front",
  "rear",
  "side",
  "inside",
  "NaN",
] as const;

const queryArray = <T extends z.ZodTypeAny>(itemSchema: T) =>
  z.preprocess((value) => {
    if (value == null || value === "") return [];
    return Array.isArray(value) ? value : [value];
  }, z.array(itemSchema));

export const coverageValues = ["ambos", "todo", "parcial"] as const;

export type Split = (typeof splitValues)[number];
export type DamageCategory = (typeof damageCategoryValues)[number];
export type ShootingAngle = (typeof shootingAngleValues)[number];
export type CoverageFilter = (typeof coverageValues)[number];

export const imagesFiltersSchema = z.object({
  cursor: z.coerce.number().int().positive().optional(),
  limit: z.coerce.number().int().min(1).max(120).default(60),

  split: queryArray(z.enum(["train", "val", "test"])).default([]),

  damageCategories: queryArray(
    z.enum([
      "dent",
      "scratch",
      "crack",
      "glass shatter",
      "lamp broken",
      "tire flat",
    ])
  ).default([]),

  minInstances: z.coerce.number().int().min(0).default(0),
  maxInstances: z.coerce.number().int().min(0).default(10),
  minCategories: z.coerce.number().int().min(0).default(0),
  maxCategories: z.coerce.number().int().min(0).default(6),

  complete: z.enum(["ambos", "todo", "parcial"]).default("ambos"),

  shootingAngle: queryArray(
    z.enum(["front", "inside", "rear", "side", "NaN"])
  ).default([]),

  vehicleColor: queryArray(z.string()).default([]),

  minArea: z.coerce.number().min(0).default(0),
  maxArea: z.coerce.number().max(100).default(100),
});

export type ImagesFiltersInput = z.input<typeof imagesFiltersSchema>;
export type ImagesFilters = z.output<typeof imagesFiltersSchema>;

export function normalizeImagesFilters(
  rawFilters: ImagesFiltersInput = {}
): ImagesFilters {
  return imagesFiltersSchema.parse(rawFilters);
}