from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle
from matplotlib.lines import Line2D

from ml.StrategyPipeline.schemas import ImageEvalRecord, RunInfo, InspectionItem

class RunInspection:
    def __init__(
        self,
        run_info: RunInfo,
        category_map: dict[int, str],
        records: list[ImageEvalRecord],
        per_image: pd.DataFrame,
        error_iou_threshold: float = 0.50,
        error_matching_policy: str = "score_greedy",
    ) -> None:

        self.run_info = run_info
        self.category_map = dict(category_map)
        self._category_colors = self._build_category_colors()
        self.error_iou_threshold = error_iou_threshold
        self.error_matching_policy = error_matching_policy
        self._records = list(records)
        self._by_image_id = {record.image_id: record for record in records}
        self._per_image = per_image.copy()
        self._metrics_by_image_id = (
            # construimos un diccionario con la información de cada imagen y sus métricas para facilitar la inspección.
            # La clave es el image_id y el valor es otro diccionario con los datos de la imagen (incluyendo el path) y las métricas calculadas.
            # orient index hace que el índice del dataframe (en este caso image_id) se convierta en la clave del diccionario, y las columnas se conviertan en las claves internas de cada valor.
            self._per_image.set_index("image_id").to_dict(orient="index")
            if not self._per_image.empty
            else {}
        )

    def get(self, image_id: int) -> InspectionItem:
        if image_id not in self._by_image_id:
            raise KeyError(f"image_id no encontrado en la run: {image_id}")

        return InspectionItem(
            record=self._by_image_id[image_id],
            metrics=dict(self._metrics_by_image_id.get(image_id, {})),
        )

    # devuelve un dataframe filtrado por los criterios que se quieran (split, tipo de corrupción, severidad, etc) para facilitar la búsqueda de casos específicos
    def search(
        self,
        *,
        split: str | None = None,
        corruption: str | None = None,
        severity: int | None = None,
        is_clean: bool | None = None,
    ) -> pd.DataFrame:

        df = self._per_image.copy()

        if split is not None:
            df = df[df["split"] == split]
        if corruption is not None:
            df = df[df["corruption"] == corruption]
        if severity is not None:
            df = df[df["severity"] == severity]
        if is_clean is not None:
            df = df[df["is_clean"] == is_clean]

        return df.sort_values("image_id").reset_index(drop=True)

    def plot(
        self,
        image_id: int,
        *,
        alpha: float = 0.18,
        with_boxes: bool = False,
        show_scores: bool = True,
        show_labels: bool = False,
        with_legend: bool = True,
        edge_alpha: float = 0.90,
        edge_linewidth: float = 2.5,
        label_group_iou_threshold: float = 0.50,
        figsize: tuple[int, int] = (14, 6),
    ) -> None:

        item = self.get(image_id)
        record = item.record
        image = self._load_image(record.image_path)
        gt_matched_indexes, pred_matched_indexes = self._match_record_instances(record)
        fig, axes = plt.subplots(1, 2, figsize=figsize)

        self._draw_panel(
            ax=axes[0],
            image=image,
            title=f"ground truth | image_id={record.image_id}",
            instances=record.gt_instances,
            panel_kind="ground_truth",
            alpha=alpha,
            with_boxes=with_boxes,
            show_scores=False,
            show_labels=show_labels,
            with_legend=with_legend,
            edge_alpha=edge_alpha,
            edge_linewidth=edge_linewidth,
            label_group_iou_threshold=label_group_iou_threshold,
            matched_indexes=gt_matched_indexes,
        )

        self._draw_panel(
            ax=axes[1],
            image=image,
            title=self._build_prediction_title(record.image_id, item.metrics),
            instances=record.pred_instances,
            panel_kind="predictions",
            alpha=alpha,
            with_boxes=with_boxes,
            show_scores=show_scores,
            show_labels=show_labels,
            with_legend=with_legend,
            edge_alpha=edge_alpha,
            edge_linewidth=edge_linewidth,
            label_group_iou_threshold=label_group_iou_threshold,
            matched_indexes=pred_matched_indexes,
        )

        plt.tight_layout()
        plt.show()

    def _load_image(self, image_path: str) -> np.ndarray:
        with Image.open(Path(image_path)) as image_file:
            return np.asarray(image_file.convert("RGB"))

    def _draw_panel(
          self,
          ax,
          image: np.ndarray,
          title: str,
          instances: list,
          panel_kind: str,
          alpha: float,
          with_boxes: bool,
          show_scores: bool,
          show_labels: bool,
          with_legend: bool,
          edge_alpha: float,
          edge_linewidth: float,
          label_group_iou_threshold: float,
          matched_indexes: set[int],
      ) -> None:

        ax.imshow(image)
        ax.set_title(title)
        ax.axis("off")

        legend_category_ids: list[int] = []

        # dibuja las máscaras y las cajas de cada instancia individual
        for instance_index, instance in enumerate(instances):
            mask = np.asarray(instance.mask, dtype=bool)
            category_id = int(instance.category_id)
            color = self._category_colors.get(category_id, (1.0, 0.0, 0.0))
            line_style = self._resolve_edge_linestyle(
                panel_kind=panel_kind,
                is_matched=instance_index in matched_indexes,
            )

            overlay = np.zeros((*mask.shape, 4), dtype=float)
            overlay[mask] = (*color, alpha)
            ax.imshow(overlay)

            # el borde se dibuja más marcado para que la forma se lea mejor
            self._draw_mask_edge(
                ax=ax,
                mask=mask,
                color=color,
                edge_alpha=edge_alpha,
                edge_linewidth=edge_linewidth,
                line_style=line_style,
            )

            if with_boxes:
                x, y, w, h = instance.bbox
                rect = Rectangle(
                    (x, y),
                    w,
                    h,
                    fill=False,
                    edgecolor=color,
                    linewidth=max(1.0, edge_linewidth - 0.5),
                    linestyle=line_style,
                )
                ax.add_patch(rect)

            if show_scores and hasattr(instance, "score"):
                self._draw_score_badge(
                    ax=ax,
                    instance=instance,
                    color=color,
                )

            if category_id not in legend_category_ids:
                legend_category_ids.append(category_id)

        # agrupa etiquetas de instancias que representan casi la misma región
        if show_labels:
            for group in self._group_overlapping_instances(
                instances,
                iou_threshold=label_group_iou_threshold,
            ):
                label = self._build_group_label(group, show_scores=show_scores)
                x, y, _, _ = self._group_bbox(group)
                ax.text(x, y, label, color="white", fontsize=9, backgroundcolor="black")

        if with_legend and legend_category_ids:
            self._draw_category_legend(
                ax=ax,
                category_ids=legend_category_ids,
                panel_kind=panel_kind,
                has_unmatched=any(
                    instance_index not in matched_indexes
                    for instance_index in range(len(instances))
                ),
            )

    def _group_overlapping_instances(
        self,
        instances: list,
        iou_threshold: float,
    ) -> list[list]:
        groups: list[list] = []

        for instance in instances:
            added = False
            for group in groups:
                if any(
                    self._mask_iou(instance.mask, grouped_instance.mask) >= iou_threshold
                    for grouped_instance in group
                ):
                    group.append(instance)
                    added = True
                    break

            if not added:
                groups.append([instance])

        return groups

    def _build_group_label(self, instances: list, show_scores: bool) -> str:
        labels = []

        for instance in instances:
            label = self.category_map.get(instance.category_id, str(instance.category_id))
            if show_scores and hasattr(instance, "score"):
                metadata = getattr(instance, "metadata", {})
                sam3_score = metadata.get("sam3_score")
                tip_adapter_score = metadata.get("tip_adapter_score")

                if sam3_score is not None and tip_adapter_score is not None:
                    label = (
                        f"{label} | score={float(instance.score):.2f} "
                        f"sam3={float(sam3_score):.2f} "
                        f"tip={float(tip_adapter_score):.2f}"
                    )
                else:
                    label = f"{label} | {float(instance.score):.2f}"
            labels.append(label)

        return "\n".join(labels)

    def _draw_mask_edge(
        self,
        *,
        ax,
        mask: np.ndarray,
        color: tuple[float, float, float],
        edge_alpha: float,
        edge_linewidth: float,
        line_style: str,
    ) -> None:
        mask = np.asarray(mask, dtype=bool)
        if not mask.any():
            return

        ax.contour(
            mask.astype(float),
            levels=[0.5],
            colors=[color],
            linewidths=edge_linewidth,
            alpha=edge_alpha,
            linestyles=[line_style],
        )

    def _draw_category_legend(
        self,
        *,
        ax,
        category_ids: list[int],
        panel_kind: str,
        has_unmatched: bool,
    ) -> None:
        color_handles = [
            Patch(
                facecolor=(*self._category_colors[category_id], 0.30),
                edgecolor=self._category_colors[category_id],
                linewidth=2,
                label=self.category_map.get(category_id, str(category_id)),
            )
            for category_id in sorted(category_ids)
        ]

        style_handles = [
            Line2D(
                [0],
                [0],
                color="black",
                linewidth=2.5,
                linestyle="-",
                label="tp",
            ),
        ]

        if has_unmatched:
            if panel_kind == "predictions":
                style_handles.append(
                    Line2D(
                        [0],
                        [0],
                        color="black",
                        linewidth=2.5,
                        linestyle=":",
                        label="fp",
                    )
                )
            else:
                style_handles.append(
                    Line2D(
                        [0],
                        [0],
                        color="black",
                        linewidth=2.5,
                        linestyle="--",
                        label="fn",
                    )
                )

        ax.legend(
            handles=[*color_handles, *style_handles],
            loc="lower left",
            framealpha=0.90,
            facecolor="white",
            edgecolor="black",
        )

    def _draw_score_badge(
        self,
        *,
        ax,
        instance,
        color: tuple[float, float, float],
    ) -> None:
        x, y, _, _ = instance.bbox
        ax.text(
            float(x),
            max(0.0, float(y) - 4.0),
            f"{float(instance.score):.2f}",
            color="white",
            fontsize=9,
            bbox={
                "boxstyle": "round,pad=0.20",
                "facecolor": (*color, 0.95),
                "edgecolor": "none",
            },
        )

    def _resolve_edge_linestyle(
        self,
        *,
        panel_kind: str,
        is_matched: bool,
    ) -> str:
        if is_matched:
            return "-"

        if panel_kind == "predictions":
            return ":"

        return "--"

    def _group_bbox(self, instances: list) -> tuple[float, float, float, float]:
        x_min = min(float(instance.bbox[0]) for instance in instances)
        y_min = min(float(instance.bbox[1]) for instance in instances)
        x_max = max(float(instance.bbox[0] + instance.bbox[2]) for instance in instances)
        y_max = max(float(instance.bbox[1] + instance.bbox[3]) for instance in instances)

        return (x_min, y_min, x_max - x_min, y_max - y_min)

    def _mask_iou(self, mask_a: np.ndarray, mask_b: np.ndarray) -> float:
        mask_a = np.asarray(mask_a, dtype=bool)
        mask_b = np.asarray(mask_b, dtype=bool)

        intersection = np.logical_and(mask_a, mask_b).sum()
        union = np.logical_or(mask_a, mask_b).sum()

        if union == 0:
            return 0.0

        return float(intersection / union)

    def _build_prediction_title(self, image_id: int, metrics: dict[str, Any]) -> str:
        if not metrics:
            return f"predictions | image_id={image_id}"

        return (
            f"predictions | image_id={image_id} | "
            f"tp={metrics.get('tp_iou50')} "
            f"fp={metrics.get('fp_iou50')} "
            f"fn={metrics.get('fn_iou50')} | "
            f"ms={metrics.get('inference_ms')}"
        )

    def _match_record_instances(
        self,
        record: ImageEvalRecord,
    ) -> tuple[set[int], set[int]]:
        gt_by_class = self._group_instances_by_class(record.gt_instances)
        pred_by_class = self._group_instances_by_class(record.pred_instances)

        matched_gt_indexes: set[int] = set()
        matched_pred_indexes: set[int] = set()

        all_category_ids = sorted(set(gt_by_class) | set(pred_by_class))
        for category_id in all_category_ids:
            gt_group = gt_by_class.get(category_id, [])
            pred_group = pred_by_class.get(category_id, [])

            if not gt_group or not pred_group:
                continue

            if self.error_matching_policy == "iou_greedy":
                class_matched_gt, class_matched_pred = self._match_class_iou_greedy(
                    gt_group=gt_group,
                    pred_group=pred_group,
                )
            else:
                class_matched_gt, class_matched_pred = self._match_class_score_greedy(
                    gt_group=gt_group,
                    pred_group=pred_group,
                )

            matched_gt_indexes.update(class_matched_gt)
            matched_pred_indexes.update(class_matched_pred)

        return matched_gt_indexes, matched_pred_indexes

    def _group_instances_by_class(
        self,
        instances: list,
    ) -> dict[int, list[tuple[int, Any]]]:
        grouped: dict[int, list[tuple[int, Any]]] = {}
        for instance_index, instance in enumerate(instances):
            grouped.setdefault(int(instance.category_id), []).append((instance_index, instance))
        return grouped

    def _match_class_score_greedy(
        self,
        *,
        gt_group: list[tuple[int, Any]],
        pred_group: list[tuple[int, Any]],
    ) -> tuple[set[int], set[int]]:
        used_gt_indexes: set[int] = set()
        matched_gt_indexes: set[int] = set()
        matched_pred_indexes: set[int] = set()

        ordered_preds = sorted(
            pred_group,
            key=lambda item: float(item[1].score),
            reverse=True,
        )

        for pred_index, pred_instance in ordered_preds:
            best_gt_index: int | None = None
            best_iou = -1.0

            for gt_index, gt_instance in gt_group:
                if gt_index in used_gt_indexes:
                    continue

                iou = self._mask_iou(gt_instance.mask, pred_instance.mask)
                if iou > best_iou:
                    best_iou = iou
                    best_gt_index = gt_index

            if (
                best_gt_index is not None
                and best_iou >= self.error_iou_threshold
            ):
                used_gt_indexes.add(best_gt_index)
                matched_gt_indexes.add(best_gt_index)
                matched_pred_indexes.add(pred_index)

        return matched_gt_indexes, matched_pred_indexes

    def _match_class_iou_greedy(
        self,
        *,
        gt_group: list[tuple[int, Any]],
        pred_group: list[tuple[int, Any]],
    ) -> tuple[set[int], set[int]]:
        candidate_pairs: list[tuple[float, int, int]] = []

        for pred_index, pred_instance in pred_group:
            for gt_index, gt_instance in gt_group:
                iou = self._mask_iou(gt_instance.mask, pred_instance.mask)
                if iou >= self.error_iou_threshold:
                    candidate_pairs.append((iou, pred_index, gt_index))

        candidate_pairs.sort(reverse=True, key=lambda item: item[0])

        used_pred_indexes: set[int] = set()
        used_gt_indexes: set[int] = set()

        for _, pred_index, gt_index in candidate_pairs:
            if pred_index in used_pred_indexes or gt_index in used_gt_indexes:
                continue

            used_pred_indexes.add(pred_index)
            used_gt_indexes.add(gt_index)

        return used_gt_indexes, used_pred_indexes

    def _build_category_colors(self) -> dict[int, tuple[float, float, float]]:
        cmap = plt.get_cmap("tab10")
        colors: dict[int, tuple[float, float, float]] = {}

        for index, category_id in enumerate(sorted(self.category_map)):
            rgba = cmap(index % 10)
            colors[category_id] = (
                float(rgba[0]),
                float(rgba[1]),
                float(rgba[2]),
            )

        return colors
