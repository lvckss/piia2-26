"""Evaluacion del Agente 2 con los siniestros sinteticos de la empresa
(specs/30-costes-cobertura.md#AC-011).

Usa los siniestros de `split` val y test de
piia2_paquete_datos/data/siniestros_sinteticos.csv, construyendo el contexto
con las columnas de cada uno, y mide:

  (a) el MAPE de `estimar_coste` con `danos_json` frente a
      `coste_facturado_sin_iva_eur` (suelo de la herramienta; referencia 9,39 %);
  (b) la concordancia de `perdida_total` y de `cubierto` con las columnas
      `perdida_total` y `cobertura_aplica` del CSV;
  (c) la indemnizacion calculada con el coste facturado del CSV frente a
      `indemnizacion_eur` (+-0,5 EUR): comprueba que la logica de cobertura
      replica la del generador;
  (d) solo se documenta: coincidencia y error relativo medio de la
      indemnizacion calculada con el coste de la herramienta.

No usa red ni API Key. Se ejecuta desde esta carpeta:  python evaluar_costes.py
Termina con codigo 1 si (a), (b) o (c) no se cumplen.
"""

from __future__ import annotations

import csv
import json
import sys

from costes_y_cobertura import PAQUETE, calcular_cobertura, estimar_coste

MAPE_REFERENCIA = 9.39   # %, medido en la revision de la PR #40
TOLERANCIA_MAPE = 0.01   # puntos porcentuales
TOLERANCIA_EUR = 0.5


def _contexto(fila: dict) -> dict:
    return {
        "vehiculo_id": fila["vehiculo_id"], "region": fila["region"], "tipo_taller": fila["tipo_taller"],
        "acabado": fila["acabado"], "tipo_pieza": fila["tipo_pieza"], "rol": fila["rol"],
        "poliza_id": fila["poliza_id"], "edad_anios": int(fila["edad_anios"]), "km": int(fila["km"]),
    }


def evaluar() -> dict:
    with open(PAQUETE / "data" / "siniestros_sinteticos.csv", encoding="utf-8") as f:
        filas = [r for r in csv.DictReader(f) if r["split"] in ("val", "test")]

    errores_coste, pt_ok, cub_ok, fact_ok, herr_ok, errores_indem = [], 0, 0, 0, 0, []
    discrepancias = []
    for r in filas:
        ctx, danos = _contexto(r), json.loads(r["danos_json"])
        est = estimar_coste(ctx["vehiculo_id"], danos, region=ctx["region"], tipo_taller=ctx["tipo_taller"],
                            acabado=ctx["acabado"], tipo_pieza=ctx["tipo_pieza"])
        facturado = float(r["coste_facturado_sin_iva_eur"])
        errores_coste.append(abs(est["subtotal_sin_iva_eur"] - facturado) / facturado)

        # (b) y (d): cobertura con el coste de la herramienta
        cob = calcular_cobertura(ctx, est, danos)
        indem_csv = float(r["indemnizacion_eur"])
        pt_ok += cob["perdida_total"] == bool(int(r["perdida_total"]))
        cub_ok += cob["cubierto"] == bool(int(r["cobertura_aplica"]))
        herr_ok += abs(cob["indemnizacion_estimada_eur"] - indem_csv) <= TOLERANCIA_EUR
        if indem_csv > 0:
            errores_indem.append(abs(cob["indemnizacion_estimada_eur"] - indem_csv) / indem_csv)

        # (c): la misma logica alimentada con el coste facturado
        est_fact = {"subtotal_sin_iva_eur": facturado, "total_con_iva_eur": round(facturado * 1.21, 2)}
        cob_fact = calcular_cobertura(ctx, est_fact, danos)
        if abs(cob_fact["indemnizacion_estimada_eur"] - indem_csv) <= TOLERANCIA_EUR:
            fact_ok += 1
        else:
            discrepancias.append((r["siniestro_id"], cob_fact["indemnizacion_estimada_eur"], indem_csv))

    n = len(filas)
    return {
        "n_siniestros": n,
        "mape_coste_pct": round(100 * sum(errores_coste) / n, 2),
        "concordancia_perdida_total_pct": round(100 * pt_ok / n, 1),
        "concordancia_cubierto_pct": round(100 * cub_ok / n, 1),
        "indemnizacion_con_coste_facturado_pct": round(100 * fact_ok / n, 1),
        "indemnizacion_con_coste_herramienta_pct": round(100 * herr_ok / n, 1),
        "error_relativo_medio_indemnizacion_pct": round(100 * sum(errores_indem) / len(errores_indem), 1),
        "discrepancias_con_coste_facturado": discrepancias[:10],
    }


def main() -> int:
    r = evaluar()
    print(f"Siniestros evaluados (val + test): {r['n_siniestros']}")
    print(f"(a) MAPE del coste de la herramienta:            {r['mape_coste_pct']:.2f} %  (referencia {MAPE_REFERENCIA} %)")
    print(f"(b) Concordancia de perdida total:               {r['concordancia_perdida_total_pct']} %")
    print(f"    Concordancia de cobertura (cubierto):        {r['concordancia_cubierto_pct']} %")
    print(f"(c) Indemnizacion con coste facturado (+-0,5):   {r['indemnizacion_con_coste_facturado_pct']} %")
    print(f"(d) Indemnizacion con coste de la herramienta:   {r['indemnizacion_con_coste_herramienta_pct']} % de coincidencia, "
          f"error relativo medio {r['error_relativo_medio_indemnizacion_pct']} % (solo se documenta)")
    fallos = []
    if abs(r["mape_coste_pct"] - MAPE_REFERENCIA) > TOLERANCIA_MAPE:
        fallos.append("(a) MAPE fuera de la referencia")
    if r["concordancia_perdida_total_pct"] < 100 or r["concordancia_cubierto_pct"] < 100:
        fallos.append("(b) concordancia por debajo del 100 %")
    if r["indemnizacion_con_coste_facturado_pct"] < 100:
        fallos.append(f"(c) discrepancias: {r['discrepancias_con_coste_facturado']}")
    print("\n" + ("Todo ok: AC-011 cumplido." if not fallos else "NO CUMPLE: " + "; ".join(fallos)))
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
