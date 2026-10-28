"""CELDA DE COLAB: exporta las detecciones de PIIA-1 como un JSON por imagen
para desarrollar y evaluar el Agente 1 (PIIA2) sin cargar SAM3 cada vez.

Se pega como una celda del notebook, DESPUES de crear `strategy` (celda 7) y
`dataset_full` (celda 6). Usa las variables CATEGORY_MAP, DRIVE_ROOT y
RUN_MODE de ese notebook.

Que hace:
- Elige N imagenes de val/test (no de train, para no mezclarlas con las que
  usa Tip-Adapter) asegurando un minimo de anotaciones de cada clase.
- Corre la strategy con un score bajo (0.3) para que haya falsos positivos que
  el Agente 1 pueda limpiar despues; los umbrales los aplica el Agente 1.
- Etiqueta cada deteccion como acierto/falso positivo contra las anotaciones
  reales de CarDD (IoU de mascara >= 0.5), y guarda tambien las anotaciones.
- Escribe cada JSON en cuanto lo tiene y libera la memoria: sin Evaluator, sin
  acumular mascaras. Si se corta, volver a ejecutar la celda retoma donde se
  quedo.
"""

from __future__ import annotations

import gc
import json
import random
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np


def seleccionar_imagenes(
    dataset: Any,
    category_ids: list[int],
    num_images: int,
    min_per_class: int,
    splits: tuple[str, ...],
    seed: int,
) -> tuple[list[int], Counter]:
    """Elige `num_images` imagenes de `splits`, garantizando (si hay datos
    suficientes) al menos `min_per_class` anotaciones de cada clase. Empieza
    por las clases mas raras y rellena el resto al azar. Determinista."""
    rng = random.Random(seed)

    candidatas = [
        image_id
        for image_id in dataset.image_ids
        if dataset.image_id_to_split.get(image_id, dataset.split) in splits
    ]
    rng.shuffle(candidatas)

    clases_por_imagen: dict[int, Counter] = {}
    for image_id in candidatas:
        anns = dataset.coco.loadAnns(dataset.coco.getAnnIds(imgIds=[image_id]))
        clases_por_imagen[image_id] = Counter(int(a["category_id"]) for a in anns)

    total_por_clase = Counter()
    for conteo in clases_por_imagen.values():
        total_por_clase.update(conteo)

    elegidas: list[int] = []
    elegidas_set: set[int] = set()
    conteo_elegidas: Counter = Counter()

    for category_id in sorted(category_ids, key=lambda c: total_por_clase[c]):
        for image_id in candidatas:
            if conteo_elegidas[category_id] >= min_per_class:
                break
            if image_id in elegidas_set:
                continue
            if clases_por_imagen[image_id][category_id] > 0:
                elegidas.append(image_id)
                elegidas_set.add(image_id)
                conteo_elegidas.update(clases_por_imagen[image_id])

    for image_id in candidatas:
        if len(elegidas) >= num_images:
            break
        if image_id not in elegidas_set:
            elegidas.append(image_id)
            elegidas_set.add(image_id)
            conteo_elegidas.update(clases_por_imagen[image_id])

    return sorted(elegidas), conteo_elegidas


def iou_matrix(pred_masks: list[np.ndarray], gt_masks: list[np.ndarray]) -> np.ndarray:
    matrix = np.zeros((len(pred_masks), len(gt_masks)))
    for i, pred_mask in enumerate(pred_masks):
        for j, gt_mask in enumerate(gt_masks):
            union = np.logical_or(pred_mask, gt_mask).sum()
            if union > 0:
                matrix[i, j] = np.logical_and(pred_mask, gt_mask).sum() / union
    return matrix


