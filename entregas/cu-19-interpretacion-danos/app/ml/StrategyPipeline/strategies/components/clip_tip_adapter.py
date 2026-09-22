import json
from dataclasses import dataclass
from PIL import Image
from pathlib import Path

from transformers import CLIPModel, CLIPProcessor
from transformers.utils import logging as hf_logging

hf_logging.set_verbosity_error()
hf_logging.disable_progress_bar()

import torch
from torch.nn import functional as F


@dataclass(frozen=True)
class RoiVerifierConfig:
    # configuración de una clase verificable, por ejemplo tire flat o lamp broken
    target_category_id: int
    positive_label: str
    negative_label: str
    proposal_prompts: list[str]
    positive_text_prompts: list[str]
    negative_text_prompts: list[str]
    cache_path: str

    alpha: float = 2.0  # peso que se le da al cache key-value del tip adapter
    # si alfa es bajo, manda más CLIP con prompts (zero-shot)
    # si alfa es alto, manda más el cache de los ejemplos (few shot)

    beta: float = 50.0  # representa el nivel de afinidad con los ejemplos del cache
    # si beta es muy bajo, muchos ejemplos del cache aportan algo
    # si beta es muy alto, solo aportan mucho los ejemplos más parecidos

    threshold: float = 0.5  # umbral mínimo para aceptar la clase POSITIVA
    crop_padding_frac: float = 0.25  # margen extra alrededor del ROI antes de pasar el prompt a CLIP
    max_proposals_per_image: int = 2  # máximo número de ROIs que se van a verificar por imagen
    clip_model_name: str = "openai/clip-vit-base-patch32"

    @classmethod
    def simple(
        cls,
        *,
        target_category_id: int,
        proposal_prompt: str,
        cache_path: str,
        positive_label: str | None = None,
        negative_label: str | None = None,
        positive_text_prompts: list[str] | None = None,
        negative_text_prompts: list[str] | None = None,
        metadata_path: str | None = None,
        alpha: float = 2.0,
        beta: float = 50.0,
        threshold: float = 0.5,
        crop_padding_frac: float = 0.25,
        max_proposals_per_image: int = 2,
        clip_model_name: str | None = None,
    ) -> "RoiVerifierConfig":
        # helper corto para no tener que escribir el RoiVerifierConfig completo a mano
        cache_defaults = _load_tip_adapter_cache_defaults(
            cache_path=cache_path,
            metadata_path=metadata_path,
        )

        effective_positive_label = (
            positive_label
            or cache_defaults.get("positive_label")
        )
        effective_negative_label = (
            negative_label
            or cache_defaults.get("negative_label")
        )

        if not effective_positive_label:
            raise ValueError(
                "No se pudo resolver positive_label. "
                "Pásalo manualmente o asegura que exista cache_metadata.json."
            )

        if not effective_negative_label:
            raise ValueError(
                "No se pudo resolver negative_label. "
                "Pásalo manualmente o asegura que exista cache_metadata.json."
            )

        effective_clip_model_name = (
            clip_model_name
            or cache_defaults.get("clip_model_name")
            or "openai/clip-vit-base-patch32"
        )

        effective_positive_text_prompts = (
            positive_text_prompts
            or _default_binary_class_prompts(effective_positive_label)
        )
        effective_negative_text_prompts = (
            negative_text_prompts
            or _default_binary_class_prompts(effective_negative_label)
        )

        return cls(
            target_category_id=target_category_id,
            positive_label=effective_positive_label,
            negative_label=effective_negative_label,
            proposal_prompts=[proposal_prompt],
            positive_text_prompts=effective_positive_text_prompts,
            negative_text_prompts=effective_negative_text_prompts,
            cache_path=cache_path,
            alpha=alpha,
            beta=beta,
            threshold=threshold,
            crop_padding_frac=crop_padding_frac,
            max_proposals_per_image=max_proposals_per_image,
            clip_model_name=effective_clip_model_name,
        )


# EJEMPLO DE ROI_VERIFIER_CONFIG:
# RoiVerifierConfig(
#     target_category_id=1,
#     positive_label="tire flat",
#     negative_label="tire healthy",
#     proposal_prompts=["a photo of a car tire"],
#     positive_text_prompts=[
#         "a photo of a flat tire",
#         "a photo of a deflated tire",
#     ],
#     negative_text_prompts=[
#         "a photo of a healthy tire",
#         "a photo of a properly inflated tire",
#     ],
#     cache_path="ml/config/tip_adapter/flat_tire/cropped_embeddings_001/cache.pt",
#     alpha=2.0,
#     beta=50.0,
#     threshold=0.5,
#     crop_padding_frac=0.25,
#     max_proposals_per_image=2,
#     clip_model_name="openai/clip-vit-base-patch32",
# ),


