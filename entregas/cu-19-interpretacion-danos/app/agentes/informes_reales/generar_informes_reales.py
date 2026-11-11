"""Primeros 30 informes reales en linea de comandos (Issue #84).

Encadena las salidas reales del Agente 1 guardadas en
ejemplos_contrato/agente1_real/ con el Agente 2 (costes y cobertura) y el
Agente 3 (informe). Sin API, sin RAG y sin web.

Plan: https://github.com/lvckss/piia2-26/issues/84#issuecomment-6802745988
"""

from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path

AGENTES = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(AGENTES / "agente_recuperacion"), str(AGENTES / "agente_redactor")]
# Si falta piia2_paquete_datos/, estos imports lanzan ImportError con la ruta esperada.
from costes_y_cobertura import PAQUETE, estimar_siniestro  # noqa: E402
from informe import comprobar_cifras, generar_informe  # noqa: E402

SALIDAS_REALES = AGENTES / "ejemplos_contrato" / "agente1_real"
DESTINO_POR_DEFECTO = Path(__file__).resolve().parent / "salida"
FECHA_POR_DEFECTO = "2026-11-12"

# Regla provisional del coche con categoria `desconocido`: el de menor coste
# (decision con el profesorado del 2026-11-10, registrada en la #34). Su sitio
# definitivo es la funcion del orquestador de la #34.
VEHICULO_DESCONOCIDO = "V14"
CAMPOS_CONTEXTO = ("region", "tipo_taller", "acabado", "tipo_pieza", "rol")


def _contexto(siniestro: dict, vehiculo_id: str) -> dict:
    """Solo los campos de contexto del siniestro (regla 1 del plan); sus danos y
    su coche no se usan. Con tercero no hay poliza."""
    contexto = {"vehiculo_id": vehiculo_id, **{c: siniestro[c] for c in CAMPOS_CONTEXTO},
                "edad_anios": int(siniestro["edad_anios"]), "km": int(siniestro["km"])}
    if siniestro["rol"] == "propio":
        contexto["poliza_id"] = siniestro["poliza_id"]
    return contexto


def preparar_casos(salidas: list[dict], siniestros: list[dict], semilla: int = 84) -> list[dict]:
    """Un caso por salida del Agente 1, en orden de `image_id`: un siniestro
    distinto elegido con random.Random(semilla) sobre los siniestros ordenados
    por `siniestro_id`, y el coche de referencia del Agente 1 o V14 con
    `desconocido` (plan #84, AC-003)."""
    ordenadas = sorted(salidas, key=lambda s: s["image_id"])
    elegidos = random.Random(semilla).sample(sorted(siniestros, key=lambda s: s["siniestro_id"]), len(ordenadas))
    casos = []
    for salida, siniestro in zip(ordenadas, elegidos):
        vehiculo = salida["vehiculo"]
        vehiculo_id = vehiculo["vehiculo_id_referencia"] or VEHICULO_DESCONOCIDO
        casos.append({"image_id": salida["image_id"], "siniestro_id": siniestro["siniestro_id"],
                      "categoria": vehiculo["categoria"], "salida_agente1": salida,
                      "contexto": _contexto(siniestro, vehiculo_id)})
    return casos


def leer_siniestros() -> list[dict]:
    with open(PAQUETE / "data" / "siniestros_sinteticos.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _total(salida2: dict, escenario: str) -> str:
    return f"{salida2['escenarios'][escenario]['estimacion']['total_con_iva_eur']:.2f}"


def generar(salidas_dir, destino, hoy: str = FECHA_POR_DEFECTO, semilla: int = 84) -> int:
    """Un informe `<image_id>.md` por salida del Agente 1 y `resumen.md`.
    Una salida que no pasa la validacion de los Agentes 2 o 3 queda en el
    resumen con su error y no detiene las demas. Devuelve 1 si hubo errores o
    cifras que no salen del Agente 2, y 0 si no (plan #84, AC-001, AC-002 y AC-004)."""
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    salidas = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(salidas_dir).glob("*.json"))]
    casos = preparar_casos(salidas, leer_siniestros(), semilla)
    filas, errores, inventadas = [], 0, 0
    for caso in casos:
        ctx = caso["contexto"]
        coche = "referencia de la categoría" if caso["categoria"] != "desconocido" else "menor coste (desconocido)"
        fila = [f"{caso['image_id']:06d}", caso["siniestro_id"], caso["categoria"], ctx["vehiculo_id"], coche, ctx["rol"]]
        try:
            salida2 = estimar_siniestro(caso["salida_agente1"], ctx)
            md = generar_informe(caso["salida_agente1"], salida2, hoy=hoy)
        except ValueError as e:
            errores += 1
            filas.append(fila + ["", "", "", "", "", "", str(e)])
            continue
        (destino / f"{caso['image_id']:06d}.md").write_text(md, encoding="utf-8")
        cifras = comprobar_cifras(md, salida2)
        inventadas += bool(cifras)
        conf = salida2["escenarios"]["confirmados"]["hallazgos_incluidos"]
        pend = salida2["escenarios"]["con_pendientes"]["hallazgos_incluidos"]
        filas.append(fila + [str(len(conf)), str(len(pend) - len(conf)), str(len(salida2["hallazgos_fuera_del_coste"])),
                             _total(salida2, "confirmados"), _total(salida2, "con_pendientes"),
                             ", ".join(f"{x:.2f}" for x in cifras) or "ninguna", ""])
    propios = sum(c["contexto"]["rol"] == "propio" for c in casos)
    md = [
        "# Resumen de los informes reales (Issue #84)",
        "",
        f"- Fecha de los informes: {hoy}. Semilla de los siniestros: {semilla}.",
        f"- Casos: {len(casos)} ({propios} propios y {len(casos) - propios} de tercero).",
        f"- Informes generados: {len(casos) - errores}. Con errores: {errores}. Con cifras que no salen del Agente 2: {inventadas}.",
        f"- Coche con categoría `desconocido`: {VEHICULO_DESCONOCIDO} (menor coste), regla provisional de la #34.",
        "",
        "| image_id | siniestro_id | categoría | vehiculo_id | coche | rol | confirmados | pendientes | fuera del coste "
        "| total confirmados con IVA | total con pendientes con IVA | cifras inventadas | error |",
        "|---|---|---|---|---|---|---:|---:|---:|---:|---:|---|---|",
        *("| " + " | ".join(f) + " |" for f in filas),
    ]
    (destino / "resumen.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return 1 if errores or inventadas else 0
