from __future__ import annotations

from ml.StrategyPipeline.schemas import ImageSample, StrategyResult
from ml.StrategyPipeline.strategies.base import StrategyModule


class VehicleDamagePredictor:
    def __init__(self, strategy: StrategyModule) -> None:
        # guardamos la strategy real detrás de una interfaz más simple para la api.
        self._strategy = strategy

    @property
    def category_map(self) -> dict[int, str]:
        return self._strategy.category_map

    @property
    def strategy_name(self) -> str:
        return self._strategy.strategy_name

    def predict(self, sample: ImageSample) -> StrategyResult:
        # la api solo necesita pedir una predicción para una imagen.
        return self._strategy.run(sample)

    def close(self) -> None:
        # hook reservado por si más adelante el predictor necesita limpiar recursos.
        return None
