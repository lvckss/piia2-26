# docs

esta carpeta reúne documentación de alto nivel del proyecto.

la idea es tener una referencia más clara que el `README.md` raíz cuando quieras entender rápido cómo está montado el repo y qué partes están realmente activas.

## documentos

- [webapp.md](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/docs/webapp.md): frontend, backend bun/hono, rutas activas y flujo de datos de la aplicación web.
- [api-docker.md](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/docs/api-docker.md): fastapi de `ml/api`, modos de arranque y empaquetado en docker.
- [ml-library.md](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/docs/ml-library.md): librería y utilidades dentro de `ml/`, incluyendo `StrategyPipeline`, evaluación, scripts y artefactos.

## criterio

estos documentos intentan reflejar el estado actual del repo, no solo la intención original.

eso significa:

- se documenta lo que está montado de verdad
- se separa lo activo de lo experimental o legacy
- se enlazan los puntos de entrada reales del código

## punto de partida rápido

si quieres orientarte por capas:

```text
frontend/   -> interfaz react + vite
server/     -> api bun + hono + acceso a bd
ml/         -> pipeline ml, evaluación y fastapi de inferencia
docker/     -> contenedorización actual de la api ml
bd/         -> datos y scripts relacionados con dataset/bd
```

## nota

el [README.md](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/README.md) raíz sigue siendo útil como visión general, pero varios detalles técnicos finos están mejor recogidos aquí.
