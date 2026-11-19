"""Parte 1 de la evaluación de punta a punta (Issue #46): comprobaciones automáticas.

Genera un informe por cada salida real del Agente 1 (como `generar_informes_reales.py`)
y reúne en `resumen_evaluacion.md` las comprobaciones del AC-002 del plan: informes
generados, cifras que no salen del Agente 2, reparto de los hallazgos, hallazgos que
entran por equivalencia (#88), temas del RAG con pasajes, sin pasajes y con error,
justificaciones (#97) por estado y la repetición con la misma entrada.

Todo se informa tal cual, sin umbrales. Lo que el Agente 2 no trae (RAG y
justificaciones, si solo se calculan los costes) consta como «no disponible»: no se
rellena con ceros.

Plan: https://github.com/lvckss/piia2-26/issues/46#issuecomment-6985712887
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from generar_informes_reales import (  # noqa: F401  (se reexportan para las pruebas)
    FECHA_POR_DEFECTO,
    SALIDAS_REALES,
    comprobar_cifras,
    estimar_siniestro,
    generar_informe,
    leer_siniestros,
    preparar_casos,
)
from costes_y_cobertura import EQUIVALENCIAS, PIEZAS, REGLAS  # noqa: E402
from equivalencias import regla_efectiva  # noqa: E402

DESTINO_POR_DEFECTO = Path(__file__).resolve().parent / "salida_evaluacion"
AGENTES = Path(__file__).resolve().parent.parent


def cargar_agente2_completo():
    """`agente2()` con RAG y justificaciones (#32, #97). Si no se puede importar
    lanza `ImportError`: no se evalúa «solo costes» sin avisar."""
    sys.path.insert(0, str(AGENTES / "agente_recuperacion"))
    try:
        from agente2 import agente2
    except ImportError as e:
        raise ImportError(f"no se puede importar agente2 (composición de la #32): {e}") from e
    return agente2


def _por_equivalencia(salida_agente1: dict, salida2: dict) -> int:
    """Hallazgos del escenario con pendientes cuya combinación (clase, zona,
    severidad) no tiene regla propia y se presupuesta con la de su equivalente."""
    hallazgos = {h["finding_id"]: h for h in salida_agente1["findings"]}
    total = 0
    for fid in salida2["escenarios"]["con_pendientes"]["hallazgos_incluidos"]:
        h = hallazgos[fid]
        zona = PIEZAS[h["pieza_id"]]["zona_tipo"]
        if (h["clase_tool"], zona, h["severidad"]) in REGLAS:
            continue
        if regla_efectiva(h["clase_tool"], zona, h["severidad"], REGLAS, EQUIVALENCIAS) is not None:
            total += 1
    return total


def _contar(valores) -> dict:
    cuentas: dict = {}
    for v in valores:
        cuentas[v] = cuentas.get(v, 0) + 1
    return cuentas


def resumir_caso(salida_agente1: dict, salida2: dict, informe_md: str) -> dict:
    """Comprobaciones del AC-002 sobre un informe y su salida del Agente 2.
    `rag` y `justificaciones` son `None` si la salida no los trae."""
    escenarios = salida2["escenarios"]
    conf = escenarios["confirmados"]["hallazgos_incluidos"]
    pend = escenarios["con_pendientes"]["hallazgos_incluidos"]
    fuera = salida2["hallazgos_fuera_del_coste"]

    rag = None
    if "diagnostico_rag" in salida2:
        estados = _contar(c["estado"] for c in salida2["diagnostico_rag"]["consultas"])
        rag = {"con_pasajes": estados.get("recuperadas", 0), "sin_pasajes": estados.get("sin_resultados", 0),
               "con_error": estados.get("error", 0)}

    justificaciones = None
    if "justificaciones" in salida2:
        lista = salida2["justificaciones"]
        estados = _contar(j["estado"] for j in lista)
        justificaciones = {"generada": estados.get("generada", 0), "descartada": estados.get("descartada", 0),
                           "no_generada": estados.get("no_generada", 0),
                           "motivos": _contar(j["motivo"] for j in lista if "motivo" in j)}

    return {
        "image_id": salida_agente1["image_id"],
        "cifras_ajenas": comprobar_cifras(informe_md, salida2),
        "confirmados": len(conf),
        "pendientes": len(pend) - len(conf),
        "fuera_del_coste": len(fuera),
        "motivos_fuera": _contar(h["motivo"] for h in fuera),
        "por_equivalencia": _por_equivalencia(salida_agente1, salida2),
        "rag": rag,
        "justificaciones": justificaciones,
    }


def _generar(caso: dict, hoy: str, agente2) -> tuple[str, dict]:
    if "error" in caso:
        raise ValueError(caso["error"])
    salida2 = agente2(caso["salida_agente1"], caso["contexto"])
    return generar_informe(caso["salida_agente1"], salida2, hoy=hoy), salida2


def _suma(resumenes: list[dict], campo: str, clave: str) -> int | None:
    datos = [r[campo] for r in resumenes if r[campo] is not None]
    return sum(d[clave] for d in datos) if datos else None


def _lineas_totales(resumenes: list[dict], errores: list[tuple[int, str]], total: int, repeticion) -> list[str]:
    cifras = sum(bool(r["cifras_ajenas"]) for r in resumenes)
    motivos_fuera = _contar(m for r in resumenes for m, n in r["motivos_fuera"].items() for _ in range(n))
    lineas = [
        f"- Informes generados: {len(resumenes)} de {total}. Con errores: {len(errores)}.",
        f"- Con cifras que no salen del Agente 2: {cifras}.",
        f"- Hallazgos: {sum(r['confirmados'] for r in resumenes)} confirmados, "
        f"{sum(r['pendientes'] for r in resumenes)} pendientes de revisión y "
        f"{sum(r['fuera_del_coste'] for r in resumenes)} fuera del coste"
        + (f" ({', '.join(f'{m}: {n}' for m, n in sorted(motivos_fuera.items()))})." if motivos_fuera else "."),
        f"- Hallazgos por equivalencia (#88): {sum(r['por_equivalencia'] for r in resumenes)}.",
    ]
    if _suma(resumenes, "rag", "con_pasajes") is None:
        lineas.append("- RAG: no disponible (solo se calcularon los costes; usar `--completo`).")
    else:
        lineas.append(f"- RAG, temas: {_suma(resumenes, 'rag', 'con_pasajes')} con pasajes, "
                      f"{_suma(resumenes, 'rag', 'sin_pasajes')} sin pasajes y {_suma(resumenes, 'rag', 'con_error')} con error.")
    if _suma(resumenes, "justificaciones", "generada") is None:
        lineas.append("- Justificaciones (#97): no disponible (solo se calcularon los costes; usar `--completo`).")
    else:
        motivos = _contar(m for r in resumenes if r["justificaciones"]
                          for m, n in r["justificaciones"]["motivos"].items() for _ in range(n))
        lineas.append(f"- Justificaciones (#97): {_suma(resumenes, 'justificaciones', 'generada')} generadas, "
                      f"{_suma(resumenes, 'justificaciones', 'descartada')} descartadas y "
                      f"{_suma(resumenes, 'justificaciones', 'no_generada')} no generadas"
                      + (f" ({'; '.join(f'{m}: {n}' for m, n in sorted(motivos.items()))})." if motivos else "."))
    if repeticion is None:
        lineas.append("- Repetición con la misma entrada: no ejecutada (usar `--repetir`).")
    else:
        iguales, cambian = repeticion
        lineas.append(f"- Repetición con la misma entrada: {iguales} de {len(resumenes)} informes iguales.")
        if cambian:
            lineas.append("- Cambian: " + ", ".join(f"{i:06d}" for i in cambian))
    return lineas


def _fila(caso: dict, r: dict, cambia: bool | None) -> str:
    rag = "n/d" if r["rag"] is None else f"{r['rag']['con_pasajes']}/{r['rag']['sin_pasajes']}/{r['rag']['con_error']}"
    j = r["justificaciones"]
    just = "n/d" if j is None else f"{j['generada']}/{j['descartada']}/{j['no_generada']}"
    rep = "" if cambia is None else ("cambia" if cambia else "igual")
    cifras = ", ".join(f"{x:.2f}" for x in r["cifras_ajenas"]) or "ninguna"
    return (f"| {r['image_id']:06d} | {caso['siniestro_id']} | {caso['rol']} | {r['confirmados']} | {r['pendientes']} "
            f"| {r['fuera_del_coste']} | {r['por_equivalencia']} | {rag} | {just} | {cifras} | {rep} | |")


def evaluar(salidas_dir, destino, hoy: str = FECHA_POR_DEFECTO, semilla: int = 84,
            agente2=None, repetir: bool = False) -> int:
    """Un informe `<image_id>.md` por salida y `resumen_evaluacion.md`. Un caso
    con un error del Agente 2 o del 3 se registra con su causa y no detiene a los
    demás. Devuelve 1 si hubo errores o cifras ajenas al Agente 2, y 0 si no."""
    agente2 = agente2 or estimar_siniestro
    archivos = sorted(Path(salidas_dir).glob("*.json"))
    if not archivos:
        raise ValueError(f"no hay salidas del Agente 1 (*.json) en {salidas_dir}: la carpeta no existe o está vacía")
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    salidas = [json.loads(p.read_text(encoding="utf-8")) for p in archivos]
    casos = preparar_casos(salidas, leer_siniestros(), semilla)

    filas, resumenes, errores, cambian = [], [], [], []
    for caso in casos:
        informe = destino / f"{caso['image_id']:06d}.md"
        try:
            md, salida2 = _generar(caso, hoy, agente2)
        except ValueError as e:
            informe.unlink(missing_ok=True)
            errores.append((caso["image_id"], str(e)))
            continue
        informe.write_text(md, encoding="utf-8")
        r = resumir_caso(caso["salida_agente1"], salida2, md)
        cambia = None
        if repetir:
            try:
                cambia = _generar(caso, hoy, agente2)[0] != md
            except ValueError:
                cambia = True
            if cambia:
                cambian.append(caso["image_id"])
        resumenes.append(r)
        filas.append(_fila(caso, r, cambia))

    repeticion = (len(resumenes) - len(cambian), cambian) if repetir else None
    md = [
        "# Evaluación de punta a punta, Parte 1 (Issue #46)",
        "",
        f"- Fecha de los informes: {hoy}. Semilla de los siniestros sintéticos: {semilla}.",
        f"- Salidas del Agente 1: {len(casos)} (carpeta `{Path(salidas_dir).name}`).",
        "- Los siniestros de contexto son sintéticos y no tienen relación con la foto.",
        *_lineas_totales(resumenes, errores, len(casos), repeticion),
        "",
        "En las columnas RAG y justificaciones, los tres números son con pasajes / sin pasajes / con error "
        "y generadas / descartadas / no generadas; `n/d` es no disponible.",
        "",
        "| image_id | siniestro_id | rol | confirmados | pendientes | fuera del coste | por equivalencia "
        "| RAG | justificaciones | cifras ajenas | repetición | error |",
        "|---|---|---|---:|---:|---:|---:|---|---|---|---|---|",
        *filas,
        *(f"| {i:06d} | | | | | | | | | | | {msg} |" for i, msg in errores),
    ]
    (destino / "resumen_evaluacion.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return 1 if errores or any(r["cifras_ajenas"] for r in resumenes) else 0


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Parte 1 de la evaluación de punta a punta (Issue #46).")
    ap.add_argument("--salidas", type=Path, default=SALIDAS_REALES, help="carpeta con las salidas del Agente 1 (*.json)")
    ap.add_argument("--destino", type=Path, default=DESTINO_POR_DEFECTO, help="carpeta de los informes (fuera de git)")
    ap.add_argument("--hoy", default=FECHA_POR_DEFECTO, help="fecha de los informes, AAAA-MM-DD")
    ap.add_argument("--semilla", type=int, default=84, help="semilla para elegir los siniestros sintéticos")
    ap.add_argument("--repetir", action="store_true", help="repite la ejecución y compara los informes")
    ap.add_argument("--completo", action="store_true", help="usa agente2() con RAG y justificaciones (#32, #97)")
    args = ap.parse_args(argv)
    try:
        agente2 = cargar_agente2_completo() if args.completo else None
        codigo = evaluar(args.salidas, args.destino, hoy=args.hoy, semilla=args.semilla,
                         agente2=agente2, repetir=args.repetir)
    except (ValueError, ImportError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    print(f"Informes y resumen_evaluacion.md en {args.destino} (código {codigo})")
    return codigo


if __name__ == "__main__":
    sys.exit(main())
