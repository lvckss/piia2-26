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


def _bloque_literal(seccion: str, fuente: str) -> list[str]:
    """Lineas del bloque literal (entre vallas de codigo) que sigue a la linea
    de la cita con esa fuente, sin la sangria de la lista."""
    lineas = seccion.splitlines()
    i = next(n for n, l in enumerate(lineas) if fuente in l)
    apertura = lineas[i + 1].strip()
    assert apertura.startswith("```"), f"la cita de {fuente} no va en un bloque literal: {lineas[i + 1]!r}"
    valla = apertura[:len(apertura) - len(apertura.lstrip("`"))]
    sangria = len(lineas[i + 1]) - len(lineas[i + 1].lstrip())
    contenido = []
    for l in lineas[i + 2:]:
        if l.strip() == valla:
            return contenido
        contenido.append(l[sangria:])
    raise AssertionError(f"el bloque literal de {fuente} no se cierra")


def probar_ac001_ac005_cita_con_titulos_no_rompe_el_informe():
    """AC-001 y AC-005: un extracto con lineas que empiezan por «#» (como los
    preambulos de la legislacion del corpus) no anade encabezados al informe y
    se conserva literal, con su tema y su fuente."""
    a1, a2 = _ejemplos()
    extracto = "# Título de la fuente\n# Fuente: referencia\n\nTexto literal con ``` comillas."
    x = copy.deepcopy(a2)
    x["normativa"] = [{"tema": "consulta de prueba", "extracto": extracto, "fuente": "fixture:preambulo"}]
    md = generar_informe(a1, x, hoy=HOY)
    encontrados = [l for l in md.splitlines() if l.startswith("# ") or l.startswith("## ")]
    assert encontrados == ENCABEZADOS, f"encabezados: {encontrados}"
    fuentes = _secciones(md)["## Fuentes consultadas"]
    linea = next(l for l in fuentes.splitlines() if "fixture:preambulo" in l)
    assert "consulta de prueba" in linea, linea
    assert _bloque_literal(fuentes, "fixture:preambulo") == extracto.split("\n")


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


def probar_ac011_hallazgos_repetidos_o_en_grupos_incompatibles():
    """AC-002 y AC-011: un hallazgo repetido dentro de una lista, o que esta a la
    vez en un escenario de coste y fuera del coste, lanza ValueError que nombra
    el id. Un confirmado en los dos escenarios es lo previsto y no da error."""
    a1, a2 = _ejemplos()
    generar_informe(a1, a2, hoy=HOY)  # 160-1 y 160-4 estan en los dos escenarios
    x = copy.deepcopy(a2)
    x["hallazgos_fuera_del_coste"].append({"finding_id": "160-1", "motivo": "sin_regla_de_coste"})
    _espera_error(a1, x, "160-1")
    x = copy.deepcopy(a2)
    x["hallazgos_fuera_del_coste"].append({"finding_id": "160-3", "motivo": "sin_regla_de_coste"})
    _espera_error(a1, x, "160-3")
    x = copy.deepcopy(a2)
    x["escenarios"]["confirmados"]["hallazgos_incluidos"].append("160-1")
    _espera_error(a1, x, "160-1")
    x = copy.deepcopy(a2)
    x["escenarios"]["con_pendientes"]["hallazgos_incluidos"].append("160-5")
    _espera_error(a1, x, "160-5")
    x = copy.deepcopy(a2)
    x["hallazgos_fuera_del_coste"].append(dict(x["hallazgos_fuera_del_coste"][0]))
    _espera_error(a1, x, "160-2")


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


# --- Issue #88, slice 4 (Agente 3): equivalencias de reglas de coste ----------
# Plan: specs/88-equivalencias-reglas-coste.md (AC-005 y AC-009); ADR 0008.
def _agente2_real(a1: dict) -> dict:
    """Salida del Agente 2 calculada con su codigo (agente_recuperacion/, slice 3 de la #88)."""
    sys.path.insert(0, str(AQUI.parent / "agente_recuperacion"))
    from costes_y_cobertura import estimar_siniestro
    return estimar_siniestro(a1, _cargar("contexto_siniestro.json"))


