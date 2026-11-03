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
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

import informe
from informe import comprobar_cifras, generar_informe

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


# --- specs/31-informe-peritaje.md#AC-003 ------------------------------------
def probar_ac003_sin_importes_inventados():
    """AC-003: ningun importe inventado y los 6 importes del ejemplo presentes."""
    a1, a2 = _ejemplos()
    md = generar_informe(a1, a2, hoy=HOY)
    assert comprobar_cifras(md, a2) == [], comprobar_cifras(md, a2)
    for importe in ("1.019,46 €", "1.233,55 €", "1.488,23 €", "1.800,76 €", "933,55 €", "1.500,76 €"):
        assert importe in md, f"falta {importe}"


# --- specs/31-informe-peritaje.md#AC-004 ------------------------------------
def probar_ac004_importe_inventado_con_y_sin_miles():
    """AC-004: un importe inventado se detecta entero, con o sin separador de miles."""
    a1, a2 = _ejemplos()
    md = generar_informe(a1, a2, hoy=HOY)
    for linea in ("Reparación extra: 1.234,56 €", "Reparación extra: 1234,56 €"):
        obtenido = comprobar_cifras(md + linea + "\n", a2)
        assert obtenido == [1234.56], f"{linea!r} -> {obtenido}"


# --- specs/31-informe-peritaje.md#AC-013 ------------------------------------
def probar_ac013_numeros_no_monetarios_no_valen_como_importe():
    """AC-013: importes inventados que coinciden con image_id, km o edad_anios
    del JSON del Agente 2 se detectan igualmente."""
    a1, a2 = _ejemplos()
    md = generar_informe(a1, a2, hoy=HOY)
    assert (a2["image_id"], a2["contexto"]["km"], a2["contexto"]["edad_anios"]) == (160, 42000, 3)
    for linea, esperado in (("Tasa: 160,00 €", [160.0]), ("Tasa: 42.000,00 €", [42000.0]), ("Tasa: 3,00 €", [3.0])):
        obtenido = comprobar_cifras(md + linea + "\n", a2)
        assert obtenido == esperado, f"{linea!r} -> {obtenido}"


def _escenario_vacio(escenario: dict) -> dict:
    """Escenario sin hallazgos con la forma de specs/30-costes-cobertura.md#AC-007:
    mismas claves, importes 0 y listas vacias."""
    vacio = copy.deepcopy(escenario)
    est = vacio["estimacion"]
    est["lineas"], est["arrastres_posibles"] = [], []
    est["desglose"] = {k: 0.0 for k in est["desglose"]}
    est["subtotal_sin_iva_eur"] = est["iva_eur"] = est["total_con_iva_eur"] = 0.0
    vacio["hallazgos_incluidos"] = []
    vacio["cobertura"] = {"cubierto": False, "motivo": "Sin daños presupuestables", "franquicia_eur": 0.0,
                          "perdida_total": False, "indemnizacion_estimada_eur": 0.0}
    return vacio


def _fila(seccion: str, inicio: str) -> str:
    return next(l for l in seccion.splitlines() if l.startswith(inicio))


# --- specs/31-informe-peritaje.md#AC-006 ------------------------------------
def probar_ac006_tercero_perjudicado():
    """AC-006: tercero sin poliza_id -> sin excepcion, cabecera con el tercero y
    «Terceros (RC obligatoria)», cobertura de cada escenario tal como viene."""
    a1, a2 = _ejemplos()
    t = copy.deepcopy(a2)
    t["contexto"]["rol"], t["contexto"]["poliza_id"] = "tercero_perjudicado", ""
    t["umbral_perdida_total"] = 1.0
    motivo = "Daños a tercero: RC obligatoria (acción directa, LRCSCVM art. 7)"
    for e in t["escenarios"].values():
        total = e["estimacion"]["total_con_iva_eur"]
        e["cobertura"] = {"cubierto": True, "motivo": motivo, "franquicia_eur": 0.0,
                          "perdida_total": False, "indemnizacion_estimada_eur": total}
    md = generar_informe(a1, t, hoy=HOY)
    s = _secciones(md)
    cabecera = s[ENCABEZADOS[0]]
    assert "Terceros (RC obligatoria)" in cabecera, cabecera
    perjudicado = next((l for l in cabecera.splitlines() if "Perjudicado" in l), "")
    assert "tercero" in perjudicado, f"la cabecera no indica que el perjudicado es un tercero:\n{cabecera}"
    cobertura = s["## Cobertura e indemnización"]
    assert motivo in cobertura, cobertura
    for e in t["escenarios"].values():
        assert informe.eur(e["cobertura"]["indemnizacion_estimada_eur"]) in cobertura
    assert comprobar_cifras(md, t) == [], comprobar_cifras(md, t)


