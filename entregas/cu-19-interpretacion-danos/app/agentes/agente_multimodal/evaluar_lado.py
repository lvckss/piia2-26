"""Evaluacion de la variante del prompt del lado izquierdo/derecho (Issue #54, slice 5, AC-012).

Plan v1.1: https://github.com/lvckss/piia2-26/issues/54#issuecomment-6806386857
Linea base y criterio de adopcion (fijados antes de ejecutar): https://github.com/lvckss/piia2-26/issues/54#issuecomment-6820567012

Tres pasos, desde esta carpeta:

    python evaluar_lado.py plan                          # sin API: comprueba fotos y recortes y cuenta las llamadas
    python evaluar_lado.py ejecutar                      # GASTA PRESUPUESTO: una llamada por hallazgo (unas 234)
    python evaluar_lado.py evaluar                       # sin API: compara con la linea base y las etiquetas

`ejecutar` necesita `OPENAI_API_KEY` y el modelo en `OPENAI_MODEL` (o `--modelo`); la variante se ejecuta UNA vez y
se niega a repetirse si ya hay resultados en la carpeta de salida (salvo `--repetir`).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Callable

from PIL import Image

from catalogo import cargar_catalogo
from evaluar_vision import ruta_foto
from vision import PROMPT_VARIANTE_ORIENTACION, analizar_hallazgo

# Criterio de adopcion de AC-012, fijado antes de ver resultados (comentario de la #54 enlazado arriba):
ACIERTOS_MINIMOS = 24  # de los 29 hallazgos decidibles (la linea base es 18)
CAMBIOS_DE_VEREDICTO_MAXIMOS = 25  # el 11 % de 234: el ruido medido al preguntar dos veces

RAIZ = Path(__file__).resolve().parents[5]
CASO = RAIZ / "entregas" / "cu-19-interpretacion-danos"
ARCHIVO_RESULTADOS = "resultados_variante.json"


# --- calculo -----------------------------------------------------------------------------------------------------

def lado_de_pieza(pieza_id: str | None) -> str | None:
    """`I` o `D` si la pieza tiene lado (sufijo `_I` o `_D`); None si no lo tiene o no hay pieza."""
    if pieza_id and pieza_id.endswith("_I"):
        return "I"
    if pieza_id and pieza_id.endswith("_D"):
        return "D"
    return None


def lado_verdadero(etiqueta: str, lado_base: str | None) -> str | None:
    """Lado verdadero de un hallazgo segun la etiqueta de Lucia: `si` conserva el lado de la linea base, `no` es el
    contrario; `nose` (o sin lado de base) no tiene lado verdadero."""
    if lado_base not in ("I", "D"):
        return None
    if etiqueta == "si":
        return lado_base
    if etiqueta == "no":
        return "D" if lado_base == "I" else "I"
    return None


def wilson(x: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalo de Wilson al 95 % (proporciones entre 0 y 1) de `x` aciertos en `n`."""
    if n == 0:
        return (0.0, 0.0)
    p = x / n
    d = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / d
    mitad = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centro - mitad), min(1.0, centro + mitad))


def _imagen_de(finding_id: str) -> str:
    return finding_id.split("-")[0]