def etiquetar_predicciones(
    iou: np.ndarray, scores: list[float], iou_threshold: float
) -> tuple[list[tuple[bool, float]], int]:
    """Emparejamiento greedy por score descendente (como COCO). Devuelve, por
    prediccion, (es_acierto, mejor_iou) y cuantas anotaciones quedan sin
    emparejar (falsos negativos de esa clase)."""
    orden = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    gt_usadas: set[int] = set()
    resultado: list[tuple[bool, float]] = [(False, 0.0)] * len(scores)

    for i in orden:
        mejor_j, mejor_iou = -1, 0.0
        for j in range(iou.shape[1]):
            if j not in gt_usadas and iou[i, j] > mejor_iou:
                mejor_j, mejor_iou = j, float(iou[i, j])
        es_acierto = mejor_iou >= iou_threshold
        if es_acierto:
            gt_usadas.add(mejor_j)
        resultado[i] = (es_acierto, mejor_iou)

    return resultado, iou.shape[1] - len(gt_usadas)


def exportar_imagen(
    strategy: Any,
    dataset: Any,
    image_id: int,
    category_map: dict[int, str],
    iou_threshold: float,
    run_mode: str,
) -> dict[str, Any]:
    sample = dataset.get_by_image_id(image_id)
    result = strategy.run(sample)

    preds = sorted(result.predictions, key=lambda p: p.score, reverse=True)
    etiquetas: list[tuple[bool, float]] = [(False, 0.0)] * len(preds)
    gt_sin_emparejar: dict[str, int] = {}

    for category_id, nombre in category_map.items():
        idx = [i for i, p in enumerate(preds) if p.category_id == category_id]
        gts = [g for g in sample.gt_instances if g.category_id == category_id]
        matriz = iou_matrix(
            [np.asarray(preds[i].mask, dtype=bool) for i in idx],
            [np.asarray(g.mask, dtype=bool) for g in gts],
        )
        resultados, sin_emparejar = etiquetar_predicciones(
            matriz, [float(preds[i].score) for i in idx], iou_threshold
        )
        for i, r in zip(idx, resultados):
            etiquetas[i] = r
        gt_sin_emparejar[nombre] = sin_emparejar

    salida = {
        "image_id": int(sample.image_id),
        "image_file": Path(sample.image_path).name,
        "image_path": str(sample.image_path),
        "image_width": int(sample.width),
        "image_height": int(sample.height),
        "split": sample.split,
        "variant": run_mode,
        "strategy_name": result.strategy_name,
        "num_predictions": len(preds),
        "predictions": [
            {
                "instance_index": k + 1,
                "damage_class": category_map.get(p.category_id, str(p.category_id)),
                "category_id": int(p.category_id),
                "score": float(p.score),
                "bbox_xywh": [float(v) for v in p.bbox],
                "area": float(p.area),
                "is_true_positive": bool(etiquetas[k][0]),
                "best_iou": round(etiquetas[k][1], 4),
            }
            for k, p in enumerate(preds)
        ],
        "ground_truth": [
            {
                "damage_class": category_map.get(g.category_id, str(g.category_id)),
                "category_id": int(g.category_id),
                "bbox_xywh": [float(v) for v in g.bbox],
            }
            for g in sample.gt_instances
        ],
        "gt_unmatched_by_class": gt_sin_emparejar,
    }

    del sample, result, preds
    return salida


def _liberar_memoria() -> None:
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def resumen_por_clase(out_dir: Path, category_map: dict[int, str]) -> list[dict[str, Any]]:
    filas = {n: {"clase": n, "gt": 0, "detecciones": 0, "aciertos": 0} for n in category_map.values()}
    for ruta in sorted(out_dir.glob("[0-9]*.json")):
        data = json.loads(ruta.read_text(encoding="utf-8"))
        for g in data["ground_truth"]:
            filas[g["damage_class"]]["gt"] += 1
        for p in data["predictions"]:
            filas[p["damage_class"]]["detecciones"] += 1
            filas[p["damage_class"]]["aciertos"] += int(p["is_true_positive"])
    for fila in filas.values():
        fila["falsos_positivos"] = fila["detecciones"] - fila["aciertos"]
        fila["precision"] = round(fila["aciertos"] / fila["detecciones"], 3) if fila["detecciones"] else None
        fila["recall"] = round(fila["aciertos"] / fila["gt"], 3) if fila["gt"] else None
    return list(filas.values())


