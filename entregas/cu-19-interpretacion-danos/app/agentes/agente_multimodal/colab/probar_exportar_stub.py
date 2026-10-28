"""Prueba exportar_detecciones.py sin SAM3 ni CarDD: dataset y strategy falsos.
Comprueba muestreo estratificado, etiquetado acierto/falso positivo, formato
del JSON (compatible con el Agente 1) y reanudacion."""

from __future__ import annotations

import json
import random
import tempfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from exportar_detecciones import (
    etiquetar_predicciones,
    exportar,
    iou_matrix,
    seleccionar_imagenes,
)

CATEGORY_MAP = {1: "dent", 2: "scratch", 3: "crack", 4: "glass shatter", 5: "lamp broken", 6: "tire flat"}
SIZE = 40


def _mask(x: int, y: int, w: int = 10, h: int = 10) -> np.ndarray:
    m = np.zeros((SIZE, SIZE), dtype=bool)
    m[y : y + h, x : x + w] = True
    return m


class FakeCoco:
    def __init__(self, anns_por_imagen: dict[int, list[int]]) -> None:
        self.anns_por_imagen = anns_por_imagen

    def getAnnIds(self, imgIds: list[int]) -> list[tuple[int, int]]:
        return [(imgIds[0], k) for k in range(len(self.anns_por_imagen[imgIds[0]]))]

    def loadAnns(self, ids: list[tuple[int, int]]) -> list[dict]:
        return [{"category_id": self.anns_por_imagen[i][k]} for i, k in ids]


class FakeDataset:
    def __init__(self, num_images: int = 400, seed: int = 0) -> None:
        rng = random.Random(seed)
        self.image_ids = list(range(1, num_images + 1))
        self.split = None
        self.image_id_to_split = {
            i: rng.choice(["train", "train", "val", "test"]) for i in self.image_ids
        }
        # la clase 6 es rara a proposito (5%), como tire flat en CarDD
        self.anns = {
            i: rng.choices([1, 2, 3, 4, 5, 6], weights=[35, 30, 10, 10, 10, 5], k=rng.randint(1, 3))
            for i in self.image_ids
        }
        self.coco = FakeCoco(self.anns)

    def get_by_image_id(self, image_id: int) -> SimpleNamespace:
        gts = [
            SimpleNamespace(category_id=c, mask=_mask(2 + 12 * k, 5), bbox=(2 + 12 * k, 5, 10, 10), area=100.0)
            for k, c in enumerate(self.anns[image_id])
        ]
        return SimpleNamespace(
            image_id=image_id,
            image_path=f"/content/drive/imgs/{image_id:06d}.jpg",
            width=SIZE,
            height=SIZE,
            split=self.image_id_to_split[image_id],
            gt_instances=gts,
        )


class FakeStrategy:
    strategy_name = "fake_baseline"

    def __init__(self) -> None:
        self.threshold_map: dict[int, float] = {}
        self.calls = 0

    def set_score_threshold_map(self, m: dict[int, float]) -> None:
        self.threshold_map = m

    def run(self, sample: SimpleNamespace) -> SimpleNamespace:
        self.calls += 1
        preds = []
        for k, g in enumerate(sample.gt_instances):
            # un acierto exacto por cada anotacion
            preds.append(SimpleNamespace(category_id=g.category_id, score=0.9, mask=g.mask.copy(), bbox=g.bbox, area=100.0))
        # y un falso positivo en una zona donde no hay anotaciones
        preds.append(SimpleNamespace(category_id=1, score=0.4, mask=_mask(2, 30), bbox=(2, 30, 10, 10), area=100.0))
        return SimpleNamespace(strategy_name=self.strategy_name, predictions=preds)


def main() -> None:
    # --- piezas puras ---
    iou = iou_matrix([_mask(0, 0)], [_mask(0, 0), _mask(20, 20)])
    assert iou[0, 0] == 1.0 and iou[0, 1] == 0.0
    etiquetas, sin_emparejar = etiquetar_predicciones(iou, [0.9], 0.5)
    assert etiquetas == [(True, 1.0)] and sin_emparejar == 1

    # dos predicciones sobre la misma anotacion: solo la de mayor score acierta
    iou2 = iou_matrix([_mask(0, 0), _mask(0, 0)], [_mask(0, 0)])
    etiquetas2, _ = etiquetar_predicciones(iou2, [0.5, 0.8], 0.5)
    assert etiquetas2 == [(False, 0.0), (True, 1.0)], etiquetas2

    # sin anotaciones: todo falso positivo
    etiquetas3, sin3 = etiquetar_predicciones(np.zeros((2, 0)), [0.9, 0.3], 0.5)
    assert etiquetas3 == [(False, 0.0), (False, 0.0)] and sin3 == 0

    # --- muestreo ---
    ds = FakeDataset()
    ids, conteo = seleccionar_imagenes(ds, list(CATEGORY_MAP), 50, 8, ("val", "test"), seed=42)
    assert len(ids) == 50, len(ids)
    assert all(ds.image_id_to_split[i] in ("val", "test") for i in ids), "colo una imagen de train"
    assert conteo[6] >= 8, f"la clase rara no llega al minimo: {conteo}"
    assert all(conteo[c] >= 8 for c in CATEGORY_MAP), conteo
    ids2, _ = seleccionar_imagenes(ds, list(CATEGORY_MAP), 50, 8, ("val", "test"), seed=42)
    assert ids == ids2, "el muestreo no es determinista"

    # --- exportacion de punta a punta y reanudacion ---
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "export"
        strategy = FakeStrategy()
        res = exportar(strategy, ds, CATEGORY_MAP, out, run_mode="baseline", num_images=30,
                       min_per_class=5, seed=1, zip_result=True)
        assert res["hechas"] == 30 and res["saltadas"] == 0
        assert strategy.threshold_map == {c: 0.3 for c in CATEGORY_MAP}
        assert (Path(tmp) / "export.zip").exists()
        assert (out / "_manifest.json").exists()

        un_json = json.loads(next(out.glob("[0-9]*.json")).read_text(encoding="utf-8"))
        for campo in ("image_id", "image_path", "image_width", "image_height", "predictions", "ground_truth"):
            assert campo in un_json, campo
        for p in un_json["predictions"]:
            for campo in ("instance_index", "damage_class", "category_id", "score", "bbox_xywh", "is_true_positive"):
                assert campo in p, campo
        # un acierto por anotacion + un falso positivo (la anotacion de dent en esa zona no existe)
        aciertos = sum(p["is_true_positive"] for p in un_json["predictions"])
        assert aciertos == len(un_json["ground_truth"]), (aciertos, len(un_json["ground_truth"]))
        assert sum(not p["is_true_positive"] for p in un_json["predictions"]) == 1

        # compatible con el Agente 1 (lee estas claves de PIIA-1)
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent))
        from hallazgos import construir_hallazgos

        hallazgos = construir_hallazgos(un_json)
        assert len(hallazgos["findings"]) == un_json["num_predictions"]

        # reanudacion: volver a ejecutar no repite inferencias
        llamadas_antes = strategy.calls
        res2 = exportar(strategy, ds, CATEGORY_MAP, out, run_mode="baseline", num_images=30,
                        min_per_class=5, seed=1, zip_result=False)
        assert res2["hechas"] == 0 and res2["saltadas"] == 30
        assert strategy.calls == llamadas_antes, "reanudar volvio a inferir"

    print("\nTodo ok: muestreo, etiquetado, formato compatible con el Agente 1 y reanudacion.")


if __name__ == "__main__":
    main()
