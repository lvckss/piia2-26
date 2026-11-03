"""Pruebas del Agente 3 (informe de peritaje) contra el plan de la #31.

Cada prueba cita su criterio: specs/31-informe-peritaje.md#AC-0XX.
Usa los ejemplos de ejemplos_contrato/ y el catalogo de la empresa
(piia2_paquete_datos/, fuera de git). No necesita API Key ni red.

Se ejecuta desde esta carpeta:  python probar_informe.py
Ejecuta todas las pruebas, informa de cada una y termina con codigo 1 si
alguna falla.
"""

from __future__ import annotations

import copy
import json
import sys
import traceback
from pathlib import Path

import informe
from informe import generar_informe

AQUI = Path(__file__).resolve().parent
EJ = AQUI.parent / "ejemplos_contrato"
HOY = "2026-10-14"

ENCABEZADOS = [
    "# Informe de peritaje — imagen 160",
    "## Resumen",
    "## Daños confirmados",
    "## Daños pendientes de revisión",
    "## Detecciones no incluidas en el coste",
    "## Desglose del coste",
    "## Posibles daños asociados (no incluidos en el coste)",
    "## Cobertura e indemnización",
    "## Fuentes consultadas",
]
AVISO_LEGAL = ("Informe generado automáticamente con datos sintéticos de prototipo. Las cifras son "
               "orientativas y no vinculantes, y no sustituyen a una valoración pericial.")


def _cargar(nombre: str) -> dict:
    return json.loads((EJ / nombre).read_text(encoding="utf-8"))


def _ejemplos():
    return _cargar("agente1_salida.json"), _cargar("agente2_salida.json")


def _secciones(md: str) -> dict[str, str]:
    """Texto de cada seccion, por su encabezado (`#` o `##`)."""
    secciones, actual = {}, None
    for linea in md.splitlines():
        if linea.startswith("# ") or linea.startswith("## "):
            actual = linea
            secciones[actual] = ""
        elif actual is not None:
            secciones[actual] += linea + "\n"
    return secciones


# --- specs/31-informe-peritaje.md#AC-001 ------------------------------------
def probar_ac001_encabezados_cabecera_y_resumen():
    """AC-001: los 9 encabezados en orden; cabecera con fecha, vehiculo,
    taller, poliza y aviso legal literal; 31 detecciones frente a 5 hallazgos."""
    a1, a2 = _ejemplos()
    md = generar_informe(a1, a2, hoy=HOY)
    encontrados = [l for l in md.splitlines() if l.startswith("# ") or l.startswith("## ")]
    assert encontrados == ENCABEZADOS, f"encabezados: {encontrados}"
    cabecera = _secciones(md)[ENCABEZADOS[0]]
    for texto in (HOY, "Volkswagen Golf", "multimarca", "Madrid", "Todo Riesgo con franquicia 300 EUR", AVISO_LEGAL):
        assert texto in cabecera, f"falta en la cabecera: {texto!r}"
    resumen = _secciones(md)["## Resumen"]
    assert "31" in resumen and "5" in resumen, resumen
    assert "31 detecciones" in resumen and "5 hallazgos analizados" in resumen, resumen


# --- specs/31-informe-peritaje.md#AC-002 ------------------------------------
def probar_ac002_confirmados_pendientes_y_no_incluidos():
    """AC-002: cada finding_id en una unica seccion; pendientes con todos sus
    motivos y scores en formato espanol; advertencia de verificacion humana."""
    a1, a2 = _ejemplos()
    s = _secciones(generar_informe(a1, a2, hoy=HOY))
    grupos = {
        "## Daños confirmados": ["160-1", "160-4"],
        "## Daños pendientes de revisión": ["160-3", "160-5"],
        "## Detecciones no incluidas en el coste": ["160-2"],
    }
    for seccion, ids in grupos.items():
        for fid in [f["finding_id"] for f in a1["findings"]]:
            dentro = fid in s[seccion]
            assert dentro == (fid in ids), f"{fid} {'no ' if not dentro else ''}aparece en «{seccion}»"
    pendientes = s["## Daños pendientes de revisión"]
    fila_3 = next(l for l in pendientes.splitlines() if "160-3" in l)
    fila_5 = next(l for l in pendientes.splitlines() if "160-5" in l)
    assert "score de detección bajo" in fila_3 and "0,28" in fila_3, fila_3
    assert "score de detección bajo" in fila_5 and "0,29" in fila_5 and "incierto" in fila_5, fila_5
    assert "verificación humana" in pendientes, pendientes
    assert "rechaz" in s["## Detecciones no incluidas en el coste"].lower()
    for fid in ("160-1", "160-4"):
        fila = next(l for l in s["## Daños confirmados"].splitlines() if fid in l)
        score = next(f["score"] for f in a1["findings"] if f["finding_id"] == fid)
        assert f"{score:.2f}".replace(".", ",") in fila, fila


