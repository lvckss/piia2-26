"""Pruebas de `tabla_umbrales.py` (Issue #44, plan v1.3, AC-003 y AC-004). Sin API ni red.

Referencia de los AC: https://github.com/lvckss/piia2-26/issues/44#issuecomment-6468549944 (plan v1.3),
que modifica AC-009 y conserva AC-003 del plan v1.2 (comentario 6449733613).

Ejecutar desde esta carpeta:  python probar_tabla_umbrales_stub.py
"""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
from pathlib import Path

from confianza import CATEGORY_REVIEW_THRESHOLD
from etiquetado import intervalo_wilson
from tabla_umbrales import (
    TRAMOS,
    UMBRALES,
    antes_despues,
    comparar_is_tp,
    filas_por_tramo,
    filas_por_umbral,
    filas_rechazados,
    formatear,
    formatear_criterio,
    leer_is_tp,
    main,
    tramo_de_score,
    umbrales_por_criterio,
)

RAIZ = Path(__file__).resolve().parents[5]


def h(finding_id: str, clase: str, score: float, veredicto: str = "confirmado", pieza: str | None = "PARAG_DEL", regla: bool | None = True) -> dict:
    return {"finding_id": finding_id, "category": clase, "score": score, "vision_verdict": veredicto, "pieza_id": pieza, "regla_coste_aplicable": regla}


# Datos de la prueba, con las cifras calculadas a mano. `scratch` (umbral actual 0,7):
#   candidatos a nivel firme (confirmado, con pieza y con regla de coste): s1, s2, s3, s4, s5, s6, s7, s8 y s15
#   fuera: s9 (sin pieza), s10 (sin regla), s11 a s13 (rechazados) y s14 (incierto)
HALLAZGOS = [
    h("1-1", "scratch", 0.35), h("1-2", "scratch", 0.38), h("1-3", "scratch", 0.45), h("1-4", "scratch", 0.47),
    h("2-1", "scratch", 0.55), h("2-2", "scratch", 0.65), h("2-3", "scratch", 0.72), h("2-4", "scratch", 0.95),
    h("3-1", "scratch", 0.60, pieza=None), h("3-2", "scratch", 0.61, regla=False),
    h("3-3", "scratch", 0.62, "rechazado", None, None), h("3-4", "scratch", 0.63, "rechazado", None, None), h("3-5", "scratch", 0.64, "rechazado", None, None),
    h("3-6", "scratch", 0.66, "incierto", None, None), h("4-1", "scratch", 0.37),
    h("5-1", "lamp broken", 0.90),
    h("6-1", "crack", 0.70), h("6-2", "crack", 0.50),  # justo en un umbral de la rejilla: con >= entran
]
SALIDAS = [{"image_id": 1, "resumen_filtro_previo": {}, "findings": HALLAZGOS}]
ETIQUETAS = {
    "1-1": "si", "1-2": "otra", "1-3": "no", "1-4": "dudo", "2-1": "si", "2-2": "si", "2-3": "si", "2-4": "si",
    "3-1": "si", "3-2": "si", "3-3": "otra", "3-4": "no", "3-5": "si", "3-6": "si", "5-1": "no", "6-1": "si", "6-2": "otra",  # 4-1 sin etiqueta a proposito
}
IS_TP = {"1-1": False, "1-2": False, "1-3": True, "2-1": True, "2-3": False, "2-4": True, "5-1": False}  # 1-4, 2-2 y 4-1 sin dato


def buscar(filas: list[dict], **claves) -> dict:
    hallazgo = [f for f in filas if all(f.get(k) == v for k, v in claves.items())]
    assert len(hallazgo) == 1, (claves, len(hallazgo))
    return hallazgo[0]


def probar_tramos() -> None:
    """AC-003: los tramos son de 0,1 y estan alineados con la rejilla de umbrales (0,3 a 0,9); el 0,3 entra, el 1,0 cae en el ultimo."""
    assert len(TRAMOS) == 7 and TRAMOS[0] == (0.3, 0.4) and TRAMOS[-1] == (0.9, 1.0)
    assert tramo_de_score(0.30) == 0 and tramo_de_score(0.3999) == 0 and tramo_de_score(0.40) == 1
    assert tramo_de_score(0.95) == 6 and tramo_de_score(1.0) == 6
    assert tramo_de_score(0.29) is None and tramo_de_score(1.01) is None
    print("tramos ok")


