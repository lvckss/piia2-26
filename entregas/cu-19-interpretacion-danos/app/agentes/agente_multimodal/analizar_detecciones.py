"""Curvas precision/recall por clase y umbral de score sobre las detecciones de
PIIA-1 exportadas de Colab (un JSON por imagen, ver colab/). Sirve para elegir
los CATEGORY_REVIEW_THRESHOLD con datos y para estimar cuantas llamadas al
modelo de vision supone cada filtro previo.

Uso:
    python analizar_detecciones.py ../../../../../piia2_detecciones/baseline_500

Notas de metodo:
- acierto = `is_true_positive` del export (IoU de mascara >= 0.5 con una
  anotacion, emparejamiento greedy por score). Como el emparejamiento va por
  score descendente, filtrar por un umbral mas alto deja exactamente los
  mismos emparejamientos que se hubieran hecho solo con esas detecciones.
- "solape real" = la caja de la deteccion solapa (IoU de cajas >= 0.3) con la
  caja de alguna anotacion de la MISMA clase, la haya emparejado o no. Separa
  los falsos positivos que caen sobre un dano real (duplicados, caja
  desplazada) de los que caen donde no hay dano de esa clase.
- deduplicar = por imagen y clase, se queda la caja de mayor score y descarta
  las que la solapan (IoU de cajas >= 0.5), como un NMS. El baseline no lo hace.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

UMBRALES = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
CLASES = ("dent", "scratch", "crack", "glass shatter", "lamp broken", "tire flat")


def iou_caja(a: list[float], b: list[float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def cargar(carpeta: Path) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(carpeta.glob("[0-9]*.json"))]


def deduplicar(preds: list[dict], iou_max: float = 0.5) -> list[dict]:
    mantenidas: list[dict] = []
    for p in sorted(preds, key=lambda p: p["score"], reverse=True):
        if all(
            p["damage_class"] != k["damage_class"] or iou_caja(p["bbox_xywh"], k["bbox_xywh"]) < iou_max
            for k in mantenidas
        ):
            mantenidas.append(p)
    return mantenidas


def solapa_real(pred: dict, gts: list[dict], iou_min: float = 0.3) -> bool:
    return any(
        g["damage_class"] == pred["damage_class"] and iou_caja(pred["bbox_xywh"], g["bbox_xywh"]) >= iou_min
        for g in gts
    )


def recopilar(imagenes: list[dict], con_dedup: bool) -> tuple[dict[str, list[dict]], dict[str, int]]:
    por_clase: dict[str, list[dict]] = {c: [] for c in CLASES}
    gt_total = {c: 0 for c in CLASES}
    for img in imagenes:
        for g in img["ground_truth"]:
            gt_total[g["damage_class"]] += 1
        preds = deduplicar(img["predictions"]) if con_dedup else img["predictions"]
        for p in preds:
            por_clase[p["damage_class"]].append(
                {"score": p["score"], "tp": p["is_true_positive"], "solape": solapa_real(p, img["ground_truth"])}
            )
    return por_clase, gt_total


def curvas(imagenes: list[dict], con_dedup: bool) -> dict[str, list[dict]]:
    por_clase, gt_total = recopilar(imagenes, con_dedup)
    n_img = len(imagenes)
    salida: dict[str, list[dict]] = {}
    for clase in CLASES:
        filas = []
        for t in UMBRALES:
            dets = [d for d in por_clase[clase] if d["score"] >= t]
            tp = sum(d["tp"] for d in dets)
            filas.append(
                {
                    "umbral": t,
                    "detecciones": len(dets),
                    "por_imagen": len(dets) / n_img,
                    "precision": tp / len(dets) if dets else None,
                    "recall": tp / gt_total[clase] if gt_total[clase] else None,
                    "solape_real": sum(d["solape"] for d in dets) / len(dets) if dets else None,
                }
            )
        salida[clase] = filas
    return salida


def _pct(x: float | None) -> str:
    return "  -  " if x is None else f"{100 * x:5.1f}"


def imprimir(titulo: str, tabla: dict[str, list[dict]], n_img: int) -> None:
    print(f"\n===== {titulo} =====")
    print(f"{'clase':14s} {'umbral':>6s} {'detecc.':>8s} {'/imagen':>8s} {'prec %':>7s} {'recall %':>9s} {'solape %':>9s}")
    for clase, filas in tabla.items():
        for f in filas:
            print(
                f"{clase:14s} {f['umbral']:>6.1f} {f['detecciones']:>8d} {f['por_imagen']:>8.1f} "
                f"{_pct(f['precision']):>7s} {_pct(f['recall']):>9s} {_pct(f['solape_real']):>9s}"
            )
        print()
    print("llamadas al modelo de vision si se mandan TODAS las detecciones >= umbral:")
    for i, t in enumerate(UMBRALES):
        total = sum(tabla[c][i]["detecciones"] for c in CLASES)
        print(f"  >= {t:.1f}: {total:>6d} llamadas ({total / n_img:.1f} por imagen)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("carpeta", type=Path)
    carpeta = parser.parse_args().carpeta

    imagenes = cargar(carpeta)
    print(f"{len(imagenes)} imagenes cargadas de {carpeta}")
    imprimir("SIN deduplicar (como sale del baseline)", curvas(imagenes, con_dedup=False), len(imagenes))
    imprimir("DEDUPLICADO (por imagen y clase, IoU de cajas >= 0.5)", curvas(imagenes, con_dedup=True), len(imagenes))


if __name__ == "__main__":
    main()
