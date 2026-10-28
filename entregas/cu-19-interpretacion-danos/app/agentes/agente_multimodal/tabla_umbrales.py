"""Tabla de precision por clase y score para calibrar los umbrales (Issue #44, plan v1.3: AC-003 y AC-004).

Cruza lo que la vision confirmo (con su score) con las etiquetas de un modelo juez (`juez_vision.py`) y calcula,
por clase de dano:

1. por tramo de score de 0,1 (alineado con la rejilla de umbrales 0,3 a 0,9): cuantos candidatos a nivel firme hay y
   que proporcion es dano real segun el juez;
2. acumulado por umbral (score >= umbral): lo mismo, con el umbral actual marcado y cuantos entrarian o saldrian;
3. lo que la vision rechaza y el juez ve como dano;
4. con `--export`, cuantos candidatos que PIIA-1 daba por fallo (`is_true_positive` falso) eran dano real.

Un **candidato a nivel firme** es un hallazgo que la vision confirmo, con pieza y con regla de coste aplicable: es lo
que `confianza.decidir_tier` convertiria en `confirmed` si su score pasara el umbral. «Dano real» cuenta `si` y
`otra` del juez; «clase correcta», solo `si`. Los `dudo` y los hallazgos sin etiqueta no entran en el denominador, y
toda celda con menos de 5 casos decididos se marca como no concluyente. **Son etiquetas de un modelo, no verdad
humana**: esto no fija ningun umbral, solo pone los datos delante de quien lo decida.

Uso (desde esta carpeta):
    python tabla_umbrales.py --salidas <carpeta de salidas del Agente 1> --etiquetas <etiquetas_juez.csv> \\
        [--export <carpeta del export de PIIA-1>] [--resumen <resumen_juez.json>] [--salida informe.md]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from confianza import CATEGORY_REVIEW_THRESHOLD
from etiquetado import ETIQUETAS, MINIMO_CONCLUYENTE, EtiquetasNoValidas, _ic, _leer_salidas, _pct, intervalo_wilson, leer_etiquetas

CLASES = tuple(CATEGORY_REVIEW_THRESHOLD)
TRAMOS = tuple((round(0.3 + 0.1 * i, 1), round(0.4 + 0.1 * i, 1)) for i in range(7))
UMBRALES = tuple(round(0.3 + 0.1 * i, 1) for i in range(7))
_EPS = 1e-9


def _num(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def _nombre_tramo(i: int) -> str:
    return f"{_num(TRAMOS[i][0])}-{_num(TRAMOS[i][1])}"


def tramo_de_score(score: float) -> int | None:
    """Indice del tramo de 0,1 (0,3-0,4 ... 0,9-1,0) al que pertenece el score; el 1,0 cae en el ultimo; None si queda fuera."""
    if score < 0.3 - _EPS or score > 1.0 + _EPS:
        return None
    return min(math.floor((score - 0.3) * 10 + 1e-6), len(TRAMOS) - 1)


def _es_candidato(h: dict[str, Any]) -> bool:
    return h["vision_verdict"] == "confirmado" and bool(h.get("pieza_id")) and bool(h.get("regla_coste_aplicable"))


def _validar(salidas: list[dict[str, Any]], etiquetas: dict[str, str]) -> dict[str, dict[str, Any]]:
    indice = {h["finding_id"]: h for s in salidas for h in s["findings"]}
    for finding_id, etiqueta in etiquetas.items():
        if etiqueta not in ETIQUETAS:
            raise EtiquetasNoValidas(f"{finding_id}: etiqueta no valida {etiqueta!r}")
    faltan = sorted(set(etiquetas) - set(indice))
    if faltan:
        raise EtiquetasNoValidas(f"{len(faltan)} ids de las etiquetas no estan en las salidas, p. ej. {faltan[:3]}")
    return indice


def _estadisticas(marcas: list[str | None], nombre: str) -> dict[str, Any]:
    """`marcas` son las etiquetas del juez de un grupo de hallazgos; None es un hallazgo sin etiqueta."""
    cuenta = Counter(m for m in marcas if m is not None)
    si, otra, no, dudo = (cuenta[e] for e in ETIQUETAS)
    n = si + otra + no
    return {
        nombre: len(marcas),
        "sin_etiqueta": sum(1 for m in marcas if m is None),
        "dudo": dudo,
        "decididos": n,
        "si": si,
        "otra": otra,
        "no": no,
        "precision_dano_real": (si + otra) / n if n else None,
        "intervalo_dano_real": intervalo_wilson(si + otra, n),
        "precision_clase": si / n if n else None,
        "intervalo_clase": intervalo_wilson(si, n),
        "concluyente": n >= MINIMO_CONCLUYENTE,
    }


def _candidatos_por_clase(salidas: list[dict[str, Any]], etiquetas: dict[str, str]) -> dict[str, list[tuple[dict[str, Any], str | None]]]:
    _validar(salidas, etiquetas)
    por_clase: dict[str, list[tuple[dict[str, Any], str | None]]] = {c: [] for c in CLASES}
    for s in salidas:
        for h in s["findings"]:
            if h["category"] in por_clase and _es_candidato(h):
                por_clase[h["category"]].append((h, etiquetas.get(h["finding_id"])))
    return por_clase


def filas_por_tramo(salidas: list[dict[str, Any]], etiquetas: dict[str, str]) -> list[dict[str, Any]]:
    """Una fila por clase y tramo de 0,1 y una de total por clase, sobre los candidatos a nivel firme. Si hay
    candidatos con score por debajo de 0,3, sale ademas una fila `<0,3` para que el total cuadre."""
    filas = []
    for clase, candidatos in _candidatos_por_clase(salidas, etiquetas).items():
        por_tramo: dict[int | None, list[str | None]] = {}
        for h, etiqueta in candidatos:
            por_tramo.setdefault(tramo_de_score(h["score"]), []).append(etiqueta)
        for i in range(len(TRAMOS)):
            filas.append({"clase": clase, "tramo": _nombre_tramo(i), **_estadisticas(por_tramo.get(i, []), "candidatos")})
        if por_tramo.get(None):
            filas.append({"clase": clase, "tramo": "<0,3", **_estadisticas(por_tramo[None], "candidatos")})
        filas.append({"clase": clase, "tramo": "total", **_estadisticas([e for _, e in candidatos], "candidatos")})
    return filas


def filas_por_umbral(salidas: list[dict[str, Any]], etiquetas: dict[str, str], umbrales: dict[str, float] | None = None) -> list[dict[str, Any]]:
    """Por clase y umbral de la rejilla 0,3 a 0,9: los candidatos con score >= umbral (acumulado), con el umbral actual
    de la clase marcado y la diferencia de candidatos frente a el."""
    umbrales = CATEGORY_REVIEW_THRESHOLD if umbrales is None else umbrales
    filas = []
    for clase, candidatos in _candidatos_por_clase(salidas, etiquetas).items():
        actual = umbrales[clase]
        en_actual = sum(1 for h, _ in candidatos if h["score"] >= actual - _EPS)
        for u in UMBRALES:
            marcas = [e for h, e in candidatos if h["score"] >= u - _EPS]
            filas.append({"clase": clase, "umbral": u, "actual": abs(u - actual) < _EPS, **_estadisticas(marcas, "candidatos"), "frente_al_actual": len(marcas) - en_actual})
    return filas


def filas_rechazados(salidas: list[dict[str, Any]], etiquetas: dict[str, str]) -> list[dict[str, Any]]:
    """Por clase, lo que la vision rechazo y lo que el juez ve en ello: `si` es dano de la clase que la vision se dejo,
    `otra` dano de otra clase y `no` un falso positivo bien descartado."""
    _validar(salidas, etiquetas)
    grupos: dict[str, list[str | None]] = {c: [] for c in CLASES}
    for s in salidas:
        for h in s["findings"]:
            if h["category"] in grupos and h["vision_verdict"] == "rechazado":
                grupos[h["category"]].append(etiquetas.get(h["finding_id"]))
    return [{"clase": c, **_estadisticas(grupos[c], "rechazados")} for c in CLASES]


def comparar_is_tp(salidas: list[dict[str, Any]], etiquetas: dict[str, str], is_tp: dict[str, bool]) -> list[dict[str, Any]]:
    """Por clase, de los candidatos que PIIA-1 daba por fallo (`is_true_positive` falso), cuantos son dano real segun el juez."""
    filas = []
    for clase, candidatos in _candidatos_por_clase(salidas, etiquetas).items():
        falsos = [e for h, e in candidatos if is_tp.get(h["finding_id"]) is False]
        cuenta = Counter(e for e in falsos if e is not None)
        filas.append(
            {
                "clase": clase,
                "candidatos": len(candidatos),
                "is_tp_falso": len(falsos),
                "is_tp_verdadero": sum(1 for h, _ in candidatos if is_tp.get(h["finding_id"]) is True),
                "sin_dato_is_tp": sum(1 for h, _ in candidatos if h["finding_id"] not in is_tp),
                "de_ellos_si": cuenta["si"],
                "de_ellos_otra": cuenta["otra"],
                "de_ellos_no": cuenta["no"],
                "de_ellos_dudo": cuenta["dudo"],
                "de_ellos_sin_etiqueta": sum(1 for e in falsos if e is None),
            }
        )
    return filas


def leer_is_tp(carpeta: Any) -> dict[str, bool]:
    """`is_true_positive` de cada deteccion del export de PIIA-1 (un JSON por imagen), por `finding_id`."""
    carpeta = Path(carpeta)
    ficheros = sorted(p for p in carpeta.glob("*.json") if p.name != "resumen_lote.json")
    if not ficheros:
        raise EtiquetasNoValidas(f"no hay export de PIIA-1 (*.json) en {carpeta}")
    resultado: dict[str, bool] = {}
    for p in ficheros:
        datos = json.loads(p.read_text(encoding="utf-8"))
        for pred in datos.get("predictions", []):
            valor = pred.get("is_true_positive")
            if isinstance(valor, bool):
                resultado[f"{datos['image_id']}-{pred['instance_index']}"] = valor
    return resultado


def _nota(f: dict[str, Any]) -> str:
    if f["decididos"] == 0:
        return "sin casos"
    return "" if f["concluyente"] else "no concluyente"


def _tabla(cabecera: list[str], filas: list[list[Any]]) -> list[str]:
    return ["| " + " | ".join(cabecera) + " |", "|" + "---|" * len(cabecera)] + ["| " + " | ".join(str(c) for c in fila) + " |" for fila in filas]


def formatear(
    filas_tramo: list[dict[str, Any]],
    filas_umbral: list[dict[str, Any]],
    filas_rech: list[dict[str, Any]],
    filas_tp: list[dict[str, Any]] | None = None,
    juez: dict[str, Any] | None = None,
) -> str:
    """El informe en Markdown con las tres tablas (y la cuarta si hay datos de `is_true_positive`)."""
    sello = ""
    if juez:
        sello = f" Juez: `{juez.get('modelo')}`, esfuerzo `{juez.get('esfuerzo')}`" + (f", prompt `{str(juez['prompt_sha256'])[:8]}`" if juez.get("prompt_sha256") else "") + "."
    lineas = [
        "# Precisión de lo que la visión confirma, por clase y score (#44)",
        "",
        "Son **etiquetas de un modelo** (juez), validadas con una muestra humana pequeña, **no verdad humana**." + sello,
        "«Candidatos» son los hallazgos que la visión confirmó, con pieza y regla de coste: los que serían nivel firme si su score pasara el umbral. "
        "«Daño real» cuenta `si` y `otra` del juez; «clase correcta», solo `si`. Los `dudo` y los hallazgos sin etiqueta no entran en el denominador, y "
        f"toda celda con menos de {MINIMO_CONCLUYENTE} casos decididos es no concluyente. Intervalos de Wilson al 95 %.",
        "",
        "## 1. Por clase y tramo de score",
        "",
    ]
    lineas += _tabla(
        ["Clase", "Tramo", "Candidatos", "Decididos", "Sí", "Otra", "No", "Dudo", "Sin etiqueta", "Daño real", "IC", "Clase correcta", "IC", "Nota"],
        [[f["clase"], f["tramo"], f["candidatos"], f["decididos"], f["si"], f["otra"], f["no"], f["dudo"], f["sin_etiqueta"], _pct(f["precision_dano_real"]),
          _ic(f["intervalo_dano_real"]), _pct(f["precision_clase"]), _ic(f["intervalo_clase"]), _nota(f)] for f in filas_tramo],
    )
    lineas += ["", "## 2. Acumulado por umbral (candidatos con score ≥ umbral)", ""]
    lineas += _tabla(
        ["Clase", "Umbral", "Candidatos", "Decididos", "Daño real", "IC", "Clase correcta", "No", "Frente al actual", "Nota"],
        [[f["clase"], _num(f["umbral"]) + (" (actual)" if f["actual"] else ""), f["candidatos"], f["decididos"], _pct(f["precision_dano_real"]), _ic(f["intervalo_dano_real"]),
          _pct(f["precision_clase"]), f["no"], f"{f['frente_al_actual']:+d}", _nota(f)] for f in filas_umbral],
    )
    lineas += ["", "## 3. Lo que la visión rechaza", "", "`Sí` es daño de la clase que la visión se dejó; `Otra`, daño de otra clase; `No`, un falso positivo bien descartado.", ""]
    lineas += _tabla(
        ["Clase", "Rechazados", "Decididos", "Sí", "Otra", "No", "Dudo", "Sin etiqueta", "Hay daño", "IC"],
        [[f["clase"], f["rechazados"], f["decididos"], f["si"], f["otra"], f["no"], f["dudo"], f["sin_etiqueta"], _pct(f["precision_dano_real"]), _ic(f["intervalo_dano_real"])] for f in filas_rech],
    )
    if filas_tp is not None:
        lineas += ["", "## 4. Candidatos que `is_true_positive` de PIIA-1 daba por fallo", ""]
        lineas += _tabla(
            ["Clase", "Candidatos", "is_true_positive falso", "de ellos sí", "de ellos otra", "de ellos no", "de ellos dudo", "verdadero", "sin dato"],
            [[f["clase"], f["candidatos"], f["is_tp_falso"], f["de_ellos_si"], f["de_ellos_otra"], f["de_ellos_no"], f["de_ellos_dudo"], f["is_tp_verdadero"], f["sin_dato_is_tp"]] for f in filas_tp],
        )
    return "\n".join(lineas) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--salidas", type=Path, required=True, help="carpeta con las salidas del Agente 1 (un JSON por imagen)")
    ap.add_argument("--etiquetas", type=Path, required=True, help="CSV finding_id,etiqueta del juez (etiquetas_juez.csv)")
    ap.add_argument("--export", type=Path, default=None, help="carpeta del export de PIIA-1, para comparar con is_true_positive")
    ap.add_argument("--resumen", type=Path, default=None, help="resumen_juez.json, para citar modelo, esfuerzo y prompt en el informe")
    ap.add_argument("--salida", type=Path, default=None, help="archivo Markdown donde guardar el informe")
    args = ap.parse_args(argv)
    try:
        salidas = _leer_salidas(args.salidas)
        etiquetas = leer_etiquetas(args.etiquetas)
        _validar(salidas, etiquetas)
        is_tp = leer_is_tp(args.export) if args.export is not None else None
        juez = json.loads(args.resumen.read_text(encoding="utf-8")) if args.resumen is not None else None
        informe = formatear(
            filas_por_tramo(salidas, etiquetas), filas_por_umbral(salidas, etiquetas), filas_rechazados(salidas, etiquetas),
            None if is_tp is None else comparar_is_tp(salidas, etiquetas, is_tp), juez,
        )
        if args.salida is not None:
            args.salida.parent.mkdir(parents=True, exist_ok=True)
            args.salida.write_text(informe, encoding="utf-8")
    except (EtiquetasNoValidas, OSError, json.JSONDecodeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    print(informe)
    if args.salida is not None:
        print(f"Informe: {args.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
