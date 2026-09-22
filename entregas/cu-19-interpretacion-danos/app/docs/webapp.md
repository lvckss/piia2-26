# webapp

## qué cubre

este documento describe la parte de aplicación web del repo:

- `frontend/`
- `server/`
- cómo se conectan entre sí
- qué rutas están activas hoy

## visión general

la webapp está separada en dos capas:

```text
frontend/  -> cliente react + vite
server/    -> backend bun + hono
```

el backend sirve tanto la api como los assets estáticos del frontend ya compilado.

## frontend

### stack

el frontend usa:

- react 19
- vite 8
- typescript
- tanstack router
- tanstack query
- tailwindcss 4
- radix ui / utilidades de ui

referencias:

- [frontend/package.json](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/frontend/package.json)
- [frontend/src/main.tsx](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/frontend/src/main.tsx)

### estructura visible

las piezas principales son:

```text
frontend/src/
  components/
    ui/
  features/
    explorer/
  lib/
    api.ts
  routes/
    __root.tsx
    index.tsx
    explorer.tsx
```

### rutas del frontend

las rutas visibles hoy son:

- `/`
- `/explorer`

referencias:

- [__root.tsx](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/frontend/src/routes/__root.tsx)
- [index.tsx](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/frontend/src/routes/index.tsx)
- [explorer.tsx](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/frontend/src/routes/explorer.tsx)

### estado funcional actual

la pantalla más trabajada es `explorer`.

ahí la ui se divide en:

- sidebar de filtros
- grid de imágenes
- diálogo de detalle de imagen

referencias:

- [FilterSidebar.tsx](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/frontend/src/features/explorer/FilterSidebar.tsx)
- [ExplorerImageGrid.tsx](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/frontend/src/features/explorer/ExplorerImageGrid.tsx)
- [ExplorerImageDialog.tsx](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/frontend/src/features/explorer/ExplorerImageDialog.tsx)

la ruta `/` sigue siendo básicamente un placeholder.

### cliente http

el frontend usa el cliente tipado de hono:

- [api.ts](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/frontend/src/lib/api.ts)

la llamada sale contra `/api/...`, no directamente contra fastapi.

## backend

### stack

el backend usa:

- bun
- hono
- zod
- postgres

referencias:

- [package.json](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/package.json)
- [server/index.ts](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/server/index.ts)
- [server/app.ts](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/server/app.ts)

### arranque

desde la raíz `app/`:

```bash
bun install
bun run dev
```

el punto de entrada real es:

- [server/index.ts](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/server/index.ts)

este archivo hace `Bun.serve(...)` con `app.fetch`.

### rutas activas

en [server/app.ts](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/server/app.ts) hoy están montadas estas rutas bajo `/api`:

- `/api/images`
- `/api/instances`

además:

- sirve `bd/clean_data` como `/dataset/*`
- sirve `frontend/dist` como aplicación estática

### rutas de imágenes

`/api/images` soporta:

- `GET /api/images`
- `GET /api/images/:id`

referencia:

- [imagesRoute.ts](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/server/routes/imagesRoute.ts)

### rutas de instancias

`/api/instances` soporta:

- `GET /api/instances`

referencia:

- [instancesRoute.ts](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/server/routes/instancesRoute.ts)

## relación frontend-backend

el flujo principal de la webapp es:

```text
usuario
  -> frontend react
  -> cliente hono tipado
  -> server bun/hono
  -> bd / datos
  -> respuesta json
```

## relación con ml

hay código en `server/` pensado para hablar con un servicio SAM3 externo:

- [sam3Service.ts](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/server/services/sam3Service.ts)
- [sam3-client.ts](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/server/services/sam3-client.ts)
- [sam3Route.ts](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/server/routes/sam3Route.ts)

pero hay dos matices importantes:

- `sam3Route` no está montada hoy en [server/app.ts](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/server/app.ts)
- parte de ese código espera un contrato `/infer` que no coincide con la fastapi nueva de `ml/api`, que expone `/v1/damage-assessment`

o sea:

- la integración webapp -> fastapi no está cerrada end-to-end todavía
- existe trabajo previo y puente parcial, pero no está cableado del todo en el árbol de rutas activo

## estructura útil de `server/`

```text
server/
  app.ts
  index.ts
  routes/
  controllers/
  services/
  models/
  bd/
```

lectura rápida:

- `routes/` define endpoints hono
- `controllers/` concentra lógica de caso de uso
- `services/` integra sistemas externos o secundarios
- `models/` define esquemas y tipos
- `bd/` inicializa acceso a base de datos

## cómo leer la webapp hoy

si quieres entender la aplicación de forma pragmática:

1. empieza en [server/app.ts](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/server/app.ts)
2. sigue por [frontend/src/routes/__root.tsx](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/frontend/src/routes/__root.tsx)
3. mira [frontend/src/routes/explorer.tsx](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/frontend/src/routes/explorer.tsx)
4. luego entra en `features/explorer`

## estado actual resumido

- la parte más madura de la webapp es el explorador de dataset
- el backend activo expone imágenes e instancias
- la integración con la fastapi de ml existe como intención y código auxiliar, pero no como flujo montado completo en producción dentro de `server/app.ts`
