from ml.StrategyPipeline.schemas import ImageSample, InstancePrediction
from ml.StrategyPipeline.strategies.base import StrategyModule, StrategyContractError
from ml.StrategyPipeline.strategies.components.clip_tip_adapter import RoiVerifierConfig
from ml.StrategyPipeline.strategies.components.roi_verificator import (
    RoiCandidate,
    RoiVerificationManager,
)
from ml.StrategyPipeline.strategies.components.sam3_backend import (
    PromptValue,
    Sam3Backend,
)

from PIL import Image

import torch
import numpy as np

class SahiStrategy(StrategyModule):
    def __init__(
        self,
        model_path: str,
        category_map: dict[int, str],
        prompt_map: dict[int, PromptValue] | None = None,
        score_threshold: float = 0.8,
        mask_threshold: float = 0.5,
        slice_size: int = 512,
        overlap_ratio: float = 0.2,
        nms_iou_threshold: float = 0.5,
        nms_ios_threshold: float = 0.8,
        batch_size: int = 8,
        include_full_image: bool = True,
        device: str | None = None,
        enable_roi_verification: bool = False,
        roi_verifier_configs: list[RoiVerifierConfig] | None = None,
    ) -> None:
        strategy_name = (
            "sahi_prompt_roi_verified"
            if enable_roi_verification
            else "sahi_prompt"
        )

        super().__init__(
            strategy_name=strategy_name,
            category_map=category_map,
        )

        if slice_size <= 0:
            raise StrategyContractError("slice_size debe ser > 0.")

        if not 0.0 <= overlap_ratio < 1.0:
            raise StrategyContractError("overlap_ratio debe estar en [0, 1).")

        if not 0.0 <= nms_iou_threshold <= 1.0:
            raise StrategyContractError("nms_iou_threshold debe estar en [0, 1].")

        if not 0.0 <= nms_ios_threshold <= 1.0:
            raise StrategyContractError("nms_ios_threshold debe estar en [0, 1].")

        if batch_size <= 0:
            raise StrategyContractError("batch_size debe ser > 0.")

        if not 0.0 <= score_threshold <= 1.0:
            raise StrategyContractError("score_threshold debe estar en [0, 1].")

        if not 0.0 <= mask_threshold <= 1.0:
            raise StrategyContractError("mask_threshold debe estar en [0, 1].")

        self.prompt_map = dict(prompt_map or category_map)
        self.score_threshold = score_threshold
        self.mask_threshold = mask_threshold
        self.slice_size = slice_size
        self.overlap_ratio = overlap_ratio
        self.nms_iou_threshold = nms_iou_threshold
        self.nms_ios_threshold = nms_ios_threshold
        self.batch_size = batch_size
        self.include_full_image = include_full_image

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        self.roi_verification = RoiVerificationManager(
            enabled=enable_roi_verification,
            category_map=category_map,
            verifier_configs=roi_verifier_configs,
            device=self.device,
        )

        # sam3 queda encapsulado en un backend reutilizable por cualquier strategy
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
        image_np = self._load_image_if_needed(sample)
        image = Image.fromarray(image_np)

        # generar recortes
        slices = self._generate_slices(sample.width, sample.height)

        predictions: list[InstancePrediction] = []
        roi_candidates_by_category: dict[int, list[RoiCandidate]] = {}

        for category_id, category_name in sorted(self.category_map.items()):
            prompts = self.roi_verification.get_prompts_for_category(
                category_id=category_id,
                category_name=category_name,
                prompt_map=self.prompt_map,
            )
            category_predictions: list[InstancePrediction] = []

            for prompt in prompts:
                # primero inferimos sobre la imagen completa para así detectar objetos grandes que podrían no caber en los recortes pequeños
                if self.include_full_image:
                    # mismo prompt, una sola imagen completa
                    full_detections = self.sam3_backend.predict_images_for_prompt(
                        images=[image],
                        prompt_spec=prompt,
                    )[0]

                    for detection in full_detections:
                        mask = np.asarray(detection.mask, dtype=bool)

                        if mask.shape != (sample.height, sample.width):
                            raise StrategyContractError(
                                "Máscara full-image inválida: "
                                f"shape={mask.shape}, expected={(sample.height, sample.width)}"
                            )

                        if not mask.any():
                            continue

                        bbox = self._mask_to_bbox(mask)
                        area = float(mask.sum())

                        category_predictions.append(
                            InstancePrediction(
                                category_id=category_id,
                                score=float(detection.score),
                                mask=mask,
                                bbox=bbox,
                                area=area,
                                metadata={
                                    **detection.metadata,
                                    "explainer_backend": (
                                        "sam3"
                                        if detection.metadata.get("sam3_backend") == "transformers_text"
                                        else detection.metadata.get("sam3_backend")
                                    ),
                                    "sam3_prompt": detection.metadata.get("sam3_prompt"),
                                    "source": "full_image",
                                    "source_bbox": (0, 0, sample.width, sample.height),

                                    # mantener compatibilidad actual
                                    "sahi_source": "full_image",
                                },
                            )
                        )

                # procesar los slices en batches para aprovechar la GPU
                for slice_batch in self._chunk_list(slices, self.batch_size):
                    # recortamos imagenes para el batch
                    batch_images = [
                        image.crop((x_min, y_min, x_max, y_max))
                        for x_min, y_min, x_max, y_max in slice_batch
                    ]

                    # mismo prompt, muchos recortes
                    batch_detections = self.sam3_backend.predict_images_for_prompt(
                        images=batch_images,
                        prompt_spec=prompt,
                    )

                    for (x_min, y_min, x_max, y_max), detections in zip(
                        slice_batch,
                        batch_detections,
                    ):
                        expected_shape = (y_max - y_min, x_max - x_min)

                        for detection in detections:
                            mask_slice = np.asarray(detection.mask, dtype=bool)

                            if mask_slice.shape != expected_shape:
                                raise StrategyContractError(
                                    "Máscara de slice inválida: "
                                    f"shape={mask_slice.shape}, expected={expected_shape}"
                                )

                            if not mask_slice.any():
                                continue

                            global_mask = np.zeros(
                                (sample.height, sample.width),
                                dtype=bool,
                            )
                            global_mask[y_min:y_max, x_min:x_max] = mask_slice

                            bbox = self._mask_to_bbox(global_mask)
                            area = float(global_mask.sum())

                            # la strategy sigue siendo responsable de remapear el slice al lienzo global
                            category_predictions.append(
                                InstancePrediction(
                                    category_id=category_id,
                                    score=float(detection.score),
                                    mask=global_mask,
                                    bbox=bbox,
                                    area=area,
                                    metadata={
                                        **detection.metadata,
                                        "explainer_backend": (
                                            "sam3"
                                            if detection.metadata.get("sam3_backend") == "transformers_text"
                                            else detection.metadata.get("sam3_backend")
                                        ),
                                        "sam3_prompt": detection.metadata.get("sam3_prompt"),
                                        "source": "slice",
                                        "source_bbox": (x_min, y_min, x_max, y_max),

                                        # mantener compatibilidad actual
                                        "sahi_source": "slice",
                                        "slice_bbox": (x_min, y_min, x_max, y_max),
                                    }
                                )
                            )

            category_predictions = self._apply_nms(
                category_predictions,
                iou_threshold=self.nms_iou_threshold,
                ios_threshold=self.nms_ios_threshold,
            )

            if self.roi_verification.has_verifier(category_id):
                # si hay tip-adapter, pasamos solo las mejores propuestas ya fusionadas por sahi
                roi_candidates_by_category[category_id] = [
                    RoiCandidate(
                        category_id=prediction.category_id,
                        score=float(prediction.score),
                        mask=prediction.mask,
                        bbox=prediction.bbox,
                        area=float(prediction.area),
                        metadata=dict(prediction.metadata),
                    )
                    for prediction in category_predictions
                ]
            else:
                # si no, estas son ya las predicciones finales de la categoría
                predictions.extend(category_predictions)

        predictions.extend(
            self.roi_verification.verify_candidates(
                image=image,
                candidates_by_category=roi_candidates_by_category,
            )
        )

        return predictions


    # genera las cajas de los crops
    # si la imagen mide 1200x800, slice_size=512 y overlap_ratio=0.2, crea recortes de 512x512 que se solapan entre sí
    def _generate_slices(
        self,
        width: int,
        height: int,
    ) -> list[tuple[int, int, int, int]]: # x_min, y_min, x_max, y_max
        slices = []
        # creamos el solape entre recortes para no perder objetos que estén en los bordes
        stride = int(self.slice_size * (1.0 - self.overlap_ratio))

        if stride <= 0:
            raise StrategyContractError(
                f"stride inválido: slice_size={self.slice_size}, "
                f"overlap_ratio={self.overlap_ratio}, stride={stride}"
            )

        y = 0
        while y < height:
            y_max = min(y + self.slice_size, height)
            y_min = max(0, y_max - self.slice_size)

            x = 0
            while x < width:
                x_max = min(x + self.slice_size, width)
                x_min = max(0, x_max - self.slice_size)

                slices.append((x_min, y_min, x_max, y_max))

                if x_max == width:
                    break

                x += stride

            if y_max == height:
                break

            y += stride

        return slices

    # divide una lista en grupos de tamaño fijo (excepto el último que puede ser más pequeño)
    # ejemplo:
    # con 20 slices y batch_size=8, devuelve:
    # [
    #     slices[0:8],
    #     slices[8:16],
    #     slices[16:20],
    # ]
    def _chunk_list(self, items: list, chunk_size: int):
        for start in range(0, len(items), chunk_size):
            yield items[start : start + chunk_size]

    # NMS = Non-Maximum Suppression, algoritmo clásico para filtrar detecciones redundantes en tareas de visión computacional
    def _apply_nms(
        self,
        predictions: list[InstancePrediction],
        iou_threshold: float = 0.5,
        ios_threshold: float = 0.8,
    ) -> list[InstancePrediction]:

        sorted_predictions = sorted(
            predictions,
            key=lambda prediction: prediction.score,
            reverse=True,
        )

        keep: list[InstancePrediction] = []

        for prediction in sorted_predictions:
            should_discard = False
            kept_ids_to_remove: set[int] = set()

            for kept_prediction in keep:
                # IoU detecta duplicados cuando las dos máscaras son muy parecidas
                iou = self._mask_iou(
                    prediction.mask,
                    kept_prediction.mask,
                )

                # IoS detecta casos donde una máscara está contenida en otra o es una parte de la otra
                ios = self._mask_ios(
                    prediction.mask,
                    kept_prediction.mask,
                )

                if iou >= iou_threshold:
                    should_discard = True
                    break

                if ios >= ios_threshold:
                    prediction_source = prediction.metadata.get("sahi_source")
                    kept_source = kept_prediction.metadata.get("sahi_source")

                    prediction_is_full = prediction_source == "full_image"
                    kept_is_slice = kept_source == "slice"

                    # si la full-image contiene un slice, la full-image debe ganar aunque tenga algo menos de score
                    if prediction_is_full and kept_is_slice and prediction.area > kept_prediction.area:
                        kept_ids_to_remove.add(id(kept_prediction))
                        continue

                    should_discard = True
                    break

            if should_discard:
                continue

            if kept_ids_to_remove:
                keep = [
                    kept_prediction
                    for kept_prediction in keep
                    if id(kept_prediction) not in kept_ids_to_remove
                ]

            keep.append(prediction)

        return keep

    def _mask_iou(
        self,
        mask_a: np.ndarray,
        mask_b: np.ndarray,
    ) -> float:
        mask_a = np.asarray(mask_a, dtype=bool)
        mask_b = np.asarray(mask_b, dtype=bool)

        intersection = np.logical_and(mask_a, mask_b).sum()
        union = np.logical_or(mask_a, mask_b).sum()

        if union == 0:
            return 0.0

        return float(intersection / union)

    def _mask_ios(
        self,
        mask_a: np.ndarray,
        mask_b: np.ndarray,
    ) -> float:
        mask_a = np.asarray(mask_a, dtype=bool)
        mask_b = np.asarray(mask_b, dtype=bool)

        intersection = np.logical_and(mask_a, mask_b).sum()
        smaller_area = min(mask_a.sum(), mask_b.sum())

        if smaller_area == 0:
            return 0.0

        return float(intersection / smaller_area)

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