def evaluar(base: dict[str, dict], variante: dict[str, dict], etiquetas: dict[str, dict]) -> dict[str, Any]:
    """Compara la variante con la linea base sobre los hallazgos etiquetados y decide si se adopta.

    Los decidibles son los etiquetados `si` o `no`. Un decidible es acierto de la variante si su `pieza_id` tiene el
    lado verdadero; sin pieza, con una pieza sin lado o con `incierto` es fallo."""
    decidibles = aciertos_base = aciertos_variante = 0
    indecidibles = indecidibles_a_incierto = 0
    imagenes: set[str] = set()
    error_base: set[str] = set()
    error_variante: set[str] = set()
    errores_variante: list[str] = []
    for fid, etiqueta in etiquetas.items():
        if fid not in base:
            continue
        imagenes.add(_imagen_de(fid))
        v = variante.get(fid)
        if etiqueta["lado"] == "nose":
            indecidibles += 1
            if v is not None and v.get("vision_verdict") == "incierto":
                indecidibles_a_incierto += 1
            continue
        lado_base = lado_de_pieza(base[fid].get("pieza_id"))
        verdadero = lado_verdadero(etiqueta["lado"], lado_base)
        if verdadero is None:
            continue
        decidibles += 1
        ok_base = lado_base == verdadero
        ok_variante = v is not None and lado_de_pieza(v.get("pieza_id")) == verdadero
        aciertos_base += ok_base
        aciertos_variante += ok_variante
        if not ok_base:
            error_base.add(_imagen_de(fid))
        if not ok_variante:
            error_variante.add(_imagen_de(fid))
            errores_variante.append(fid)
    comunes = [f for f in base if f in variante]
    cambios = sum(1 for f in comunes if base[f].get("vision_verdict") != variante[f].get("vision_verdict"))
    condicion_lado = aciertos_variante >= ACIERTOS_MINIMOS
    condicion_veredictos = cambios <= CAMBIOS_DE_VEREDICTO_MAXIMOS
    return {
        "decidibles": decidibles,
        "aciertos_base": aciertos_base,
        "aciertos_variante": aciertos_variante,
        "wilson_base": wilson(aciertos_base, decidibles),
        "wilson_variante": wilson(aciertos_variante, decidibles),
        "errores_variante": errores_variante,
        "hallazgos_comparados": len(comunes),
        "cambios_de_veredicto": cambios,
        "indecidibles": indecidibles,
        "indecidibles_a_incierto": indecidibles_a_incierto,
        "imagenes": len(imagenes),
        "imagenes_con_error_base": len(error_base),
        "imagenes_con_error_variante": len(error_variante),
        "condicion_lado": condicion_lado,
        "condicion_veredictos": condicion_veredictos,
        "adoptar": condicion_lado and condicion_veredictos,
    }


# --- datos y ejecucion -------------------------------------------------------------------------------------------

def cargar_salidas(base_dir: Path) -> dict[int, dict]:
    """Las salidas del Agente 1 de la linea base (una por imagen), por `image_id`."""
    salidas: dict[int, dict] = {}
    for ruta in sorted(Path(base_dir).glob("[0-9]*.json")):
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        salidas[int(datos["image_id"])] = datos
    return salidas


def findings_por_id(salidas: dict[int, dict]) -> dict[str, dict]:
    return {f["finding_id"]: f for s in salidas.values() for f in s["findings"]}


def _problemas(salidas: dict[int, dict], recortes_dir: Path, detecciones_dir: Path, cardd_dir: Path) -> list[str]:
    """Fotos, detecciones y recortes que faltan para poder ejecutar."""
    faltan: list[str] = []
    for image_id, salida in sorted(salidas.items()):
        deteccion_ruta = Path(detecciones_dir) / f"{image_id:06d}.json"
        if not deteccion_ruta.exists():
            faltan.append(f"deteccion {deteccion_ruta.name}")
        else:
            foto = ruta_foto(Path(cardd_dir), json.loads(deteccion_ruta.read_text(encoding="utf-8")))
            if not foto.exists():
                faltan.append(f"foto {foto.name}")
        for finding in salida["findings"]:
            if not (Path(recortes_dir) / finding["crop_image_path"]).exists():
                faltan.append(f"recorte {finding['crop_image_path']}")
    return faltan