@dataclass(frozen=True)
class VerificationResult:
    # resultado que usará la estrategia para decidir si conserva o descarta la roi
    predicted_label: str
    is_positive: bool
    positive_score: float
    negative_score: float
    positive_logit: float
    negative_logit: float


class ClipTipAdapterRoiVerifier:
    # recibe crops ya propuestos por SAM3 y decide positive vs negative con CLIP + tip-adapter
    def __init__(
        self,
        config: RoiVerifierConfig,
        device: str | None = None,
    ) -> None:
        # guarda la config y usa gpu si está disponible
        self.config = config
        self._validate_config()
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        # carga CLIP congelado
        self.model = CLIPModel.from_pretrained(config.clip_model_name).to(self.device)
        self.processor = CLIPProcessor.from_pretrained(config.clip_model_name)
        self.model.eval()

        # carga el cache few-shot y deja preparados los embeddings de texto
        self.cache_embeddings, self.cache_values = self._load_cache(config.cache_path)
        self.text_embeddings = self._build_text_embeddings()
        self._validate_cache_embedding_dim()

        with torch.no_grad():
            self.logit_scale = self.model.logit_scale.exp().to(self.device)

        print("[CLIP cargado correctamente!] ◝(ᵔᵕᵔ)◜")

    def _validate_config(self) -> None:
        # valida solo lo necesario para fallar pronto con mensajes claros
        if self.config.target_category_id <= 0:
            raise ValueError("target_category_id debe ser positivo.")

        if not self.config.positive_label.strip():
            raise ValueError("positive_label no puede estar vacío.")

        if not self.config.negative_label.strip():
            raise ValueError("negative_label no puede estar vacío.")

        if not self.config.clip_model_name.strip():
            raise ValueError("clip_model_name no puede estar vacío.")

        if not self.config.cache_path.strip():
            raise ValueError("cache_path no puede estar vacío.")

        if not self.config.proposal_prompts:
            raise ValueError("proposal_prompts no puede estar vacío.")

        if not self.config.positive_text_prompts:
            raise ValueError("positive_text_prompts no puede estar vacío.")

        if not self.config.negative_text_prompts:
            raise ValueError("negative_text_prompts no puede estar vacío.")

        if self.config.alpha < 0:
            raise ValueError("alpha debe ser >= 0.")

        if self.config.beta < 0:
            raise ValueError("beta debe ser >= 0.")

        if not 0.0 <= self.config.threshold <= 1.0:
            raise ValueError("threshold debe estar en [0, 1].")

        if self.config.crop_padding_frac < 0:
            raise ValueError("crop_padding_frac debe ser >= 0.")

        if self.config.max_proposals_per_image <= 0:
            raise ValueError("max_proposals_per_image debe ser > 0.")

    def _validate_cache_embedding_dim(self) -> None:
        # el cache solo es válido si se generó con el mismo CLIP
        if self.cache_embeddings.shape[1] != self.text_embeddings.shape[1]:
            raise ValueError(
                "cache_embeddings no coincide con la dimensión de CLIP: "
                f"cache_dim={self.cache_embeddings.shape[1]}, "
                f"clip_dim={self.text_embeddings.shape[1]}"
            )

    def verify_batch(self, crops: list[Image.Image]) -> list[VerificationResult]:
        # si no hay crops, no hay nada que verificar
        if not crops:
            return []

        # convierte todos los crops en embeddings CLIP normalizados
        image_embeddings = self._encode_images(crops)

        # logits zero-shot de CLIP contra los prompts de positive y negative
        clip_logits = self._compute_clip_logits(image_embeddings)

        # logits few-shot del cache key-value de tip-adapter
        cache_logits = self._compute_cache_logits(image_embeddings)

        final_logits = clip_logits + self.config.alpha * cache_logits
        probs = torch.softmax(final_logits, dim=-1)  # dim -1 porque las clases están en la última dimensión

        results = []
        for logit_row, prob_row in zip(final_logits, probs):
            # por convención, columna 0 es positive y columna 1 es negative
            positive_score = float(prob_row[0])
            negative_score = float(prob_row[1])
            is_positive = (
                positive_score >= self.config.threshold
                and positive_score >= negative_score
            )

            results.append(
                VerificationResult(
                    predicted_label=(
                        self.config.positive_label
                        if positive_score >= negative_score
                        else self.config.negative_label
                    ),
                    is_positive=is_positive,
                    positive_score=positive_score,
                    negative_score=negative_score,
                    positive_logit=float(logit_row[0]),
                    negative_logit=float(logit_row[1]),
                )
            )

        return results

    def verify(self, crop: Image.Image) -> VerificationResult:
        # wrapper cómodo para cuando solo se quiere verificar un crop
        return self.verify_batch([crop])[0]

    def _compute_cache_logits(self, image_embeddings: torch.Tensor) -> torch.Tensor:
        # compara cada crop contra todos los ejemplos del cache
        affinity = image_embeddings @ self.cache_embeddings.T

        # beta controla cuánto pesan los ejemplos más parecidos frente al resto
        cache_logits = (
            torch.exp(-self.config.beta * (1.0 - affinity)) @ self.cache_values
        )

        return cache_logits

    def _compute_clip_logits(self, image_embeddings: torch.Tensor) -> torch.Tensor:
        # similitud zero-shot entre el crop y los embeddings de texto de cada clase
        return self.logit_scale * (image_embeddings @ self.text_embeddings.T)

    def _encode_images(self, crops: list[Image.Image]) -> torch.Tensor:
        # el processor aplica el preprocesado esperado por CLIP
        inputs = self.processor(
            images=crops,
            return_tensors="pt",
        )

        # solo los tensores se mueven al dispositivo, el resto se ignora aquí
        inputs = {
            key: value.to(self.device)
            for key, value in inputs.items()
            if torch.is_tensor(value)
        }

        # extrae embeddings visuales sin gradiente
        with torch.no_grad():
            image_output = self.model.get_image_features(**inputs)
            image_embeddings = self._extract_pooled_embeddings(image_output)

        # normaliza para que el producto escalar sea similitud coseno
        return F.normalize(image_embeddings, dim=-1)

    def _build_text_embeddings(self) -> torch.Tensor:
        # se mantiene el orden: primero positive, luego negative
        prompts = [
            self.config.positive_text_prompts,
            self.config.negative_text_prompts,
        ]

        class_embeddings = []

        for class_prompts in prompts:
            # cada clase puede tener varios prompts, luego se promedian
            inputs = self.processor(
                text=class_prompts,
                return_tensors="pt",
                padding=True,
            )

            inputs = {
                key: value.to(self.device)
                for key, value in inputs.items()
                if torch.is_tensor(value)
            }

            with torch.no_grad():
                text_output = self.model.get_text_features(**inputs)
                text_embeddings = self._extract_pooled_embeddings(text_output)

            # prompt ensembling simple: normalizar, promediar y normalizar otra vez
            text_embeddings = F.normalize(text_embeddings, dim=-1)
            class_embeddings.append(F.normalize(text_embeddings.mean(dim=0), dim=0))

        return torch.stack(class_embeddings, dim=0)

    def _extract_pooled_embeddings(self, model_output: object) -> torch.Tensor:
        # transformers 5 devuelve pooler_output; versiones anteriores devuelven el tensor directamente
        if torch.is_tensor(model_output):
            return model_output

        if hasattr(model_output, "pooler_output") and model_output.pooler_output is not None:
            return model_output.pooler_output

        if isinstance(model_output, (tuple, list)):
            if len(model_output) > 1 and torch.is_tensor(model_output[1]):
                return model_output[1]

            if len(model_output) > 0 and torch.is_tensor(model_output[0]):
                return model_output[0]

        raise TypeError(
            "CLIP devolvió un output sin tensor de embeddings usable. "
            f"tipo recibido={type(model_output)!r}"
        )

    def _load_cache(self, cache_path: str) -> tuple[torch.Tensor, torch.Tensor]:
        # cache esperado -> embeddings de crops y etiquetas one-hot
        cache = torch.load(Path(cache_path), map_location=self.device)

        if "cache_keys" not in cache or "cache_values" not in cache:
            raise ValueError("el cache debe contener cache_keys y cache_values.")

        # cache_keys: embeddings CLIP de crops few-shot
        # cache_values: etiquetas one-hot
        cache_embeddings = cache["cache_keys"].to(self.device).float()
        cache_values = cache["cache_values"].to(self.device).float()

        if cache_embeddings.ndim != 2:
            raise ValueError(
                f"cache_embeddings debe ser 2D, shape recibido={tuple(cache_embeddings.shape)}"
            )

        if cache_values.ndim != 2:
            raise ValueError(
                f"cache_values debe ser 2D, shape recibido={tuple(cache_values.shape)}"
            )

        if cache_embeddings.shape[0] != cache_values.shape[0]:
            raise ValueError(
                "cache_embeddings y cache_values deben tener el mismo número de ejemplos: "
                f"embeddings={cache_embeddings.shape[0]}, values={cache_values.shape[0]}"
            )

        if cache_values.shape[1] != 2:
            raise ValueError(
                "cache_values debe tener 2 columnas: positive y negative. "
                f"shape recibido={tuple(cache_values.shape)}"
            )

        # normaliza los embeddings del cache para comparar por similitud coseno
        cache_embeddings = F.normalize(cache_embeddings, dim=-1)

        return cache_embeddings, cache_values


