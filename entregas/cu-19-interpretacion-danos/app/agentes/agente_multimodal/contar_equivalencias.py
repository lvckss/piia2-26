"""Recuento de hallazgos sin regla de coste, antes y despues de las equivalencias (#88, AC-007).

Plan v1: specs/88-equivalencias-reglas-coste.md#AC-007. Decision: docs/adr/0008-equivalencias-reglas-coste.md.

Solo lee las salidas del Agente 1 de una carpeta (sin API ni red) y no cambia ningun archivo. Cuenta,
entre los hallazgos que la vision no rechaza y que tienen pieza y severidad, cuantos no tienen regla
propia en `reglas_dano.csv` y cuantos de ellos pasan a tener regla por una equivalencia.

    python contar_equivalencias.py [CARPETA ...]    (por defecto, las 30 salidas versionadas)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from catalogo import Catalogo, cargar_catalogo, combinacion_valida

VERSIONADAS = Path(__file__).resolve().parent.parent / "ejemplos_contrato" / "agente1_real"


def contar(carpeta: str | Path, catalogo: Catalogo) -> dict:
    """Recuento de las salidas `*.json` de `carpeta`. Los archivos que no son una salida del Agente 1
    (sin `findings`, como `resumen_lote.json`) se omiten y se listan en `omitidos`."""
    r = {"salidas": 0, "omitidos": [], "hallazgos": 0, "no_rechazados": 0, "con_pieza_y_severidad": 0,
         "sin_regla_propia": 0, "sin_regla_con_equivalencias": 0, "ganan_regla": 0, "pierden_regla": 0,
         "salidas_que_cambian": []}
    for ruta in sorted(Path(carpeta).glob("*.json")):
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        if not isinstance(datos, dict) or "findings" not in datos:
            r["omitidos"].append(ruta.name)
            continue
        r["salidas"] += 1
        cambia = False
        for f in datos["findings"]:
            r["hallazgos"] += 1
            if f.get("vision_verdict") == "rechazado":
                continue
            r["no_rechazados"] += 1
            pieza = catalogo.piezas.get(f.get("pieza_id"))
            if pieza is None or not f.get("severidad"):
                continue
            r["con_pieza_y_severidad"] += 1
            propia = (f["clase_tool"], pieza["zona_tipo"], f["severidad"]) in catalogo.reglas
            efectiva = combinacion_valida(catalogo, f["clase_tool"], f["pieza_id"], f["severidad"])
            r["sin_regla_propia"] += not propia
            r["sin_regla_con_equivalencias"] += not efectiva
            if not propia and efectiva:
                r["ganan_regla"] += 1
                cambia = True
            elif propia and not efectiva:
                r["pierden_regla"] += 1
        if cambia:
            r["salidas_que_cambian"].append(ruta.stem)
    return r


def informe(nombre: str, r: dict) -> str:
    return "\n".join([
        f"{nombre}: {r['salidas']} salidas, {r['hallazgos']} hallazgos"
        + (f" (archivos omitidos: {', '.join(r['omitidos'])})" if r["omitidos"] else ""),
        f"  no rechazados por la vision: {r['no_rechazados']}; con pieza y severidad: {r['con_pieza_y_severidad']}",
        f"  sin regla propia (solo reglas de la empresa): {r['sin_regla_propia']}",
        f"  sin regla con las equivalencias:               {r['sin_regla_con_equivalencias']}",
        f"  ganan regla: {r['ganan_regla']}; pierden la que tenian: {r['pierden_regla']}",
        f"  salidas con algun hallazgo que gana regla: {', '.join(r['salidas_que_cambian']) or 'ninguna'}",
    ])


def main(argv: list[str]) -> int:
    catalogo = cargar_catalogo()
    carpetas = [Path(a) for a in argv] or [VERSIONADAS]
    for carpeta in carpetas:
        print(informe(carpeta.name, contar(carpeta, catalogo)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