def _fila_por_id(seccion: str, finding_id: str) -> list[str]:
    """Columnas de la fila de la tabla de una seccion cuyo ID es `finding_id`."""
    for linea in seccion.splitlines():
        celdas = [c.strip() for c in linea.strip().strip("|").split("|")]
        if linea.startswith("|") and finding_id in [x.strip() for x in celdas[0].split(",")]:
            return celdas
    raise AssertionError(f"{finding_id} no aparece en la tabla:\n{seccion}")


def _salida_1248_con_tabla() -> dict:
    """001248 como la deja el Agente 1 con la tabla de equivalencias (AC-007): 1248-9, cristal roto en
    PILOTO_TRAS_I, moderado, needs_review, pasa a `regla_coste_aplicable = true`."""
    a1 = _cargar("agente1_real/001248.json")
    nueve = next(f for f in a1["findings"] if f["finding_id"] == "1248-9")
    nueve["regla_coste_aplicable"] = True
    return a1


def probar_88_ac005_reparacion_de_la_regla_efectiva_1248():
    """specs/88-equivalencias-reglas-coste.md#AC-005: en el informe de la salida de AC-004, `1248-9` aparece
    en «Daños pendientes de revisión» con la clase detectada y, en «Reparación», la accion de la regla
    efectiva (optica rota -> «Sustituir la pieza»); no figura en «Detecciones no incluidas en el coste»; el
    texto no habla de equivalencias ni de reglas propias; `comprobar_cifras == []`."""
    a1 = _salida_1248_con_tabla()
    a2 = _agente2_real(a1)
    md = generar_informe(a1, a2, hoy=HOY)
    s = _secciones(md)
    fila = _fila_por_id(s["## Daños pendientes de revisión"], "1248-9")
    assert fila[2] == "rotura de cristal", fila          # clase detectada, no la equivalente
    assert fila[3] == "moderado", fila
    assert fila[4] == "Sustituir la pieza", fila          # accion de lamp_broken/optica/moderado
    assert "sin regla de coste" not in fila[5], fila
    assert "1248-9" not in s["## Detecciones no incluidas en el coste"], s["## Detecciones no incluidas en el coste"]
    assert "equivalen" not in md.lower() and "regla propia" not in md.lower(), "el informe no menciona equivalencias"
    assert comprobar_cifras(md, a2) == [], comprobar_cifras(md, a2)


def probar_88_ac005_grieta_de_neumatico_leve_con_severidad_minima():
    """specs/88-equivalencias-reglas-coste.md#AC-005 (severidad minima): una grieta `leve` en el neumatico se
    muestra como grieta y `leve`, pero su reparacion es la de `tire_flat` `moderado`
    («Sustituir el neumático y alinear»), la que se ha presupuestado."""
    a1 = {"image_id": 7, "resumen_filtro_previo": {"detecciones_totales": 1, "candidatas": 1, "descartadas_por_clase": {}},
          "findings": [{"finding_id": "7-1", "category": "crack", "clase_tool": "crack", "score": 0.9,
                        "score_tier": "confirmed", "confidence_tier": "needs_review", "bbox_xywh": [0, 0, 10, 10],
                        "vision_verdict": "confirmado", "pieza_id": "NEUMATICO", "severidad": "leve",
                        "regla_coste_aplicable": True, "vision_description": "Grieta en el flanco.",
                        "crop_image_path": None}]}
    a2 = _agente2_real(a1)
    md = generar_informe(a1, a2, hoy=HOY)
    fila = _fila_por_id(_secciones(md)["## Daños pendientes de revisión"], "7-1")
    assert (fila[2], fila[3], fila[4]) == ("grieta", "leve", "Sustituir el neumático y alinear"), fila
    assert comprobar_cifras(md, a2) == []


def probar_88_ac009_informe_con_equivalencia_determinista_sin_clave_ni_red():
    """specs/88-equivalencias-reglas-coste.md#AC-009: dos ejecuciones de `generar_informe` sobre una salida con
    una equivalencia dan el mismo informe, sin clave ni red. Regresion: verde antes y despues."""
    a1 = _salida_1248_con_tabla()
    a2 = _agente2_real(a1)
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


