from __future__ import annotations

from ml.StrategyPipeline.schemas import (
    EvalOutput,
    ImageEvalRecord,
    ImageSample,
    RunInfo,
    SummaryMetrics,
    StrategyResult,
)

from ml.StrategyPipeline.evaluation.metrics.error_metrics import compute_error_metrics
from ml.StrategyPipeline.evaluation.metrics.runtime_metrics import compute_runtime_metrics
from ml.StrategyPipeline.evaluation.metrics.coco_metrics import compute_coco_metrics
from ml.StrategyPipeline.evaluation.metrics.robustness_metrics import compute_robustness_metrics

from ml.StrategyPipeline.evaluation.utils.record_utils import copy_gt_instance, copy_prediction, build_per_image_base
from ml.StrategyPipeline.evaluation.utils.validators import EvaluationContractError, validate_evaluator_input
from ml.StrategyPipeline.evaluation.inspection import RunInspection


# Mapeo por defecto de categorías, se puede sobreescribir al crear el Evaluator
DEFAULT_CATEGORY_MAP = {
    1: "dent",
    2: "scratch",
    3: "crack",
    4: "glass shatter",
    5: "lamp broken",
    6: "tire flat",
}


class Evaluator:
    def __init__(
        self,
        # info general de la run
        run_info: RunInfo,
        category_map: dict[int, str] | None = None,
        error_iou_threshold: float = 0.50, # para compute_error_metrics
        robustness_base_metric: str = "mask_ap_50_95",
        error_matching_policy: str = "score_greedy",
    ) -> None:
        self.run_info = run_info
        self.category_map = dict(
            DEFAULT_CATEGORY_MAP if category_map is None else category_map
        )
        self.error_iou_threshold = error_iou_threshold
        self.robustness_base_metric = robustness_base_metric
        self.error_matching_policy = error_matching_policy

        self._records: dict[int, ImageEvalRecord] = {}

        # esta propiedad se llena al llamar a finalize() y contiene toda la información de la run para facilitar la inspección de resultados
        self._inspection: RunInspection | None = None

    def add(self, sample: ImageSample, result: StrategyResult) -> None:
        """Agrega un nuevo registro de evaluación al evaluator. Valida que el input cumpla con el contrato esperado."""

        if sample.image_id in self._records:
            raise EvaluationContractError(
                f"La imagen {sample.image_id} ya fue añadida al evaluator"
            )

        validate_evaluator_input(
            self.run_info,
            sample,
            result,
            category_map=self.category_map,
        )

        self._records[sample.image_id] = ImageEvalRecord(
            image_id=sample.image_id,
            image_path=sample.image_path,
            height=sample.height,
            width=sample.width,
            split=sample.split,
            corruption=sample.corruption,
            severity=sample.severity,
            is_clean=sample.is_clean,
            gt_instances=[copy_gt_instance(gt) for gt in sample.gt_instances],
            pred_instances=[
                copy_prediction(pred) for pred in result.predictions
            ],
            inference_ms=float(result.runtime.inference_ms),
            peak_vram_mb=(
                None
                if result.runtime.peak_vram_mb is None
                else float(result.runtime.peak_vram_mb)
            ),
        )

    def finalize(self) -> EvalOutput:
        """Llama a las funciones de métrica para computar los resultados finales del evaluator."""

        if not self._records:
            raise EvaluationContractError(
                "No se puede finalizar un evaluator sin registros."
            )

        records = self._get_ordered_records()

        per_image_base = build_per_image_base(records)

        runtime_out = compute_runtime_metrics(records)
        error_out = compute_error_metrics(
            records=records,
            iou_threshold=self.error_iou_threshold,
            matching_policy=self.error_matching_policy,
        )
        coco_out = compute_coco_metrics(
            records=records,
            category_map=self.category_map,
        )
        robustness_out = compute_robustness_metrics(
            records=records,
            category_map=self.category_map,
            error_iou_threshold=self.error_iou_threshold,
            error_matching_policy=self.error_matching_policy,
            base_metric_name=self.robustness_base_metric,
        )

        per_image = (
            per_image_base
            .merge(error_out.per_image, on="image_id", how="left")
            .merge(runtime_out.per_image, on="image_id", how="left")
            .sort_values("image_id")
            .reset_index(drop=True)
        )

        per_class = (
            coco_out.per_class
            .merge(error_out.per_class, on="category_id", how="left")
            .fillna({
                "tp_iou50": 0,
                "fp_iou50": 0,
                "fn_iou50": 0,
                "fp_per_image": 0.0,
            })
            .sort_values("category_id")
            .reset_index(drop=True)
        )

        summary = SummaryMetrics(
            mask_ap_50_95=coco_out.mask_ap_50_95,
            ap75=coco_out.ap75,
            ap_small=coco_out.ap_small,
            fp_per_image=error_out.fp_per_image,
            pclean=robustness_out.pclean,
            mpc=robustness_out.mpc,
            rpc=robustness_out.rpc,
            ms_per_image=runtime_out.ms_per_image,
            peak_vram_mb=runtime_out.peak_vram_mb,
        )

        self._inspection = RunInspection(
            run_info=self.run_info,
            category_map=self.category_map,
            records=records,
            per_image=per_image,
            error_iou_threshold=self.error_iou_threshold,
            error_matching_policy=self.error_matching_policy,
        )

        return EvalOutput(
            run_info=self.run_info,
            summary=summary,
            per_class=per_class,
            per_condition=robustness_out.per_condition.copy(),
            per_image=per_image,
        )


    def _get_ordered_records(self) -> list[ImageEvalRecord]:
        return [self._records[image_id] for image_id in sorted(self._records)]

    def get_inspection(self) -> RunInspection:
        if self._inspection is None:
            raise EvaluationContractError("Primero hay que llamar a finalize().")
        return self._inspection