def exportar(
    strategy: Any,
    dataset: Any,
    category_map: dict[int, str],
    out_dir: str | Path,
    *,
    run_mode: str,
    num_images: int = 500,
    min_per_class: int = 25,
    splits: tuple[str, ...] = ("val", "test"),
    seed: int = 42,
    score_threshold: float = 0.3,
    iou_threshold: float = 0.5,
    zip_result: bool = True,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    strategy.set_score_threshold_map({cid: score_threshold for cid in category_map})

    elegidas, conteo = seleccionar_imagenes(
        dataset, list(category_map), num_images, min_per_class, splits, seed
    )
    faltan = {category_map[c]: min_per_class - conteo[c] for c in category_map if conteo[c] < min_per_class}
    if faltan:
        print("AVISO: no hay anotaciones suficientes para el minimo pedido en:", faltan)

    (out_dir / "_manifest.json").write_text(
        json.dumps(
            {
                "run_mode": run_mode,
                "num_images": len(elegidas),
                "min_per_class": min_per_class,
                "splits": list(splits),
                "seed": seed,
                "score_threshold": score_threshold,
                "iou_threshold": iou_threshold,
                "gt_por_clase_en_la_muestra": {category_map[c]: conteo[c] for c in category_map},
                "image_ids": elegidas,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"{len(elegidas)} imagenes elegidas. GT por clase:", {category_map[c]: conteo[c] for c in category_map})

    hechas = saltadas = 0
    t0 = time.time()
    for n, image_id in enumerate(elegidas, 1):
        destino = out_dir / f"{image_id:06d}.json"
        if destino.exists():
            saltadas += 1
            continue

        datos = exportar_imagen(strategy, dataset, image_id, category_map, iou_threshold, run_mode)
        destino.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        hechas += 1

        if hechas % 25 == 0:
            _liberar_memoria()
            por_imagen = (time.time() - t0) / hechas
            restan = (len(elegidas) - n) * por_imagen
            print(f"{n}/{len(elegidas)} | {por_imagen:.1f} s/imagen | quedan ~{restan / 60:.0f} min")

    resumen = resumen_por_clase(out_dir, category_map)
    print(f"\nHechas {hechas}, ya existian {saltadas}. Resumen a score >= {score_threshold}:")
    for fila in resumen:
        print(fila)

    if zip_result:
        ruta_zip = shutil.make_archive(str(out_dir), "zip", out_dir)
        print("\nZIP para descargar:", ruta_zip)

    return {"hechas": hechas, "saltadas": saltadas, "resumen": resumen}


if __name__ == "__main__" and "strategy" in globals() and "dataset_full" in globals():
    # ---- configuracion (ajustala aqui) ----
    EXPORT_NUM_IMAGES = 500
    EXPORT_MIN_PER_CLASS = 25
    EXPORT_SPLITS = ("val", "test")
    EXPORT_SEED = 42
    EXPORT_SCORE_THRESHOLD = 0.3
    EXPORT_DIR = DRIVE_ROOT / "results" / "piia2_detecciones" / f"{RUN_MODE}_{EXPORT_NUM_IMAGES}"  # noqa: F821

    exportar(
        strategy=strategy,  # noqa: F821
        dataset=dataset_full,  # noqa: F821
        category_map=CATEGORY_MAP,  # noqa: F821
        out_dir=EXPORT_DIR,
        run_mode=RUN_MODE,  # noqa: F821
        num_images=EXPORT_NUM_IMAGES,
        min_per_class=EXPORT_MIN_PER_CLASS,
        splits=EXPORT_SPLITS,
        seed=EXPORT_SEED,
        score_threshold=EXPORT_SCORE_THRESHOLD,
    )