# --- Issue #97, slice 3 (Agente 3): justificaciones con LLM de la normativa ---
# Plan: specs/97-justificacion-llm-normativa.md (AC-008, AC-009 y AC-010); ADR 0009.
AVISO_JUSTIFICACION = ("Informe preliminar: no se ha podido redactar la justificación de algunas fuentes; "
                       "se muestran sus citas sin justificación y requieren revisión.")
FUENTE_FR300 = "docs/polizas_sinteticas/P-TR-FR300.md"
J_DANOS = {"tema": "cobertura de daños propios", "estado": "generada",
           "texto": "La póliza cubre los daños propios por colisión, vuelco, atropello de animales y actos "
                    "vandálicos, con una franquicia por siniestro.",
           "citas": [{"extracto": "Daños propios por colisión, vuelco, atropello de animales y actos vandálicos",
                      "fuente": f"{FUENTE_FR300}#2. Coberturas incluidas"}]}
J_PT = {"tema": "pérdida total", "estado": "generada",
        "texto": "Hay pérdida total cuando la reparación sin IVA alcanza el umbral fijado sobre el valor venal.",
        "citas": [{"extracto": "Habrá pérdida total cuando el coste de reparación (sin IVA) alcance o supere el 75 % "
                               "del valor venal.", "fuente": f"{FUENTE_FR300}#5. Pérdida total"}]}
MOTIVO_NO_GENERADA = "El modelo no respondió (error del proveedor o tiempo agotado)."


def _con_justificaciones(a2: dict, *justificaciones: dict) -> dict:
    x = copy.deepcopy(a2)
    x["justificaciones"] = [copy.deepcopy(j) for j in justificaciones]
    return x


def probar_97_ac008_justificaciones_con_sus_citas():
    """specs/97-justificacion-llm-normativa.md#AC-008: con dos justificaciones `generada`, «Fuentes
    consultadas» muestra el texto de cada tema y, debajo, sus citas con su fuente como bloque literal; los
    9 encabezados no cambian, no aparece «verificada» y `comprobar_cifras == []`."""
    a1, a2 = _ejemplos()
    a2j = _con_justificaciones(a2, J_DANOS, J_PT)
    md = generar_informe(a1, a2j, hoy=HOY)
    assert [l for l in md.splitlines() if l.startswith("#")] == ENCABEZADOS, md
    fuentes = _secciones(md)["## Fuentes consultadas"]
    for j in (J_DANOS, J_PT):
        assert j["texto"] in fuentes, (j["tema"], fuentes)
        cita = j["citas"][0]
        assert f"  {cita['extracto']}" in fuentes.splitlines(), (cita, fuentes)  # dentro del bloque literal
        assert cita["fuente"] in fuentes, (cita, fuentes)
        assert fuentes.index(j["texto"]) < fuentes.index(cita["extracto"]), "la cita va debajo de su texto"
    assert "verificad" not in md.lower(), md
    assert AVISO_JUSTIFICACION not in md
    assert comprobar_cifras(md, a2j) == [], comprobar_cifras(md, a2j)


def probar_97_ac009_justificacion_no_generada_da_informe_preliminar():
    """specs/97-justificacion-llm-normativa.md#AC-009: una justificacion `no_generada` (o `descartada`) pone en
    la cabecera el aviso de informe preliminar de justificaciones y, en «Fuentes consultadas», el tema con su
    motivo y sus citas sin justificacion."""
    a1, a2 = _ejemplos()
    for estado in ("no_generada", "descartada"):
        sin = {"tema": "pérdida total", "estado": estado, "motivo": MOTIVO_NO_GENERADA}
        md = generar_informe(a1, _con_justificaciones(a2, J_DANOS, sin), hoy=HOY)
        cabecera = md.split("## Resumen")[0]
        assert AVISO_JUSTIFICACION in cabecera, (estado, cabecera)
        fuentes = _secciones(md)["## Fuentes consultadas"]
        pasaje = next(n for n in a2["normativa"] if n["tema"] == "pérdida total")
        assert MOTIVO_NO_GENERADA in fuentes, (estado, fuentes)
        assert f"  {pasaje['extracto']}" in fuentes.splitlines(), (estado, fuentes)  # su cita, sin justificacion
        assert J_DANOS["texto"] in fuentes, fuentes
        assert comprobar_cifras(md, a2) == []


