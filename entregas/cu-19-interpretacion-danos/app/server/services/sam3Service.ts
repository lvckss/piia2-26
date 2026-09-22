import { z } from "zod";

const SAM3_SERVICE_URL = process.env.SAM3_SERVICE_URL ?? "http://127.0.0.1:8001";

// estos tipos son distintos de los de models/Sam3.ts ya que estos son de comunicación entre FastAPI y el backend
// mientras que los otros son de comunicación entre hono y el frontend
type Sam3ServiceInput = {
  imagePath: string;
  prompt: string;
  scoreThreshold?: number;
  maskThreshold?: number;
};

const sam3ServiceResponseSchema = z.object({
  boxes: z.array(z.array(z.number())),
  scores: z.array(z.number()),
  labels: z.array(z.string()).optional(),
  masks: z.array(z.unknown()).optional(),
});

type Sam3ServiceResponse = z.infer<typeof sam3ServiceResponseSchema>;

export const inferWithSam3Service = async (
  input: Sam3ServiceInput
): Promise<Sam3ServiceResponse> => {
  const res = await fetch(`${SAM3_SERVICE_URL}/infer`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      image_path: input.imagePath,
      prompt: input.prompt,
      score_threshold: input.scoreThreshold ?? 0.3,
      mask_threshold: input.maskThreshold ?? 0.5,
    }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`SAM3 service error: ${res.status} ${text}`);
  }

  const data: unknown = await res.json();
  return sam3ServiceResponseSchema.parse(data);
};