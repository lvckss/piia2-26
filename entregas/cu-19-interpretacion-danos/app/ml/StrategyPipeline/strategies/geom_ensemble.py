from __future__ import annotations

import numpy as np
import torch
from PIL import Image

from ml.StrategyPipeline.schemas import ImageSample, InstancePrediction
from ml.StrategyPipeline.strategies.base import StrategyContractError, StrategyModule
from ml.StrategyPipeline.strategies.components.clip_tip_adapter import RoiVerifierConfig
from ml.StrategyPipeline.strategies.components.roi_verificator import (
    RoiCandidate,
    RoiVerificationManager,
)
from ml.StrategyPipeline.strategies.components.sam3_backend import (
    GeometricConsensusPolicy,
    GeometricEnsembleConfig,
    PromptSpec,
    PromptValue,
    Sam3Backend,
)


class GeometricEnsembleStrategy(StrategyModule):
    def __init__(
        self,
        model_path: str,
        category_map: dict[int, str],
        prompt_map: dict[int, PromptValue] | None = None,
        score_threshold: float = 0.3,
        mask_threshold: float = 0.5,
        num_perturbations: int = 5,
        perturbation_scale: float = 0.05,
        consensus_threshold: float = 0.6,
        min_valid_perturbations: int = 2,
        min_detection_rate: float = 0.40,
        include_seed_box: bool = True,
        consensus_policy: GeometricConsensusPolicy = "valid_plus_detection_rate",
        device: str | None = None,
        random_seed: int | None = None,
        enable_roi_verification: bool = False,
        roi_verifier_configs: list[RoiVerifierConfig] | None = None,
    ) -> None:
        strategy_name = (
            "geometric_ensemble_prompt_roi_verified"
            if enable_roi_verification
            else "geometric_ensemble_prompt"
        )

        super().__init__(
            strategy_name=strategy_name,
            category_map=category_map,
        )

        if not 0.0 <= score_threshold <= 1.0:
            raise StrategyContractError("score_threshold debe estar en [0, 1].")

        if not 0.0 <= mask_threshold <= 1.0:
            raise StrategyContractError("mask_threshold debe estar en [0, 1].")

        self.prompt_map = dict(prompt_map or category_map)
        self.score_threshold = score_threshold
        self.mask_threshold = mask_threshold
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        # si activamos tip-adapter, el flujo es igual que en baseline: sam3 propone y clip decide positivo o negativo
        self.roi_verification = RoiVerificationManager(
            enabled=enable_roi_verification,
            category_map=category_map,
            verifier_configs=roi_verifier_configs,
            device=self.device,
        )

        # la strategy no implementa el ensemble a mano: delega toda la parte sam3 al backend
        self.sam3_backend = Sam3Backend(
            model_path=model_path,
            score_threshold=score_threshold,
            mask_threshold=mask_threshold,
            device=self.device,
            geometric_ensemble_config=GeometricEnsembleConfig(
                num_perturbations=num_perturbations,
                perturbation_scale=perturbation_scale,
                consensus_threshold=consensus_threshold,
                min_valid_perturbations=min_valid_perturbations,
                min_detection_rate=min_detection_rate,
                include_seed_box=include_seed_box,
                consensus_policy=consensus_policy,
                random_seed=random_seed,
            ),
        )

        # mantener compatibilidad con notebooks y explainability actuales
        self.model = self.sam3_backend.model
        self.processor = self.sam3_backend.processor

    def set_score_threshold(self, score_threshold: float) -> None:
        self.score_threshold = score_threshold
        self.sam3_backend.set_score_threshold(score_threshold)

    def _predict_instances(self, sample: ImageSample) -> list[InstancePrediction]:
        image_np = self._load_image_if_needed(sample)
        image = Image.fromarray(image_np)

        predictions: list[InstancePrediction] = []
        roi_candidates_by_category: dict[int, list[RoiCandidate]] = {}

        prompt_items: list[tuple[int, PromptSpec]] = []
        for category_id, category_name in sorted(self.category_map.items()):
            # si una categoría usa verifier, aquí ya sustituimos su prompt normal por el prompt genérico de proposal
            prompts = self.roi_verification.get_prompts_for_category(
                category_id=category_id,
                category_name=category_name,
                prompt_map=self.prompt_map,
            )

            for prompt_spec in prompts:
                prompt_items.append((category_id, prompt_spec))

        if not prompt_items:
            return []

        # aquí el backend ya decide seed generation, refinamiento geométrico y consenso final
        batch_outputs = self.sam3_backend.predict_prompt_specs(
            image=image,
            prompt_specs=[prompt_spec for _, prompt_spec in prompt_items],
        )

        for (category_id, _), detections in zip(prompt_items, batch_outputs):
            for detection in detections:
                mask = np.asarray(detection.mask, dtype=bool)
                if mask.shape != (sample.height, sample.width):
                    raise StrategyContractError(
                        f"Máscara inválida para image_id={sample.image_id}, "
                        f"category_id={category_id}: shape={mask.shape}"
                    )

                if not mask.any():
                    continue

                bbox = self._mask_to_bbox(mask)
                area = float(mask.sum())

                metadata = {
                    **detection.metadata,
                    # grad-cam sigue funcionando si la ruta interna del backend sigue siendo una variante transformers_text
                    "explainer_backend": (
                        "sam3"
                        if str(detection.metadata.get("sam3_backend", "")).startswith(
                            "transformers_text"
                        )
                        else detection.metadata.get("sam3_backend")
                    ),
                    "sam3_prompt": detection.metadata.get("sam3_prompt"),
                    "source": "full_image",
                    "source_bbox": (0, 0, sample.width, sample.height),
                }

                if self.roi_verification.has_verifier(category_id):
                    # si la categoría usa tip-adapter, primero guardamos la roi refinada por ensemble como candidata
                    roi_candidates_by_category.setdefault(category_id, []).append(
                        RoiCandidate(
                            category_id=category_id,
                            score=float(detection.score),
                            mask=mask,
                            bbox=bbox,
                            area=area,
                            metadata=metadata,
                        )
                    )
                    continue

                predictions.append(
                    InstancePrediction(
                        category_id=category_id,
                        score=float(detection.score),
                        mask=mask,
                        bbox=bbox,
                        area=area,
                        metadata=metadata,
                    )
                )

        predictions.extend(
            self.roi_verification.verify_candidates(
                image=image,
                candidates_by_category=roi_candidates_by_category,
            )
        )

        return predictions

    def _mask_to_bbox(
        self,
        mask: np.ndarray,
    ) -> tuple[float, float, float, float]:
        # la strategy sigue entregando bbox xywh al contrato general del pipeline
        ys, xs = np.where(mask)

        if len(xs) == 0:
            return (0.0, 0.0, 0.0, 0.0)

        x_min = float(xs.min())
        y_min = float(ys.min())
        x_max = float(xs.max())
        y_max = float(ys.max())

        return (
            x_min,
            y_min,
            x_max - x_min + 1.0,
            y_max - y_min + 1.0,
        )