def probar_97_ac009_sin_justificaciones_el_informe_no_cambia():
    """specs/97-justificacion-llm-normativa.md#AC-009: sin el campo `justificaciones`, el informe es el actual:
    sin aviso de justificaciones y con «Fuentes consultadas» en el formato de la spec 31."""
    a1, a2 = _ejemplos()
    md = generar_informe(a1, a2, hoy=HOY)
    assert AVISO_JUSTIFICACION not in md and "Justificación" not in md
    fuentes = _secciones(md)["## Fuentes consultadas"]
    for n in a2["normativa"]:
        assert f"- {n['tema']} ({n['fuente']}):" in fuentes.splitlines(), fuentes


def probar_97_ac009_justificaciones_mal_formadas():
    """specs/97-justificacion-llm-normativa.md#AC-009: estado desconocido, tema ausente o una `generada` con un
    importe en el texto («1.500 €», «300 EUR») -> excepcion que nombra el campo y ningun informe."""
    a1, a2 = _ejemplos()
    sin_tema = {k: v for k, v in J_DANOS.items() if k != "tema"}
    malas = [dict(J_DANOS, estado="rara"), sin_tema,
             dict(J_DANOS, texto="La póliza cubre las lunas hasta 1.500 € al año."),
             dict(J_DANOS, texto="La franquicia es de 300 EUR por siniestro."),
             # revision de Lucas en la #101: moneda pegada al numero o escrita delante
             dict(J_DANOS, texto="La franquicia es de 300EUR por siniestro."),
             dict(J_DANOS, texto="El límite es de euros 1500 al año.")]
    for mala in malas:
        try:
            generar_informe(a1, _con_justificaciones(a2, mala), hoy=HOY)
        except ValueError as error:
            assert "justificaciones" in str(error), (mala, error)
        else:
            raise AssertionError(f"se esperaba ValueError con {mala}")


def probar_97_ejemplo_completo_del_contrato():
    """specs/97-justificacion-llm-normativa.md#AC-006 y AC-008 (ejemplos, slice 4): `agente2_salida_completa.json`
    (la salida de `agente2()` con RAG y LLM simulados) tiene las mismas cifras que `agente2_salida.json`; cada
    cita de sus justificaciones esta literalmente en un pasaje de su tema, y el informe la muestra sin aviso y
    con `comprobar_cifras == []`."""
    a1, a2 = _ejemplos()
    completa = _cargar("agente2_salida_completa.json")
    nuevos = ("normativa", "diagnostico_rag", "justificaciones")
    assert {k: v for k, v in completa.items() if k not in nuevos} == {k: v for k, v in a2.items() if k != "normativa"}
    assert completa["diagnostico_rag"]["estado"] == "recuperadas"
    for j in completa["justificaciones"]:
        assert j["estado"] == "generada", j
        pasajes = [n["extracto"] for n in completa["normativa"] if n["tema"] == j["tema"]]
        for cita in j["citas"]:
            assert any(cita["extracto"] in p for p in pasajes), (j["tema"], cita)
    md = generar_informe(a1, completa, hoy=HOY)
    assert AVISO_JUSTIFICACION not in md and AVISO_PRELIMINAR not in md
    fuentes = _secciones(md)["## Fuentes consultadas"]
    assert all(j["texto"] in fuentes for j in completa["justificaciones"]), fuentes
    assert comprobar_cifras(md, completa) == [], comprobar_cifras(md, completa)


def probar_97_ac010_informe_con_justificaciones_determinista():
    """specs/97-justificacion-llm-normativa.md#AC-010: dos informes iguales con las mismas justificaciones, sin
    clave ni red (el Agente 3 no llama a ningun modelo)."""
    a1, a2 = _ejemplos()
    a2j = _con_justificaciones(a2, J_DANOS, J_PT)
    clave = os.environ.pop("OPENAI_API_KEY", None)
    socket_original = socket.socket

    def _sin_red(*args, **kwargs):
        raise AssertionError("intento de conexion de red")

    socket.socket = _sin_red
    try:
        assert generar_informe(a1, a2j, hoy=HOY) == generar_informe(a1, a2j, hoy=HOY)
    finally:
        socket.socket = socket_original
        if clave is not None:
            os.environ["OPENAI_API_KEY"] = clave


