from __future__ import annotations

from ...schemas import ImageSample, RunInfo, StrategyResult


class EvaluationContractError(ValueError):
    """El input del evaluator no respeta el contrato del pipeline."""


def validate_evaluator_input(
    run_info: RunInfo,
    sample: ImageSample,
    result: StrategyResult,
    category_map: dict[int, str],
) -> None:
    _validate_strategy_name(run_info, result)
    _validate_sample_alignment(sample, result)
    _validate_ground_truth(sample, category_map)
    _validate_runtime(result)
    _validate_predictions(sample, result, category_map)


def _validate_strategy_name(
    run_info: RunInfo,
    result: StrategyResult,
) -> None:
    if result.strategy_name != run_info.strategy_name:
        raise EvaluationContractError(
            "El StrategyResult no pertenece al strategy del run: "
            f"result.strategy_name={result.strategy_name!r}, "
            f"run_info.strategy_name={run_info.strategy_name!r}"
        )


def _validate_sample_alignment(
    sample: ImageSample,
    result: StrategyResult,
) -> None:
    ref = result.sample

    if ref.image_id != sample.image_id:
        raise EvaluationContractError(
            "image_id inconsistente entre sample y result.sample: "
            f"sample={sample.image_id}, result={ref.image_id}"
        )

    if ref.width != sample.width or ref.height != sample.height:
        raise EvaluationContractError(
            "Dimensiones inconsistentes entre sample y result.sample: "
            f"sample=({sample.width}, {sample.height}), "
            f"result=({ref.width}, {ref.height})"
        )

    if ref.split != sample.split:
        raise EvaluationContractError(
            "split inconsistente entre sample y result.sample: "
            f"sample={sample.split!r}, result={ref.split!r}"
        )

    if ref.corruption != sample.corruption:
        raise EvaluationContractError(
            "corruption inconsistente entre sample y result.sample: "
            f"sample={sample.corruption!r}, result={ref.corruption!r}"
        )

    if ref.severity != sample.severity:
        raise EvaluationContractError(
            "severity inconsistente entre sample y result.sample: "
            f"sample={sample.severity!r}, result={ref.severity!r}"
        )

    if ref.is_clean != sample.is_clean:
        raise EvaluationContractError(
            "is_clean inconsistente entre sample y result.sample: "
            f"sample={sample.is_clean}, result={ref.is_clean}"
        )


def _validate_ground_truth(
    sample: ImageSample,
    category_map: dict[int, str],
) -> None:
    expected_shape = (sample.height, sample.width)

    for idx, gt in enumerate(sample.gt_instances):
        if gt.mask.shape != expected_shape:
            raise EvaluationContractError(
                "Máscara de ground truth con shape inválido: "
                f"gt_index={idx}, shape={gt.mask.shape}, expected={expected_shape}"
            )

        if gt.category_id not in category_map:
            raise EvaluationContractError(
                "category_id de ground truth desconocido para el evaluator: "
                f"gt_index={idx}, category_id={gt.category_id}"
            )

        if gt.area < 0:
            raise EvaluationContractError(
                "Area de ground truth no puede ser negativa: "
                f"gt_index={idx}, area={gt.area}"
            )

        if len(gt.bbox) != 4:
            raise EvaluationContractError(
                "bbox de ground truth inválida: "
                f"gt_index={idx}, bbox={gt.bbox}"
            )


def _validate_runtime(
    result: StrategyResult,
) -> None:
    runtime = result.runtime

    if runtime.inference_ms < 0:
        raise EvaluationContractError(
            f"inference_ms no puede ser negativo: {runtime.inference_ms}"
        )

    if runtime.peak_vram_mb is not None and runtime.peak_vram_mb < 0:
        raise EvaluationContractError(
            f"peak_vram_mb no puede ser negativo: {runtime.peak_vram_mb}"
        )


def _validate_predictions(
    sample: ImageSample,
    result: StrategyResult,
    category_map: dict[int, str],
) -> None:
    expected_shape = (sample.height, sample.width)

    for idx, pred in enumerate(result.predictions):
        if pred.mask.shape != expected_shape:
            raise EvaluationContractError(
                "Máscara de predicción con shape inválido: "
                f"prediction_index={idx}, shape={pred.mask.shape}, expected={expected_shape}"
            )

        if pred.score < 0.0 or pred.score > 1.0:
            raise EvaluationContractError(
                "Score de predicción fuera de rango [0, 1]: "
                f"prediction_index={idx}, score={pred.score}"
            )

        if pred.category_id not in category_map:
            raise EvaluationContractError(
                "category_id de predicción desconocido para el evaluator: "
                f"prediction_index={idx}, category_id={pred.category_id}"
            )

        if pred.area < 0:
            raise EvaluationContractError(
                "Area de predicción no puede ser negativa: "
                f"prediction_index={idx}, area={pred.area}"
            )

        if len(pred.bbox) != 4:
            raise EvaluationContractError(
                "bbox de predicción inválida: "
                f"prediction_index={idx}, bbox={pred.bbox}"
            )