def simple_roi_verifier_config(
    *,
    target_category_id: int,
    proposal_prompt: str,
    cache_path: str,
    positive_label: str | None = None,
    negative_label: str | None = None,
    positive_text_prompts: list[str] | None = None,
    negative_text_prompts: list[str] | None = None,
    metadata_path: str | None = None,
    alpha: float = 2.0,
    beta: float = 50.0,
    threshold: float = 0.5,
    crop_padding_frac: float = 0.25,
    max_proposals_per_image: int = 2,
    clip_model_name: str | None = None,
) -> RoiVerifierConfig:
    # función espejo para que en notebooks se vea más directo que usar el classmethod
    return RoiVerifierConfig.simple(
        target_category_id=target_category_id,
        proposal_prompt=proposal_prompt,
        cache_path=cache_path,
        positive_label=positive_label,
        negative_label=negative_label,
        positive_text_prompts=positive_text_prompts,
        negative_text_prompts=negative_text_prompts,
        metadata_path=metadata_path,
        alpha=alpha,
        beta=beta,
        threshold=threshold,
        crop_padding_frac=crop_padding_frac,
        max_proposals_per_image=max_proposals_per_image,
        clip_model_name=clip_model_name,
    )


def _default_binary_class_prompts(label: str) -> list[str]:
    # si el usuario no define prompts de texto, generamos unos razonables a partir de la etiqueta
    normalized_label = " ".join(label.strip().split())
    return [
        f"a photo of a {normalized_label}",
        f"a close-up of a {normalized_label}",
    ]


