from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    # rutas base del proyecto.
    app_root: Path
    ml_root: Path
    models_root: Path
    # artefactos que necesita la api para inferir.
    sam3_model_path: Path
    flat_tire_cache_path: Path
    broken_lamp_cache_path: Path


# este archivo vive en ml/api/core, así que parents[3] es la raíz app/.
APP_ROOT = Path(__file__).resolve().parents[3]
ML_ROOT = APP_ROOT / "ml"
# El código vive dentro de entregas/<caso>/app/. Los modelos no se versionan;
# por defecto se buscan en la raíz del repositorio y se puede sobrescribir la
# ruta mediante ML_API_MODEL_PATH.
MODELS_ROOT = APP_ROOT.parents[2] / "models"

# agrupamos todas las rutas en un único objeto para no repartir constantes sueltas.
paths = Paths(
    app_root=APP_ROOT,
    ml_root=ML_ROOT,
    models_root=MODELS_ROOT,
    sam3_model_path=MODELS_ROOT / "facebook_sam3",
    flat_tire_cache_path=(
        ML_ROOT
        / "config"
        / "tip_adapter"
        / "flat_tire"
        / "cropped_embeddings_001"
        / "cache.pt"
    ),
    broken_lamp_cache_path=(
        ML_ROOT
        / "config"
        / "tip_adapter"
        / "broken_lamp"
        / "cropped_embeddings_001"
        / "cache.pt"
    ),
)
