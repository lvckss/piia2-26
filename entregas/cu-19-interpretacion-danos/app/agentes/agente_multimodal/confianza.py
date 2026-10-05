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
    """Primer filtro, solo con el score de PIIA-1: `confirmed` si pasa el
    umbral de su clase, `needs_review` si no.

    Un falso positivo con score alto seria una afirmacion economica falsa en
    el informe; un falso negativo simplemente omite un dano real. Por eso el
    umbral es por clase, no un unico numero global (ver spec).
    """
    threshold = CATEGORY_REVIEW_THRESHOLD.get(category_name, DEFAULT_REVIEW_THRESHOLD)
    return "confirmed" if score >= threshold else "needs_review"


def decidir_tier(
    category_name: str,
    score: float,
    vision_verdict: str | None,
    pieza_id: str | None,
    regla_coste_aplicable: bool | None,
) -> ConfidenceTier:
    """Tier final: `confirmed` solo si coinciden las tres condiciones. Nada
    se descarta aqui; lo que no cumple alguna queda como `needs_review` y el
    informe lo presenta como pendiente de verificacion.

    1. el score de PIIA-1 pasa el umbral de su clase,
    2. el modelo de vision confirma el dano (segunda opinion),
    3. se sabe sobre que pieza esta y la tool de costes tiene una regla para
       esa clase + pieza + severidad (si no, no se puede presupuestar).
    """
    if classify_confidence(category_name, score) != "confirmed":
        return "needs_review"
    if vision_verdict != "confirmado":
        return "needs_review"
    if pieza_id is None or regla_coste_aplicable is not True:
        return "needs_review"
    return "confirmed"