def probar_filas_por_tramo() -> None:
    """AC-003: por clase y tramo, solo los candidatos a nivel firme; los dudo y los sin etiquetar quedan fuera del denominador;
    precision de «daño real» (si u otra) y de la clase (si), con Wilson y marca de no concluyente por debajo de 5 casos."""
    filas = filas_por_tramo(SALIDAS, ETIQUETAS)
    assert len(filas) == 6 * 8, len(filas)  # 6 clases x (7 tramos + total)
    f = buscar(filas, clase="scratch", tramo="0,3-0,4")
    assert (f["candidatos"], f["sin_etiqueta"], f["dudo"], f["decididos"], f["si"], f["otra"], f["no"]) == (3, 1, 0, 2, 1, 1, 0), f
    assert f["precision_dano_real"] == 1.0 and f["precision_clase"] == 0.5 and f["concluyente"] is False
    assert f["intervalo_dano_real"] == intervalo_wilson(2, 2) and f["intervalo_clase"] == intervalo_wilson(1, 2)
    f = buscar(filas, clase="scratch", tramo="0,4-0,5")
    assert (f["candidatos"], f["dudo"], f["decididos"], f["no"]) == (2, 1, 1, 1) and f["precision_dano_real"] == 0.0
    t = buscar(filas, clase="scratch", tramo="total")
    assert (t["candidatos"], t["sin_etiqueta"], t["dudo"], t["decididos"], t["si"], t["otra"], t["no"]) == (9, 1, 1, 7, 5, 1, 1), t
    assert t["precision_dano_real"] == 6 / 7 and t["precision_clase"] == 5 / 7 and t["concluyente"] is True
    vacia = buscar(filas, clase="dent", tramo="total")
    assert vacia["candidatos"] == 0 and vacia["decididos"] == 0 and vacia["precision_dano_real"] is None and vacia["concluyente"] is False
    assert buscar(filas, clase="crack", tramo="0,7-0,8")["si"] == 1 and buscar(filas, clase="crack", tramo="0,5-0,6")["otra"] == 1  # 0,70 y 0,50 caen en el tramo que empieza ahi
    solo_lampara = buscar(filas, clase="lamp broken", tramo="0,9-1,0")
    assert solo_lampara["decididos"] == 1 and solo_lampara["no"] == 1 and solo_lampara["precision_dano_real"] == 0.0
    # los rechazados, los inciertos y los candidatos sin pieza o sin regla no entran en ninguna celda de candidatos
    assert sum(f["candidatos"] for f in filas if f["tramo"] == "total") == 12
    print("filas por tramo ok")


def probar_filas_por_umbral() -> None:
    """AC-004: tabla acumulada (score >= umbral) por clase para la rejilla 0,3 a 0,9, con el umbral actual marcado y lo que
    cambia respecto a el."""
    filas = filas_por_umbral(SALIDAS, ETIQUETAS)
    assert len(filas) == 6 * 7
    esperado = {0.3: (9, 7, 6), 0.4: (6, 5, 4), 0.5: (4, 4, 4), 0.6: (3, 3, 3), 0.7: (2, 2, 2), 0.8: (1, 1, 1), 0.9: (1, 1, 1)}
    for u, (cand, dec, real) in esperado.items():
        f = buscar(filas, clase="scratch", umbral=u)
        assert (f["candidatos"], f["decididos"], round(f["precision_dano_real"] * f["decididos"])) == (cand, dec, real), (u, f)
    assert [f["umbral"] for f in filas if f["clase"] == "scratch" and f["actual"]] == [0.7]
    assert [f["umbral"] for f in filas if f["clase"] == "lamp broken" and f["actual"]] == [0.6]
    f03 = buscar(filas, clase="scratch", umbral=0.3)
    assert f03["frente_al_actual"] == 9 - 2, f03  # +7 candidatos que entrarian respecto al umbral actual 0,7
    assert buscar(filas, clase="scratch", umbral=0.7)["frente_al_actual"] == 0
    assert buscar(filas, clase="scratch", umbral=0.9)["frente_al_actual"] == 1 - 2
    # un score justo en el umbral cuenta (score >= umbral, como en decidir_tier)
    assert buscar(filas, clase="crack", umbral=0.7)["candidatos"] == 1 and buscar(filas, clase="crack", umbral=0.7)["actual"] is True
    assert buscar(filas, clase="crack", umbral=0.5)["candidatos"] == 2 and buscar(filas, clase="crack", umbral=0.8)["candidatos"] == 0
    assert buscar(filas, clase="crack", umbral=0.5)["frente_al_actual"] == 1 and buscar(filas, clase="crack", umbral=0.7)["frente_al_actual"] == 0  # el 0,70 ya cuenta en el actual
    # con 4 casos decididos no basta (no concluyente); con 5, si
    assert buscar(filas, clase="scratch", umbral=0.5)["concluyente"] is False and buscar(filas, clase="scratch", umbral=0.4)["concluyente"] is True
    print("filas por umbral ok")


