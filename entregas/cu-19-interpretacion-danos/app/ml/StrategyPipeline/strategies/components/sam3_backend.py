from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
import importlib
import inspect
import json
import warnings

import numpy as np
from PIL import Image
import torch
from transformers import Sam3Model, Sam3Processor
from transformers.utils import logging as hf_logging

from ml.StrategyPipeline.strategies.base import StrategyContractError


hf_logging.disable_progress_bar()

# timm lanza este warning desde una ruta vieja usada internamente por sam3
# lo silenciamos aqui para que no ensucie notebooks ni runs normales
warnings.filterwarnings(
    "ignore",
    message="Importing from timm.models.layers is deprecated, please import via timm.layers",
    category=FutureWarning,
    module=r"timm\.models\.layers(\..*)?",
)


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
DEFAULT_EXEMPLAR_MANIFEST_NAME = "manifest.json"
PromptMode = Literal["text", "exemplar", "hybrid"]
GeometricConsensusPolicy = Literal[
    "strict_attempted",
    "valid_only",
    "valid_plus_detection_rate",
]
PathLike = str | Path


@dataclass(frozen=True)
class ExemplarRef:
    # referencia mínima a una imagen exemplar y, opcionalmente, a una roi dentro de ella
    image_path: str
    bbox_xywh: tuple[float, float, float, float] | None = None

    def __post_init__(self) -> None:
        image_path = self.image_path.strip()
        if not image_path:
            raise StrategyContractError("ExemplarRef.image_path no puede estar vacío.")

        object.__setattr__(self, "image_path", image_path)

        if self.bbox_xywh is None:
            return

        if len(self.bbox_xywh) != 4:
            raise StrategyContractError(
                "ExemplarRef.bbox_xywh debe tener formato xywh."
            )

        object.__setattr__(
            self,
            "bbox_xywh",
            tuple(float(value) for value in self.bbox_xywh),
        )


@dataclass(frozen=True)
class PromptSpec:
    # prompt estructurado que puede ser solo texto, solo exemplars o una combinación de ambos
    text: str | None = None
    exemplars: tuple[ExemplarRef, ...] = ()
    mode: PromptMode = "text"
    name: str | None = None

    def __post_init__(self) -> None:
        text = None if self.text is None else self.text.strip()
        name = None if self.name is None else self.name.strip()

        exemplars = tuple(
            exemplar
            if isinstance(exemplar, ExemplarRef)
            else ExemplarRef(str(exemplar))
            for exemplar in self.exemplars
        )

        object.__setattr__(self, "text", text or None)
        object.__setattr__(self, "name", name or None)
        object.__setattr__(self, "exemplars", exemplars)

        if self.mode not in {"text", "exemplar", "hybrid"}:
            raise StrategyContractError(
                f"PromptSpec.mode no soportado: {self.mode!r}"
            )

        if self.mode == "text" and self.text is None:
            raise StrategyContractError(
                "PromptSpec en modo 'text' requiere text."
            )

        if self.mode == "exemplar" and not self.exemplars:
            raise StrategyContractError(
                "PromptSpec en modo 'exemplar' requiere al menos un exemplar."
            )

        if self.mode == "hybrid" and (self.text is None or not self.exemplars):
            raise StrategyContractError(
                "PromptSpec en modo 'hybrid' requiere text y exemplars."
            )

        if self.text is None and not self.exemplars:
            raise StrategyContractError(
                "PromptSpec requiere al menos text o exemplars."
            )

    @classmethod
    def text_prompt(
        cls,
        text: str,
        *,
        name: str | None = None,
    ) -> "PromptSpec":
        return cls(text=text, mode="text", name=name)

    @classmethod
    def exemplar_prompt(
        cls,
        exemplars: list[ExemplarRef] | tuple[ExemplarRef, ...],
        *,
        name: str | None = None,
    ) -> "PromptSpec":
        return cls(exemplars=tuple(exemplars), mode="exemplar", name=name)

    @classmethod
    def hybrid_prompt(
        cls,
        text: str,
        exemplars: list[ExemplarRef] | tuple[ExemplarRef, ...],
        *,
        name: str | None = None,
    ) -> "PromptSpec":
        return cls(
            text=text,
            exemplars=tuple(exemplars),
            mode="hybrid",
            name=name,
        )

    @classmethod
    def from_exemplar_dir(
        cls,
        exemplar_dir: PathLike,
        *,
        text: str | None = None,
        mode: PromptMode | None = None,
        name: str | None = None,
    ) -> "PromptSpec":
        # si la carpeta ya tiene manifest usamos esa configuración directamente
        root = Path(exemplar_dir)
        if not root.exists():
            raise FileNotFoundError(f"No existe exemplar_dir: {root}")

        manifest_path = root / DEFAULT_EXEMPLAR_MANIFEST_NAME
        if manifest_path.exists():
            return cls.from_manifest(
                manifest_path,
                text=text,
                mode=mode,
                name=name,
            )

        # si no hay manifest seguimos con el modo simple de usar todas las imágenes
        exemplars = tuple(
            ExemplarRef(str(path))
            for path in sorted(root.iterdir())
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        )

        if not exemplars:
            raise StrategyContractError(
                f"No se encontraron imágenes de exemplar en: {root}"
            )

        effective_mode = mode
        if effective_mode is None:
            effective_mode = "hybrid" if text else "exemplar"

        return cls(
            text=text,
            exemplars=exemplars,
            mode=effective_mode,
            name=name or root.name,
        )

    @classmethod
    def from_manifest(
        cls,
        manifest_path: PathLike,
        *,
        text: str | None = None,
        mode: PromptMode | None = None,
        name: str | None = None,
    ) -> "PromptSpec":
        # helper principal para reutilizar support sets exportados con manifest.json
        manifest_file, manifest_data = load_exemplar_manifest(manifest_path)

        raw_exemplars = manifest_data.get("exemplars")
        if not isinstance(raw_exemplars, list) or not raw_exemplars:
            raise StrategyContractError(
                "El manifest de exemplars debe contener una lista no vacía en 'exemplars'."
            )

        exemplars: list[ExemplarRef] = []
        for exemplar_item in raw_exemplars:
            if not isinstance(exemplar_item, dict):
                raise StrategyContractError(
                    "Cada exemplar del manifest debe ser un objeto con imagen y bbox opcional."
                )

            image_value = exemplar_item.get("image")
            if image_value is None:
                image_value = exemplar_item.get("image_path")

            if not image_value:
                raise StrategyContractError(
                    "Cada exemplar del manifest debe incluir 'image' o 'image_path'."
                )

            exemplar_image_path = (manifest_file.parent / str(image_value)).resolve()
            bbox_xywh = exemplar_item.get("bbox_xywh")

            exemplars.append(
                ExemplarRef(
                    image_path=str(exemplar_image_path),
                    bbox_xywh=(
                        tuple(bbox_xywh)
                        if bbox_xywh is not None
                        else None
                    ),
                )
            )

        effective_text = text if text is not None else manifest_data.get("text")
        effective_mode = mode if mode is not None else manifest_data.get("mode")
        if effective_mode is None:
            effective_mode = "hybrid" if effective_text else "exemplar"

        effective_name = (
            name
            or manifest_data.get("category_name")
            or manifest_file.parent.name
        )

        return cls(
            text=effective_text,
            exemplars=tuple(exemplars),
            mode=effective_mode,
            name=effective_name,
        )


