from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from ml.api.core.settings import settings


# router mínimo para observabilidad y debug.
router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request) -> dict[str, Any]:
    # el predictor vive en app.state porque se carga al arrancar la api.
    predictor = getattr(request.app.state, "predictor", None)

    return {
        "status": "ok",
        "app_name": settings.app_name,
        "strategy_name": (
            predictor.strategy_name
            if predictor is not None
            else settings.strategy_name
        ),
        "model_path": str(settings.model_path),
        "model_loaded": predictor is not None,
        "roi_verification_enabled": settings.enable_roi_verification,
    }