def _load_tip_adapter_cache_defaults(
    *,
    cache_path: str,
    metadata_path: str | None,
) -> dict[str, str]:
    # intentamos recuperar labels y clip_model_name desde el metadata json del cache
    resolved_metadata_path = _resolve_tip_adapter_metadata_path(
        cache_path=cache_path,
        metadata_path=metadata_path,
    )

    if resolved_metadata_path is None or not resolved_metadata_path.exists():
        return {}

    with resolved_metadata_path.open(encoding="utf-8") as metadata_file:
        metadata = json.load(metadata_file)

    if not isinstance(metadata, dict):
        return {}

    defaults: dict[str, str] = {}

    positive_label = metadata.get("positive_label") or metadata.get("positive_dir_name")
    negative_label = metadata.get("negative_label") or metadata.get("negative_dir_name")
    clip_model_name = metadata.get("clip_model_name")

    if isinstance(positive_label, str) and positive_label.strip():
        defaults["positive_label"] = _normalize_tip_adapter_label(positive_label)

    if isinstance(negative_label, str) and negative_label.strip():
        defaults["negative_label"] = _normalize_tip_adapter_label(negative_label)

    if isinstance(clip_model_name, str) and clip_model_name.strip():
        defaults["clip_model_name"] = clip_model_name.strip()

    return defaults


def _resolve_tip_adapter_metadata_path(
    *,
    cache_path: str,
    metadata_path: str | None,
) -> Path | None:
    if metadata_path is not None:
        return Path(metadata_path).expanduser().resolve()

    cache_file = Path(cache_path).expanduser().resolve()
    if cache_file.is_dir():
        return cache_file / "cache_metadata.json"

    return cache_file.parent / "cache_metadata.json"


def _normalize_tip_adapter_label(label: str) -> str:
    # convertimos nombres de carpeta tipo broken_lamp en etiquetas legibles
    return " ".join(label.replace("_", " ").strip().split())
