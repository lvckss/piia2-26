"""Prueba evaluar_vision.py sin API Key: con un modelo falso, sobre las
detecciones reales exportadas de Colab y las fotos reales del CarDD local (se
salta si faltan). Comprueba la eleccion de imagenes, el plan (que no llama a
nada), el flujo completo con cache y la aritmetica de las metricas."""

from __future__ import annotations

import tempfile
from pathlib import Path

from analizar_detecciones import cargar
from catalogo import cargar_catalogo
from evaluar_vision import elegir_imagenes, evaluar_modelo, metricas, plan, ruta_foto
from probar_vision_stub import ClienteFalso

RAIZ = Path(__file__).resolve().parents[5]


def probar_metricas() -> None:
    def r(clase, score, tp, verdict, pieza="PARAG_DEL", regla=True):
        return {"category": clase, "score": score, "is_tp": tp, "verdict": verdict, "pieza_id": pieza, "regla": regla}

    resultados = [
        r("dent", 0.9, True, "confirmado"),          # acierto confirmado
        r("dent", 0.5, True, "rechazado", None, None),  # acierto que la vision pierde
        r("dent", 0.8, False, "rechazado", None, None),  # FP bien rechazado
        r("dent", 0.7, False, "confirmado"),         # FP que se cuela
        r("dent", 0.4, False, "incierto", None, None),
    ]
    m = metricas(resultados)["por_clase"]["dent"]
    assert (m["candidatas"], m["aciertos_piia1"], m["falsos_positivos"]) == (5, 2, 3)
    assert m["acierto_confirmado"] == 0.5 and m["acierto_rechazado"] == 0.5
    assert abs(m["fp_rechazado"] - 1 / 3) < 1e-9 and abs(m["fp_confirmado"] - 1 / 3) < 1e-9

    puerta = {f["umbral"]: f for f in metricas(resultados)["puertas"]["dent"]}
    # a >= 0.7: sin vision entran 0.9(TP), 0.8(FP), 0.7(FP) -> precision 1/3; con vision solo 0.9 y 0.7 -> 1/2
    assert abs(puerta[0.7]["precision_sin_vision"] - 1 / 3) < 1e-9
    assert puerta[0.7]["precision_con_vision"] == 0.5 and puerta[0.7]["confirmed"] == 2
    assert puerta[0.7]["recall_con_vision"] == 0.5          # 1 de los 2 aciertos de PIIA-1
    # clase sin candidatas: sin division por cero
    assert metricas(resultados)["por_clase"]["tire flat"]["acierto_confirmado"] is None


def probar_con_datos_reales() -> None:
    detecciones = RAIZ / "piia2_detecciones" / "baseline_500"
    cardd = RAIZ / "CarDD_release" / "CarDD_COCO"
    if not detecciones.exists() or not cardd.exists():
        print("(faltan las detecciones exportadas o el CarDD local: se salta la prueba con datos reales)")
        return

    imagenes = cargar(detecciones)
    elegidas, cuenta = elegir_imagenes(imagenes, n=40, min_aciertos=8, seed=42)
    assert len(elegidas) == 40
    assert all(cuenta[c] >= 8 for c in ("glass shatter", "lamp broken", "tire flat", "dent", "scratch", "crack")), cuenta
    assert [i["image_id"] for i in elegidas] == [i["image_id"] for i in elegir_imagenes(imagenes, 40, 8, 42)[0]], "no determinista"

    llamadas = plan(elegidas, cardd, ["modelo-a", "modelo-b"])      # el plan no llama a nada
    assert 150 < llamadas < 500, llamadas
    assert all(ruta_foto(cardd, i).exists() for i in elegidas), "faltan fotos locales"

    pocas = elegidas[:6]
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        cliente, uso = ClienteFalso(), {}
        res = evaluar_modelo(cliente, "modelo-falso", pocas, cardd, cargar_catalogo(), tmp_dir / "cache", tmp_dir / "crops", uso)
        esperadas = plan_llamadas(pocas)
        assert len(res) == esperadas == uso["llamadas"] == len(cliente.llamadas), (len(res), esperadas, uso)
        assert uso["prompt_tokens"] == 1500 * esperadas

        # segunda pasada con la misma cache: no se factura nada
        uso2 = {}
        evaluar_modelo(cliente, "modelo-falso", pocas, cardd, cargar_catalogo(), tmp_dir / "cache", tmp_dir / "crops", uso2)
        assert uso2 == {} and len(cliente.llamadas) == esperadas, "la cache no evito las llamadas"

        m = metricas(res)["por_clase"]
        assert sum(c["candidatas"] for c in m.values()) == esperadas
    print(f"datos reales ok: {len(res)} candidatas de {len(pocas)} fotos reales evaluadas con modelo falso, cache sin coste")


def plan_llamadas(imagenes: list[dict]) -> int:
    from seleccion import seleccionar_candidatos

    return sum(len(seleccionar_candidatos(i["predictions"])[0]) for i in imagenes)


def main() -> None:
    probar_metricas()
    probar_con_datos_reales()
    print("Todo ok: evaluar_vision.")


if __name__ == "__main__":
    main()