# --- specs/31-informe-peritaje.md#AC-005 ------------------------------------
def probar_ac005_normativa_vacia_y_con_extractos():
    """AC-005: sin normativa, «Sin fuentes» y nada mas; con los 2 extractos,
    cada uno con su tema y su fuente."""
    a1, a2 = _ejemplos()
    fuentes = _secciones(generar_informe(a1, a2, hoy=HOY))["## Fuentes consultadas"]
    assert len(a2["normativa"]) == 2
    for n in a2["normativa"]:
        linea = next((l for l in fuentes.splitlines() if n["fuente"] in l), None)
        assert linea and n["tema"] in linea, f"falta la fuente {n['fuente']} con su tema"
    vacia = copy.deepcopy(a2)
    vacia["normativa"] = []
    fuentes = _secciones(generar_informe(a1, vacia, hoy=HOY))["## Fuentes consultadas"]
    lineas = [l for l in fuentes.splitlines() if l.strip()]
    assert len(lineas) == 1 and "Sin fuentes" in lineas[0], lineas


# --- specs/31-informe-peritaje.md#AC-009 ------------------------------------
def probar_ac009_arrastres_con_nombre_y_probabilidad():
    """AC-009: cada arrastre con su nombre del catalogo y su probabilidad en la
    seccion de no incluidos en el coste; sin arrastres, «Ninguno previsto»."""
    a1, a2 = _ejemplos()
    seccion = _secciones(generar_informe(a1, a2, hoy=HOY))["## Posibles daños asociados (no incluidos en el coste)"]
    arrastres = a2["escenarios"]["con_pendientes"]["estimacion"]["arrastres_posibles"]
    assert len(arrastres) == 6
    nombres = {"ABSORB_DEL": "Absorbedor", "RADIADOR": "Radiador", "AIRBAG_CONDUCTOR": "Airbag"}
    for a in arrastres:
        if a["pieza_id"] in nombres:
            linea = next((l for l in seccion.splitlines() if nombres[a["pieza_id"]] in l), None)
            assert linea, f"falta el arrastre {a['pieza_id']}"
            assert f"{a['probabilidad']:.0%}".replace("%", " %") in linea, linea
    assert sum(1 for l in seccion.splitlines() if l.startswith("- ")) == 6, seccion
    sin = copy.deepcopy(a2)
    for e in sin["escenarios"].values():
        e["estimacion"]["arrastres_posibles"] = []
    seccion = _secciones(generar_informe(a1, sin, hoy=HOY))["## Posibles daños asociados (no incluidos en el coste)"]
    assert "Ninguno previsto" in seccion and "- " not in seccion, seccion


PRUEBAS = [
    probar_ac001_encabezados_cabecera_y_resumen,
    probar_ac002_confirmados_pendientes_y_no_incluidos,
    probar_ac005_normativa_vacia_y_con_extractos,
    probar_ac009_arrastres_con_nombre_y_probabilidad,
]


def main() -> int:
    fallos = 0
    for prueba in PRUEBAS:
        try:
            prueba()
        except Exception:  # noqa: BLE001 - se informa y se sigue con las demas
            fallos += 1
            ultima = traceback.format_exc().strip().splitlines()[-1]
            print(f"FALLA  {prueba.__name__}: {ultima}")
        else:
            print(f"ok     {prueba.__name__}")
    print(f"\n{len(PRUEBAS) - fallos} de {len(PRUEBAS)} pruebas en verde (modulo: {Path(informe.__file__).name})")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
