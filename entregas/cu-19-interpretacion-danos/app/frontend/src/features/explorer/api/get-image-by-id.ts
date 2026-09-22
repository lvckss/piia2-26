import { api } from "@/lib/api";
import type { ImageWithInstances } from "@server/models/ImageWithInstances";

export async function getImageByID(id: number): Promise<ImageWithInstances> {

    const res = await api.images[":id"].$get({
        param: { id: String(id) },
    });

    if (!res.ok) {
        throw new Error("No se pudo obtener la imagen");
    }

    return await res.json();
}