# --- specs/31-informe-peritaje.md#AC-014 y AC-015 ---------------------------
# `diagnostico_rag` con la forma del contrato integrado de la #32
# (specs/32-rag-normativa.md, «Contrato propuesto de diagnóstico»; ADR 0006).
AVISO_PRELIMINAR = ("Informe preliminar: no se han recuperado fuentes suficientes para respaldar las "
                    "conclusiones indicadas sobre cobertura e indemnización. Estas conclusiones requieren revisión")
TEMA_OK, TEMA_VACIO, TEMA_FALLO = "cobertura de daños propios", "franquicia de daños propios", "regla de indemnización"
MENSAJE_FALLO = "No se pudo consultar el buscador de normativa: el servicio tardó demasiado en responder."
MENSAJE_VACIO = "La búsqueda terminó sin encontrar fragmentos para este tema."
TECNICOS = ("EMBEDDINGS_TIMEOUT", "SIN_RESULTADOS", "reintentable", "etapa")


def _consulta(tema, estado, fuentes=(), incidencias=()):
    return {"tema": tema, "estado": estado, "fuentes": list(fuentes), "incidencias": list(incidencias)}


def _incidencia(codigo, etapa, mensaje, reintentable):
    return {"codigo": codigo, "etapa": etapa, "mensaje": mensaje, "reintentable": reintentable}


def _con_diagnostico(a2: dict, estado: str) -> dict:
    """Copia de la salida del Agente 2 con un diagnostico en ese estado."""
    x = copy.deepcopy(a2)
    cita = a2["normativa"][0]
    ok = _consulta(TEMA_OK, "recuperadas", [cita["fuente"]])
    vacia = _consulta(TEMA_VACIO, "sin_resultados")
    fallo = _consulta(TEMA_FALLO, "error", incidencias=[_incidencia("EMBEDDINGS_TIMEOUT", "embeddings", MENSAJE_FALLO, True)])
    vacia_con_motivo = _consulta(TEMA_VACIO, "sin_resultados",
                                 incidencias=[_incidencia("SIN_RESULTADOS", "consulta", MENSAJE_VACIO, False)])
    consultas = {
        "recuperadas": [ok],
        "parcial": [ok, vacia, fallo],
        "sin_resultados": [vacia_con_motivo],
        "error": [fallo],
        "no_aplica": [],
    }[estado]
    x["normativa"] = [cita] if estado in ("recuperadas", "parcial") else []
    x["diagnostico_rag"] = {"estado": estado, "consultas": consultas}
    return x


def probar_ac014_diagnostico_en_sus_cinco_estados():
    """AC-014: aviso preliminar literal solo en parcial, sin_resultados y error;
    tema y mensaje de cada consulta no recuperada; en parcial se conserva la
    cita; nunca «verificada» ni codigo/etapa/reintentable; cifras del Agente 2."""
    a1, a2 = _ejemplos()
    for estado in ("recuperadas", "parcial", "sin_resultados", "error", "no_aplica"):
        x = _con_diagnostico(a2, estado)
        md = generar_informe(a1, x, hoy=HOY)
        s = _secciones(md)
        preliminar = estado in ("parcial", "sin_resultados", "error")
        assert (AVISO_PRELIMINAR in s[ENCABEZADOS[0]]) == preliminar, f"{estado}: aviso preliminar mal\n{s[ENCABEZADOS[0]]}"
        assert md.count(AVISO_PRELIMINAR) == (1 if preliminar else 0), estado
        fuentes = s["## Fuentes consultadas"]
        for c in x["diagnostico_rag"]["consultas"]:
            if c["estado"] == "recuperadas":
                continue
            linea = next((l for l in fuentes.splitlines() if c["tema"] in l), "")
            assert linea, f"{estado}: falta el tema {c['tema']!r} en Fuentes consultadas\n{fuentes}"
            esperados = [i["mensaje"] for i in c["incidencias"]] or ["sin resultados"]
            for texto in esperados:
                assert texto in linea, f"{estado}: falta {texto!r} en {linea!r}"
        if estado == "parcial":
            cita = x["normativa"][0]
            assert cita["fuente"] in fuentes and cita["tema"] in fuentes, fuentes
        assert "verificad" not in md.lower(), f"{estado}: aparece «verificada»"
        for tecnico in TECNICOS:
            assert tecnico not in md, f"{estado}: se muestra {tecnico!r}"
        assert comprobar_cifras(md, x) == [], (estado, comprobar_cifras(md, x))


