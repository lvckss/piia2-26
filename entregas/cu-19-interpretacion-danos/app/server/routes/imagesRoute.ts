import { Hono } from "hono";
import { z } from "zod";
import { zValidator } from "@hono/zod-validator";
import { imagesFiltersSchema } from '../models/ImageFilters';
import { getImagesPage, getImageByID } from "../controllers/imageController";

const imageIdParamSchema = z.object({
  id: z.coerce.number().int().positive(),
});

export const imagesRoute = new Hono()
    .get("/", zValidator("query", imagesFiltersSchema), async (c) => {
        const filters = c.req.valid("query");
        const result = await getImagesPage(filters);
        return c.json(result, 200);
    })
    .get("/:id", zValidator("param", imageIdParamSchema), async (c) => {
        const { id } = c.req.valid("param");

        const image = await getImageByID(id);

        if (!image) {
            return c.json({ error: "Imagen no encontrada" }, 404);
        }

        return c.json(image, 200);
    });