def ejecutar(
    base_dir: Path,
    recortes_dir: Path,
    detecciones_dir: Path,
    cardd_dir: Path,
    salida_dir: Path,
    cliente: Any,
    modelo: str,
    catalogo: Any,
    cache_dir: Path,
    max_llamadas: int = 260,
) -> dict[str, dict]:
    """Ejecuta la variante del prompt sobre cada hallazgo de la linea base (una llamada por hallazgo) y guarda
    `<salida>/resultados_variante.json` con el veredicto, la pieza, la severidad y la descripcion de cada uno.
    Se niega (ValueError) antes de llamar a nada si las llamadas previstas superan `max_llamadas`."""
    salidas = cargar_salidas(base_dir)
    previstas = sum(len(s["findings"]) for s in salidas.values())
    if previstas > max_llamadas:
        raise ValueError(f"{previstas} llamadas previstas superan el tope de {max_llamadas}")
    salida_dir = Path(salida_dir)
    salida_dir.mkdir(parents=True, exist_ok=True)
    uso: dict[str, int] = {}
    resultados: dict[str, dict] = {}
    for k, (image_id, salida) in enumerate(sorted(salidas.items()), start=1):
        deteccion = json.loads((Path(detecciones_dir) / f"{image_id:06d}.json").read_text(encoding="utf-8"))
        with Image.open(ruta_foto(Path(cardd_dir), deteccion)) as imagen:
            imagen.load()
            for finding in salida["findings"]:
                entrada = dict(finding)
                entrada["crop_image_path"] = str(Path(recortes_dir) / finding["crop_image_path"])
                r = analizar_hallazgo(cliente, modelo, imagen, entrada, catalogo, cache_dir, uso,
                                      prompt_template=PROMPT_VARIANTE_ORIENTACION)
                resultados[finding["finding_id"]] = {
                    "vision_verdict": r["vision_verdict"], "pieza_id": r["pieza_id"], "severidad": r["severidad"],
                    "vision_description": r["vision_description"],
                }
        print(f"  [{k}/{len(salidas)}] imagen {image_id}: {len(salida['findings'])} hallazgos "
              f"(llamadas facturadas hasta ahora: {uso.get('llamadas', 0)})", flush=True)
    (salida_dir / ARCHIVO_RESULTADOS).write_text(json.dumps(resultados, ensure_ascii=False, indent=1), encoding="utf-8")
    (salida_dir / "uso_ejecucion.json").write_text(json.dumps(uso, indent=1), encoding="utf-8")
    return resultados


# --- linea de comandos -------------------------------------------------------------------------------------------

def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paso", choices=("plan", "ejecutar", "evaluar"))
    ap.add_argument("--base", type=Path, default=CASO / "app" / "agentes" / "ejemplos_contrato" / "agente1_real",
                    help="salidas del Agente 1 de la linea base (las 30 versionadas)")
    ap.add_argument("--recortes", type=Path, default=RAIZ / "piia2_detecciones" / "salida_agente1",
                    help="carpeta que contiene `crops/` de la linea base")
    ap.add_argument("--detecciones", type=Path, default=RAIZ / "piia2_detecciones" / "baseline_500")
    ap.add_argument("--cardd", type=Path, default=RAIZ / "CarDD_release" / "CarDD_COCO")
    ap.add_argument("--salida", type=Path, default=RAIZ / "piia2_detecciones" / "evaluacion_lado")
    ap.add_argument("--cache-dir", type=Path, default=RAIZ / "piia2_detecciones" / "cache_lado")
    ap.add_argument("--etiquetas", type=Path, default=RAIZ / "piia2_detecciones" / "revision" / "etiquetas_lado.json")
    ap.add_argument("--max-llamadas", type=int, default=260, help="tope de llamadas (proteccion de presupuesto)")
    ap.add_argument("--modelo", help="id del modelo (o variable OPENAI_MODEL)")
    ap.add_argument("--repetir", action="store_true", help="permite volver a ejecutar aunque ya haya resultados")
    return ap.parse_args(argv)


def _porcentaje(x: int, n: int) -> str:
    return f"{round(100 * x / n)} %" if n else "-"


