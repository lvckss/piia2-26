type Sam3InferInput = {
  imagePath: string;
  prompt: string;
  scoreThreshold?: number;
  maskThreshold?: number;
};

export async function inferWithSam3(input: Sam3InferInput) {
  const res = await fetch("http://127.0.0.1:8001/infer", {
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

  return await res.json();
}