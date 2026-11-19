"""Pruebas del script de la Parte 1 de la evaluacion de punta a punta (Issue #46).

Cada prueba cita su criterio del plan v1:
https://github.com/lvckss/piia2-26/issues/46#issuecomment-6985712887 (AC-0XX).
Usa las salidas reales de ejemplos_contrato/agente1_real/ y el paquete de la
empresa (piia2_paquete_datos/, fuera de git). No necesita API Key ni red.

Se ejecuta desde esta carpeta:  python probar_evaluar_informes.py
Ejecuta todas las pruebas, informa de cada una y termina con codigo 1 si
alguna falla.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

import evaluar_informes
import generar_informes_reales as generador

HOY = "2026-11-12"
AQUI = Path(__file__).resolve().parent
REALES = generador.SALIDAS_REALES
PLAN = "https://github.com/lvckss/piia2-26/issues/46#issuecomment-6985712887"


def _casos() -> list[dict]:
    salidas = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(REALES.glob("*.json"))]
    return generador.preparar_casos(salidas, generador.leer_siniestros())


def _caso(image_id: int) -> dict:
    return next(c for c in _casos() if c["image_id"] == image_id)


def _salida2(caso: dict) -> dict:
    return evaluar_informes.estimar_siniestro(caso["salida_agente1"], caso["contexto"])


def _informe(caso: dict, salida2: dict) -> str:
    return evaluar_informes.generar_informe(caso["salida_agente1"], salida2, hoy=HOY)


# --- plan #46, AC-002 --------------------------------------------------------
def probar_ac002_reparto_de_hallazgos_y_cifras():
    """AC-002: el resumen de un caso cuenta confirmados, pendientes (los que
    solo entran en el escenario con pendientes) y fuera del coste como el
    Agente 2, y `cifras_ajenas` esta vacia si el informe solo usa cifras suyas."""
    for image_id in (381, 1248):
        caso = _caso(image_id)
        salida2 = _salida2(caso)
        r = evaluar_informes.resumir_caso(caso["salida_agente1"], salida2, _informe(caso, salida2))
        conf = salida2["escenarios"]["confirmados"]["hallazgos_incluidos"]
        pend = salida2["escenarios"]["con_pendientes"]["hallazgos_incluidos"]
        assert r["image_id"] == image_id
        assert r["confirmados"] == len(conf), r
        assert r["pendientes"] == len(pend) - len(conf), r
        assert r["fuera_del_coste"] == len(salida2["hallazgos_fuera_del_coste"]), r
        assert r["motivos_fuera"] == _contar(h["motivo"] for h in salida2["hallazgos_fuera_del_coste"]), r
        assert r["cifras_ajenas"] == [], r


def _contar(valores) -> dict:
    cuentas: dict = {}
    for v in valores:
        cuentas[v] = cuentas.get(v, 0) + 1
    return cuentas


def probar_ac002_cifra_ajena_se_detecta():
    """AC-002: un importe del informe que no sale del Agente 2 queda en la lista."""
    caso = _caso(381)
    salida2 = _salida2(caso)
    md = _informe(caso, salida2) + "\nTotal estimado: 98.765,43 €\n"
    r = evaluar_informes.resumir_caso(caso["salida_agente1"], salida2, md)
    assert 98765.43 in r["cifras_ajenas"], r


def probar_ac002_hallazgos_por_equivalencia():
    """AC-002: con las 30 salidas versionadas, solo 381 y 1248 tienen un
    hallazgo presupuestado con la regla de su equivalente (#88)."""
    por_imagen = {}
    for caso in _casos():
        salida2 = _salida2(caso)
        r = evaluar_informes.resumir_caso(caso["salida_agente1"], salida2, _informe(caso, salida2))
        por_imagen[caso["image_id"]] = r["por_equivalencia"]
    con = {i: n for i, n in por_imagen.items() if n}
    assert con == {381: 1, 1248: 1}, con


def probar_ac002_rag_y_justificaciones_ausentes_no_se_inventan():
    """AC-002: sin `diagnostico_rag` ni `justificaciones` (solo costes) el
    resumen dice `None`: no disponible, no cero."""
    caso = _caso(381)
    salida2 = _salida2(caso)
    r = evaluar_informes.resumir_caso(caso["salida_agente1"], salida2, _informe(caso, salida2))
    assert r["rag"] is None and r["justificaciones"] is None, r


def probar_ac002_rag_y_justificaciones_se_cuentan_por_estado():
    """AC-002: temas del RAG con pasajes, sin pasajes y con error; justificaciones
    por estado y los motivos de las que no se generaron."""
    caso = _caso(381)
    salida2 = _salida2(caso)
    salida2["diagnostico_rag"] = {"estado": "parcial", "consultas": [
        {"tema": "A", "estado": "recuperadas", "fuentes": ["f#1"], "incidencias": []},
        {"tema": "B", "estado": "recuperadas", "fuentes": ["f#2"], "incidencias": []},
        {"tema": "C", "estado": "sin_resultados", "fuentes": [], "incidencias": []},
        {"tema": "D", "estado": "error", "fuentes": [], "incidencias": [{"codigo": "BD_NO_DISPONIBLE"}]},
    ]}
    salida2["justificaciones"] = [
        {"tema": "A", "estado": "generada", "texto": "t", "citas": []},
        {"tema": "B", "estado": "descartada", "motivo": "cita inexistente"},
        {"tema": "C", "estado": "no_generada", "motivo": "sin clave"},
        {"tema": "D", "estado": "no_generada", "motivo": "sin clave"},
    ]
    r = evaluar_informes.resumir_caso(caso["salida_agente1"], salida2, "# informe sin cifras")
    assert r["rag"] == {"con_pasajes": 2, "sin_pasajes": 1, "con_error": 1}, r["rag"]
    assert r["justificaciones"] == {"generada": 1, "descartada": 1, "no_generada": 2,
                                    "motivos": {"cita inexistente": 1, "sin clave": 2}}, r["justificaciones"]


def probar_ac002_tabla_con_todas_las_comprobaciones():
    """AC-002: la tabla del resumen tiene una fila por caso y los totales de
    informes, cifras ajenas, reparto, equivalencias, RAG, justificaciones y
    repeticion. Con costes solo, el RAG y las justificaciones constan como no disponibles."""
    with tempfile.TemporaryDirectory() as tmp:
        codigo = evaluar_informes.evaluar(REALES, tmp, hoy=HOY, repetir=True)
        assert codigo == 0, codigo
        md = (Path(tmp) / "resumen_evaluacion.md").read_text(encoding="utf-8")
        filas = [f for f in md.splitlines() if f.startswith("| 0")]
        assert len(filas) == 30, len(filas)
        for texto in ("Informes generados: 30 de 30", "Con cifras que no salen del Agente 2: 0",
                      "Hallazgos por equivalencia (#88): 2", "RAG: no disponible",
                      "Justificaciones (#97): no disponible",
                      "Repetición con la misma entrada: 30 de 30 informes iguales"):
            assert texto in md, (texto, md[:900])
        assert len([p for p in Path(tmp).glob("0*.md")]) == 30


# --- plan #46, AC-001 y AC-002 (repeticion y errores) -------------------------
def probar_ac002_repeticion_senala_los_informes_que_cambian():
    """AC-002: si repetir la ejecucion con la misma entrada cambia un informe,
    el resumen lo lista por image_id."""
    llamadas = {"n": 0}

    def variable(salida_agente1, contexto):
        salida2 = evaluar_informes.estimar_siniestro(salida_agente1, contexto)
        if salida_agente1["image_id"] == 381:
            llamadas["n"] += 1
            salida2["normativa"] = [{"tema": "T", "extracto": f"texto distinto {llamadas['n']}", "fuente": "f#1"}]
        return salida2

    with tempfile.TemporaryDirectory() as tmp:
        codigo = evaluar_informes.evaluar(REALES, tmp, hoy=HOY, repetir=True, agente2=variable)
        md = (Path(tmp) / "resumen_evaluacion.md").read_text(encoding="utf-8")
        assert "Repetición con la misma entrada: 29 de 30 informes iguales" in md, md[:900]
        assert "Cambian: 000381" in md, md
        assert codigo == 0, codigo


def probar_ac001_un_error_se_registra_y_no_detiene_a_los_demas():
    """AC-001: un fallo tecnico de un caso queda listado con su causa, los
    demas informes se generan y el codigo es 1."""
    def falla_uno(salida_agente1, contexto):
        if salida_agente1["image_id"] == 381:
            raise ValueError("fallo de prueba en el Agente 2")
        return evaluar_informes.estimar_siniestro(salida_agente1, contexto)

    with tempfile.TemporaryDirectory() as tmp:
        codigo = evaluar_informes.evaluar(REALES, tmp, hoy=HOY, agente2=falla_uno)
        md = (Path(tmp) / "resumen_evaluacion.md").read_text(encoding="utf-8")
        assert codigo == 1, codigo
        assert "Informes generados: 29 de 30" in md, md[:600]
        assert "000381" in md and "fallo de prueba en el Agente 2" in md
        assert not (Path(tmp) / "000381.md").exists()
        assert len(list(Path(tmp).glob("0*.md"))) == 29


def probar_ac001_entrada_inexistente_o_vacia():
    """AC-001: sin salidas del Agente 1 el comando falla con codigo 2 y la ruta."""
    with tempfile.TemporaryDirectory() as tmp:
        for carpeta in (Path(tmp) / "no_existe", Path(tmp)):
            r = subprocess.run([sys.executable, "evaluar_informes.py", "--salidas", str(carpeta),
                                "--destino", str(Path(tmp) / "out")], cwd=AQUI, capture_output=True, text=True)
            assert r.returncode == 2, (r.returncode, r.stderr[-300:])
            assert str(carpeta) in r.stderr, r.stderr[-300:]


# --- plan #46, AC-007 (comando) -----------------------------------------------
def probar_ac007_comando_documentado():
    """AC-007: el comando del README genera la evaluacion de las 30 en una
    carpeta indicada y termina con codigo 0."""
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run([sys.executable, "evaluar_informes.py", "--destino", tmp, "--hoy", HOY, "--repetir"],
                           cwd=AQUI, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout[-400:] + r.stderr[-400:]
        assert (Path(tmp) / "resumen_evaluacion.md").is_file()
        assert len(list(Path(tmp).glob("0*.md"))) == 30


def probar_ac007_modo_completo_sin_agente2_da_error_claro():
    """AC-007: `--completo` pide el `agente2()` con RAG (#32); si no se puede
    importar, el comando falla con codigo 2 y lo dice, en lugar de evaluar solo
    costes sin avisar."""
    sys.modules["agente2"] = None  # simula que el modulo no esta disponible
    try:
        try:
            evaluar_informes.cargar_agente2_completo()
        except ImportError as e:
            assert "agente2" in str(e), e
        else:
            raise AssertionError("debia lanzar ImportError")
    finally:
        del sys.modules["agente2"]


def probar_ac007_modo_completo_usa_el_agente2_de_la_composicion():
    """AC-007: con `agente2()` disponible, `--completo` evalua con el."""
    import types

    falso = types.ModuleType("agente2")
    falso.agente2 = lambda a1, ctx: {**evaluar_informes.estimar_siniestro(a1, ctx),
                                     "diagnostico_rag": {"estado": "recuperadas", "consultas": []},
                                     "justificaciones": []}
    sys.modules["agente2"] = falso
    try:
        fn = evaluar_informes.cargar_agente2_completo()
        caso = _caso(381)
        assert "diagnostico_rag" in fn(caso["salida_agente1"], caso["contexto"])
    finally:
        del sys.modules["agente2"]


PRUEBAS = [
    probar_ac002_reparto_de_hallazgos_y_cifras,
    probar_ac002_cifra_ajena_se_detecta,
    probar_ac002_hallazgos_por_equivalencia,
    probar_ac002_rag_y_justificaciones_ausentes_no_se_inventan,
    probar_ac002_rag_y_justificaciones_se_cuentan_por_estado,
    probar_ac002_tabla_con_todas_las_comprobaciones,
    probar_ac002_repeticion_senala_los_informes_que_cambian,
    probar_ac001_un_error_se_registra_y_no_detiene_a_los_demas,
    probar_ac001_entrada_inexistente_o_vacia,
    probar_ac007_comando_documentado,
    probar_ac007_modo_completo_sin_agente2_da_error_claro,
    probar_ac007_modo_completo_usa_el_agente2_de_la_composicion,
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
    print(f"\n{len(PRUEBAS) - fallos} de {len(PRUEBAS)} pruebas en verde (modulo: evaluar_informes.py)")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
