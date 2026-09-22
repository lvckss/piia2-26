from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from PIL import UnidentifiedImageError

from ml.api.core.settings import settings
from ml.api.schemas.response import DamageAssessmentResponse
from ml.api.services.response_mapper import map_strategy_result_to_response
from ml.api.services.sample_builder import (
    build_image_sample,
    load_upload_as_rgb_image,
)
from ml.api.services.visualization import build_visualization_payload


# aquí vive el endpoint principal de inferencia.
router = APIRouter(tags=["damage-assessment"])


@router.post(
    "/damage-assessment",
    response_model=DamageAssessmentResponse,
)
async def damage_assessment(
    request: Request,
    file: UploadFile = File(...),
    include_visualization: bool | None = Query(
        default=None,
        description="Si es true, devuelve también la imagen anotada en base64.",
    ),
) -> DamageAssessmentResponse:
    # recuperamos el predictor ya cargado en startup.
    predictor = getattr(request.app.state, "predictor", None)
    if predictor is None:
        raise HTTPException(
            status_code=503,
            detail="El predictor todavía no está cargado.",
        )

    # si viene content-type y no parece imagen, rechazamos rápido.
    if file.content_type is not None and not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=415,
            detail="El fichero enviado no es una imagen soportada.",
        )

    # leemos todo el fichero en memoria porque la inferencia necesita la imagen completa.
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=400,
            detail="La imagen está vacía.",
        )

    try:
        # pasamos los bytes a una imagen rgb normalizada.
        image = load_upload_as_rgb_image(file_bytes)
    except UnidentifiedImageError as exc:
        raise HTTPException(
            status_code=400,
            detail="No se pudo decodificar la imagen enviada.",
        ) from exc

    # convertimos la imagen subida al schema que entiende el pipeline.
    sample = build_image_sample(
        image=image,
        filename=file.filename,
    )

    try:
        # aquí ocurre la inferencia real contra la strategy cargada.
        result = predictor.predict(sample)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Falló la inferencia de daño: {exc}",
        ) from exc

    # traducimos StrategyResult al json público de la api.
    assessment_items = map_strategy_result_to_response(
        result=result,
        category_map=predictor.category_map,
    )

    # si el caller no decide nada, usamos el default global.
    effective_include_visualization = (
        settings.include_visualization_by_default
        if include_visualization is None
        else include_visualization
    )

    visualization = None
    if effective_include_visualization:
        # la visualización es una ayuda de debug o demo, no el dato principal.
        visualization = build_visualization_payload(
            image=image,
            result=result,
            category_map=predictor.category_map,
            image_format=settings.visualization_format,
        )

    # devolvemos predicciones estructuradas y, opcionalmente, la imagen anotada.
    return DamageAssessmentResponse(
        vehicle_damage_assessment=assessment_items,
        visualization=visualization,
    )
