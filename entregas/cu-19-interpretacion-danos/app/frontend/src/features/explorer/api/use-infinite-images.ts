import { useInfiniteQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { type ImagesFiltersInput, normalizeImagesFilters } from "@server/models/ImageFilters";

export function useInfiniteImages(rawFilters: ImagesFiltersInput = {}) {
  const filters = normalizeImagesFilters(rawFilters);

  return useInfiniteQuery({
    queryKey: ["images", filters],
    queryFn: async ({ pageParam }) => {
      const res = await api.images.$get({
        query: {
          limit: "30",
          ...(pageParam != null ? { cursor: String(pageParam) } : {}),
          ...(filters.split.length ? { split: filters.split } : {}),
          ...(filters.damageCategories.length
            ? { damageCategories: filters.damageCategories }
            : {}),
          ...(filters.minInstances != null
            ? { minInstances: String(filters.minInstances) }
            : {}),
          ...(filters.maxInstances != null
            ? { maxInstances: String(filters.maxInstances) }
            : {}),
          ...(filters.minCategories != null
            ? { minCategories: String(filters.minCategories) }
            : {}),
          ...(filters.maxCategories != null
            ? { maxCategories: String(filters.maxCategories) }
            : {}),
          ...(filters.minArea != null
            ? { minArea: String(filters.minArea) }
            : {}),
          ...(filters.maxArea != null
            ? { maxArea: String(filters.maxArea) }
            : {}),
          ...(filters.complete !== "ambos"
            ? { complete: filters.complete }
            : {}),
          ...(filters.shootingAngle.length
            ? { shootingAngle: filters.shootingAngle }
            : {}),
          ...(filters.vehicleColor.length
            ? { vehicleColor: filters.vehicleColor }
            : {}),
        },
      });

      if (!res.ok) {
        throw new Error("No se pudieron cargar las imágenes");
      }

      return await res.json();
    },
    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
    initialPageParam: null as number | null,
  });
}