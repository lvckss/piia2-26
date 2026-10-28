"""Pruebas del Agente 2 (costes y cobertura) contra el plan de la #30.

Cada prueba cita su criterio: specs/30-costes-cobertura.md#AC-0XX.
Usa la herramienta real de la empresa (piia2_paquete_datos/, fuera de git) y
los ejemplos de ejemplos_contrato/. No necesita API Key ni red.

Se ejecuta desde esta carpeta:  python probar_costes.py
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

import costes_y_cobertura
from costes_y_cobertura import estimar_siniestro

AQUI = Path(__file__).resolve().parent
EJ = AQUI.parent / "ejemplos_contrato"


def _cargar(nombre: str) -> dict:
    return json.loads((EJ / nombre).read_text(encoding="utf-8"))


def _ejemplos():
    return _cargar("agente1_salida.json"), _cargar("contexto_siniestro.json"), _cargar("agente2_salida.json")


def _hallazgo(fid, tier, veredicto, pieza, severidad, regla, clase="dent"):
    """Hallazgo con la forma del contrato Agente 1 -> Agente 2 (ADR 0002)."""
    return {
        "finding_id": fid, "category": clase.replace("_", " "), "clase_tool": clase,
        "score": 0.9, "score_tier": "confirmed", "confidence_tier": tier,
        "bbox_xywh": [0.0, 0.0, 10.0, 10.0], "vision_verdict": veredicto,
        "pieza_id": pieza, "severidad": severidad, "regla_coste_aplicable": regla,
        "vision_description": "prueba", "crop_image_path": None,
    }


def _escenarios(salida):
    return salida["escenarios"]["confirmados"], salida["escenarios"]["con_pendientes"]


# --- specs/30-costes-cobertura.md#AC-001 ------------------------------------
def probar_ac001_contrato_del_ejemplo():
    """AC-001: con los ejemplos del contrato, la salida es igual a
    agente2_salida.json (version de main) salvo `normativa`, que es []."""
    a1, ctx, esperado = _ejemplos()
    obtenido = estimar_siniestro(a1, ctx)
    assert obtenido.get("normativa") == [], "normativa debe ser []"
    esperado = copy.deepcopy(esperado)
    esperado["normativa"] = []
    assert obtenido == esperado, "la salida no coincide con agente2_salida.json"
    conf, pend = _escenarios(obtenido)
    assert (conf["estimacion"]["subtotal_sin_iva_eur"], conf["cobertura"]["indemnizacion_estimada_eur"]) == (1019.46, 933.55)
    assert (pend["estimacion"]["subtotal_sin_iva_eur"], pend["cobertura"]["indemnizacion_estimada_eur"]) == (1488.23, 1500.76)


# --- specs/30-costes-cobertura.md#AC-002 ------------------------------------
def probar_ac002_reparto_de_hallazgos():
    """AC-002: confirmados en los dos escenarios, pendientes solo en
    con_pendientes y el resto fuera del coste con su motivo exacto; cada
    finding_id en un unico grupo y ninguno perdido."""
    _, ctx, _ = _ejemplos()
    findings = [
        _hallazgo("1-1", "confirmed", "confirmado", "FARO_DEL_D", "grave", True, "lamp_broken"),
        _hallazgo("1-2", "needs_review", "confirmado", "PARAG_DEL", "grave", True),
        _hallazgo("1-3", "needs_review", "rechazado", None, None, None, "tire_flat"),
        _hallazgo("1-4", "needs_review", "incierto", None, "leve", None, "scratch"),
        _hallazgo("1-5", "needs_review", "confirmado", "PUERTA_DEL_I", None, None, "scratch"),
        _hallazgo("1-6", "needs_review", "confirmado", "PARABRISAS", "grave", False),
        _hallazgo("1-7", "needs_review", "incierto", "PUERTA_DEL_I", "leve", None, "scratch"),
    ]
    salida = estimar_siniestro({"image_id": 1, "findings": findings}, ctx)
    conf, pend = _escenarios(salida)
    assert conf["hallazgos_incluidos"] == ["1-1"], conf["hallazgos_incluidos"]
    assert pend["hallazgos_incluidos"] == ["1-1", "1-2"], pend["hallazgos_incluidos"]
    fuera = {x["finding_id"]: x["motivo"] for x in salida["hallazgos_fuera_del_coste"]}
    assert fuera == {
        "1-3": "rechazado_por_vision",
        "1-4": "sin_pieza_o_severidad",
        "1-5": "sin_pieza_o_severidad",
        "1-6": "sin_regla_de_coste",
        "1-7": "sin_regla_de_coste",
    }, fuera
    vistos = pend["hallazgos_incluidos"] + list(fuera)
    assert sorted(vistos) == sorted(f["finding_id"] for f in findings), "un hallazgo se pierde o se repite"


# --- specs/30-costes-cobertura.md#AC-003 ------------------------------------
def probar_ac003_tercero_perjudicado():
    """AC-003: tercero perjudicado -> umbral 1,0, cubierto, franquicia 0,
    motivo de RC obligatoria e indemnizacion = total con IVA (o valor venal
    si hay perdida total)."""
    a1, ctx, _ = _ejemplos()
    ctx = dict(ctx, rol="tercero_perjudicado", poliza_id="")
    salida = estimar_siniestro(a1, ctx)
    assert salida["umbral_perdida_total"] == 1.0
    for esc in _escenarios(salida):
        cob, est = esc["cobertura"], esc["estimacion"]
        assert cob["cubierto"] is True and cob["franquicia_eur"] == 0
        assert "RC obligatoria" in cob["motivo"], cob["motivo"]
        esperado = salida["valor_venal_eur"] if cob["perdida_total"] else est["total_con_iva_eur"]
        assert cob["indemnizacion_estimada_eur"] == round(esperado, 2)


# --- specs/30-costes-cobertura.md#AC-004 ------------------------------------
def probar_ac004_poliza_sin_colision():
    """AC-004: P-TERC-BASICO no cubre colision ni lunas -> no cubierto, 0,00 EUR."""
    a1, ctx, _ = _ejemplos()
    salida = estimar_siniestro(a1, dict(ctx, poliza_id="P-TERC-BASICO"))
    for esc in _escenarios(salida):
        assert esc["cobertura"]["cubierto"] is False
        assert esc["cobertura"]["indemnizacion_estimada_eur"] == 0.0


# --- specs/30-costes-cobertura.md#AC-005 ------------------------------------
def probar_ac005_perdida_total_v14():
    """AC-005: V14, 16 anos, 300.000 km, P-TR-FR300 -> valor venal 1.160,00;
    confirmados 560,80 / 678,57 / sin PT / 378,57; con_pendientes 935,85 /
    1.132,38 / PT / 860,00."""
    a1, ctx, _ = _ejemplos()
    salida = estimar_siniestro(a1, dict(ctx, vehiculo_id="V14", edad_anios=16, km=300000))
    assert salida["valor_venal_eur"] == 1160.0
    assert round(salida["umbral_perdida_total"] * salida["valor_venal_eur"], 2) == 870.0
    conf, pend = _escenarios(salida)
    for esc, sub, tot, pt, ind in ((conf, 560.80, 678.57, False, 378.57), (pend, 935.85, 1132.38, True, 860.00)):
        assert esc["estimacion"]["subtotal_sin_iva_eur"] == sub, esc["estimacion"]["subtotal_sin_iva_eur"]
        assert esc["estimacion"]["total_con_iva_eur"] == tot, esc["estimacion"]["total_con_iva_eur"]
        assert esc["cobertura"]["perdida_total"] is pt
        assert esc["cobertura"]["indemnizacion_estimada_eur"] == ind, esc["cobertura"]["indemnizacion_estimada_eur"]


# --- specs/30-costes-cobertura.md#AC-006 ------------------------------------
def probar_ac006_lunas_con_limite():
    """AC-006: parabrisas grave, V25 + P-TERC-AMPLIADO -> cobertura de lunas,
    franquicia 0,00, total 987,60 e indemnizacion 800,00 (actua el limite)."""
    _, ctx, _ = _ejemplos()
    a1 = {"image_id": 2, "findings": [_hallazgo("2-1", "confirmed", "confirmado", "PARABRISAS", "grave", True, "glass_shatter")]}
    salida = estimar_siniestro(a1, dict(ctx, vehiculo_id="V25", poliza_id="P-TERC-AMPLIADO"))
    for esc in _escenarios(salida):
        assert esc["cobertura"]["motivo"] == "Cobertura de lunas", esc["cobertura"]["motivo"]
        assert esc["cobertura"]["franquicia_eur"] == 0.0
        assert esc["estimacion"]["total_con_iva_eur"] == 987.60, esc["estimacion"]["total_con_iva_eur"]
        assert esc["cobertura"]["indemnizacion_estimada_eur"] == 800.00


# --- specs/30-costes-cobertura.md#AC-007 ------------------------------------
def probar_ac007_escenario_vacio():
    """AC-007: sin hallazgos presupuestables, cada escenario conserva la forma
    de uno con danos (mismas claves, importes 0, listas vacias) y la cobertura
    es «Sin danos presupuestables»."""
    a1, ctx, ejemplo = _ejemplos()
    claves_est = set(ejemplo["escenarios"]["confirmados"]["estimacion"])
    claves_cob = set(ejemplo["escenarios"]["confirmados"]["cobertura"])
    rechazados = [dict(f, confidence_tier="needs_review", vision_verdict="rechazado",
                       pieza_id=None, severidad=None, regla_coste_aplicable=None) for f in a1["findings"]]
    for findings in ([], rechazados):
        salida = estimar_siniestro({"image_id": 160, "findings": findings}, ctx)
        for esc in _escenarios(salida):
            est, cob = esc["estimacion"], esc["cobertura"]
            assert esc["hallazgos_incluidos"] == []
            assert set(est) == claves_est, set(est) ^ claves_est
            assert set(cob) == claves_cob, set(cob) ^ claves_cob
            assert len(est["desglose"]) == 6 and all(v == 0 for v in est["desglose"].values())
            assert est["subtotal_sin_iva_eur"] == est["iva_eur"] == est["total_con_iva_eur"] == 0
            assert est["lineas"] == [] and est["arrastres_posibles"] == []
            assert cob == {"cubierto": False, "motivo": "Sin daños presupuestables", "franquicia_eur": 0.0,
                           "perdida_total": False, "indemnizacion_estimada_eur": 0.0}, cob


# --- specs/30-costes-cobertura.md#AC-008 ------------------------------------
def probar_ac008_determinista_sin_red():
    """AC-008: dos ejecuciones identicas sin OPENAI_API_KEY y sin red."""
    a1, ctx, _ = _ejemplos()
    clave = os.environ.pop("OPENAI_API_KEY", None)
    socket_original = socket.socket

    def _sin_red(*args, **kwargs):
        raise AssertionError("intento de conexion de red")

    socket.socket = _sin_red
    try:
        assert estimar_siniestro(a1, ctx) == estimar_siniestro(a1, ctx)
    finally:
        socket.socket = socket_original
        if clave is not None:
            os.environ["OPENAI_API_KEY"] = clave


# --- specs/30-costes-cobertura.md#AC-010 ------------------------------------
def _espera_error(contexto, campo):
    a1, _, _ = _ejemplos()
    try:
        estimar_siniestro(a1, contexto)
    except Exception as e:  # noqa: BLE001 - se comprueba el mensaje
        assert campo in str(e), f"el error no nombra «{campo}»: {e}"
        return
    raise AssertionError(f"no se lanzo excepcion con {campo} invalido")


def probar_ac010_contexto_invalido():
    """AC-010: poliza, vehiculo, rol, edad o km invalidos, o un campo
    obligatorio ausente -> excepcion que nombra el campo."""
    _, ctx, _ = _ejemplos()
    _espera_error(dict(ctx, poliza_id="P-NO-EXISTE"), "poliza_id")
    _espera_error(dict(ctx, vehiculo_id="V999"), "vehiculo_id")
    _espera_error(dict(ctx, rol="conductor"), "rol")
    _espera_error(dict(ctx, edad_anios="tres"), "edad_anios")
    _espera_error(dict(ctx, km=-5), "km")
    for campo in ("vehiculo_id", "region", "tipo_taller", "acabado", "tipo_pieza", "rol", "edad_anios", "km"):
        incompleto = dict(ctx)
        del incompleto[campo]
        _espera_error(incompleto, campo)
    sin_poliza = dict(ctx)
    del sin_poliza["poliza_id"]
    _espera_error(sin_poliza, "poliza_id")


def probar_ac010_paquete_ausente():
    """AC-010: sin piia2_paquete_datos/ el modulo falla al importar con un
    mensaje que indica la ruta esperada."""
    with tempfile.TemporaryDirectory() as tmp:
        raiz = Path(tmp)
        (raiz / ".git").mkdir()
        shutil.copy(AQUI / "costes_y_cobertura.py", raiz / "costes_y_cobertura.py")
        r = subprocess.run([sys.executable, "-c", "import costes_y_cobertura"], cwd=raiz,
                           capture_output=True, text=True)
        assert r.returncode != 0, "el modulo importo sin el paquete"
        esperado = str(raiz.resolve() / "piia2_paquete_datos")
        assert "piia2_paquete_datos" in r.stderr and (esperado in r.stderr or str(raiz / "piia2_paquete_datos") in r.stderr), \
            f"el error no indica la ruta esperada:\n{r.stderr[-400:]}"


PRUEBAS = [
    probar_ac001_contrato_del_ejemplo,
    probar_ac002_reparto_de_hallazgos,
    probar_ac003_tercero_perjudicado,
    probar_ac004_poliza_sin_colision,
    probar_ac005_perdida_total_v14,
    probar_ac006_lunas_con_limite,
    probar_ac007_escenario_vacio,
    probar_ac008_determinista_sin_red,
    probar_ac010_contexto_invalido,
    probar_ac010_paquete_ausente,
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
    print(f"\n{len(PRUEBAS) - fallos} de {len(PRUEBAS)} pruebas en verde (modulo: {Path(costes_y_cobertura.__file__).name})")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
