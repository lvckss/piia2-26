from __future__ import annotations

import torch

from ml.api.core.settings import settings
from ml.api.services.predictor import VehicleDamagePredictor
from ml.StrategyPipeline.strategies.base import StrategyModule
from ml.StrategyPipeline.strategies.baseline import BaselineStrategy
from ml.StrategyPipeline.strategies.geom_ensemble import GeometricEnsembleStrategy
from ml.StrategyPipeline.strategies.sahi import SahiStrategy
from ml.StrategyPipeline.strategies.components.clip_tip_adapter import (
    RoiVerifierConfig,
    simple_roi_verifier_config,
)


def build_predictor() -> VehicleDamagePredictor:
    # si el modelo no existe, preferimos romper en startup y no en la primera request.
    if not settings.model_path.exists():
        raise FileNotFoundError(
            f"No existe el modelo SAM3 en: {settings.model_path}"
        )

    roi_verifier_configs = _build_roi_verifier_configs()
    strategy = _build_strategy(roi_verifier_configs=roi_verifier_configs)

    # la api trabaja contra este wrapper y no contra la strategy en crudo.
    return VehicleDamagePredictor(strategy=strategy)


def _build_strategy(
    *,
    roi_verifier_configs: list[RoiVerifierConfig] | None,
) -> StrategyModule:
    # parámetros comunes a todas las strategies.
    common_kwargs = {
        "model_path": str(settings.model_path),
        "category_map": settings.category_map,
        "prompt_map": settings.prompt_map,
        "score_threshold": settings.score_threshold,
        "mask_threshold": settings.mask_threshold,
        "device": settings.device,
        "enable_roi_verification": settings.enable_roi_verification,
        "roi_verifier_configs": roi_verifier_configs,
    }

    # elegimos la implementación concreta según settings.
    if settings.strategy_name == "baseline":
        return BaselineStrategy(
            **common_kwargs,
            prompt_batch_size=settings.prompt_batch_size,
        )

    if settings.strategy_name == "sahi":
        return SahiStrategy(
            **common_kwargs,
        )

    if settings.strategy_name == "geometric_ensemble":
        return GeometricEnsembleStrategy(
            **common_kwargs,
        )

    raise ValueError(
        f"Estrategia no soportada: {settings.strategy_name!r}"
    )


def shutdown_predictor(predictor: VehicleDamagePredictor) -> None:
    # por ahora el predictor no abre recursos extra, pero dejamos el hook listo.
    predictor.close()

    # si hay cuda, liberamos la caché para apagar limpio.
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _build_roi_verifier_configs() -> list[RoiVerifierConfig] | None:
    # si no queremos tip-adapter, devolvemos none y listo.
    if not settings.enable_roi_verification:
        return None

    configs: list[RoiVerifierConfig] = []

    # añadimos verificación para rueda pinchada solo si el cache está en disco.
    if settings.flat_tire_cache_path.exists():
        configs.append(
            simple_roi_verifier_config(
                target_category_id=6,
                proposal_prompt="a visible car tire",
                cache_path=str(settings.flat_tire_cache_path),
                positive_label="flat car tire",
                negative_label="healthy car tire",
            )
        )

    # añadimos verificación para faro roto solo si el cache está en disco.
    if settings.broken_lamp_cache_path.exists():
        configs.append(
            simple_roi_verifier_config(
                target_category_id=5,
                proposal_prompt="a visible car headlamp or tail lamp",
                cache_path=str(settings.broken_lamp_cache_path),
                positive_label="broken car lamp",
                negative_label="healthy car lamp",
            )
        )

    # si no se pudo construir ninguna config, devolvemos none.
    return configs or None
