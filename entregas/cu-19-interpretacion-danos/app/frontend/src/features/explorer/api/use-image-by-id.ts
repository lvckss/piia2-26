import { useQuery } from "@tanstack/react-query";
import { getImageByID } from "./get-image-by-id";

export function useImageByID(id: number | null, enabled = true) {
  return useQuery({
    queryKey: ["image", id],
    queryFn: () => getImageByID(id as number),
    enabled: enabled && id != null && id > 0,
    staleTime: 60_000,
  });
}