def _espera_error_diagnostico(a1, a2, campo):
    try:
        generar_informe(a1, a2, hoy=HOY)
    except ValueError as e:
        assert campo in str(e), f"el error no nombra «{campo}»: {e}"
        return
    raise AssertionError(f"no se lanzo ValueError con {campo} malformado")


def probar_ac015_sin_diagnostico_y_diagnostico_malformado():
    """AC-015: sin el campo, el informe es el de siempre (sin aviso
    preliminar); con estado fuera de los cinco valores o una consulta sin
    tema, ValueError que nombra el campo."""
    a1, a2 = _ejemplos()
    assert "diagnostico_rag" not in a2
    md = generar_informe(a1, a2, hoy=HOY)
    assert "Informe preliminar" not in md
    for prueba in (probar_ac001_encabezados_cabecera_y_resumen, probar_ac002_confirmados_pendientes_y_no_incluidos,
                   probar_ac003_sin_importes_inventados, probar_ac004_importe_inventado_con_y_sin_miles,
                   probar_ac005_normativa_vacia_y_con_extractos):
        prueba()
    x = _con_diagnostico(a2, "parcial")
    x["diagnostico_rag"]["estado"] = "casi"
    _espera_error_diagnostico(a1, x, "estado")
    x = _con_diagnostico(a2, "parcial")
    del x["diagnostico_rag"]["consultas"][1]["tema"]
    _espera_error_diagnostico(a1, x, "tema")


# --- plan v1.1 de la #54, AC-003 y AC-011 -----------------------------------
# https://github.com/lvckss/piia2-26/issues/54#issuecomment-6806386857 (AC-003, modificado)
# https://github.com/lvckss/piia2-26/issues/54#issuecomment-6805208293 (AC-011)
REAL = AQUI.parent / "ejemplos_contrato" / "agente1_real"


def _agente2_real_con_vehiculo(salida_agente1: dict) -> dict:
    """Salida real del Agente 2 para una salida del Agente 1, con el contexto del ejemplo y el coche de
    referencia (o V14 con `desconocido`)."""
    sys.path.insert(0, str(AQUI.parent / "agente_recuperacion"))
    from costes_y_cobertura import estimar_siniestro

    ctx = _cargar("contexto_siniestro.json")
    ctx["vehiculo_id"] = salida_agente1["vehiculo"]["vehiculo_id_referencia"] or "V14"
    return estimar_siniestro(salida_agente1, ctx)


