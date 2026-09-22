import sql from "../bd/bd";
import {
  type Sam3InferBody,
  type Sam3InferResult,
  sam3InferResultSchema,
} from "../models/Sam3";
import { inferWithSam3Service } from "../services/sam3Service";

export const inferSam3ByImageID = async (
  input: Sam3InferBody
): Promise<Sam3InferResult | null> => {
  const imageId = input.imageId;
  const prompt = input.prompt;
  const scoreThreshold = input.scoreThreshold ?? 0.3;
  const maskThreshold = input.maskThreshold ?? 0.5;

  const rows = await sql`
    SELECT
      i.id,
      i.ruta_imagen
    FROM imagenes i
    WHERE i.id = ${imageId}
    LIMIT 1
  `;

  if (rows.length === 0) return null;

  const image = rows[0];

  const sam3Result = await inferWithSam3Service({
    imagePath: image.ruta_imagen,
    prompt,
    scoreThreshold,
    maskThreshold,
  });

  const predictions = sam3Result.boxes.map((box, index) => ({
    score: sam3Result.scores[index] ?? 0,
    box: [
      box[0] ?? 0,
      box[1] ?? 0,
      box[2] ?? 0,
      box[3] ?? 0,
    ] as [number, number, number, number],
    label: sam3Result.labels?.[index],
    mask: sam3Result.masks?.[index],
  }));

  return sam3InferResultSchema.parse({
    imageId,
    prompt,
    predictions,
  });
};