@dataclass(frozen=True)
class Sam3MaskPrediction:
    score: float
    mask: np.ndarray
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GeometricEnsembleConfig:
    # define cuántas veces refinamos cada seed y qué criterio usamos para aceptar el consenso
    num_perturbations: int = 5
    perturbation_scale: float = 0.05
    consensus_threshold: float = 0.60
    min_valid_perturbations: int = 2
    min_detection_rate: float = 0.40
    include_seed_box: bool = True
    consensus_policy: GeometricConsensusPolicy = "valid_plus_detection_rate"
    random_seed: int | None = None

    def __post_init__(self) -> None:
        if self.num_perturbations <= 0:
            raise StrategyContractError(
                "GeometricEnsembleConfig.num_perturbations debe ser > 0."
            )

        if self.perturbation_scale < 0:
            raise StrategyContractError(
                "GeometricEnsembleConfig.perturbation_scale debe ser >= 0."
            )

        if not 0.0 <= self.consensus_threshold <= 1.0:
            raise StrategyContractError(
                "GeometricEnsembleConfig.consensus_threshold debe estar en [0, 1]."
            )

        if self.min_valid_perturbations <= 0:
            raise StrategyContractError(
                "GeometricEnsembleConfig.min_valid_perturbations debe ser > 0."
            )

        if not 0.0 <= self.min_detection_rate <= 1.0:
            raise StrategyContractError(
                "GeometricEnsembleConfig.min_detection_rate debe estar en [0, 1]."
            )

        if self.consensus_policy not in {
            "strict_attempted",
            "valid_only",
            "valid_plus_detection_rate",
        }:
            raise StrategyContractError(
                "GeometricEnsembleConfig.consensus_policy no soportado: "
                f"{self.consensus_policy!r}"
            )


@dataclass(frozen=True)
class GeometricConsensusResult:
    # resume qué pasó realmente durante el ensemble para poder auditar cada seed
    consensus_mask: np.ndarray | None
    votes: np.ndarray | None
    attempted_count: int
    valid_count: int
    detection_rate: float
    vote_denominator: int
    min_votes: int
    max_votes: int


PromptLike = str | PromptSpec
PromptValue = PromptLike | list[PromptLike] | tuple[PromptLike, ...]


def load_exemplar_manifest(
    manifest_path: PathLike,
) -> tuple[Path, dict[str, Any]]:
    manifest_file = Path(manifest_path).expanduser().resolve()
    if not manifest_file.exists():
        raise FileNotFoundError(f"No existe manifest_path: {manifest_file}")

    if not manifest_file.is_file():
        raise FileNotFoundError(f"manifest_path no es un fichero: {manifest_file}")

    with manifest_file.open(encoding="utf-8") as manifest_stream:
        manifest_data = json.load(manifest_stream)

    if not isinstance(manifest_data, dict):
        raise StrategyContractError(
            "El manifest de exemplars debe ser un objeto json."
        )

    return manifest_file, manifest_data


def prompt_map_entry_from_manifest(
    manifest_path: PathLike,
    *,
    text: str | None = None,
    mode: PromptMode | None = None,
    name: str | None = None,
) -> tuple[int, PromptSpec]:
    # devuelve una entrada lista para meterla en prompt_map
    manifest_file, manifest_data = load_exemplar_manifest(manifest_path)

    if "category_id" not in manifest_data:
        raise StrategyContractError(
            f"El manifest no incluye 'category_id': {manifest_file}"
        )

    category_id = int(manifest_data["category_id"])
    prompt_spec = PromptSpec.from_manifest(
        manifest_file,
        text=text,
        mode=mode,
        name=name,
    )

    return category_id, prompt_spec


def prompt_map_from_manifests(
    *manifest_paths: PathLike,
) -> dict[int, PromptSpec]:
    # helper compacto para construir un prompt_map entero a partir de manifests
    prompt_map: dict[int, PromptSpec] = {}

    for manifest_path in manifest_paths:
        category_id, prompt_spec = prompt_map_entry_from_manifest(manifest_path)

        if category_id in prompt_map:
            raise StrategyContractError(
                "Hay manifests duplicados para la misma categoría en prompt_map: "
                f"category_id={category_id}"
            )

        prompt_map[category_id] = prompt_spec

    return prompt_map


def normalize_prompt_specs(
    prompt_value: PromptValue | None,
    *,
    fallback_text: str | None = None,
) -> list[PromptSpec]:
    # normaliza la api pública para que el resto del backend trabaje siempre con promptspec
    if prompt_value is None:
        if fallback_text is None or not fallback_text.strip():
            raise StrategyContractError(
                "No se pudo resolver ningún prompt para la categoría."
            )
        return [PromptSpec.text_prompt(fallback_text)]

    if isinstance(prompt_value, (str, PromptSpec)):
        raw_items = [prompt_value]
    elif isinstance(prompt_value, (list, tuple)):
        raw_items = list(prompt_value)
        if not raw_items:
            raise StrategyContractError("La lista de prompts no puede estar vacía.")
    else:
        raise StrategyContractError(
            "Cada valor de prompt_map debe ser str, PromptSpec o una lista/tupla de ellos."
        )

    normalized: list[PromptSpec] = []
    for item in raw_items:
        if isinstance(item, PromptSpec):
            normalized.append(item)
            continue

        if isinstance(item, str):
            normalized.append(PromptSpec.text_prompt(item))
            continue

        raise StrategyContractError(
            "prompt_map contiene un elemento inválido: "
            f"{type(item)!r}"
        )

    # una categoría solo puede tener un prompt con texto para evitar ensembles implícitos
    text_prompt_count = sum(
        1
        for prompt_spec in normalized
        if prompt_spec.text is not None
    )
    if text_prompt_count > 1:
        raise StrategyContractError(
            "Cada categoría puede tener como máximo un prompt de texto. "
            "Si quieres combinar texto y exemplars, usa un único PromptSpec en modo 'hybrid'."
        )

    return normalized