# --- specs/31-informe-peritaje.md#AC-007 ------------------------------------
def probar_ac007_sin_confirmados_y_todo_rechazado():
    """AC-007: sin confirmados, y con todo rechazado (los dos escenarios vacios):
    sin excepcion, «Ninguno», importes 0,00 €, comprobar_cifras == []."""
    a1, a2 = _ejemplos()
    sin_conf = copy.deepcopy(a2)
    sin_conf["escenarios"]["confirmados"] = _escenario_vacio(a2["escenarios"]["confirmados"])
    sin_conf["escenarios"]["con_pendientes"]["hallazgos_incluidos"] = ["160-3", "160-5"]
    a1_sin = copy.deepcopy(a1)
    for f in a1_sin["findings"]:
        if f["finding_id"] in ("160-1", "160-4"):
            f["confidence_tier"], f["vision_verdict"] = "needs_review", "incierto"
    sin_conf["hallazgos_fuera_del_coste"] = a2["hallazgos_fuera_del_coste"] + [
        {"finding_id": "160-1", "motivo": "sin_regla_de_coste"}, {"finding_id": "160-4", "motivo": "sin_regla_de_coste"}]
    md = generar_informe(a1_sin, sin_conf, hoy=HOY)
    s = _secciones(md)
    assert "Ninguno" in s["## Daños confirmados"], s["## Daños confirmados"]
    assert "0,00 €" in _fila(s["## Desglose del coste"], "| **Total con IVA**"), s["## Desglose del coste"]
    assert comprobar_cifras(md, sin_conf) == [], comprobar_cifras(md, sin_conf)

    todo = copy.deepcopy(a2)
    todo["escenarios"] = {k: _escenario_vacio(v) for k, v in a2["escenarios"].items()}
    todo["hallazgos_fuera_del_coste"] = [{"finding_id": f["finding_id"], "motivo": "rechazado_por_vision"}
                                         for f in a1["findings"]]
    a1_todo = copy.deepcopy(a1)
    for f in a1_todo["findings"]:
        f["confidence_tier"], f["vision_verdict"] = "needs_review", "rechazado"
    md = generar_informe(a1_todo, todo, hoy=HOY)
    s = _secciones(md)
    for seccion in ("## Daños confirmados", "## Daños pendientes de revisión"):
        assert "Ninguno" in s[seccion], s[seccion]
    for f in a1["findings"]:
        assert f["finding_id"] in s["## Detecciones no incluidas en el coste"], f["finding_id"]
    fila_total = _fila(s["## Desglose del coste"], "| **Total con IVA**")
    assert fila_total.count("0,00 €") == 2, fila_total
    assert comprobar_cifras(md, todo) == [], comprobar_cifras(md, todo)


# --- specs/31-informe-peritaje.md#AC-008 ------------------------------------
def probar_ac008_perdida_total_solo_con_pendientes():
    """AC-008: perdida total solo en con_pendientes -> «No» para confirmados y
    «Sí» para con_pendientes en Resumen y en Cobertura, con motivo, franquicia e
    indemnizacion de cada escenario."""
    a1, a2 = _ejemplos()
    pt = copy.deepcopy(a2)
    cob_p = pt["escenarios"]["con_pendientes"]["cobertura"]
    cob_p.update(perdida_total=True, motivo="Pérdida total", indemnizacion_estimada_eur=pt["valor_venal_eur"] - 300.0)
    pt["valor_venal_eur"] = round(cob_p["indemnizacion_estimada_eur"] + 300.0, 2)
    md = generar_informe(a1, pt, hoy=HOY)
    s = _secciones(md)
    linea = next(l for l in s["## Resumen"].splitlines() if "Pérdida total" in l)
    assert "No con los confirmados" in linea and "Sí incluyendo los pendientes" in linea, linea
    cobertura = s["## Cobertura e indemnización"]
    assert _fila(cobertura, "| Pérdida total").replace(" ", "") == "|Pérdidatotal|No|Sí|", cobertura
    cob_c = pt["escenarios"]["confirmados"]["cobertura"]
    for c in (cob_c, cob_p):
        assert c["motivo"] in _fila(cobertura, "| Motivo")
        assert informe.eur(c["franquicia_eur"]) in _fila(cobertura, "| Franquicia")
        assert informe.eur(c["indemnizacion_estimada_eur"]) in _fila(cobertura, "| Indemnización estimada")
    assert comprobar_cifras(md, pt) == [], comprobar_cifras(md, pt)