def probar_54_ac003_requieren_revision_humana():
    """#54 AC-003: los hallazgos fuera del coste por `sin_pieza_o_severidad` o `sin_regla_de_coste` se listan
    aparte bajo «Requieren revisión humana» con su finding_id y clase, y el «Resumen» dice cuántos son; los
    rechazados conservan su texto; sin ninguno, el «Resumen» no cambia."""
    a1, a2 = _ejemplos()
    resumen_actual = _secciones(generar_informe(a1, a2, hoy=HOY))["## Resumen"]
    assert "revisión humana" not in resumen_actual, resumen_actual
    assert sum(l.startswith("- ") for l in resumen_actual.splitlines()) == 5, resumen_actual

    x = copy.deepcopy(a2)
    x["escenarios"]["con_pendientes"]["hallazgos_incluidos"] = ["160-1", "160-4"]
    x["hallazgos_fuera_del_coste"] += [{"finding_id": "160-3", "motivo": "sin_pieza_o_severidad"},
                                       {"finding_id": "160-5", "motivo": "sin_regla_de_coste"}]
    md = generar_informe(a1, x, hoy=HOY)
    s = _secciones(md)
    fuera = s["## Detecciones no incluidas en el coste"]
    lineas = fuera.splitlines()
    i = next(n for n, l in enumerate(lineas) if "Requieren revisión humana" in l)
    bloque = "\n".join(lineas[i:])
    for fid, clase in (("160-3", "abolladura"), ("160-5", "arañazo")):
        linea = next(l for l in bloque.splitlines() if fid in l)
        assert clase in linea, linea
    linea_2 = next(l for l in lineas if "160-2" in l)
    assert lineas.index(linea_2) < i and "rechazado por la visión" in linea_2, fuera
    assert "2 detecciones requieren revisión humana" in s["## Resumen"], s["## Resumen"]
    encontrados = [l for l in md.splitlines() if l.startswith("# ") or l.startswith("## ")]
    assert encontrados == ENCABEZADOS, encontrados
    assert comprobar_cifras(md, x) == [], comprobar_cifras(md, x)


def probar_54_ac003_sin_nada_presupuestable_003478():
    """#54 AC-003: con todos los hallazgos fuera del coste y 0 € (el 003478 real), el «Resumen» dice que ningún
    hallazgo es presupuestable y cuántas detecciones requieren revisión humana."""
    a1 = json.loads((REAL / "003478.json").read_text(encoding="utf-8"))
    a2 = _agente2_real_con_vehiculo(a1)
    assert a2["escenarios"]["con_pendientes"]["hallazgos_incluidos"] == []
    md = generar_informe(a1, a2, hoy=HOY)
    resumen = _secciones(md)["## Resumen"]
    assert "Ningún hallazgo es presupuestable" in resumen, resumen
    assert "1 detección requiere revisión humana" in resumen, resumen
    assert "3478-4" in _secciones(md)["## Detecciones no incluidas en el coste"]
    encontrados = [l for l in md.splitlines() if l.startswith("# ") or l.startswith("## ")]
    assert encontrados == [ENCABEZADOS[0].replace("160", "3478")] + ENCABEZADOS[1:], encontrados
    assert comprobar_cifras(md, a2) == [], comprobar_cifras(md, a2)


def probar_54_ac011_aviso_de_lo_que_detecta_piia1():
    """#54 AC-011: el informe incluye, aparte del aviso literal de la cabecera, una línea que dice que solo se
    analizan los daños detectados por PIIA 1 y que puede haber otros (el ejemplo y el 000423 real)."""
    a1, a2 = _ejemplos()
    real = json.loads((REAL / "000423.json").read_text(encoding="utf-8"))
    for salida1, salida2 in ((a1, a2), (real, _agente2_real_con_vehiculo(real))):
        md = generar_informe(salida1, salida2, hoy=HOY)
        cabecera = _secciones(md)[next(l for l in md.splitlines() if l.startswith("# "))]
        assert AVISO_LEGAL in cabecera, cabecera
        linea = next((l for l in cabecera.splitlines() if "PIIA 1" in l), "")
        assert linea and AVISO_LEGAL not in linea and "puede haber otros" in linea, cabecera
        encontrados = [l for l in md.splitlines() if l.startswith("# ") or l.startswith("## ")]
        assert encontrados[1:] == ENCABEZADOS[1:], encontrados
        assert comprobar_cifras(md, salida2) == [], comprobar_cifras(md, salida2)


# --- plan v1 de la #54, AC-001, AC-002 y AC-004 ------------------------------
# https://github.com/lvckss/piia2-26/issues/54#issuecomment-6805208293
def probar_54_ac001_taller_legible():
    """#54 AC-001: con `concertado_aseguradora` la cabecera muestra un nombre legible y ningun valor con guion
    bajo; con `multimarca`, `oficial` y `concesionario` la cabecera es identica a la actual."""
    a1, a2 = _ejemplos()
    for taller in ("multimarca", "oficial", "concesionario"):
        x = copy.deepcopy(a2)
        x["contexto"]["tipo_taller"] = taller
        cabecera = _secciones(generar_informe(a1, x, hoy=HOY))[ENCABEZADOS[0]]
        assert f"- **Taller:** {taller} (Madrid)" in cabecera, cabecera
    x = copy.deepcopy(a2)
    x["contexto"]["tipo_taller"] = "concertado_aseguradora"
    cabecera = _secciones(generar_informe(a1, x, hoy=HOY))[ENCABEZADOS[0]]
    linea = next(l for l in cabecera.splitlines() if l.startswith("- **Taller:**"))
    assert "_" not in cabecera and "concertado con la aseguradora" in linea, cabecera


