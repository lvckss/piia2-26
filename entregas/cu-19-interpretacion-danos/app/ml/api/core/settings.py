from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from ml.api.core.paths import paths


DEFAULT_CATEGORY_MAP = {
    1: "dent",
    2: "scratch",
    3: "crack",
    4: "glass shatter",
    5: "lamp broken",
    6: "tire flat",
}

DEFAULT_PROMPT_MAP = {
    1: "a visible dent on the metal body of a car",
    2: "a visible scratch on the painted surface of a car",
    3: "a visible crack on a car part or surface",
    4: "shattered or broken car window glass",
    5: "a broken or damaged car headlamp or tail lamp",
    6: "a flat or deflated car tire",
}


# os.getenv siempre devuelve texto o none.
# estos helpers convierten eso a tipos más útiles para settings.
def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: list[str]) -> list[str]:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default

    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _env_path(
    primary_name: str,
    default: Path,
    *,
    fallback_name: str | None = None,
) -> Path:
    raw_value = os.getenv(primary_name)
    if raw_value is None and fallback_name is not None:
        raw_value = os.getenv(fallback_name)

    if raw_value is None or not raw_value.strip():
        return default

    return Path(raw_value).expanduser()


@dataclass(frozen=True)
class Settings:
    # datos básicos del servicio http.
    app_name: str = "Vehicle Damage Assessment API"
    api_prefix: str = "/v1"

    host: str = field(default_factory=lambda: os.getenv("ML_API_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.getenv("ML_API_PORT", "8001")))

    # cors mínimo para desarrollo local con server o frontend.
    cors_allow_origins: list[str] = field(
        default_factory=lambda: _env_list(
            "ML_API_CORS_ALLOW_ORIGINS",
            [
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            ],
        )
    )

    # aquí elegimos qué strategy del pipeline usa la api.
    strategy_name: str = field(
        default_factory=lambda: os.getenv("ML_API_STRATEGY", "baseline")
    )
    device: str | None = field(
        default_factory=lambda: os.getenv("ML_API_DEVICE") or None
    )

    # thresholds de inferencia del backend.
    score_threshold: float = field(
        default_factory=lambda: float(os.getenv("ML_API_SCORE_THRESHOLD", "0.6"))
    )
    mask_threshold: float = field(
        default_factory=lambda: float(os.getenv("ML_API_MASK_THRESHOLD", "0.5"))
    )
    prompt_batch_size: int = field(
        default_factory=lambda: int(os.getenv("ML_API_PROMPT_BATCH_SIZE", "6"))
    )

    # la visualización es opcional porque aumenta bastante la respuesta.
    include_visualization_by_default: bool = field(
        default_factory=lambda: _env_bool(
            "ML_API_INCLUDE_VISUALIZATION",
            False,
        )
    )
    visualization_format: str = field(
        default_factory=lambda: os.getenv("ML_API_VISUALIZATION_FORMAT", "PNG").upper()
    )

    enable_roi_verification: bool = field(
        default_factory=lambda: _env_bool(
            "ML_API_ENABLE_ROI_VERIFICATION",
            False,
        )
    )

    # estas rutas vienen ya resueltas desde core.paths.
    app_root: Path = field(default_factory=lambda: paths.app_root)
    ml_root: Path = field(default_factory=lambda: paths.ml_root)
    model_path: Path = field(
        default_factory=lambda: _env_path(
            "ML_API_MODEL_PATH",
            paths.sam3_model_path,
            fallback_name="SAM3_MODEL_PATH",
        )
    )
    flat_tire_cache_path: Path = field(
        default_factory=lambda: _env_path(
            "ML_API_FLAT_TIRE_CACHE_PATH",
            paths.flat_tire_cache_path,
        )
    )
    broken_lamp_cache_path: Path = field(
        default_factory=lambda: _env_path(
            "ML_API_BROKEN_LAMP_CACHE_PATH",
            paths.broken_lamp_cache_path,
        )
    )

    # mapa del problema y prompts por defecto.
    category_map: dict[int, str] = field(
        default_factory=lambda: dict(DEFAULT_CATEGORY_MAP)
    )
    prompt_map: dict[int, str] = field(
        default_factory=lambda: dict(DEFAULT_PROMPT_MAP)
    )

    def __post_init__(self) -> None:
        # validamos lo mínimo para fallar pronto si la configuración viene mal.
        if self.strategy_name not in {"baseline", "sahi", "geometric_ensemble"}:
            raise ValueError(
                "strategy_name debe ser 'baseline', 'sahi' o 'geometric_ensemble'."
            )

        if not 0.0 <= self.score_threshold <= 1.0:
            raise ValueError("score_threshold debe estar en [0, 1].")

        if not 0.0 <= self.mask_threshold <= 1.0:
            raise ValueError("mask_threshold debe estar en [0, 1].")

        if self.prompt_batch_size <= 0:
            raise ValueError("prompt_batch_size debe ser > 0.")

        if self.visualization_format not in {"PNG", "JPEG"}:
            raise ValueError("visualization_format debe ser 'PNG' o 'JPEG'.")


# instancia única de settings para el resto de la api.
settings = Settings()
