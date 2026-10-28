from __future__ import annotations

from typing import Any

# Filtro previo: que detecciones de PIIA-1 llegan al modelo de vision. Sin el,
# SAM3 (baseline, score >= 0.3) deja ~37 detecciones por imagen, el 97 % falsas
# en dent/scratch/crack, y pagarias el modelo por cada una.
#
# Valores medidos sobre 500 imagenes de val/test (ver
# specs/agente-confianza-hallazgos.md, seccion "Filtro previo"):
# - glass shatter: el score SI separa (a >= 0.5 queda el 97 % del recall con
#   262 detecciones).
# - lamp broken / tire flat: el score casi no separa, pero con las 2 mejores
#   por imagen se recupera el 94 % y el 100 %.
# - dent / scratch / crack: ni el score ni top-k recuperan mucho (techo de
#   SAM3); mas de 2 por imagen cuesta llamadas y casi no suma recall.
# Total: ~3.700 llamadas para 500 imagenes en vez de 18.507.
FILTRO_PREVIO: dict[str, dict[str, float | int]] = {
    "glass shatter": {"score_min": 0.5},
    "lamp broken": {"top_k": 2},
    "tire flat": {"top_k": 2},
    "dent": {"top_k": 2},
    "scratch": {"top_k": 2},
    "crack": {"top_k": 2},
}
FILTRO_POR_DEFECTO: dict[str, float | int] = {"top_k": 2}  # clase desconocida


def seleccionar_candidatos(
    predictions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Aplica `FILTRO_PREVIO` por clase a las predicciones de una imagen.

    Devuelve (candidatas en su orden original, nº de descartadas por clase).
    Una prediccion se queda si supera `score_min` (cuando la clase lo define)
    y esta entre las `top_k` de su clase por score (cuando lo define).
    """
    por_clase: dict[str, list[dict[str, Any]]] = {}
    for pred in predictions:
        por_clase.setdefault(pred["damage_class"], []).append(pred)

    elegidas: set[int] = set()
    descartadas: dict[str, int] = {}
    for clase, preds in por_clase.items():
        regla = FILTRO_PREVIO.get(clase, FILTRO_POR_DEFECTO)
        ordenadas = sorted(preds, key=lambda p: p["score"], reverse=True)
        if "score_min" in regla:
            ordenadas = [p for p in ordenadas if p["score"] >= regla["score_min"]]
        if "top_k" in regla:
            ordenadas = ordenadas[: int(regla["top_k"])]
        elegidas.update(id(p) for p in ordenadas)
        if len(ordenadas) < len(preds):
            descartadas[clase] = len(preds) - len(ordenadas)

    candidatas = [p for p in predictions if id(p) in elegidas]
    return candidatas, descartadas