def probar_54_ac002_umbral_cero_no_aplica():
    """#54 AC-002: con `umbral_perdida_total = 0.0` (polizas P-TERC-*) el «Resumen» no dice «umbral 0 %» e
    indica que no aplica; con 0.75 el texto es el de siempre."""
    a1, a2 = _ejemplos()
    resumen = _secciones(generar_informe(a1, a2, hoy=HOY))["## Resumen"]
    assert "umbral 75 %" in resumen, resumen
    x = copy.deepcopy(a2)
    x["umbral_perdida_total"] = 0.0
    md = generar_informe(a1, x, hoy=HOY)
    resumen = _secciones(md)["## Resumen"]
    linea = next(l for l in resumen.splitlines() if "Pérdida total" in l)
    assert "umbral 0 %" not in resumen and "no aplica" in linea, linea
    assert comprobar_cifras(md, x) == [], comprobar_cifras(md, x)


def probar_54_ac004_hallazgos_iguales_en_una_fila_000341():
    """#54 AC-004: en el 000341 real, los confirmados con la misma pieza, dano, severidad y reparacion
    (`341-1` y `341-2`, cristal roto grave del parabrisas) van en una sola fila con sus finding_id y scores;
    cada finding_id aparece y los importes no cambian."""
    a1 = json.loads((REAL / "000341.json").read_text(encoding="utf-8"))
    a2 = _agente2_real(a1)
    md = generar_informe(a1, a2, hoy=HOY)
    tabla = [l for l in _secciones(md)["## Daños confirmados"].splitlines() if l.startswith("| 341-")]
    fila = next(l for l in tabla if "341-1" in l)
    assert "341-2" in fila and "0,96" in fila and "0,95" in fila, fila
    assert len(tabla) == 3, tabla
    for fid in ("341-1", "341-2", "341-3", "341-4"):
        assert any(fid in l for l in tabla), fid
    for esc in ("confirmados", "con_pendientes"):
        assert informe.eur(a2["escenarios"][esc]["estimacion"]["total_con_iva_eur"]) in md, esc
    assert comprobar_cifras(md, a2) == [], comprobar_cifras(md, a2)


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
    probar_ac011_hallazgos_repetidos_o_en_grupos_incompatibles,
    probar_ac001_ac005_cita_con_titulos_no_rompe_el_informe,
    probar_ac011_paquete_ausente,
    probar_ac012_determinista_sin_clave_ni_red,
    probar_ac014_diagnostico_en_sus_cinco_estados,
    probar_ac015_sin_diagnostico_y_diagnostico_malformado,
    probar_54_ac003_requieren_revision_humana,
    probar_54_ac003_sin_nada_presupuestable_003478,
    probar_54_ac011_aviso_de_lo_que_detecta_piia1,
    probar_88_ac005_reparacion_de_la_regla_efectiva_1248,
    probar_88_ac005_grieta_de_neumatico_leve_con_severidad_minima,
    probar_88_ac009_informe_con_equivalencia_determinista_sin_clave_ni_red,
    probar_54_ac001_taller_legible,
    probar_54_ac002_umbral_cero_no_aplica,
    probar_54_ac004_hallazgos_iguales_en_una_fila_000341,
    probar_97_ac008_justificaciones_con_sus_citas,
    probar_97_ac009_justificacion_no_generada_da_informe_preliminar,
    probar_97_ac009_sin_justificaciones_el_informe_no_cambia,
    probar_97_ac009_justificaciones_mal_formadas,
    probar_97_ac010_informe_con_justificaciones_determinista,
    probar_97_ejemplo_completo_del_contrato,
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
