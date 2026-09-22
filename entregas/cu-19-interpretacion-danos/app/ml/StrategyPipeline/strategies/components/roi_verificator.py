from dataclasses import dataclass, field
from typing import Any
from PIL import Image

import numpy as np

from ml.StrategyPipeline.schemas import InstancePrediction
from ml.StrategyPipeline.strategies.base import StrategyContractError
from ml.StrategyPipeline.strategies.components.clip_tip_adapter import (
    ClipTipAdapterRoiVerifier,
    RoiVerifierConfig,
)
from ml.StrategyPipeline.strategies.components.sam3_backend import (
    PromptSpec,
    PromptValue,
    normalize_prompt_specs,
)


@dataclass(frozen=True)
class RoiCandidate:
    # propuesta de una strategy ya colocada en coordenadas de la imagen original
    # todavía puede ser un objeto sano parecido, por eso se verifica después
    category_id: int
    score: float
    mask: np.ndarray
    bbox: tuple[float, float, float, float]
    area: float
    metadata: dict[str, Any] = field(default_factory=dict)


class RoiVerificationManager:
    # puente entre cualquier strategy y CLIP + tip-adapter
    # la strategy propone ROIs y este manager decide cuáles pasan como clase positiva
    def __init__(
        self,
        *,
        enabled: bool,
        category_map: dict[int, str],
        verifier_configs: list[RoiVerifierConfig] | None,
        device: str | None = None,
    ) -> None:
        self.enabled = enabled
        self.verifiers_by_category: dict[int, ClipTipAdapterRoiVerifier] = {}

        # si está desactivado no se carga CLIP ni se valida ninguna config
        if not self.enabled:
            return

        if not verifier_configs:
            raise StrategyContractError(
                "enable_roi_verification está activado pero no se proveyeron roi_verifier_configs."
            )

        for config in verifier_configs:
            # cada config debe apuntar a una categoría real del problema
            if config.target_category_id not in category_map:
                raise StrategyContractError(
                    "roi_verifier_configs contiene un target_category_id que no existe en category_map: "
                    f"category_id={config.target_category_id}"
                )

            # dos verificadores para la misma categoría se pisarían entre sí
            if config.target_category_id in self.verifiers_by_category:
                raise StrategyContractError(
                    "roi_verifier_configs contiene múltiples configuraciones para la misma category_id: "
                    f"category_id={config.target_category_id}"
                )

            # las propuestas de sam3 también quedan limitadas a un único prompt de texto por clase
            if len(config.proposal_prompts) != 1:
                raise StrategyContractError(
                    "Cada roi_verifier_config debe tener exactamente un proposal_prompt. "
                    "Si quieres combinar texto y señales visuales, usa tip-adapter o prompts hybrid."
                )

            # aquí se carga CLIP y el cache key-value de esa categoría
            self.verifiers_by_category[config.target_category_id] = ClipTipAdapterRoiVerifier(
                config=config,
                device=device,
            )

    def has_verifier(self, category_id: int) -> bool:
        # indica si una categoría debe pasar por CLIP + tip-adapter
        return category_id in self.verifiers_by_category

    def get_prompts_for_category(
        self,
        *,
        category_id: int,
        category_name: str,
        prompt_map: dict[int, PromptValue],
    ) -> list[PromptSpec]:
        # esta función ya no devuelve str sino prompts estructurados listos para el backend
        # si hay verifier, SAM3 busca el objeto genérico y CLIP decide si está dañado
        verifier = self.verifiers_by_category.get(category_id)

        if verifier is not None:
            # para proponer rois seguimos usando prompts genéricos de texto
            return [PromptSpec.text_prompt(verifier.config.proposal_prompts[0])]

        # si no hay verifier, resolvemos el prompt tal y como lo definió la strategy
        return normalize_prompt_specs(
            prompt_map.get(category_id),
            fallback_text=category_name,
        )


    def verify_candidates(
        self,
        *,
        image: Image.Image,
        candidates_by_category: dict[int, list[RoiCandidate]],
    ) -> list[InstancePrediction]:
        # convierte candidatos verificados en predicciones finales del pipeline
        predictions: list[InstancePrediction] = []

        for category_id, candidates in candidates_by_category.items():
            verifier = self.verifiers_by_category.get(category_id)

            if verifier is None:
                raise StrategyContractError(
                    "se recibieron candidatos para una categoría sin verifier: "
                    f"category_id={category_id}"
                )

            if not candidates:
                continue

            # primero las mejores propuestas de SAM3 para no mandar demasiados crops a CLIP
            selected_candidates = sorted(
                candidates,
                key=lambda candidate: candidate.score,
                reverse=True,
            )
            selected_candidates = selected_candidates[
                : verifier.config.max_proposals_per_image
            ]

            # cada crop conserva algo de contexto alrededor de la máscara
            crops = [
                self._crop_mask_roi(
                    image=image,
                    mask=candidate.mask,
                    padding_frac=verifier.config.crop_padding_frac,
                )
                for candidate in selected_candidates
            ]

            verification_results = verifier.verify_batch(crops)

            # si CLIP dice negative, el candidato se descarta y no llega al evaluator
            for candidate, verification in zip(
                selected_candidates,
                verification_results,
            ):
                if not verification.is_positive:
                    continue

                predictions.append(
                    InstancePrediction(
                        category_id=candidate.category_id,
                        score=float(candidate.score * verification.positive_score),
                        mask=candidate.mask,
                        bbox=candidate.bbox,
                        area=candidate.area,
                        metadata={
                            **candidate.metadata,
                            # score original de SAM3 antes de combinarlo con el verificador
                            "sam3_score": float(candidate.score),
                            # probabilidad final de la clase positiva según CLIP + tip-adapter
                            "tip_adapter_score": float(verification.positive_score),
                            "tip_adapter_negative_score": float(
                                verification.negative_score
                            ),
                            "tip_adapter_predicted_label": verification.predicted_label,
                            "tip_adapter_positive_logit": float(
                                verification.positive_logit
                            ),
                            "tip_adapter_negative_logit": float(
                                verification.negative_logit
                            ),
                        },
                    )
                )

        return predictions

    def _crop_mask_roi(
        self,
        *,
        image: Image.Image,
        mask: np.ndarray,
        padding_frac: float,
    ) -> Image.Image:
        # recorta la roi usando la caja de la máscara y añade margen para CLIP
        x_min, y_min, width, height = self._mask_to_bbox(mask)

        if width <= 0 or height <= 0:
            raise StrategyContractError("no se puede recortar una roi con máscara vacía.")

        pad_x = width * padding_frac
        pad_y = height * padding_frac

        # PIL usa x2/y2 como borde exclusivo, por eso se usa x_min + width
        x1 = max(0, int(np.floor(x_min - pad_x)))
        y1 = max(0, int(np.floor(y_min - pad_y)))
        x2 = min(image.width, int(np.ceil(x_min + width + pad_x)))
        y2 = min(image.height, int(np.ceil(y_min + height + pad_y)))

        if x2 <= x1 or y2 <= y1:
            raise StrategyContractError(
                f"crop inválido para roi: x1={x1}, y1={y1}, x2={x2}, y2={y2}"
            )

        return image.crop((x1, y1, x2, y2))

    def _mask_to_bbox(
        self,
        mask: np.ndarray,
    ) -> tuple[float, float, float, float]:
        # calcula la caja mínima que contiene todos los píxeles activos
        ys, xs = np.where(mask)

        if len(xs) == 0:
            return (0.0, 0.0, 0.0, 0.0)

        x_min = float(xs.min())
        y_min = float(ys.min())
        x_max = float(xs.max())
        y_max = float(ys.max())

        width = x_max - x_min + 1.0
        height = y_max - y_min + 1.0

        return (x_min, y_min, width, height)
