from __future__ import annotations

from typing import Literal

ConfidenceTier = Literal["confirmed", "needs_review"]

# PENDIENTE de calibrar con el barrido de thresholds extendido a las 6 clases
# (ver entregas/cu-19-interpretacion-danos/specs/agente-confianza-hallazgos.md).
# Estos valores son un punto de partida razonable, no un resultado medido.
CATEGORY_REVIEW_THRESHOLD: dict[str, float] = {
    "dent": 0.7,
    "scratch": 0.7,
    "crack": 0.7,
    "lamp broken": 0.6,
    "glass shatter": 0.6,
    "tire flat": 0.6,
}

# categoria desconocida -> conservador, mejor pedir revision de mas que de menos
DEFAULT_REVIEW_THRESHOLD = 0.8


def classify_confidence(category_name: str, score: float) -> ConfidenceTier:
    """Decide si un hallazgo se puede afirmar (`confirmed`) o si el informe
    debe presentarlo como pendiente de verificacion humana (`needs_review`).

    Un falso positivo con score alto seria una afirmacion economica falsa en
    el informe; un falso negativo simplemente omite un dano real. Por eso el
    umbral es por clase, no un unico numero global (ver spec).
    """
    threshold = CATEGORY_REVIEW_THRESHOLD.get(category_name, DEFAULT_REVIEW_THRESHOLD)
    return "confirmed" if score >= threshold else "needs_review"