def _imprimir_evaluacion(r: dict[str, Any]) -> None:
    n = r["decidibles"]
    wb, wv = r["wilson_base"], r["wilson_variante"]
    print(f"Linea base: {r['aciertos_base']} de {n} ({_porcentaje(r['aciertos_base'], n)}), Wilson {round(100 * wb[0])}-{round(100 * wb[1])} %")
    print(f"Variante:   {r['aciertos_variante']} de {n} ({_porcentaje(r['aciertos_variante'], n)}), Wilson {round(100 * wv[0])}-{round(100 * wv[1])} %"
          f" | condicion 1 (al menos {ACIERTOS_MINIMOS}): {'SI' if r['condicion_lado'] else 'NO'}")
    print(f"Veredictos distintos: {r['cambios_de_veredicto']} de {r['hallazgos_comparados']} (como mucho {CAMBIOS_DE_VEREDICTO_MAXIMOS})"
          f" | condicion 2: {'SI' if r['condicion_veredictos'] else 'NO'}")
    print(f"Indecidibles que pasan a `incierto`: {r['indecidibles_a_incierto']} de {r['indecidibles']}")
    print(f"Imagenes con algun lado al reves: base {r['imagenes_con_error_base']} de {r['imagenes']}; "
          f"variante {r['imagenes_con_error_variante']} de {r['imagenes']}")
    print(f"Fallos de la variante: {', '.join(r['errores_variante']) or 'ninguno'}")
    print("\nDECISION:", "SE CUMPLEN LAS DOS CONDICIONES: se puede adoptar" if r["adoptar"] else "NO se cumplen las dos condiciones: no se adopta")


def main(argv: list[str] | None = None, crear_cliente: Callable[[], Any] | None = None, catalogo: Any = None) -> int:
    args = _argumentos(argv)
    salidas = cargar_salidas(args.base)
    previstas = sum(len(s["findings"]) for s in salidas.values())

    if args.paso == "evaluar":
        ruta = args.salida / ARCHIVO_RESULTADOS
        if not ruta.exists():
            print(f"Falta {ruta}: ejecuta antes `python evaluar_lado.py ejecutar`.")
            return 2
        resultados = json.loads(ruta.read_text(encoding="utf-8"))
        etiquetas = json.loads(args.etiquetas.read_text(encoding="utf-8"))
        r = evaluar(findings_por_id(salidas), resultados, etiquetas)
        _imprimir_evaluacion(r)
        (args.salida / "evaluacion.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
        return 0

    faltan = _problemas(salidas, args.recortes, args.detecciones, args.cardd)
    print(f"{len(salidas)} imagenes, {previstas} hallazgos: {previstas} llamadas previstas (una por hallazgo) | faltan: {len(faltan)}")
    if faltan:
        print("AVISO: faltan", ", ".join(faltan[:6]), "..." if len(faltan) > 6 else "")
        return 1
    if args.paso == "plan":
        print("\nPLAN SOLO: no se ha llamado a la API. Para ejecutar de verdad: `python evaluar_lado.py ejecutar`.")
        return 0

    if previstas > args.max_llamadas:
        print(f"{previstas} llamadas previstas superan --max-llamadas={args.max_llamadas}.")
        return 2
    if (args.salida / ARCHIVO_RESULTADOS).exists() and not args.repetir:
        print(f"Ya hay resultados en {args.salida}: la variante se ejecuta una sola vez. Usa --repetir solo si es un error.")
        return 2
    try:
        from agente1 import crear_cliente_openai, resolver_modelo

        modelo = resolver_modelo(args.modelo)
        catalogo = catalogo or cargar_catalogo()
        cliente = (crear_cliente or crear_cliente_openai)()
    except (RuntimeError, FileNotFoundError) as error:
        print(f"ERROR: {error}")
        return 2
    print(f"\nEjecutando la variante con {modelo}: una linea por imagen (lo servido desde cache no se factura)", flush=True)
    ejecutar(args.base, args.recortes, args.detecciones, args.cardd, args.salida, cliente, modelo, catalogo,
             args.cache_dir, args.max_llamadas)
    print(f"\nListo. Resultados en {args.salida}. Ahora: `python evaluar_lado.py evaluar`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