# --- specs/31-informe-peritaje.md#AC-011 ------------------------------------
def _espera_error(a1, a2, identificador):
    try:
        generar_informe(a1, a2, hoy=HOY)
    except ValueError as e:
        assert identificador in str(e), f"el error no nombra «{identificador}»: {e}"
        return
    raise AssertionError(f"no se lanzo ValueError con «{identificador}»")


def probar_ac011_entradas_incoherentes():
    """AC-011: ids que no existen en el Agente 1, hallazgos sin grupo, image_id
    distintos, vehiculo_id o pieza_id fuera del catalogo -> ValueError que
    nombra el identificador; no se devuelve informe."""
    a1, a2 = _ejemplos()
    x = copy.deepcopy(a2)
    x["escenarios"]["con_pendientes"]["hallazgos_incluidos"].append("160-9")
    _espera_error(a1, x, "160-9")
    x = copy.deepcopy(a2)
    x["hallazgos_fuera_del_coste"].append({"finding_id": "160-8", "motivo": "sin_regla_de_coste"})
    _espera_error(a1, x, "160-8")
    x = copy.deepcopy(a2)
    x["hallazgos_fuera_del_coste"] = []
    _espera_error(a1, x, "160-2")
    x = copy.deepcopy(a2)
    x["image_id"] = 999
    _espera_error(a1, x, "999")
    x = copy.deepcopy(a2)
    x["contexto"]["vehiculo_id"] = "V999"
    _espera_error(a1, x, "V999")
    y = copy.deepcopy(a1)
    y["findings"][0]["pieza_id"] = "PIEZA_INVENTADA"
    _espera_error(y, a2, "PIEZA_INVENTADA")


def probar_ac011_paquete_ausente():
    """AC-011: sin piia2_paquete_datos/ el modulo falla al importar con un
    mensaje que indica la ruta esperada."""
    with tempfile.TemporaryDirectory() as tmp:
        raiz = Path(tmp)
        (raiz / ".git").mkdir()
        shutil.copy(AQUI / "informe.py", raiz / "informe.py")
        r = subprocess.run([sys.executable, "-c", "import informe"], cwd=raiz, capture_output=True, text=True)
        assert r.returncode != 0, "el modulo importo sin el paquete"
        assert "ImportError" in r.stderr, f"no es un ImportError:\n{r.stderr[-400:]}"
        esperado = (str(raiz.resolve() / "piia2_paquete_datos"), str(raiz / "piia2_paquete_datos"))
        assert any(e in r.stderr for e in esperado), f"el error no indica la ruta esperada:\n{r.stderr[-400:]}"


# --- specs/31-informe-peritaje.md#AC-012 ------------------------------------
def probar_ac012_determinista_sin_clave_ni_red():
    """AC-012: dos informes identicos con la misma fecha, sin OPENAI_API_KEY y sin red."""
    a1, a2 = _ejemplos()
    clave = os.environ.pop("OPENAI_API_KEY", None)
    socket_original = socket.socket

    def _sin_red(*args, **kwargs):
        raise AssertionError("intento de conexion de red")

    socket.socket = _sin_red
    try:
        assert generar_informe(a1, a2, hoy=HOY) == generar_informe(a1, a2, hoy=HOY)
    finally:
        socket.socket = socket_original
        if clave is not None:
            os.environ["OPENAI_API_KEY"] = clave


PRUEBAS = [
    probar_ac001_encabezados_cabecera_y_resumen,
    probar_ac002_confirmados_pendientes_y_no_incluidos,
    probar_ac005_normativa_vacia_y_con_extractos,
    probar_ac009_arrastres_con_nombre_y_probabilidad,
    probar_ac003_sin_importes_inventados,
    probar_ac004_importe_inventado_con_y_sin_miles,
    probar_ac013_numeros_no_monetarios_no_valen_como_importe,
    probar_ac006_tercero_perjudicado,
    probar_ac007_sin_confirmados_y_todo_rechazado,
    probar_ac008_perdida_total_solo_con_pendientes,
    probar_ac011_entradas_incoherentes,
    probar_ac011_paquete_ausente,
    probar_ac012_determinista_sin_clave_ni_red,
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
