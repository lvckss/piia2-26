from PIL import Image

from ml.StrategyPipeline.schemas import ImageSample, InstancePrediction
from ml.StrategyPipeline.strategies.base import StrategyModule, StrategyContractError

from ml.StrategyPipeline.strategies.components.clip_tip_adapter import RoiVerifierConfig
from ml.StrategyPipeline.strategies.components.roi_verificator import (
    RoiCandidate,
    RoiVerificationManager,
)
from ml.StrategyPipeline.strategies.components.sam3_backend import (
    PromptSpec,
    PromptValue,
    Sam3Backend,
)

import numpy as np
import torch

class BaselineStrategy(StrategyModule):
    def __init__(
        self,
        model_path: str,
        category_map: dict[int, str],
        prompt_map: dict[int, PromptValue] | None = None,
        score_threshold: float = 0.3,
        mask_threshold: float = 0.5,
        prompt_batch_size: int = 1, # permite procesar múltiples prompts en paralelo
        device: str | None = None,
        enable_roi_verification: bool = False, # si se activa, se usa un módulo adicional para verificar la coherencia de las regiones propuestas por SAM con los ejemplos del cache de tip-adapter
        roi_verifier_configs: list[RoiVerifierConfig] | None = None,
    ) -> None:

        strategy_name = (
            "baseline_prompt_roi_verified"
            if enable_roi_verification
            else "baseline_prompt"
        )

        super().__init__(
            strategy_name=strategy_name,
            category_map=category_map,
        )

        # si no se provee un prompt_map específico, se usa el category_map como fuente de prompts (es decir, el nombre de la categoría se usa como prompt)
        self.prompt_map = dict(prompt_map or category_map)
        self.score_threshold = score_threshold
        self.mask_threshold = mask_threshold

        # elige gpu si está disponible para acelerar la inferencia
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        if prompt_batch_size <= 0:
            raise StrategyContractError("prompt_batch_size debe ser >= 1.")

        self.prompt_batch_size = prompt_batch_size

        # configura el manager de verificación de ROIs, que se encarga de usar CLIP + tip-adapter para decidir si las regiones propuestas por SAM3
        # realmente corresponden a la clase positiva o son falsos positivos que se parecen a objetos sanos
        self.roi_verification = RoiVerificationManager(
            enabled=enable_roi_verification,
            category_map=category_map,
            verifier_configs=roi_verifier_configs,
            device=self.device,
        )

        # toda la lógica de cómo se habla con sam3 vive aquí y no en la strategy
        self.sam3_backend = Sam3Backend(
            model_path=model_path,
            score_threshold=score_threshold,
            mask_threshold=mask_threshold,
            device=self.device,
        )

        # mantener compatibilidad con explainability y notebooks actuales
        self.model = self.sam3_backend.model
        self.processor = self.sam3_backend.processor

    def set_score_threshold(self, score_threshold: float) -> None:
        # helper cómodo para notebooks: actualiza el threshold sin recargar sam3
        self.score_threshold = score_threshold
        self.sam3_backend.set_score_threshold(score_threshold)

    def _predict_instances(self, sample: ImageSample) -> list[InstancePrediction]:
        # garantiza que la estrategia trabaje con una imagen rgb en memoria
        image_np = self._load_image_if_needed(sample)
        image = Image.fromarray(image_np)

        predictions: list[InstancePrediction] = []
        roi_candidates_by_category: dict[int, list[RoiCandidate]] = {}

        prompt_items: list[tuple[int, PromptSpec]] = []
        for category_id, category_name in sorted(self.category_map.items()):
            prompts = self.roi_verification.get_prompts_for_category(
                category_id=category_id,
                category_name=category_name,
                prompt_map=self.prompt_map,
            )

            for prompt in prompts:
                prompt_items.append((category_id, prompt))

        # procesa los prompts en lotes para aprovechar mejor la gpu
        for start in range(0, len(prompt_items), self.prompt_batch_size):
            chunk = prompt_items[start : start + self.prompt_batch_size]
            # el backend decide si cada prompt va por texto normal o por exemplars
            batch_outputs = self.sam3_backend.predict_prompt_specs(
                image=image,
                prompt_specs=[prompt_spec for _, prompt_spec in chunk],
            )

            for (category_id, prompt_spec), detections in zip(chunk, batch_outputs):
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

                    # mantenemos la metadata del backend y añadimos el contexto del baseline
                    metadata = {
                        **detection.metadata,
                        "explainer_backend": (
                            "sam3"
                            if detection.metadata.get("sam3_backend") == "transformers_text"
                            else detection.metadata.get("sam3_backend")
                        ),
                        "sam3_prompt": detection.metadata.get("sam3_prompt"),
                        "source": "full_image",
                        "source_bbox": (0, 0, sample.width, sample.height),
                    }

                    if self.roi_verification.has_verifier(category_id):
                        # si la categoría usa tip-adapter, primero guardamos candidatos y luego verificamos
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

                    # si no hay verificación extra, esta ya es la predicción final
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
        # localiza todos los píxeles activos de la instancia (1 y no 0) para calcular la caja mínima que los contiene
        ys, xs = np.where(mask)

        # si la máscara está vacía, devuelve una caja nula
        if len(xs) == 0:
            return (0.0, 0.0, 0.0, 0.0)

        # calcula la caja mínima que contiene la máscara
        x_min = float(xs.min())
        y_min = float(ys.min())
        x_max = float(xs.max())
        y_max = float(ys.max())

        width = x_max - x_min + 1.0
        height = y_max - y_min + 1.0

        return (x_min, y_min, width, height)
