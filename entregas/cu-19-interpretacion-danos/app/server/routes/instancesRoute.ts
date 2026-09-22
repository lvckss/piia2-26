import { Hono } from "hono";
import { zValidator } from "@hono/zod-validator";
import { type Instance, InstanceSchema, createInstanceSchema } from '../models/Instance';
import { getInstances } from "../controllers/instanceController";

export const instancesRoute = new Hono()
    .get("/", async (c) => {
        const result = await getInstances();
        return c.json({ images: result })
    })
    /* .get("/:id{[0-9]+}", (c) => {
        const id = Number.parseInt(c.req.param("id"))
        // función de la bd
        const image = fakeImages.find(image => image.id === id)
        if (!image) {
            return c.notFound()
        }
        return c.json({ image })
    }) */