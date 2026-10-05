"""Mide la segunda opinion del modelo de vision con las detecciones exportadas
de Colab, usando `is_true_positive` (acierto de PIIA-1 contra las anotaciones
reales de CarDD) como verdad. Sirve para comparar modelos y para elegir el
umbral de score de `confirmed` con la regla completa (score + vision).

POR DEFECTO NO LLAMA A LA API: solo cuenta cuantas llamadas haria y las
estima. Para ejecutarlo de verdad hay que anadir `--ejecutar` (y tener
OPENAI_API_KEY en el entorno).

    python evaluar_vision.py --modelos ID_MODELO_1 ID_MODELO_2          # plan, no gasta nada
    python evaluar_vision.py --modelos ID_MODELO_1 --n-imagenes 5 --ejecutar   # prueba barata
    python evaluar_vision.py --modelos ID_MODELO_1 ID_MODELO_2 --ejecutar      # comparacion

Que mide, por clase y modelo:
- de los aciertos de PIIA-1 que llegan a la vision, cuantos confirma (si
  rechaza aciertos reales, pierde dano real);
- de los falsos positivos de PIIA-1, cuantos rechaza (para eso esta);
- para cada umbral de score, precision y recall de `confirmed` con y sin
  vision (recall = sobre los aciertos de PIIA-1 que llegaron a la vision; el
  techo de SAM3 queda fuera, ver analizar_detecciones.py).

No se puede medir si la PIEZA y la SEVERIDAD son correctas: CarDD no trae
esas etiquetas. Eso requiere revisar a mano una muestra.

Las imagenes elegidas no son una muestra al azar: se garantizan unos aciertos
minimos de cada clase para poder medir tambien las raras.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image

from analizar_detecciones import CLASES, cargar
from catalogo import Catalogo, cargar_catalogo
from hallazgos import construir_hallazgos
from recorte import generar_recortes
from seleccion import seleccionar_candidatos
from vision import analizar_hallazgo

# estimacion gruesa de entrada por llamada: 2 imagenes + prompt con 35 piezas
TOKENS_POR_LLAMADA_ESTIMADOS = 2000
UMBRALES_PUERTA = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)


def _raiz_repo() -> Path:
    return Path(__file__).resolve().parents[5]


def _aciertos_candidatos(img: dict[str, Any]) -> Counter:
    candidatas, _ = seleccionar_candidatos(img["predictions"])
    return Counter(p["damage_class"] for p in candidatas if p["is_true_positive"])


def elegir_imagenes(
    imagenes: list[dict[str, Any]], n: int, min_aciertos: int, seed: int
) -> tuple[list[dict[str, Any]], Counter]:
    """Elige `n` imagenes procurando al menos `min_aciertos` aciertos de PIIA-1
    de cada clase entre las candidatas (empieza por las clases raras) y rellena
    el resto al azar. Determinista."""
    rng = random.Random(seed)
    orden = imagenes[:]
    rng.shuffle(orden)
    aciertos = {id(i): _aciertos_candidatos(i) for i in orden}

    total_por_clase: Counter = Counter()
    for a in aciertos.values():
        total_por_clase.update(a)

    elegidas: list[dict[str, Any]] = []
    elegidas_ids: set[int] = set()
    cuenta: Counter = Counter()
    for clase in sorted(total_por_clase, key=lambda c: total_por_clase[c]):
        for img in orden:
            if cuenta[clase] >= min_aciertos or len(elegidas) >= n:
                break
            if id(img) in elegidas_ids or not aciertos[id(img)][clase]:
                continue
            elegidas.append(img)
            elegidas_ids.add(id(img))
            cuenta.update(aciertos[id(img)])
    for img in orden:
        if len(elegidas) >= n:
            break
        if id(img) not in elegidas_ids:
            elegidas.append(img)
            elegidas_ids.add(id(img))
            cuenta.update(aciertos[id(img)])
    return elegidas, cuenta


def ruta_foto(cardd_dir: Path, deteccion: dict[str, Any]) -> Path:
    """Foto local del CarDD oficial: <cardd>/<split>2017/<fichero>.jpg."""
    return cardd_dir / f"{deteccion['split']}2017" / deteccion["image_file"]


def plan(imagenes: list[dict[str, Any]], cardd_dir: Path, modelos: list[str]) -> int:
    candidatas: Counter = Counter()
    aciertos: Counter = Counter()
    for img in imagenes:
        cand, _ = seleccionar_candidatos(img["predictions"])
        candidatas.update(p["damage_class"] for p in cand)
        aciertos.update(p["damage_class"] for p in cand if p["is_true_positive"])
    llamadas = sum(candidatas.values())
    faltan = [i["image_file"] for i in imagenes if not ruta_foto(cardd_dir, i).exists()]

    print(f"{len(imagenes)} imagenes elegidas | fotos locales que faltan: {len(faltan)}")
    print(f"{'clase':14s} {'candidatas':>10s} {'aciertos PIIA-1':>16s}")
    for clase in CLASES:
        print(f"{clase:14s} {candidatas[clase]:>10d} {aciertos[clase]:>16d}")
    print(f"\nLlamadas por modelo: {llamadas}  (~{llamadas * TOKENS_POR_LLAMADA_ESTIMADOS / 1e6:.1f} M tokens de entrada, estimacion gruesa)")
    print(f"Modelos: {len(modelos)} -> {llamadas * len(modelos)} llamadas en total")
    print("Multiplica los tokens por el precio por millon de tokens de cada modelo en la cuenta de la empresa.")
    if faltan:
        print("AVISO: faltan fotos, esas imagenes se saltaran:", faltan[:5], "...")
    return llamadas


def evaluar_modelo(
    client: Any,
    modelo: str,
    imagenes: list[dict[str, Any]],
    cardd_dir: Path,
    catalogo: Catalogo,
    cache_dir: Path,
    crops_dir: Path,
    uso: dict[str, int],
) -> list[dict[str, Any]]:
    resultados: list[dict[str, Any]] = []
    for n, det in enumerate(imagenes, 1):
        ruta = ruta_foto(cardd_dir, det)
        if not ruta.exists():
            continue
        local = dict(det)
        local["image_path"] = str(ruta)
        hallazgos = construir_hallazgos(local)
        generar_recortes(local, hallazgos, crops_dir)
        acierto = {f"{det['image_id']}-{p['instance_index']}": p["is_true_positive"] for p in det["predictions"]}

        with Image.open(ruta) as imagen:
            imagen.load()
            for f in hallazgos["findings"]:
                r = analizar_hallazgo(client, modelo, imagen, f, catalogo, cache_dir, uso)
                resultados.append(
                    {
                        "finding_id": f["finding_id"],
                        "category": f["category"],
                        "score": f["score"],
                        "is_tp": bool(acierto[f["finding_id"]]),
                        "verdict": r["vision_verdict"],
                        "pieza_id": r["pieza_id"],
                        "severidad": r["severidad"],
                        "regla": r["regla_coste_aplicable"],
                    }
                )
        if n % 10 == 0:
            print(f"  {modelo}: {n}/{len(imagenes)} imagenes, {uso.get('llamadas', 0)} llamadas facturadas")
    return resultados


def _frac(num: int, den: int) -> float | None:
    return num / den if den else None


def metricas(resultados: list[dict[str, Any]]) -> dict[str, Any]:
    por_clase: dict[str, Any] = {}
    puertas: dict[str, list[dict[str, Any]]] = {}
    for clase in CLASES:
        filas = [r for r in resultados if r["category"] == clase]
        tp = [r for r in filas if r["is_tp"]]
        fp = [r for r in filas if not r["is_tp"]]
        cuenta = lambda grupo, v: sum(r["verdict"] == v for r in grupo)  # noqa: E731
        por_clase[clase] = {
            "candidatas": len(filas),
            "aciertos_piia1": len(tp),
            "falsos_positivos": len(fp),
            "acierto_confirmado": _frac(cuenta(tp, "confirmado"), len(tp)),
            "acierto_rechazado": _frac(cuenta(tp, "rechazado"), len(tp)),
            "acierto_incierto": _frac(cuenta(tp, "incierto"), len(tp)),
            "fp_rechazado": _frac(cuenta(fp, "rechazado"), len(fp)),
            "fp_confirmado": _frac(cuenta(fp, "confirmado"), len(fp)),
            "fp_incierto": _frac(cuenta(fp, "incierto"), len(fp)),
        }
        filas_puerta = []
        for gate in UMBRALES_PUERTA:
            solo_score = [r for r in filas if r["score"] >= gate]
            con_vision = [r for r in solo_score if r["verdict"] == "confirmado" and r["pieza_id"] and r["regla"] is True]
            filas_puerta.append(
                {
                    "umbral": gate,
                    "precision_sin_vision": _frac(sum(r["is_tp"] for r in solo_score), len(solo_score)),
                    "recall_sin_vision": _frac(sum(r["is_tp"] for r in solo_score), len(tp)),
                    "precision_con_vision": _frac(sum(r["is_tp"] for r in con_vision), len(con_vision)),
                    "recall_con_vision": _frac(sum(r["is_tp"] for r in con_vision), len(tp)),
                    "confirmed": len(con_vision),
                }
            )
        puertas[clase] = filas_puerta
    return {"por_clase": por_clase, "puertas": puertas}


def _p(x: float | None) -> str:
    return "  -  " if x is None else f"{100 * x:5.1f}"


def imprimir(modelo: str, m: dict[str, Any]) -> None:
    print(f"\n===== {modelo} =====")
    print("Que hace la vision con lo que le llega (% sobre aciertos / sobre falsos positivos de PIIA-1)")
    print(f"{'clase':14s} {'acierto':>7s} {'FP':>4s} | {'ACIERTO:conf':>12s} {'rech':>6s} {'incier':>7s} | {'FP:rech':>8s} {'conf':>6s} {'incier':>7s}")
    for clase, c in m["por_clase"].items():
        print(
            f"{clase:14s} {c['aciertos_piia1']:>7d} {c['falsos_positivos']:>4d} | {_p(c['acierto_confirmado']):>12s} "
            f"{_p(c['acierto_rechazado']):>6s} {_p(c['acierto_incierto']):>7s} | {_p(c['fp_rechazado']):>8s} "
            f"{_p(c['fp_confirmado']):>6s} {_p(c['fp_incierto']):>7s}"
        )
    print("\nconfirmed segun el umbral de score (precision/recall %, sin vision -> con vision)")
    print(f"{'clase':14s} {'umbral':>6s} {'prec sin':>9s} {'prec con':>9s} {'rec sin':>8s} {'rec con':>8s} {'confirmed':>9s}")
    for clase, filas in m["puertas"].items():
        for f in filas:
            print(
                f"{clase:14s} {f['umbral']:>6.1f} {_p(f['precision_sin_vision']):>9s} {_p(f['precision_con_vision']):>9s} "
                f"{_p(f['recall_sin_vision']):>8s} {_p(f['recall_con_vision']):>8s} {f['confirmed']:>9d}"
            )
        print()


def _slug(modelo: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", modelo)


def main() -> None:
    raiz = _raiz_repo()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modelos", nargs="+", required=True, help="ids de modelo exactos de la cuenta de la empresa")
    ap.add_argument("--detecciones", type=Path, default=raiz / "piia2_detecciones" / "baseline_500")
    ap.add_argument("--cardd", type=Path, default=raiz / "CarDD_release" / "CarDD_COCO")
    ap.add_argument("--n-imagenes", type=int, default=40)
    ap.add_argument("--min-aciertos", type=int, default=8, help="aciertos minimos de PIIA-1 por clase en la muestra")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--cache-dir", type=Path, default=raiz / "piia2_detecciones" / "cache_vision")
    ap.add_argument("--salida", type=Path, default=raiz / "piia2_detecciones" / "evaluacion_vision")
    ap.add_argument("--max-llamadas", type=int, default=600, help="tope de llamadas POR MODELO (proteccion de presupuesto)")
    ap.add_argument("--ejecutar", action="store_true", help="hacer las llamadas de verdad (gasta presupuesto)")
    args = ap.parse_args()

    imagenes = cargar(args.detecciones)
    elegidas, cuenta = elegir_imagenes(imagenes, args.n_imagenes, args.min_aciertos, args.seed)
    llamadas = plan(elegidas, args.cardd, args.modelos)

    if not args.ejecutar:
        print("\nPLAN SOLO: no se ha llamado a la API. Anade --ejecutar para hacerlo de verdad.")
        return
    if llamadas > args.max_llamadas:
        raise SystemExit(f"{llamadas} llamadas por modelo superan --max-llamadas={args.max_llamadas}. Reduce --n-imagenes o sube el tope a conciencia.")

    from agente1 import crear_cliente_openai

    client = crear_cliente_openai()
    catalogo = cargar_catalogo()
    args.salida.mkdir(parents=True, exist_ok=True)

    for modelo in args.modelos:
        uso: dict[str, int] = {}
        t0 = time.time()
        resultados = evaluar_modelo(client, modelo, elegidas, args.cardd, catalogo, args.cache_dir, args.salida / "crops", uso)
        m = metricas(resultados)
        imprimir(modelo, m)
        print(f"\nCoste real de {modelo}: {uso.get('llamadas', 0)} llamadas facturadas | "
              f"{uso.get('prompt_tokens', 0)} tokens de entrada | {uso.get('completion_tokens', 0)} de salida | "
              f"{time.time() - t0:.0f} s (lo servido desde cache no cuenta)")
        (args.salida / f"resultados_{_slug(modelo)}.json").write_text(
            json.dumps({"modelo": modelo, "uso": uso, "metricas": m, "resultados": resultados}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
