import { Hono } from "hono";
import { z } from "zod";
import { inferWithSam3 } from "../services/sam3-client";
// importa aquí tu acceso a BD
// import { db } from "../db";

const sam3Route = new Hono();

const InferSchema = z.object({
  imageId: z.number(),
  prompt: z.string().min(1),
  scoreThreshold: z.number().min(0).max(1).optional(),
  maskThreshold: z.number().min(0).max(1).optional(),
});

sam3Route.post("/infer", async (c) => {
  const body = await c.req.json();
  const parsed = InferSchema.safeParse(body);

  if (!parsed.success) {
    return c.json({ error: parsed.error.flatten() }, 400);
  }

  const { imageId, prompt, scoreThreshold, maskThreshold } = parsed.data;

  // Ejemplo: saca image_path desde Postgres
  // const image = await db.query.images.findFirst({ where: eq(images.id, imageId) });

  const image = {
    id: imageId,
    file_path: `/ruta/al/dataset/${imageId}.jpg`,
  };

  if (!image) {
    return c.json({ error: "Image not found" }, 404);
  }

  try {
    const result = await inferWithSam3({
      imagePath: image.file_path,
      prompt,
      scoreThreshold,
      maskThreshold,
    });

    return c.json({
      imageId,
      prompt,
      result,
    });
  } catch (error) {
    console.error(error);
    return c.json({ error: "SAM3 inference failed" }, 500);
  }
});

export default sam3Route;