def probar_rechazados_e_is_tp() -> None:
    """AC-003: lo que la vision rechaza y el juez ve como daño; y cuantos confirmados que PIIA-1 daba por fallo eran daño real."""
    r = buscar(filas_rechazados(SALIDAS, ETIQUETAS), clase="scratch")
    assert (r["rechazados"], r["sin_etiqueta"], r["dudo"], r["decididos"], r["si"], r["otra"], r["no"]) == (3, 0, 0, 3, 1, 1, 1), r
    assert r["precision_dano_real"] == 2 / 3 and r["intervalo_dano_real"] == intervalo_wilson(2, 3)
    assert buscar(filas_rechazados(SALIDAS, ETIQUETAS), clase="dent")["rechazados"] == 0
    c = buscar(comparar_is_tp(SALIDAS, ETIQUETAS, IS_TP), clase="scratch")
    # candidatos con is_true_positive falso: 1-1 (si), 1-2 (otra), 2-3 (si); con verdadero: 1-3, 2-1, 2-4; sin dato: 1-4, 2-2, 4-1
    assert (c["is_tp_falso"], c["de_ellos_si"], c["de_ellos_otra"], c["de_ellos_no"], c["de_ellos_dudo"]) == (3, 2, 1, 0, 0), c
    assert c["is_tp_verdadero"] == 3 and c["sin_dato_is_tp"] == 3, c
    assert buscar(comparar_is_tp(SALIDAS, ETIQUETAS, IS_TP), clase="lamp broken")["is_tp_falso"] == 1
    print("rechazados e is_true_positive ok")


def probar_formato() -> None:
    """AC-003 + plan v1.3: el informe dice que son etiquetas de un modelo, marca lo no concluyente y lleva las cuatro secciones."""
    texto = formatear(
        filas_por_tramo(SALIDAS, ETIQUETAS), filas_por_umbral(SALIDAS, ETIQUETAS), filas_rechazados(SALIDAS, ETIQUETAS),
        comparar_is_tp(SALIDAS, ETIQUETAS, IS_TP), {"modelo": "modelo-falso", "esfuerzo": "high"},
    )
    for esperado in ("modelo-falso", "high", "etiquetas de un modelo", "no verdad humana", "no concluyente", "0,3-0,4", "Umbral", "Rechazados", "is_true_positive"):
        assert esperado in texto, esperado
    assert "100 %" in texto and "86 %" in texto  # scratch total: 6/7 daño real
    lineas_tabla = [l for l in texto.splitlines() if l.startswith("|")]
    assert len({l.count("|") for l in lineas_tabla if "---" not in l}) >= 1 and all(l.rstrip().endswith("|") for l in lineas_tabla)
    # la marca de no concluyente va en la celda concreta (no basta con que la leyenda la mencione)
    corta = next(l for l in lineas_tabla if l.startswith("| scratch | 0,3-0,4 |"))
    assert corta.rstrip().endswith("no concluyente |"), corta
    assert "no concluyente" not in next(l for l in lineas_tabla if l.startswith("| scratch | total |"))
    print("formato ok")


