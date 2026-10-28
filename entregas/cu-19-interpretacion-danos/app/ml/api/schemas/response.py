from __future__ import annotations

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    # bbox en formato xywh porque es el formato que usa el pipeline.
    x: float
    y: float
    width: float
    height: float


class DamageAssessmentItem(BaseModel):
    # cada elemento representa un daño detectado en la imagen.
    damage_class: str
    bbox: BoundingBox
    area: float
    score: float


class VisualizationPayload(BaseModel):
    # esta imagen anotada se devuelve en base64 para que viaje dentro del json.
    mime_type: str
    image_base64: str


class DamageAssessmentResponse(BaseModel):
    # una imagen puede contener cero, uno o varios daños.
    vehicle_damage_assessment: list[DamageAssessmentItem] = Field(
        default_factory=list
    )
    # este campo es opcional porque infla bastante la respuesta.
    visualization: VisualizationPayload | None = None
