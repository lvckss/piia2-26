from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image
from torch.nn import functional as F

from ml.StrategyPipeline.schemas import ImageEvalRecord, InstancePrediction
from ml.StrategyPipeline.strategies.base import StrategyContractError


@dataclass(frozen=True)
class Sam3GradCamResult:
    heatmap: np.ndarray
    query_index: int
    matched_iou: float
    prompt: str
    source_bbox: tuple[int, int, int, int]


class Sam3GradCamExplainer:
    def __init__(
        self,
        *,
        mask_threshold: float = 0.5,
        eps: float = 1e-8,
    ) -> None:
        self.mask_threshold = mask_threshold
        self.eps = eps

    def explain(
        self,
        *,
        record: ImageEvalRecord,
        strategy: Any,
        prediction: InstancePrediction,
    ) -> Sam3GradCamResult:
        metadata = prediction.metadata

        if metadata.get("explainer_backend") != "sam3":
            raise StrategyContractError(
                "esta predicción no tiene contexto de explicación sam3."
            )

        prompt = metadata.get("sam3_prompt")
        if not prompt:
            raise StrategyContractError("falta sam3_prompt en prediction.metadata.")

        source_bbox = self._get_source_bbox(
            prediction=prediction,
            record=record,
        )

        image = self._load_record_image(record)
        source_image = image.crop(source_bbox)

        prediction_mask = self._prediction_mask_in_source(
            prediction=prediction,
            source_bbox=source_bbox,
        )

        target_layer = self._get_target_layer(strategy)
        activations: torch.Tensor | None = None
        gradients: torch.Tensor | None = None

        def forward_hook(_, __, output):
            nonlocal activations
            activations = self._extract_tensor(output)

        def backward_hook(_, __, grad_output):
            nonlocal gradients
            gradients = self._extract_tensor(grad_output)

        forward_handle = target_layer.register_forward_hook(forward_hook)
        backward_handle = target_layer.register_full_backward_hook(backward_hook)

        was_training = strategy.model.training
        strategy.model.eval()

        try:
            outputs = self._forward_sam3(
                strategy=strategy,
                image=source_image,
                prompt=prompt,
            )

            query_index, matched_iou = self._match_query_index(
                outputs=outputs,
                prediction_mask=prediction_mask,
                source_size=(source_image.height, source_image.width),
                mask_threshold=getattr(strategy, "mask_threshold", self.mask_threshold),
            )

            strategy.model.zero_grad(set_to_none=True)
            target = self._target_score(
                outputs=outputs,
                query_index=query_index,
                prediction_mask=prediction_mask,
            )
            target.backward()

            if activations is None or gradients is None:
                raise StrategyContractError(
                    "no se capturaron activaciones o gradientes para grad-cam."
                )

            source_heatmap = self._build_cam(
                activations=activations,
                gradients=gradients,
                output_size=(source_image.height, source_image.width),
            )

            full_heatmap = self._paste_source_heatmap(
                source_heatmap=source_heatmap,
                record=record,
                source_bbox=source_bbox,
            )

            return Sam3GradCamResult(
                heatmap=full_heatmap,
                query_index=query_index,
                matched_iou=matched_iou,
                prompt=prompt,
                source_bbox=source_bbox,
            )

        finally:
            forward_handle.remove()
            backward_handle.remove()

            if was_training:
                strategy.model.train()

    def _forward_sam3(
        self,
        *,
        strategy: Any,
        image: Image.Image,
        prompt: str,
    ):
        inputs = strategy.processor(
            images=[image],
            text=[prompt],
            return_tensors="pt",
        )

        inputs = {
            key: (value.to(strategy.device) if torch.is_tensor(value) else value)
            for key, value in inputs.items()
        }

        return strategy.model(**inputs)

    def _target_score(
        self,
        *,
        outputs: Any,
        query_index: int,
        prediction_mask: np.ndarray,
    ) -> torch.Tensor:
        mask_logits = outputs.pred_masks

        if mask_logits is None:
            raise StrategyContractError("outputs no tiene pred_masks para grad-cam.")

        if mask_logits.ndim != 4:
            raise StrategyContractError(
                f"outputs.pred_masks debe ser 4d, shape recibido={tuple(mask_logits.shape)}"
            )

        target_mask_np = np.asarray(prediction_mask, dtype=bool)
        if target_mask_np.ndim != 2:
            raise StrategyContractError(
                f"prediction_mask debe ser 2d, shape recibido={target_mask_np.shape}"
            )

        if not target_mask_np.any():
            raise StrategyContractError("prediction_mask está vacío.")

        # usamos la máscara final como target para explicar la segmentación concreta, no solo el score global de la query
        query_mask_logits = mask_logits[0, query_index]
        query_mask_logits = F.interpolate(
            query_mask_logits[None, None],
            size=target_mask_np.shape,
            mode="bilinear",
            align_corners=False,
        )[0, 0]

        target_mask = torch.from_numpy(target_mask_np).to(
            device=query_mask_logits.device,
            dtype=torch.bool,
        )

        inside_score = query_mask_logits[target_mask].mean()

        # si hay fondo disponible, penalizamos activación fuera de la máscara para focalizar más el grad-cam
        # outside_mask = ~target_mask
        # if outside_mask.any():
        #    outside_score = query_mask_logits[outside_mask].mean()
        #    return inside_score - outside_score

        return inside_score

    def _match_query_index(
        self,
        *,
        outputs: Any,
        prediction_mask: np.ndarray,
        source_size: tuple[int, int],
        mask_threshold: float,
    ) -> tuple[int, float]:
        mask_logits = outputs.pred_masks

        if mask_logits.ndim != 4:
            raise StrategyContractError(
                f"outputs.pred_masks debe ser 4d, shape recibido={tuple(mask_logits.shape)}"
            )

        resized_masks = F.interpolate(
            mask_logits,
            size=source_size,
            mode="bilinear",
            align_corners=False,
        )

        mask_probs = resized_masks.sigmoid()[0]
        candidate_masks = mask_probs >= mask_threshold

        best_index = 0
        best_iou = -1.0

        for query_index, candidate_mask in enumerate(candidate_masks):
            candidate_np = candidate_mask.detach().cpu().numpy().astype(bool)
            iou = self._mask_iou(prediction_mask, candidate_np)

            if iou > best_iou:
                best_iou = iou
                best_index = query_index

        return best_index, float(best_iou)

    def _build_cam(
        self,
        *,
        activations: torch.Tensor,
        gradients: torch.Tensor,
        output_size: tuple[int, int],
    ) -> np.ndarray:
        activations = self._to_bchw(activations)
        gradients = self._to_bchw(gradients)

        # cam = (activations * F.relu(gradients)).sum(dim=1, keepdim=True)
        cam = (activations * gradients).sum(dim=1, keepdim=True)
        cam = F.relu(cam)

        cam = F.interpolate(
            cam,
            size=output_size,
            mode="bilinear",
            align_corners=False,
        )

        cam_np = cam[0, 0].detach().cpu().numpy()
        return self._normalize(cam_np)

    def _to_bchw(self, tensor: torch.Tensor) -> torch.Tensor:
        if tensor.ndim != 4:
            raise StrategyContractError(
                f"se esperaba un tensor 4d [B, C, H, W], shape={tuple(tensor.shape)}"
            )

        return tensor

    def _get_target_layer(self, strategy: Any):
        return strategy.model.mask_decoder.instance_projection

    def _get_source_bbox(
        self,
        *,
        prediction: InstancePrediction,
        record: ImageEvalRecord,
    ) -> tuple[int, int, int, int]:
        raw_bbox = prediction.metadata.get("source_bbox")

        if raw_bbox is None:
            return (0, 0, record.width, record.height)

        if len(raw_bbox) != 4:
            raise StrategyContractError(f"source_bbox inválido: {raw_bbox}")

        x1, y1, x2, y2 = [int(round(value)) for value in raw_bbox]

        x1 = max(0, min(record.width, x1))
        x2 = max(0, min(record.width, x2))
        y1 = max(0, min(record.height, y1))
        y2 = max(0, min(record.height, y2))

        if x2 <= x1 or y2 <= y1:
            raise StrategyContractError(f"source_bbox vacío o inválido: {raw_bbox}")

        return (x1, y1, x2, y2)

    def _prediction_mask_in_source(
        self,
        *,
        prediction: InstancePrediction,
        source_bbox: tuple[int, int, int, int],
    ) -> np.ndarray:
        x1, y1, x2, y2 = source_bbox
        mask = np.asarray(prediction.mask, dtype=bool)
        return mask[y1:y2, x1:x2]

    def _paste_source_heatmap(
        self,
        *,
        source_heatmap: np.ndarray,
        record: ImageEvalRecord,
        source_bbox: tuple[int, int, int, int],
    ) -> np.ndarray:
        full_heatmap = np.zeros((record.height, record.width), dtype=np.float32)
        x1, y1, x2, y2 = source_bbox
        full_heatmap[y1:y2, x1:x2] = source_heatmap
        return full_heatmap

    def _load_record_image(self, record: ImageEvalRecord) -> Image.Image:
        with Image.open(Path(record.image_path)) as image_file:
            return image_file.convert("RGB")

    def _extract_tensor(self, value: Any) -> torch.Tensor:
        if torch.is_tensor(value):
            return value

        if isinstance(value, (tuple, list)):
            for item in value:
                if torch.is_tensor(item):
                    return item

        raise StrategyContractError(
            f"hook devolvió un valor sin tensor usable: tipo={type(value)!r}"
        )

    def _normalize(self, heatmap: np.ndarray) -> np.ndarray:
        heatmap = np.asarray(heatmap, dtype=np.float32)
        heatmap = heatmap - float(heatmap.min())

        max_value = float(heatmap.max())
        if max_value <= self.eps:
            return np.zeros_like(heatmap, dtype=np.float32)

        return heatmap / max_value

    def _mask_iou(self, mask_a: np.ndarray, mask_b: np.ndarray) -> float:
        mask_a = np.asarray(mask_a, dtype=bool)
        mask_b = np.asarray(mask_b, dtype=bool)

        intersection = np.logical_and(mask_a, mask_b).sum()
        union = np.logical_or(mask_a, mask_b).sum()

        if union == 0:
            return 0.0

        return float(intersection / union)