class Sam3Backend:
    # backend compartido para que las strategies no sepan cómo se habla con sam3
    def __init__(
        self,
        *,
        model_path: str,
        score_threshold: float,
        mask_threshold: float,
        device: str | None = None,
        native_bpe_path: str | None = None,
        exemplar_nms_iou_threshold: float = 0.80,
        geometric_ensemble_config: GeometricEnsembleConfig | None = None,
    ) -> None:
        if not 0.0 <= score_threshold <= 1.0:
            raise StrategyContractError("score_threshold debe estar en [0, 1].")

        if not 0.0 <= mask_threshold <= 1.0:
            raise StrategyContractError("mask_threshold debe estar en [0, 1].")

        if not 0.0 <= exemplar_nms_iou_threshold <= 1.0:
            raise StrategyContractError(
                "exemplar_nms_iou_threshold debe estar en [0, 1]."
            )

        self.model_path = model_path
        self.score_threshold = score_threshold
        self.mask_threshold = mask_threshold
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.dtype = torch.float16 if self._uses_cuda_device() else torch.float32
        self.native_bpe_path = native_bpe_path
        self.exemplar_nms_iou_threshold = exemplar_nms_iou_threshold
        self.geometric_ensemble_config = geometric_ensemble_config
        # dejamos un rng persistente para poder repetir el ensemble si se fija random_seed
        self._ensemble_rng = (
            np.random.default_rng(geometric_ensemble_config.random_seed)
            if geometric_ensemble_config is not None
            else None
        )

        self.model = Sam3Model.from_pretrained(
            model_path,
            torch_dtype=self.dtype,
            local_files_only=True,
        ).to(self.device)
        self.model.eval()

        self.processor = Sam3Processor.from_pretrained(
            model_path,
            local_files_only=True,
        )

        self._native_model: Any | None = None
        self._native_processor: Any | None = None

        print("[SAM3 backend cargado correctamente!] (∩^o^)⊃")

    def set_score_threshold(self, score_threshold: float) -> None:
        # permite recalibrar el threshold sin recargar pesos ni reinstanciar el backend
        if not 0.0 <= score_threshold <= 1.0:
            raise StrategyContractError("score_threshold debe estar en [0, 1].")

        self.score_threshold = score_threshold

        # en la ruta native_exemplar el processor guarda su propio confidence_threshold
        if self._native_processor is not None:
            self._native_processor.confidence_threshold = score_threshold

    def predict_prompt_specs(
        self,
        *,
        image: Image.Image,
        prompt_specs: list[PromptSpec],
    ) -> list[list[Sam3MaskPrediction]]:
        # caso baseline -> una imagen y muchos prompts distintos
        if not prompt_specs:
            return []

        resolved_specs = [
            prompt_spec
            if isinstance(prompt_spec, PromptSpec)
            else normalize_prompt_specs(prompt_spec)[0]
            for prompt_spec in prompt_specs
        ]

        outputs: list[list[Sam3MaskPrediction]] = [[] for _ in resolved_specs]
        text_indexes: list[int] = []
        text_specs: list[PromptSpec] = []

        for idx, prompt_spec in enumerate(resolved_specs):
            # los prompts solo texto siguen yendo por transformers porque permiten batching real
            if self._is_text_only_prompt(prompt_spec):
                text_indexes.append(idx)
                text_specs.append(prompt_spec)
                continue

            # los prompts con exemplars usan el workaround de stitching en una sola inferencia por promptspec
            outputs[idx] = self._predict_exemplar_prompt(
                image=image,
                prompt_spec=prompt_spec,
            )

        if text_specs:
            # ejecutamos de golpe todos los prompts de texto para aprovechar mejor la gpu
            if self.geometric_ensemble_config is None:
                text_outputs = self._predict_text_batch(
                    images=[image] * len(text_specs),
                    prompts=[prompt_spec.text or "" for prompt_spec in text_specs],
                    prompt_specs=text_specs,
                )
            else:
                # si el ensemble está activado, cada prompt de texto hace seed + refinamiento por cajas perturbadas
                text_outputs = self._predict_text_batch_with_geometric_ensemble(
                    images=[image] * len(text_specs),
                    prompt_specs=text_specs,
                )

            for idx, detections in zip(text_indexes, text_outputs):
                outputs[idx] = detections

        return outputs

    def predict_images_for_prompt(
        self,
        *,
        images: list[Image.Image],
        prompt_spec: PromptLike,
    ) -> list[list[Sam3MaskPrediction]]:
        # caso sahi -> un prompt y muchas imágenes o recortes
        if not images:
            return []

        resolved_prompt = (
            prompt_spec
            if isinstance(prompt_spec, PromptSpec)
            else normalize_prompt_specs(prompt_spec)[0]
        )

        if self._is_text_only_prompt(resolved_prompt):
            if self.geometric_ensemble_config is None:
                return self._predict_text_batch(
                    images=images,
                    prompts=[resolved_prompt.text or ""] * len(images),
                    prompt_specs=[resolved_prompt] * len(images),
                )

            # la misma idea del ensemble sirve también cuando sahi llama al backend con muchas imágenes para un solo prompt
            return self._predict_text_batch_with_geometric_ensemble(
                images=images,
                prompt_specs=[resolved_prompt] * len(images),
            )

        # en sahi seguimos yendo imagen a imagen, pero cada imagen usa todos sus exemplars en una sola inferencia
        return [
            self._predict_exemplar_prompt(
                image=image,
                prompt_spec=resolved_prompt,
            )
            for image in images
        ]

    def _predict_text_batch(
        self,
        *,
        images: list[Image.Image],
        prompts: list[str],
        prompt_specs: list[PromptSpec],
    ) -> list[list[Sam3MaskPrediction]]:
        # ruta estándar de texto puro sin refinamiento geométrico adicional
        return self._run_transformers_text_batch(
            images=images,
            prompts=prompts,
            prompt_specs=prompt_specs,
            input_boxes=None,
            backend_name="transformers_text",
        )

    def _run_transformers_text_batch(
        self,
        *,
        images: list[Image.Image],
        prompts: list[str],
        prompt_specs: list[PromptSpec],
        input_boxes: list[list[tuple[float, float, float, float]]] | None,
        backend_name: str,
    ) -> list[list[Sam3MaskPrediction]]:
        # ruta transformers compartida entre texto puro y refinamiento guiado por cajas
        if len(images) != len(prompts) or len(images) != len(prompt_specs):
            raise StrategyContractError(
                "images, prompts y prompt_specs deben tener la misma longitud."
            )

        if input_boxes is not None and len(input_boxes) != len(images):
            raise StrategyContractError(
                "input_boxes debe tener la misma longitud que images."
            )

        target_sizes = [
            (image.height, image.width)
            for image in images
        ]

        processor_kwargs: dict[str, Any] = {
            "images": images,
            "text": prompts,
            "return_tensors": "pt",
        }

        if input_boxes is not None:
            # transformers espera las cajas por imagen en formato xyxy
            processor_kwargs["input_boxes"] = [
                [
                    [float(x1), float(y1), float(x2), float(y2)]
                    for x1, y1, x2, y2 in image_boxes
                ]
                for image_boxes in input_boxes
            ]

        inputs = self.processor(**processor_kwargs)

        inputs = {
            key: (
                value.to(self.device).to(self.dtype)
                if torch.is_tensor(value) and torch.is_floating_point(value)
                else value.to(self.device)
                if torch.is_tensor(value)
                else value
            )
            for key, value in inputs.items()
        }

        with torch.no_grad():
            outputs = self.model(**inputs)

        results = self.processor.post_process_instance_segmentation(
            outputs,
            threshold=self.score_threshold,
            mask_threshold=self.mask_threshold,
            target_sizes=target_sizes,
        )

        batch_predictions: list[list[Sam3MaskPrediction]] = []

        for index, (prompt_spec, result, image) in enumerate(
            zip(prompt_specs, results, images)
        ):
            # unificamos scores y masks para que el resto del pipeline no dependa del formato de salida
            scores = self._normalize_scores(result.get("scores", []))
            masks = self._normalize_masks(
                result.get("masks", []),
                expected_shape=(image.height, image.width),
            )

            metadata = self._build_prompt_metadata(
                prompt_spec=prompt_spec,
                backend_name=backend_name,
            )

            if input_boxes is not None and input_boxes[index]:
                # guardamos también las cajas usadas en el refinamiento para inspección y debug
                metadata["sam3_input_boxes_xyxy"] = [
                    tuple(float(value) for value in box_xyxy)
                    for box_xyxy in input_boxes[index]
                ]

            batch_predictions.append(
                [
                    Sam3MaskPrediction(
                        score=float(score),
                        mask=mask,
                        metadata=dict(metadata),
                    )
                    for score, mask in zip(scores, masks)
                ]
            )

        return batch_predictions

    def _predict_text_batch_with_geometric_ensemble(
        self,
        *,
        images: list[Image.Image],
        prompt_specs: list[PromptSpec],
    ) -> list[list[Sam3MaskPrediction]]:
        config = self.geometric_ensemble_config
        if config is None:
            raise StrategyContractError(
                "Se pidió geometric ensemble sin geometric_ensemble_config."
            )

        # primero generamos las seeds normales de sam3 y luego refinamos cada una por separado
        base_predictions = self._predict_text_batch(
            images=images,
            prompts=[prompt_spec.text or "" for prompt_spec in prompt_specs],
            prompt_specs=prompt_specs,
        )

        return [
            self._refine_text_predictions_with_geometric_ensemble(
                image=image,
                prompt_spec=prompt_spec,
                seed_predictions=seed_predictions,
            )
            for image, prompt_spec, seed_predictions in zip(
                images,
                prompt_specs,
                base_predictions,
            )
        ]

    def _refine_text_predictions_with_geometric_ensemble(
        self,
        *,
        image: Image.Image,
        prompt_spec: PromptSpec,
        seed_predictions: list[Sam3MaskPrediction],
    ) -> list[Sam3MaskPrediction]:
        config = self.geometric_ensemble_config
        if config is None:
            raise StrategyContractError(
                "Se pidió geometric ensemble sin geometric_ensemble_config."
            )

        if not prompt_spec.text:
            raise StrategyContractError(
                "Geometric ensemble requiere un prompt de texto."
            )

        refined_predictions: list[Sam3MaskPrediction] = []

        for seed_prediction in seed_predictions:
            # cada seed define la roi inicial alrededor de la cual perturbamos la caja
            seed_bbox_xywh = self._mask_to_bbox_xywh(seed_prediction.mask)
            if seed_bbox_xywh[2] <= 0 or seed_bbox_xywh[3] <= 0:
                continue

            ensemble_boxes_xywh = self._build_geometric_ensemble_boxes(
                bbox_xywh=seed_bbox_xywh,
                image_width=image.width,
                image_height=image.height,
            )

            consensus_result = self._predict_consensus_mask(
                image=image,
                prompt_spec=prompt_spec,
                boxes_xywh=ensemble_boxes_xywh,
            )

            if (
                consensus_result.consensus_mask is None
                or not consensus_result.consensus_mask.any()
            ):
                continue

            refined_predictions.append(
                Sam3MaskPrediction(
                    score=float(seed_prediction.score),
                    mask=consensus_result.consensus_mask,
                    metadata={
                        **seed_prediction.metadata,
                        # mantenemos la trazabilidad de la seed original y del proceso de votación
                        "sam3_backend": "transformers_text_geometric_ensemble",
                        "sam3_seed_score": float(seed_prediction.score),
                        "sam3_seed_bbox_xywh": tuple(
                            float(value) for value in seed_bbox_xywh
                        ),
                        "ensemble_num_perturbations": config.num_perturbations,
                        "ensemble_perturbation_scale": float(
                            config.perturbation_scale
                        ),
                        "ensemble_consensus_policy": config.consensus_policy,
                        "ensemble_include_seed_box": bool(
                            config.include_seed_box
                        ),
                        "ensemble_attempted_count": int(
                            consensus_result.attempted_count
                        ),
                        "ensemble_valid_count": int(
                            consensus_result.valid_count
                        ),
                        "ensemble_detection_rate": float(
                            consensus_result.detection_rate
                        ),
                        "ensemble_consensus_threshold": float(
                            config.consensus_threshold
                        ),
                        "ensemble_min_valid_perturbations": int(
                            config.min_valid_perturbations
                        ),
                        "ensemble_min_detection_rate": float(
                            config.min_detection_rate
                        ),
                        "ensemble_vote_denominator": int(
                            consensus_result.vote_denominator
                        ),
                        "ensemble_min_votes": int(
                            consensus_result.min_votes
                        ),
                        "ensemble_max_votes": int(
                            consensus_result.max_votes
                        ),
                    },
                )
            )

        return refined_predictions

    def _predict_consensus_mask(
        self,
        *,
        image: Image.Image,
        prompt_spec: PromptSpec,
        boxes_xywh: list[tuple[float, float, float, float]],
    ) -> GeometricConsensusResult:
        config = self.geometric_ensemble_config
        if config is None:
            raise StrategyContractError(
                "Se pidió geometric ensemble sin geometric_ensemble_config."
            )

        attempted_count = len(boxes_xywh)
        if not boxes_xywh:
            return GeometricConsensusResult(
                consensus_mask=None,
                votes=None,
                attempted_count=0,
                valid_count=0,
                detection_rate=0.0,
                vote_denominator=0,
                min_votes=0,
                max_votes=0,
            )

        # aquí relanzamos sam3 varias veces con el mismo texto pero cambiando la caja guía
        box_predictions = self._run_transformers_text_batch(
            images=[image] * len(boxes_xywh),
            prompts=[prompt_spec.text or ""] * len(boxes_xywh),
            prompt_specs=[prompt_spec] * len(boxes_xywh),
            input_boxes=[
                [self._xywh_to_xyxy(box_xywh)]
                for box_xywh in boxes_xywh
            ],
            backend_name="transformers_text_box_prompt",
        )

        ensemble_masks: list[np.ndarray] = []
        for detections in box_predictions:
            # de cada perturbación nos quedamos con la mejor máscara disponible
            best_detection = self._select_best_detection(detections)
            if best_detection is None:
                continue

            ensemble_masks.append(np.asarray(best_detection.mask, dtype=bool))

        if not ensemble_masks:
            return GeometricConsensusResult(
                consensus_mask=None,
                votes=None,
                attempted_count=attempted_count,
                valid_count=0,
                detection_rate=0.0,
                vote_denominator=0,
                min_votes=0,
                max_votes=0,
            )

        return self._build_geometric_consensus_result(
            valid_masks=ensemble_masks,
            attempted_count=attempted_count,
        )

    def _select_best_detection(
        self,
        detections: list[Sam3MaskPrediction],
    ) -> Sam3MaskPrediction | None:
        if not detections:
            return None

        # resolvemos empates de una perturbación usando el mismo score que devuelve sam3
        return max(detections, key=lambda detection: detection.score)

    def _generate_perturbed_boxes(
        self,
        *,
        bbox_xywh: tuple[float, float, float, float],
        image_width: int,
        image_height: int,
    ) -> list[tuple[float, float, float, float]]:
        config = self.geometric_ensemble_config
        if config is None:
            raise StrategyContractError(
                "Se pidió geometric ensemble sin geometric_ensemble_config."
            )

        x, y, width, height = bbox_xywh
        noise = max(width, height) * config.perturbation_scale
        rng = self._ensemble_rng or np.random.default_rng()

        perturbed_boxes: list[tuple[float, float, float, float]] = []
        max_x = max(0.0, float(image_width) - 1.0)
        max_y = max(0.0, float(image_height) - 1.0)

        for _ in range(config.num_perturbations):
            perturbed_x = float(x + rng.uniform(-noise, noise))
            perturbed_y = float(y + rng.uniform(-noise, noise))
            perturbed_width = float(width + rng.uniform(-noise, noise))
            perturbed_height = float(height + rng.uniform(-noise, noise))

            # recortamos la caja al lienzo de la imagen para no enviar prompts inválidos al processor
            perturbed_x = min(max(0.0, perturbed_x), max_x)
            perturbed_y = min(max(0.0, perturbed_y), max_y)

            max_width = max(1.0, float(image_width) - perturbed_x)
            max_height = max(1.0, float(image_height) - perturbed_y)

            perturbed_width = min(max(1.0, perturbed_width), max_width)
            perturbed_height = min(max(1.0, perturbed_height), max_height)

            perturbed_boxes.append(
                (
                    perturbed_x,
                    perturbed_y,
                    perturbed_width,
                    perturbed_height,
                )
            )

        return perturbed_boxes

    def _build_geometric_ensemble_boxes(
        self,
        *,
        bbox_xywh: tuple[float, float, float, float],
        image_width: int,
        image_height: int,
    ) -> list[tuple[float, float, float, float]]:
        config = self.geometric_ensemble_config
        if config is None:
            raise StrategyContractError(
                "Se pidió geometric ensemble sin geometric_ensemble_config."
            )

        # la seed/original se puede incluir como vista estable además de las cajas perturbadas
        perturbed_boxes = self._generate_perturbed_boxes(
            bbox_xywh=bbox_xywh,
            image_width=image_width,
            image_height=image_height,
        )

        if not config.include_seed_box:
            return perturbed_boxes

        return [bbox_xywh, *perturbed_boxes]

    def _build_geometric_consensus_result(
        self,
        *,
        valid_masks: list[np.ndarray],
        attempted_count: int,
    ) -> GeometricConsensusResult:
        config = self.geometric_ensemble_config
        if config is None:
            raise StrategyContractError(
                "Se pidió geometric ensemble sin geometric_ensemble_config."
            )

        valid_count = len(valid_masks)
        detection_rate = (
            float(valid_count / attempted_count)
            if attempted_count > 0
            else 0.0
        )

        if valid_count == 0:
            return GeometricConsensusResult(
                consensus_mask=None,
                votes=None,
                attempted_count=attempted_count,
                valid_count=0,
                detection_rate=detection_rate,
                vote_denominator=0,
                min_votes=0,
                max_votes=0,
            )

        # el consenso espacial siempre se construye a partir de las máscaras que sí existen
        votes = np.stack(
            [np.asarray(mask, dtype=bool) for mask in valid_masks],
            axis=0,
        ).sum(axis=0)

        vote_denominator = self._resolve_geometric_vote_denominator(
            attempted_count=attempted_count,
            valid_count=valid_count,
        )
        min_votes = int(np.ceil(vote_denominator * config.consensus_threshold))
        max_votes = int(votes.max()) if votes.size > 0 else 0

        if not self._passes_geometric_detection_robustness(
            attempted_count=attempted_count,
            valid_count=valid_count,
            detection_rate=detection_rate,
        ):
            return GeometricConsensusResult(
                consensus_mask=None,
                votes=votes,
                attempted_count=attempted_count,
                valid_count=valid_count,
                detection_rate=detection_rate,
                vote_denominator=vote_denominator,
                min_votes=min_votes,
                max_votes=max_votes,
            )

        consensus_mask = np.asarray(votes >= min_votes, dtype=bool)
        if not consensus_mask.any():
            consensus_mask = None

        return GeometricConsensusResult(
            consensus_mask=consensus_mask,
            votes=votes,
            attempted_count=attempted_count,
            valid_count=valid_count,
            detection_rate=detection_rate,
            vote_denominator=vote_denominator,
            min_votes=min_votes,
            max_votes=max_votes,
        )

    def _resolve_geometric_vote_denominator(
        self,
        *,
        attempted_count: int,
        valid_count: int,
    ) -> int:
        config = self.geometric_ensemble_config
        if config is None:
            raise StrategyContractError(
                "Se pidió geometric ensemble sin geometric_ensemble_config."
            )

        if config.consensus_policy == "strict_attempted":
            return attempted_count

        return valid_count

    def _passes_geometric_detection_robustness(
        self,
        *,
        attempted_count: int,
        valid_count: int,
        detection_rate: float,
    ) -> bool:
        config = self.geometric_ensemble_config
        if config is None:
            raise StrategyContractError(
                "Se pidió geometric ensemble sin geometric_ensemble_config."
            )

        if valid_count == 0:
            return False

        # esta política replica el comportamiento antiguo: los fallos cuentan como no-votos,
        # pero no hay un filtro explícito de robustez más allá del consenso espacial
        if config.consensus_policy == "strict_attempted":
            return True

        # aquí solo miramos el acuerdo entre máscaras válidas y permitimos estudiar ese ablation aparte
        if config.consensus_policy == "valid_only":
            return True

        # la política nueva exige acuerdo espacial y también estabilidad global ante perturbaciones fallidas
        if valid_count < config.min_valid_perturbations:
            return False

        if attempted_count <= 0:
            return False

        return detection_rate >= config.min_detection_rate

    def _mask_to_bbox_xywh(
        self,
        mask: np.ndarray,
    ) -> tuple[float, float, float, float]:
        # convertimos la seed en una caja xywh porque es más cómoda para perturbar tamaño y posición
        ys, xs = np.where(np.asarray(mask, dtype=bool))

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

    def _xywh_to_xyxy(
        self,
        box_xywh: tuple[float, float, float, float],
    ) -> tuple[float, float, float, float]:
        # transformers usa cajas xyxy en input_boxes, así que convertimos justo antes de inferir
        x, y, width, height = box_xywh
        return (
            float(x),
            float(y),
            float(x + width),
            float(y + height),
        )

    def _predict_exemplar_prompt(
        self,
        *,
        image: Image.Image,
        prompt_spec: PromptSpec,
    ) -> list[Sam3MaskPrediction]:
        # ruta image exemplar con el hack de coser exemplar + target en una sola imagen
        if not prompt_spec.exemplars:
            raise StrategyContractError(
                "Se pidió inferencia por exemplars sin exemplars en PromptSpec."
            )

        processor = self._get_or_create_native_processor()
        target_image = image.convert("RGB")
        exemplar_images = [
            self._load_exemplar_image(exemplar)
            for exemplar in prompt_spec.exemplars
        ]
        composite, target_x_offset, exemplar_x_offsets = self._stitch_exemplar_strip(
            exemplars=exemplar_images,
            target=target_image,
        )

        exemplar_prompt_boxes_xywh: list[tuple[float, float, float, float]] = []
        exemplar_prompt_boxes_normalized: list[list[float]] = []
        for exemplar, exemplar_image, exemplar_x_offset in zip(
            prompt_spec.exemplars,
            exemplar_images,
            exemplar_x_offsets,
        ):
            # cada exemplar aporta una caja positiva distinta dentro del mismo composite
            box_abs = self._compute_exemplar_box(
                exemplar=exemplar_image,
                target_height=target_image.height,
                bbox_xywh=exemplar.bbox_xywh,
            )
            box_abs = self._translate_box_xywh(
                box_xywh=box_abs,
                x_offset=exemplar_x_offset,
            )
            exemplar_prompt_boxes_xywh.append(box_abs)
            exemplar_prompt_boxes_normalized.append(
                self._normalize_box_to_composite(
                    box_xywh=box_abs,
                    composite_width=composite.width,
                    composite_height=composite.height,
                )
            )

        with self._build_native_inference_context():
            state = processor.set_image(composite)

            if prompt_spec.text:
                # en modo hybrid combinamos la pista visual con la textual
                state = processor.set_text_prompt(prompt_spec.text, state)

            for box_normalized in exemplar_prompt_boxes_normalized:
                state = processor.add_geometric_prompt(
                    box_normalized,
                    label=True,
                    state=state,
                )

        # después de inferir sobre la imagen compuesta nos quedamos solo con lo que cae en target
        boxes, masks, scores = self._filter_target_results(
            state=state,
            target_x_offset=target_x_offset,
        )

        single_exemplar = (
            prompt_spec.exemplars[0]
            if len(prompt_spec.exemplars) == 1
            else None
        )
        base_metadata = self._build_prompt_metadata(
            prompt_spec=prompt_spec,
            backend_name="native_exemplar",
            exemplar=single_exemplar,
        )

        detections: list[Sam3MaskPrediction] = []
        for box, mask, score in zip(boxes, masks, scores):
            detections.append(
                Sam3MaskPrediction(
                    score=float(score),
                    mask=np.asarray(mask, dtype=bool),
                    metadata={
                        **base_metadata,
                        "sam3_exemplar_prompt_boxes_xywh": [
                            tuple(float(value) for value in prompt_box)
                            for prompt_box in exemplar_prompt_boxes_xywh
                        ],
                        "sam3_target_box_xyxy": tuple(float(value) for value in box),
                    },
                )
            )

        # aunque ahora todos los exemplars van en una sola inferencia, puede seguir habiendo duplicados
        return self._apply_mask_nms(
            detections,
            iou_threshold=self.exemplar_nms_iou_threshold,
        )

    def _build_native_inference_context(self):
        # el backend nativo va mejor en bf16 sobre cuda, en cpu no hace falta autocast
        if self._uses_cuda_device():
            return torch.autocast("cuda", dtype=torch.bfloat16)

        return nullcontext()

    def _get_or_create_native_processor(self) -> Any:
        # solo cargamos el paquete sam3 nativo si realmente alguien usa exemplars
        if self._native_processor is not None:
            return self._native_processor

        try:
            sam3_module = importlib.import_module("sam3")
            sam3_processor_module = importlib.import_module(
                "sam3.model.sam3_image_processor"
            )
        except ModuleNotFoundError as exc:
            missing_module = exc.name or "desconocido"

            if missing_module == "sam3":
                raise StrategyContractError(
                    "Los prompts con exemplars requieren el paquete `sam3` instalado "
                    "en el entorno activo. El backend de texto con transformers sigue "
                    "funcionando sin él."
                ) from exc

            if missing_module.startswith("sam3."):
                raise StrategyContractError(
                    "El paquete `sam3` instalado no expone el modulo esperado "
                    f"{missing_module!r}. Puede ser una version incompatible con "
                    "el backend actual."
                ) from exc

            raise StrategyContractError(
                "El paquete `sam3` esta instalado, pero no pudo importarse por una "
                f"dependencia faltante: {missing_module!r}. Instala esa dependencia "
                "en el mismo entorno y vuelve a probar."
            ) from exc

        build_sam3_image_model = getattr(
            sam3_module,
            "build_sam3_image_model",
        )
        native_processor_cls = getattr(
            sam3_processor_module,
            "Sam3Processor",
        )

        builder_signature = inspect.signature(build_sam3_image_model)
        builder_kwargs: dict[str, Any] = {}

        # algunas builds del paquete piden bpe_path y otras no, así que lo resolvemos en runtime
        if "bpe_path" in builder_signature.parameters:
            builder_kwargs["bpe_path"] = self._resolve_native_bpe_path(sam3_module)

        # el nombre del parámetro del checkpoint puede variar según la versión instalada
        for parameter_name in (
            "model_path",
            "checkpoint_path",
            "checkpoint",
            "weights_path",
            "pretrained_path",
        ):
            if parameter_name in builder_signature.parameters:
                builder_kwargs[parameter_name] = self._resolve_native_checkpoint_path()
                break

        if self._uses_cuda_device():
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True

        self._native_model = build_sam3_image_model(**builder_kwargs)
        self._native_processor = native_processor_cls(
            self._native_model,
            device=self.device,
            confidence_threshold=self.score_threshold,
        )

        return self._native_processor

    def _resolve_native_bpe_path(self, sam3_module: Any) -> str:
        if self.native_bpe_path:
            return self.native_bpe_path

        # soportamos tanto install editable del repo como wheel instalado desde pip
        package_root = Path(sam3_module.__file__).resolve().parent
        candidate_paths = [
            package_root / "assets" / "bpe_simple_vocab_16e6.txt.gz",
            package_root.parent / "assets" / "bpe_simple_vocab_16e6.txt.gz",
        ]

        for candidate_path in candidate_paths:
            if candidate_path.exists():
                return str(candidate_path)

        raise StrategyContractError(
            "No se pudo localizar el vocabulario BPE de `sam3`. "
            "Se esperaba encontrar `bpe_simple_vocab_16e6.txt.gz` en alguna de estas rutas: "
            + ", ".join(str(candidate_path) for candidate_path in candidate_paths)
            + ". Si tu instalacion usa otra ruta, pasa native_bpe_path manualmente."
        )

    def _resolve_native_checkpoint_path(self) -> str:
        # transformers acepta un directorio de hf, pero sam3 nativo necesita el checkpoint real
        model_path = Path(self.model_path).expanduser().resolve()

        if model_path.is_file():
            return str(model_path)

        if not model_path.exists():
            raise FileNotFoundError(
                f"No existe model_path para el backend nativo de sam3: {self.model_path}"
            )

        if not model_path.is_dir():
            raise StrategyContractError(
                "model_path para el backend nativo de sam3 debe ser un fichero de checkpoint "
                f"o un directorio que lo contenga: {self.model_path}"
            )

        candidate_paths = [
            model_path / "sam3.pt",
            model_path / "checkpoints" / "sam3.pt",
        ]
        candidate_paths.extend(
            sorted(model_path.glob("*.pt"))
        )
        candidate_paths.extend(
            sorted(model_path.glob("*.pth"))
        )

        seen_paths: set[Path] = set()
        unique_candidates: list[Path] = []
        for candidate_path in candidate_paths:
            if candidate_path in seen_paths:
                continue
            seen_paths.add(candidate_path)
            unique_candidates.append(candidate_path)

        existing_candidates = [
            candidate_path
            for candidate_path in unique_candidates
            if candidate_path.exists() and candidate_path.is_file()
        ]

        if len(existing_candidates) == 1:
            return str(existing_candidates[0])

        if len(existing_candidates) > 1:
            raise StrategyContractError(
                "model_path apunta a un directorio con varios checkpoints posibles para sam3: "
                + ", ".join(str(candidate_path) for candidate_path in existing_candidates)
                + ". Pasa el fichero concreto en model_path."
            )

        raise StrategyContractError(
            "model_path apunta a un directorio, pero no se encontro ningun checkpoint `.pt` "
            f"o `.pth` dentro de {self.model_path}. Si usas sam3 nativo, pasa el fichero "
            "de checkpoint concreto en model_path."
        )

    def _load_exemplar_image(self, exemplar: ExemplarRef) -> Image.Image:
        exemplar_path = Path(exemplar.image_path)
        if not exemplar_path.exists():
            raise FileNotFoundError(
                f"No existe el exemplar: {exemplar.image_path}"
            )

        with Image.open(exemplar_path) as image_file:
            return image_file.convert("RGB")

    def _stitch_exemplar_strip(
        self,
        *,
        exemplars: list[Image.Image],
        target: Image.Image,
    ) -> tuple[Image.Image, int, list[int]]:
        # cosemos todos los exemplars a la izquierda y el target al final
        if not exemplars:
            raise StrategyContractError(
                "Se esperaba al menos un exemplar para construir el composite."
            )

        target_height = target.height
        resized_exemplars: list[Image.Image] = []
        exemplar_x_offsets: list[int] = []
        current_x_offset = 0
        for exemplar in exemplars:
            exemplar_resized = exemplar.resize(
                (
                    int(exemplar.width * target_height / exemplar.height),
                    target_height,
                ),
                Image.LANCZOS,
            )
            resized_exemplars.append(exemplar_resized)
            exemplar_x_offsets.append(current_x_offset)
            current_x_offset += exemplar_resized.width

        target_x_offset = current_x_offset
        composite = Image.new(
            "RGB",
            (target_x_offset + target.width, target_height),
        )
        for exemplar_resized, exemplar_x_offset in zip(
            resized_exemplars,
            exemplar_x_offsets,
        ):
            composite.paste(exemplar_resized, (exemplar_x_offset, 0))
        composite.paste(target, (target_x_offset, 0))

        return composite, target_x_offset, exemplar_x_offsets

    def _compute_exemplar_box(
        self,
        *,
        exemplar: Image.Image,
        target_height: int,
        bbox_xywh: tuple[float, float, float, float] | None,
    ) -> tuple[float, float, float, float]:
        # la caja del exemplar se recalcula en el sistema de coordenadas del composite
        scale = target_height / exemplar.height
        exemplar_width = int(exemplar.width * scale)

        if bbox_xywh is None:
            return (0.0, 0.0, float(exemplar_width), float(target_height))

        x, y, width, height = bbox_xywh
        return (
            float(x * scale),
            float(y * scale),
            float(width * scale),
            float(height * scale),
        )

    def _translate_box_xywh(
        self,
        *,
        box_xywh: tuple[float, float, float, float],
        x_offset: int,
    ) -> tuple[float, float, float, float]:
        # movemos la caja local del exemplar a la posición que ocupa en el composite
        x, y, width, height = box_xywh
        return (
            float(x + x_offset),
            float(y),
            float(width),
            float(height),
        )

    def _normalize_box_to_composite(
        self,
        *,
        box_xywh: tuple[float, float, float, float],
        composite_width: int,
        composite_height: int,
    ) -> list[float]:
        # el processor nativo espera cajas normalizadas en formato cxcywh
        x, y, width, height = box_xywh
        cx = x + (width / 2.0)
        cy = y + (height / 2.0)

        return [
            float(cx / composite_width),
            float(cy / composite_height),
            float(width / composite_width),
            float(height / composite_height),
        ]

    def _filter_target_results(
        self,
        *,
        state: Any,
        target_x_offset: int,
    ) -> tuple[list[list[float]], list[np.ndarray], list[float]]:
        # filtramos cualquier detección que se quede en la mitad exemplar del composite
        if "boxes" not in state or len(state["boxes"]) == 0:
            return [], [], []

        boxes = self._to_numpy(state["boxes"])
        masks = self._to_numpy(state["masks"])
        scores = self._to_numpy(state["scores"]).astype(float)

        target_boxes: list[list[float]] = []
        target_masks: list[np.ndarray] = []
        target_scores: list[float] = []

        for index in range(len(boxes)):
            x1, y1, x2, y2 = boxes[index]
            center_x = (x1 + x2) / 2.0

            # usamos el centro de la caja para decidir si la detección pertenece al target
            if center_x < target_x_offset:
                continue

            target_boxes.append(
                [
                    float(x1 - target_x_offset),
                    float(y1),
                    float(x2 - target_x_offset),
                    float(y2),
                ]
            )
            target_masks.append(
                np.asarray(masks[index, 0, :, target_x_offset:], dtype=bool)
            )
            target_scores.append(float(scores[index]))

        return target_boxes, target_masks, target_scores

    def _normalize_scores(self, scores: Any) -> np.ndarray:
        # convertimos scores vacíos, tensores o listas a un único formato
        if torch.is_tensor(scores):
            scores = scores.detach().cpu().numpy()
        else:
            scores = np.asarray(scores, dtype=float)

        if scores.size == 0:
            return np.zeros((0,), dtype=float)

        return scores.astype(float)

    def _normalize_masks(
        self,
        masks: Any,
        *,
        expected_shape: tuple[int, int],
    ) -> np.ndarray:
        # convertimos la salida de sam3 a máscaras booleanas con el shape esperado
        if torch.is_tensor(masks):
            masks = masks.detach().cpu().numpy()
        else:
            masks = np.asarray(masks)

        if masks.size == 0:
            return np.zeros((0, *expected_shape), dtype=bool)

        if masks.ndim == 2:
            masks = masks[None, ...]

        if tuple(masks.shape[1:]) != expected_shape:
            raise StrategyContractError(
                "La máscara devuelta por SAM3 no coincide con la imagen: "
                f"shape={tuple(masks.shape[1:])}, expected={expected_shape}"
            )

        return masks.astype(bool)

    def _build_prompt_metadata(
        self,
        *,
        prompt_spec: PromptSpec,
        backend_name: str,
        exemplar: ExemplarRef | None = None,
    ) -> dict[str, Any]:
        # dejamos trazabilidad de qué prompt disparó cada predicción
        metadata = {
            "sam3_backend": backend_name,
            "prompt_name": prompt_spec.name,
            "prompt_mode": prompt_spec.mode,
            "sam3_prompt": prompt_spec.text,
            "exemplar_paths": [
                exemplar_ref.image_path
                for exemplar_ref in prompt_spec.exemplars
            ],
            "exemplar_count": len(prompt_spec.exemplars),
            "exemplar_bboxes_xywh": [
                exemplar_ref.bbox_xywh
                for exemplar_ref in prompt_spec.exemplars
            ],
        }

        if exemplar is not None:
            metadata["exemplar_image_path"] = exemplar.image_path
            metadata["exemplar_bbox_xywh"] = exemplar.bbox_xywh

        return metadata

    def _apply_mask_nms(
        self,
        detections: list[Sam3MaskPrediction],
        *,
        iou_threshold: float,
    ) -> list[Sam3MaskPrediction]:
        # nms sencillo entre máscaras para fusionar duplicados entre exemplars
        if not detections:
            return []

        ordered = sorted(
            detections,
            key=lambda detection: detection.score,
            reverse=True,
        )

        kept: list[Sam3MaskPrediction] = []
        for detection in ordered:
            if any(
                self._mask_iou(detection.mask, kept_detection.mask) >= iou_threshold
                for kept_detection in kept
            ):
                continue

            kept.append(detection)

        return kept

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

    def _is_text_only_prompt(self, prompt_spec: PromptSpec) -> bool:
        # si no hay exemplars reales no hace falta salir de la ruta clásica de texto
        return prompt_spec.mode == "text" or not prompt_spec.exemplars

    def _uses_cuda_device(self) -> bool:
        return str(self.device).startswith("cuda")

    def _to_numpy(self, value: Any) -> np.ndarray:
        if torch.is_tensor(value):
            # numpy no soporta bfloat16, así que antes lo subimos a float32
            if value.dtype == torch.bfloat16:
                value = value.float()
            return value.detach().cpu().numpy()

        return np.asarray(value)
