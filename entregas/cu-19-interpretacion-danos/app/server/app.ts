import { Hono } from 'hono';
import { logger } from 'hono/logger';

import { serveStatic } from 'hono/bun';

import { imagesRoute } from './routes/imagesRoute';
import { instancesRoute } from './routes/instancesRoute';

import { resolve } from "node:path";

const app = new Hono()

app.use('*', logger())

const apiRoutes = app.basePath("/api")
    .route("/images", imagesRoute)
    .route("/instances", instancesRoute)

// Exponer bd/clean_data como /dataset/*
const datasetRoot = resolve(import.meta.dir, "../bd/clean_data");

app.use(
  "/dataset/*",
  serveStatic({
    root: datasetRoot,
    rewriteRequestPath: (path) => path.replace(/^\/dataset\/?/, ""),
  })
);

app.get('*', serveStatic({ root: '../frontend/dist' }))
app.get('*', serveStatic({ path: '../frontend/dist/index.html' }))

export default app
export type ApiRoutes = typeof apiRoutes