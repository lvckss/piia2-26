from __future__ import annotations

import time
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np
from PIL import Image

from ml.StrategyPipeline.schemas import (
    ImageSample,
    InstancePrediction,
    RuntimeStats,
    SampleRef,
    StrategyResult,
)

import torch

# CLASE ABSTRACTA QUE TODAS LAS ESTRATEGIAS DEBEN HEREDAR PARA GARANTIZAR CONTRATO CON EL PIPELINE


class StrategyContractError(ValueError):
    """El strategy no respeta el contrato esperado del pipeline."""


class StrategyModule(ABC):
    def __init__(self, strategy_name: str, category_map: dict[int, str]) -> None:
        if not strategy_name or not strategy_name.strip():
            raise StrategyContractError("strategy_name no puede estar vacío.")
        if not category_map:
            raise StrategyContractError("category_map no puede estar vacío.")

        self.strategy_name = strategy_name.strip()
        self.category_map = dict(category_map)

    # ejecuta la estrategia y empaqueta su salida en un strategyresult
    def run(self, sample: ImageSample) -> StrategyResult:
        # valida la entrada antes de lanzar inferencia
        self._validate_sample(sample)

        # prepara la medición de tiempo y memoria de esta imagen
        self._reset_peak_vram_stats_if_needed()
        self._synchronize_device_if_needed()
        start = time.perf_counter()

        # delega la inferencia concreta en la estrategia hija
        predictions = self._predict_instances(sample)

        # cierra la medición cuando la gpu ha terminado de trabajar
        self._synchronize_device_if_needed()
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        peak_vram_mb = self._get_peak_vram_mb()

        # fuerza que la salida cumpla el contrato del pipeline
        validated_predictions = self._validate_predictions_output(
            sample,
            predictions,
        )

        return StrategyResult(
            strategy_name=self.strategy_name,
            sample=SampleRef(
                image_id=int(sample.image_id),
                width=int(sample.width),
                height=int(sample.height),
                split=sample.split,
                corruption=sample.corruption,
                severity=sample.severity,
                is_clean=bool(sample.is_clean),
            ),
            predictions=validated_predictions,
            runtime=RuntimeStats(
                inference_ms=elapsed_ms,
                peak_vram_mb=peak_vram_mb,
            ),
        )

    @abstractmethod
    def _predict_instances(self, sample: ImageSample) -> list[InstancePrediction]:
        """Devuelve la predicción consolidada para una única imagen."""

    # comprueba que el sample de entrada tenga un formato válido
    def _validate_sample(self, sample: ImageSample) -> None:
        # asegura que el pipeline reciba el tipo esperado
        if not isinstance(sample, ImageSample):
            raise StrategyContractError(
                "run() esperaba un ImageSample como entrada."
            )

        # la imagen debe tener un id y dimensiones válidas
        if sample.image_id < 0:
            raise StrategyContractError(
                f"image_id inválido: {sample.image_id}"
            )

        if sample.width <= 0 or sample.height <= 0:
            raise StrategyContractError(
                "Las dimensiones del sample deben ser positivas: "
                f"width={sample.width}, height={sample.height}"
            )

        if not sample.split or not sample.split.strip():
            raise StrategyContractError("sample.split no puede estar vacío.")

        # si no viene la imagen en memoria, al menos debe existir la ruta
        if not sample.image_path or not sample.image_path.strip():
            raise StrategyContractError("sample.image_path no puede estar vacío.")
        image_path = Path(sample.image_path)
        if sample.image is None and not image_path.exists():
            raise StrategyContractError(
                f"La imagen no existe en disco: {sample.image_path}"
            )

        # si ya viene cargada, comprueba que su forma coincida con el sample
        if sample.image is not None:
            image = np.asarray(sample.image)
            if image.ndim not in {2, 3}:
                raise StrategyContractError(
                    "sample.image debe ser un array HxW o HxWxC."
                )

            if image.shape[0] != sample.height or image.shape[1] != sample.width:
                raise StrategyContractError(
                    "La imagen cargada no coincide con las dimensiones declaradas: "
                    f"image.shape={image.shape}, "
                    f"expected=({sample.height}, {sample.width}, ...)"
                )

    # valida y normaliza las predicciones antes de devolverlas
    def _validate_predictions_output(
        self,
        sample: ImageSample,
        predictions: list[InstancePrediction],
    ) -> list[InstancePrediction]:
        # todas las estrategias deben devolver una lista de instancias
        if not isinstance(predictions, list):
            raise StrategyContractError(
                "_predict_instances() debe devolver list[InstancePrediction]."
            )

        expected_shape = (sample.height, sample.width)
        validated: list[InstancePrediction] = []

        for idx, prediction in enumerate(predictions):
            # comprueba que cada elemento ya venga envuelto en el schema correcto
            if not isinstance(prediction, InstancePrediction):
                raise StrategyContractError(
                    "_predict_instances() devolvió un elemento inválido en "
                    f"prediction_index={idx}: {repr(type(prediction))}"
                )

            # normaliza la máscara y verifica que use el mismo lienzo que la imagen
            mask = np.asarray(prediction.mask, dtype=bool)
            if mask.shape != expected_shape:
                raise StrategyContractError(
                    "La máscara de predicción no coincide con el sample: "
                    f"prediction_index={idx}, shape={mask.shape}, "
                    f"expected={expected_shape}"
                )

            # la clase predicha debe existir dentro del problema
            if prediction.category_id not in self.category_map:
                raise StrategyContractError(
                    "category_id de predicción desconocido para el strategy: "
                    f"prediction_index={idx}, category_id={prediction.category_id}"
                )

            # el score siempre debe quedar en rango probabilístico
            if not 0.0 <= float(prediction.score) <= 1.0:
                raise StrategyContractError(
                    "score fuera de rango [0, 1]: "
                    f"prediction_index={idx}, score={prediction.score}"
                )

            # la bbox se guarda en formato xywh
            if len(prediction.bbox) != 4:
                raise StrategyContractError(
                    "bbox inválida: "
                    f"prediction_index={idx}, bbox={prediction.bbox}"
                )

            # el área no puede ser negativa
            if float(prediction.area) < 0:
                raise StrategyContractError(
                    "area no puede ser negativa: "
                    f"prediction_index={idx}, area={prediction.area}"
                )

            # reconstruye la predicción con tipos consistentes para el resto del pipeline
            x, y, w, h = prediction.bbox
            validated.append(
                InstancePrediction(
                    category_id=int(prediction.category_id),
                    score=float(prediction.score),
                    mask=mask,
                    bbox=(float(x), float(y), float(w), float(h)),
                    area=float(prediction.area),
                    metadata=dict(prediction.metadata),
                )
            )

        return validated

    # carga la imagen desde memoria o desde disco si hace falta
    def _load_image_if_needed(self, sample: ImageSample) -> np.ndarray:
        # reutiliza la imagen ya cargada si el dataloader la trajo en memoria
        if sample.image is not None:
            return np.asarray(sample.image)

        image_path = Path(sample.image_path)
        if not image_path.exists():
            raise StrategyContractError(
                f"No se puede cargar la imagen porque no existe la ruta: {sample.image_path}"
            )

        # carga la imagen como rgb para que todas las estrategias la vean igual
        with Image.open(image_path) as image_file:
            image = np.asarray(image_file.convert("RGB"))

        # comprueba que el contenido cargado coincide con la metadata del sample
        if image.shape[0] != sample.height or image.shape[1] != sample.width:
            raise StrategyContractError(
                "La imagen cargada desde disco no coincide con el sample: "
                f"image.shape={image.shape}, "
                f"expected=({sample.height}, {sample.width}, 3)"
            )

        return image

    # reinicia la medición de pico de vram antes de inferir
    def _reset_peak_vram_stats_if_needed(self) -> None:
        if torch is None or not torch.cuda.is_available():
            return

        torch.cuda.reset_peak_memory_stats()

    # devuelve el pico de vram usado durante la inferencia
    def _get_peak_vram_mb(self) -> float | None:
        if torch is None or not torch.cuda.is_available():
            return None

        return float(torch.cuda.max_memory_allocated() / (1024 ** 2))

    # sincroniza cuda para medir tiempos reales de inferencia
    def _synchronize_device_if_needed(self) -> None:
        if torch is None or not torch.cuda.is_available():
            return

        torch.cuda.synchronize()
