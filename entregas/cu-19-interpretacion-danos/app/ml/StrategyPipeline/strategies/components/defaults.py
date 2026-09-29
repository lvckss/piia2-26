from __future__ import annotations

from typing import Any

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


# category_map/prompt_map por defecto para el problema de daños de CarDD.
#
# antes de este modulo esta misma tabla estaba duplicada de forma independiente
# en ml/api/core/settings.py, ml/StrategyPipeline/evaluation/evaluator.py y
# ml/notebooks/utils/notebook_utils.py; cada copia podia irse desincronizando
# de las otras sin que nadie lo notara. Ahora las tres importan esta.
DEFAULT_CATEGORY_MAP: dict[int, str] = {
    1: "dent",
    2: "scratch",
    3: "crack",
    4: "glass shatter",
    5: "lamp broken",
    6: "tire flat",
}

# variante "v1": la que ya se usaba en README_EVALUACION.md y settings.py.
DEFAULT_PROMPT_MAP: dict[int, str] = {
    1: "a visible dent on the metal body of a car",
    2: "a visible scratch on the painted surface of a car",
    3: "a visible crack on a car part or surface",
    4: "shattered or broken car window glass",
    5: "a broken or damaged car headlamp or tail lamp",
    6: "a flat or deflated car tire",
}

# variante "v2": candidata sin validar para la tarea de mejorar prompts.
# cambia "car" por "vehicle" (menos sesgo hacia turismos frente a
# camiones/furgonetas/motos, ver mejora-robustez-tipos-vehiculo.md) y
# redacta cada frase de forma distinta a la v1, para poder compararla con
# output.per_class sobre val antes de decidir cual usar por defecto.
DEFAULT_PROMPT_MAP_V2: dict[int, str] = {
    1: "a dent deforming the sheet metal panel of a vehicle",
    2: "a scratch mark scraped into the paint of a vehicle",
    3: "a visible crack fracturing a vehicle part or surface",
    4: "a vehicle window or windshield with shattered glass",
    5: "a vehicle headlight or taillight that is cracked or broken",
    6: "a vehicle tire that looks flat or deflated",
}


def resolve_prompt_map(
    category_map: dict[int, str],
    prompt_map: dict[int, Any] | None,
    *,
    default_prompt_map: dict[int, str] = DEFAULT_PROMPT_MAP,
) -> dict[int, Any]:
    """Resuelve el prompt_map efectivo sin caer nunca en el nombre desnudo de
    la categoria como prompt de texto.

    Antes, las tres strategies hacian `dict(prompt_map or category_map)`, asi
    que si no se pasaba prompt_map (o se pasaba uno incompleto), SAM3 acababa
    recibiendo literalmente "dent" o "tire flat" como prompt en vez de una
    descripcion real. Aqui, cualquier category_id sin prompt explicito cae en
    default_prompt_map (bien redactado); si tampoco esta ahi, se lanza un
    error en vez de degradar en silencio.
    """
    caller_prompt_map = dict(prompt_map) if prompt_map else {}

    resolved: dict[int, Any] = {}
    missing_category_ids: list[int] = []

    for category_id in category_map:
        if category_id in caller_prompt_map:
            resolved[category_id] = caller_prompt_map[category_id]
        elif category_id in default_prompt_map:
            resolved[category_id] = default_prompt_map[category_id]
        else:
            missing_category_ids.append(category_id)

    if missing_category_ids:
        raise StrategyContractError(
            "No se paso prompt_map (o esta incompleto) y las siguientes "
            "category_id no tienen un prompt por defecto conocido, asi que "
            "no hay forma de resolverlas sin caer en el nombre desnudo de la "
            f"categoria: category_ids={missing_category_ids}. Pasa un "
            "prompt_map explicito para esas categorias."
        )

    return resolved