def escribir_entradas(base: Path) -> tuple[Path, Path, Path, Path]:
    salidas = base / "salidas"
    export = base / "export"
    salidas.mkdir()
    export.mkdir()
    por_imagen: dict[int, list[dict]] = {}
    for hallazgo in HALLAZGOS:
        por_imagen.setdefault(int(hallazgo["finding_id"].split("-")[0]), []).append(hallazgo)
    for imagen, hallazgos in por_imagen.items():
        (salidas / f"{imagen:06d}.json").write_text(json.dumps({"image_id": imagen, "resumen_filtro_previo": {}, "findings": hallazgos}), encoding="utf-8")
        predicciones = [
            {"instance_index": int(x["finding_id"].split("-")[1]), "damage_class": x["category"], "score": x["score"], **({"is_true_positive": IS_TP[x["finding_id"]]} if x["finding_id"] in IS_TP else {})}
            for x in hallazgos
        ]
        (export / f"{imagen:06d}.json").write_text(json.dumps({"image_id": imagen, "predictions": predicciones}), encoding="utf-8")
    (salidas / "resumen_lote.json").write_text("{}", encoding="utf-8")
    etiquetas = base / "etiquetas_juez.csv"
    etiquetas.write_text("finding_id,etiqueta\n" + "".join(f"{i},{e}\n" for i, e in ETIQUETAS.items()), encoding="utf-8")
    resumen = base / "resumen_juez.json"
    resumen.write_text(json.dumps({"modelo": "modelo-falso", "esfuerzo": "high", "prompt_sha256": "ab" * 32}), encoding="utf-8")
    return salidas, export, etiquetas, resumen


