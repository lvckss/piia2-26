from __future__ import annotations

from ml.StrategyPipeline.schemas import StrategyContractError

# valores por defecto de threshold compartidos por las tres strategies del
# pipeline (baseline, sahi, geometric ensemble) y por ml/api/core/settings.py.
#
# antes de este modulo cada strategy tenia su propio default hardcodeado
# (baseline=0.3, sahi=0.8, geom_ensemble=0.3, settings.py=0.6), asi que "no
# pasar score_threshold" daba un resultado distinto segun la strategy usada.
#
# si una strategy concreta necesita de verdad un valor distinto (por ejemplo
# geom_ensemble suele calibrarse mas bajo porque filtra por consenso despues),
# ese valor debe pasarse explicitamente en la construccion, nunca quedar como
# default silencioso de la clase.
DEFAULT_SCORE_THRESHOLD: float = 0.6
DEFAULT_MASK_THRESHOLD: float = 0.5


def resolve_score_threshold_map(
    category_map: dict[int, str],
    score_threshold_map: dict[int, float] | None,
    fallback_threshold: float,
) -> dict[int, float]:
    """Resuelve el umbral de score efectivo para cada categoria.

    El desequilibrio de CarDD (scratch 41%, tire_flat 3.6%) hace que un unico
    score_threshold global perjudique a las clases minoritarias. Esta funcion
    permite calibrar un umbral distinto por clase (apoyandose en
    output.per_class del Evaluator) sin tocar las clases que no se calibran,
    que siguen usando fallback_threshold exactamente como antes.
    """
    if score_threshold_map:
        for category_id, threshold in score_threshold_map.items():
            if category_id not in category_map:
                raise StrategyContractError(
                    "score_threshold_map contiene un category_id que no existe "
                    f"en category_map: category_id={category_id}"
                )
            if not 0.0 <= threshold <= 1.0:
                raise StrategyContractError(
                    "score_threshold_map debe tener valores en [0, 1]: "
                    f"category_id={category_id}, threshold={threshold}"
                )

    return {
        category_id: (
            score_threshold_map[category_id]
            if score_threshold_map and category_id in score_threshold_map
            else fallback_threshold
        )
        for category_id in category_map
    }
