from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ml.api.core.settings import settings
from ml.api.core.startup import build_predictor, shutdown_predictor
from ml.api.routes.damage_assessment import router as damage_assessment_router
from ml.api.routes.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # cargamos el predictor una sola vez al arrancar la api.
    app.state.predictor = build_predictor()
    try:
        yield
    finally:
        # liberamos recursos al cerrar el proceso.
        shutdown_predictor(app.state.predictor)


def create_app() -> FastAPI:
    # aquí montamos la app y registramos middleware y rutas.
    app = FastAPI(
        title="Vehicle Damage Assessment API",
        version="0.1.0",
        description="API de inferencia para detectar daños en vehículos",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # health va sin prefijo porque sirve para saber rápido si el servicio está vivo.
    app.include_router(health_router)
    # las rutas funcionales de la api van bajo /v1.
    app.include_router(damage_assessment_router, prefix="/v1")

    return app


# este es el objeto que uvicorn importa al arrancar.
app = create_app()