def probar_cli() -> None:
    """La linea de comandos lee salidas, etiquetas, export y resumen; escribe el informe; y rechaza ids que no existen."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        salidas, export, etiquetas, resumen = escribir_entradas(base)
        assert leer_is_tp(export) == {**{k: v for k, v in IS_TP.items()}}
        informe = base / "informe" / "tabla_umbrales.md"
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            assert main(["--salidas", str(salidas), "--etiquetas", str(etiquetas), "--export", str(export), "--resumen", str(resumen), "--salida", str(informe)]) == 0
        texto = informe.read_text(encoding="utf-8")
        assert "modelo-falso" in texto and "abababab" in texto and "scratch" in texto and "is_true_positive" in texto
        assert "tabla_umbrales.md" in out.getvalue()
        sin_export = io.StringIO()
        with contextlib.redirect_stdout(sin_export):
            assert main(["--salidas", str(salidas), "--etiquetas", str(etiquetas)]) == 0
        assert "is_true_positive" not in sin_export.getvalue() and "scratch" in sin_export.getvalue()
        malas = base / "malas.csv"
        malas.write_text("finding_id,etiqueta\n99-9,si\n", encoding="utf-8")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            assert main(["--salidas", str(salidas), "--etiquetas", str(malas)]) == 2
        assert "99-9" in err.getvalue() and "ERROR" in err.getvalue()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            assert main(["--salidas", str(base / "no_existe"), "--etiquetas", str(etiquetas)]) == 2
        assert "ERROR" in err.getvalue()
    print("linea de comandos ok")


def probar_con_datos_reales() -> None:
    """Con las salidas reales (fuera de git) y las etiquetas del juez, las cifras coinciden con las calculadas por separado el
    2026-10-28 (1.558 candidatos; scratch con score >= 0,7: 222 candidatos). Se salta si no estan."""
    sal = RAIZ / "piia2_detecciones" / "salida_agente1_500"
    jue = RAIZ / "piia2_detecciones" / "juez" / "gpt-6.1-terra" / "etiquetas_juez.csv"
    exp = RAIZ / "piia2_detecciones" / "baseline_500"
    if not (sal.is_dir() and jue.is_file() and exp.is_dir()):
        print("(salidas, export o etiquetas del juez reales no encontrados: se salta la comprobacion con datos reales)")
        return
    from etiquetado import _leer_salidas, leer_etiquetas

    salidas, etiquetas = _leer_salidas(sal), leer_etiquetas(jue)
    filas = filas_por_tramo(salidas, etiquetas)
    assert sum(f["candidatos"] for f in filas if f["tramo"] == "total") == 1558
    u = buscar(filas_por_umbral(salidas, etiquetas), clase="scratch", umbral=0.7)
    assert u["candidatos"] == 222 and u["actual"] is True
    comp = comparar_is_tp(salidas, etiquetas, leer_is_tp(exp))
    assert sum(c["is_tp_falso"] + c["is_tp_verdadero"] + c["sin_dato_is_tp"] for c in comp) == 1558
    print("datos reales ok: 1.558 candidatos, scratch a 0,7 = 222, is_true_positive de los 1.558 cuadra")


def construir(*grupos: tuple[str, float, dict[str, int]]) -> tuple[list[dict], dict[str, str]]:
    """Hallazgos candidatos (confirmados, con pieza y con regla) y etiquetas del juez a partir de grupos
    `(clase, score, {etiqueta: cantidad})`; la etiqueta `sin` es un candidato sin etiquetar."""
    hallazgos, etiquetas, n = [], {}, 0
    for clase, score, cuentas in grupos:
        for etiqueta, cantidad in cuentas.items():
            for _ in range(cantidad):
                n += 1
                hallazgos.append(h(f"{n}-1", clase, score))
                if etiqueta != "sin":
                    etiquetas[f"{n}-1"] = etiqueta
    return [{"image_id": 1, "resumen_filtro_previo": {}, "findings": hallazgos}], etiquetas


def escenario_criterio() -> tuple[list[dict], dict[str, str]]:
    """Plan v1.4 (D-6). Con el limite inferior de Wilson al 95 %, n casos todos «daño real» dan n / (n + 3,84): 60 → 94,0 %,
    80 → 95,4 %, 100 → 96,3 %, 190 → 98,0 %. Umbral actual de dent, scratch y crack: 0,7; del resto: 0,6.
      dent         100 decididos, todos daño real (70 % de clase correcta) desde 0,3  → sale 0,3
      scratch      con los de 0,35 y 0,45 hay `no`; desde 0,5 son 190 de 190 reales   → sale 0,5 (los valores mas altos tambien cumplen)
      crack        60 de 60 reales, a 0,8: el limite inferior es 94,0 %                 → se mantiene 0,7
      glass shatter 80 reales + 30 `dudo` + 30 sin etiqueta: solo cuentan los 80         → sale 0,3
      lamp broken  4 reales                                                              → se mantiene 0,6
      tire flat    ningun candidato                                                      → se mantiene 0,6"""
    return construir(
        ("dent", 0.35, {"si": 50, "otra": 30}), ("dent", 0.75, {"si": 20}),
        ("scratch", 0.35, {"si": 20, "no": 20}), ("scratch", 0.45, {"si": 10, "no": 10}), ("scratch", 0.55, {"si": 90}), ("scratch", 0.75, {"si": 100}),
        ("crack", 0.80, {"si": 60}),
        ("glass shatter", 0.35, {"si": 80, "dudo": 30, "sin": 30}),
        ("lamp broken", 0.35, {"si": 4}),
    )


def umbrales_de(filas: list[dict]) -> dict[str, float]:
    return {f["clase"]: f["umbral"] for f in filas}


def probar_criterio_el_valor_mas_bajo() -> None:
    """AC-004 (plan v1.4, D-6): por clase, el valor MAS BAJO de la rejilla cuyo limite inferior de Wilson del «daño real» (si u
    otra) es al menos el 95 %; si ninguno llega, se mantiene el actual."""
    salidas, etiquetas = escenario_criterio()
    filas = umbrales_por_criterio(salidas, etiquetas)
    assert [f["clase"] for f in filas] == list(CATEGORY_REVIEW_THRESHOLD)
    assert umbrales_de(filas) == {"dent": 0.3, "scratch": 0.5, "crack": 0.7, "lamp broken": 0.6, "glass shatter": 0.3, "tire flat": 0.6}, umbrales_de(filas)
    assert {f["clase"]: (f["motivo"], f["cambia"]) for f in filas} == {
        "dent": ("criterio", True), "scratch": ("criterio", True), "crack": ("se mantiene", False),
        "lamp broken": ("se mantiene", False), "glass shatter": ("criterio", True), "tire flat": ("se mantiene", False),
    }
    # scratch: a 0,6 (100 de 100 reales) tambien se cumple el criterio, pero se elige el mas bajo (0,5); a 0,4 (200 de 210) todavia no
    por_umbral = filas_por_umbral(salidas, etiquetas)
    assert buscar(por_umbral, clase="scratch", umbral=0.6)["intervalo_dano_real"][0] >= 0.95
    assert buscar(por_umbral, clase="scratch", umbral=0.4)["intervalo_dano_real"][0] < 0.95
    # lo que se informa es lo medido en el umbral elegido
    dent = buscar(filas, clase="dent")
    assert (dent["actual"], dent["candidatos"], dent["decididos"]) == (0.7, 100, 100)
    assert dent["precision_dano_real"] == 1.0 and dent["precision_clase"] == 0.7  # se elige por «daño real», no por clase correcta
    assert dent["limite_inferior"] == intervalo_wilson(100, 100)[0] and dent["limite_inferior"] >= 0.95
    # en lo que se mantiene, lo medido es en el umbral actual
    crack = buscar(filas, clase="crack")
    assert (crack["umbral"], crack["candidatos"], crack["decididos"]) == (0.7, 60, 60) and crack["limite_inferior"] < 0.95
    assert buscar(filas, clase="tire flat")["decididos"] == 0 and buscar(filas, clase="tire flat")["limite_inferior"] is None
    print("criterio: el valor mas bajo ok")


def probar_criterio_dudo_y_sin_etiqueta_fuera_del_denominador() -> None:
    """AC-004 + AC-005: los `dudo` y los hallazgos sin etiqueta no cuentan en el denominador (si los `dudo` fueran `no`, esta
    clase no llegaria al 95 %)."""
    glass = buscar(umbrales_por_criterio(*escenario_criterio()), clase="glass shatter")
    assert (glass["umbral"], glass["candidatos"], glass["decididos"], glass["dudo"], glass["sin_etiqueta"]) == (0.3, 140, 80, 30, 30), glass
    assert intervalo_wilson(80, 110)[0] < 0.95 <= glass["limite_inferior"]
    print("criterio: dudo y sin etiqueta fuera del denominador ok")


def probar_criterio_minimo_configurable_y_minimo_de_casos() -> None:
    """AC-004: el minimo del limite inferior se puede cambiar (el plan v1.4 lo compara con 90 %); y con menos de 5 casos decididos
    no se acepta ningun umbral aunque el limite inferior supere el minimo."""
    salidas, etiquetas = escenario_criterio()
    assert umbrales_de(umbrales_por_criterio(salidas, etiquetas))["crack"] == 0.7  # 94,0 % < 95 %
    assert umbrales_de(umbrales_por_criterio(salidas, etiquetas, minimo=0.90))["crack"] == 0.3
    assert umbrales_de(umbrales_por_criterio(salidas, etiquetas, minimo=0.90))["scratch"] == 0.4  # a 0,4: 200 de 210 reales, limite inferior 91,5 %; a 0,3 solo 83,4 %
    cuatro = construir(("lamp broken", 0.90, {"si": 4}))
    cinco = construir(("lamp broken", 0.90, {"si": 5}))
    assert intervalo_wilson(4, 4)[0] > 0.5  # el limite inferior ya supera el 50 %, pero con 4 casos no basta
    assert buscar(umbrales_por_criterio(*cuatro, minimo=0.5), clase="lamp broken")["motivo"] == "se mantiene"
    assert buscar(umbrales_por_criterio(*cinco, minimo=0.5), clase="lamp broken")["umbral"] == 0.3
    print("criterio: minimo configurable y minimo de casos ok")


def probar_criterio_rejilla_y_umbrales_actuales() -> None:
    """AC-004: todo valor propuesto esta en la rejilla 0,3 a 0,9 o es el actual que se mantiene; se pueden pasar otros umbrales
    actuales (incluso fuera de la rejilla) y la tabla de `confianza.py` no se toca."""
    antes = dict(CATEGORY_REVIEW_THRESHOLD)
    salidas, etiquetas = escenario_criterio()
    for f in umbrales_por_criterio(salidas, etiquetas):
        assert f["umbral"] in UMBRALES or f["motivo"] == "se mantiene", f
    con_otros = umbrales_por_criterio(salidas, etiquetas, actuales={**CATEGORY_REVIEW_THRESHOLD, "crack": 0.8})
    assert buscar(con_otros, clase="crack")["umbral"] == 0.8 and buscar(con_otros, clase="crack")["actual"] == 0.8
    fuera = umbrales_por_criterio(salidas, etiquetas, actuales={**CATEGORY_REVIEW_THRESHOLD, "crack": 0.65})
    assert buscar(fuera, clase="crack")["umbral"] == 0.65 and buscar(fuera, clase="crack")["candidatos"] == 60
    assert CATEGORY_REVIEW_THRESHOLD == antes
    print("criterio: rejilla y umbrales actuales ok")


def probar_antes_y_despues() -> None:
    """AC-004: tabla «antes y despues» (umbrales actuales frente a los del criterio): firmes (candidatos con score >= umbral),
    precision de «daño real» y recall de «daño real» (reales decididos que quedan como firmes sobre todos los reales)."""
    salidas, etiquetas = escenario_criterio()
    nuevos = umbrales_de(umbrales_por_criterio(salidas, etiquetas))
    filas = antes_despues(salidas, etiquetas, nuevos)
    assert [f["clase"] for f in filas] == list(CATEGORY_REVIEW_THRESHOLD)
    d = buscar(filas, clase="dent")
    assert (d["actual"], d["nuevo"], d["firmes_actual"], d["firmes_nuevo"], d["decididos_actual"], d["decididos_nuevo"]) == (0.7, 0.3, 20, 100, 20, 100), d
    assert (d["precision_actual"], d["precision_nuevo"], d["recall_actual"], d["recall_nuevo"]) == (1.0, 1.0, 0.2, 1.0), d
    assert d["intervalo_nuevo"] == intervalo_wilson(100, 100) and d["intervalo_actual"] == intervalo_wilson(20, 20)
    s = buscar(filas, clase="scratch")
    assert (s["firmes_actual"], s["firmes_nuevo"]) == (100, 190) and s["precision_nuevo"] == 1.0
    assert abs(s["recall_actual"] - 100 / 220) < 1e-12 and abs(s["recall_nuevo"] - 190 / 220) < 1e-12  # 220 reales decididos en la clase
    c = buscar(filas, clase="crack")
    assert c["actual"] == c["nuevo"] == 0.7 and c["firmes_actual"] == c["firmes_nuevo"] == 60 and c["recall_actual"] == c["recall_nuevo"] == 1.0
    g = buscar(filas, clase="glass shatter")
    assert (g["firmes_actual"], g["firmes_nuevo"], g["decididos_actual"], g["decididos_nuevo"]) == (0, 140, 0, 80), g  # los 140 candidatos cuentan como firmes
    assert g["precision_actual"] is None and g["recall_actual"] == 0.0 and g["recall_nuevo"] == 1.0
    t = buscar(filas, clase="tire flat")
    assert t["firmes_actual"] == t["firmes_nuevo"] == 0 and t["precision_nuevo"] is None and t["recall_nuevo"] is None
    assert sum(f["firmes_actual"] for f in filas) == 180 and sum(f["firmes_nuevo"] for f in filas) == 490
    print("antes y despues ok")


def probar_formato_criterio() -> None:
    """AC-004: el informe del criterio dice cual es, con su minimo, y lleva una fila por clase con actual, nuevo y motivo, y la
    tabla antes y despues."""
    salidas, etiquetas = escenario_criterio()
    filas = umbrales_por_criterio(salidas, etiquetas)
    ad = antes_despues(salidas, etiquetas, umbrales_de(filas))
    texto = formatear_criterio(filas, ad)
    for esperado in ("Umbrales que salen del criterio", "Wilson", "95 %", "daño real", "se mantiene", "Antes y después", "Recall"):
        assert esperado in texto, esperado
    tabla = [l for l in texto.splitlines() if l.startswith("|")]
    assert all(l.rstrip().endswith("|") for l in tabla)
    dent = next(l for l in tabla if l.startswith("| dent |") and "criterio" in l)
    assert "0,7" in dent and "0,3" in dent, dent
    crack = next(l for l in tabla if l.startswith("| crack |") and "se mantiene" in l)
    assert "0,7" in crack, crack
    assert "90 %" in formatear_criterio(umbrales_por_criterio(salidas, etiquetas, minimo=0.90), ad, minimo=0.90)
    print("formato del criterio ok")


def probar_cli_criterio() -> None:
    """La linea de comandos incluye la seccion del criterio solo con --criterio, acepta --minimo-wilson y rechaza un minimo fuera de (0, 1]."""
    salidas, etiquetas = escenario_criterio()
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "salidas").mkdir()
        (base / "salidas" / "000001.json").write_text(json.dumps(salidas[0]), encoding="utf-8")
        csv = base / "etiquetas.csv"
        csv.write_text("finding_id,etiqueta\n" + "".join(f"{i},{e}\n" for i, e in etiquetas.items()), encoding="utf-8")
        base_args = ["--salidas", str(base / "salidas"), "--etiquetas", str(csv)]

        def correr(*extra: str) -> tuple[int, str, str]:
            salida, error = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(error):
                codigo = main([*base_args, *extra])
            return codigo, salida.getvalue(), error.getvalue()

        codigo, texto, _ = correr()
        assert codigo == 0 and "Umbrales que salen del criterio" not in texto
        codigo, texto, _ = correr("--criterio")
        assert codigo == 0 and "Umbrales que salen del criterio" in texto and "se mantiene" in texto and "95 %" in texto
        fila_crack = next(l for l in texto.splitlines() if l.startswith("| crack |") and "0,7" in l)
        codigo, texto, _ = correr("--criterio", "--minimo-wilson", "0.90")
        assert codigo == 0 and "90 %" in texto
        assert any(l.startswith("| crack |") and "criterio" in l for l in texto.splitlines()), "con 90 % crack sale a 0,3"
        for malo in ("0", "1.5", "-0.2"):
            codigo, _, error = correr("--criterio", "--minimo-wilson", malo)
            assert codigo == 2 and "ERROR" in error and "minimo" in error.lower(), (malo, codigo, error)
    print("linea de comandos del criterio ok")


def probar_criterio_con_datos_reales() -> None:
    """AC-004 con las 500 salidas reales y las etiquetas del juez (fuera de git): el criterio reproduce la tabla del plan v1.4 (dent, scratch
    y crack a 0,3; lamp broken, glass shatter y tire flat se mantienen en 0,6) con sus limites inferiores, y los firmes pasan de 799 a 1.531.
    Con las etiquetas que incluyen la revision humana de los 60 `dudo` salen los mismos umbrales. Se salta si no estan los datos."""
    sal = RAIZ / "piia2_detecciones" / "salida_agente1_500"
    base = RAIZ / "piia2_detecciones" / "juez" / "gpt-6.1-terra"
    if not (sal.is_dir() and (base / "etiquetas_juez.csv").is_file()):
        print("(salidas o etiquetas del juez reales no encontradas: se salta el criterio con datos reales)")
        return
    from etiquetado import _leer_salidas, leer_etiquetas

    salidas = _leer_salidas(sal)
    esperado = {"dent": 0.3, "scratch": 0.3, "crack": 0.3, "lamp broken": 0.6, "glass shatter": 0.6, "tire flat": 0.6}
    inferior = {"dent": 98.7, "scratch": 97.6, "crack": 97.9, "lamp broken": 81.2, "glass shatter": 90.3, "tire flat": 86.5}  # plan v1.4, en %
    filas = umbrales_por_criterio(salidas, leer_etiquetas(base / "etiquetas_juez.csv"))
    assert umbrales_de(filas) == esperado, umbrales_de(filas)
    for f in filas:
        assert round(f["limite_inferior"] * 100, 1) == inferior[f["clase"]], (f["clase"], f["limite_inferior"])
    assert {f["clase"] for f in filas if f["cambia"]} == {"dent", "scratch", "crack"}
    ad = antes_despues(salidas, leer_etiquetas(base / "etiquetas_juez.csv"), esperado)
    assert (sum(f["firmes_actual"] for f in ad), sum(f["firmes_nuevo"] for f in ad)) == (799, 1531)
    revisadas = base / "etiquetas_juez_con_revision.csv"
    if revisadas.is_file():
        assert umbrales_de(umbrales_por_criterio(salidas, leer_etiquetas(revisadas))) == esperado
    print("criterio con datos reales ok: 0,3 en dent, scratch y crack; se mantienen 0,6 en el resto; firmes 799 -> 1.531")


def main_pruebas() -> None:
    probar_tramos()
    probar_filas_por_tramo()
    probar_filas_por_umbral()
    probar_rechazados_e_is_tp()
    probar_formato()
    probar_cli()
    probar_con_datos_reales()
    probar_criterio_el_valor_mas_bajo()
    probar_criterio_dudo_y_sin_etiqueta_fuera_del_denominador()
    probar_criterio_minimo_configurable_y_minimo_de_casos()
    probar_criterio_rejilla_y_umbrales_actuales()
    probar_antes_y_despues()
    probar_formato_criterio()
    probar_cli_criterio()
    probar_criterio_con_datos_reales()
    print("Todo ok: tabla_umbrales.")


if __name__ == "__main__":
    main_pruebas()
