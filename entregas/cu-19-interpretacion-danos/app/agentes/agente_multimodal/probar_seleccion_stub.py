"""Prueba el filtro previo (seleccion.py): casos pequenos a mano y, si esta la
exportacion real de Colab en piia2_detecciones/baseline_500, que reproduce las
cifras medidas (3.712 candidatas de 18.507 detecciones)."""

from __future__ import annotations

from pathlib import Path

from analizar_detecciones import cargar
from hallazgos import construir_hallazgos
from seleccion import seleccionar_candidatos


def _pred(i: int, clase: str, score: float) -> dict:
    return {"instance_index": i, "damage_class": clase, "score": score, "bbox_xywh": [0, 0, 10, 10]}


def probar_casos_pequenos() -> None:
    preds = [
        _pred(1, "dent", 0.9), _pred(2, "dent", 0.8), _pred(3, "dent", 0.7),   # top_k=2 -> se quedan 1 y 2
        _pred(4, "glass shatter", 0.55), _pred(5, "glass shatter", 0.45),       # score_min=0.5 -> solo la 4
        _pred(6, "lamp broken", 0.31),                                           # una sola: se queda aunque sea baja
        _pred(7, "clase nueva", 0.6), _pred(8, "clase nueva", 0.5), _pred(9, "clase nueva", 0.4),  # por defecto top_k=2
    ]
    candidatas, descartadas = seleccionar_candidatos(preds)
    assert [p["instance_index"] for p in candidatas] == [1, 2, 4, 6, 7, 8], candidatas
    assert descartadas == {"dent": 1, "glass shatter": 1, "clase nueva": 1}, descartadas

    # el resultado conserva el orden original y no depende de que vengan ordenadas por score
    barajadas = [preds[2], preds[0], preds[1]]
    assert sorted(p["instance_index"] for p in seleccionar_candidatos(barajadas)[0]) == [1, 2]

    # integrado en construir_hallazgos: nada desaparece sin rastro
    r = construir_hallazgos({"image_id": 7, "predictions": preds})
    assert [f["finding_id"] for f in r["findings"]] == ["7-1", "7-2", "7-4", "7-6", "7-7", "7-8"]
    assert r["resumen_filtro_previo"] == {
        "detecciones_totales": 9, "candidatas": 6,
        "descartadas_por_clase": {"dent": 1, "glass shatter": 1, "clase nueva": 1},
    }
    sin_filtro = construir_hallazgos({"image_id": 7, "predictions": preds}, filtrar=False)
    assert len(sin_filtro["findings"]) == 9 and sin_filtro["resumen_filtro_previo"]["descartadas_por_clase"] == {}


def probar_export_real() -> None:
    carpeta = Path(__file__).resolve().parents[5] / "piia2_detecciones" / "baseline_500"
    if not carpeta.exists():
        print("(exportacion real no encontrada: se salta la comprobacion con las 500 imagenes)")
        return
    imagenes = cargar(carpeta)
    total = sum(len(i["predictions"]) for i in imagenes)
    candidatas = sum(len(seleccionar_candidatos(i["predictions"])[0]) for i in imagenes)
    assert (total, candidatas) == (18507, 3712), (total, candidatas)

    # recall de PIIA-1 que sobrevive al filtro (aciertos entre las candidatas / aciertos totales)
    for clase, minimo in (("glass shatter", 0.97), ("tire flat", 0.99), ("lamp broken", 0.93)):
        tp_total = tp_cand = 0
        for im in imagenes:
            cand_ids = {p["instance_index"] for p in seleccionar_candidatos(im["predictions"])[0]}
            for p in im["predictions"]:
                if p["damage_class"] == clase and p["is_true_positive"]:
                    tp_total += 1
                    tp_cand += p["instance_index"] in cand_ids
        assert tp_cand / tp_total >= minimo, (clase, tp_cand, tp_total)
    print(f"export real ok: {candidatas} candidatas de {total} detecciones ({100 * candidatas / total:.0f} %)")


def main() -> None:
    probar_casos_pequenos()
    probar_export_real()
    print("Todo ok: filtro previo.")


if __name__ == "__main__":
    main()
