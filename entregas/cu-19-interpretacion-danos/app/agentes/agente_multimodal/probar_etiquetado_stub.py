"""Prueba etiquetado.py sin API Key ni datos reales (Issue #44, AC-003): el
calculo de la precision por tramo de score con intervalo, la eleccion de la
muestra a etiquetar, la lectura del CSV de etiquetas y la pagina de etiquetado.
Cada prueba cita su AC con la forma "Plan v1 de #44 + AC-003". Con las salidas
reales del lote de la #43 en local hace ademas una comprobacion de la muestra y
de la pagina (se salta si no estan).

    python probar_etiquetado_stub.py
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
from pathlib import Path

from PIL import Image

from confianza import CATEGORY_REVIEW_THRESHOLD
from etiquetado import (
    ETIQUETAS,
    MINIMO_CONCLUYENTE,
    TRAMOS,
    EtiquetasNoValidas,
    candidatos_a_etiquetar,
    elegir_muestra,
    elegir_muestra_validacion,
    formatear_tabla,
    generar_pagina,
    intervalo_wilson,
    leer_etiquetas,
    main,
    tabla_precision,
    tramo_de,
)

RAIZ = Path(__file__).resolve().parents[5]


def hallazgo(image_id: int, n: int, clase: str, score: float, veredicto: str = "confirmado") -> dict:
    slug = clase.replace(" ", "_")
    return {
        "finding_id": f"{image_id}-{n}",
        "category": clase,
        "clase_tool": slug,
        "score": score,
        "confidence_tier": "needs_review",
        "vision_verdict": veredicto,
        "pieza_id": "PARAG_DEL" if veredicto == "confirmado" else None,
        "vision_description": f"descripcion del hallazgo {image_id}-{n}",
        "crop_image_path": f"crops/{image_id}_{slug}_{n}.jpg",
    }


def salidas_sinteticas() -> list[dict]:
    """Salidas del Agente 1 inventadas: dent con 12 candidatas por tramo, scratch con 4 y 3,
    crack sin ninguna, y ruido que no debe entrar (firmes, rechazados, otra clase)."""
    hallazgos: list[dict] = []
    n = 0

    def anadir(clase: str, score: float, veredicto: str = "confirmado") -> None:
        nonlocal n
        n += 1
        hallazgos.append(hallazgo(100 + n // 5, n, clase, round(score, 4), veredicto))

    for i in range(12):
        anadir("dent", 0.50 + 0.015 * i)  # tramo 0,5-0,7
        anadir("dent", 0.30 + 0.015 * i)  # tramo 0,3-0,5
    for i in range(4):
        anadir("scratch", 0.52 + 0.04 * i)
    for i in range(3):
        anadir("scratch", 0.31 + 0.05 * i)
    for score in (0.70, 0.85, 0.95):
        anadir("dent", score)  # ya pasan el umbral actual: no se etiquetan
    anadir("dent", 0.60, "rechazado")  # la vision no los confirma
    anadir("dent", 0.40, "incierto")
    anadir("crack", 0.65, "rechazado")
    for i in range(5):
        anadir("lamp broken", 0.35 + 0.05 * i)  # otra clase
    anadir("dent", 0.29)  # por debajo de PIIA-1 (0,3): sin tramo
    por_imagen: dict[int, list[dict]] = {}
    for h in hallazgos:
        por_imagen.setdefault(int(h["finding_id"].split("-")[0]), []).append(h)
    return [{"image_id": i, "resumen_filtro_previo": {"candidatas": len(f)}, "findings": f} for i, f in sorted(por_imagen.items())]


def probar_tramos() -> None:
    """Plan v1 de #44 + AC-003: los dos tramos por debajo del umbral actual y sus bordes."""
    assert TRAMOS == ((0.3, 0.5), (0.5, 0.7))
    assert tramo_de(0.3) == 0 and tramo_de(0.4999) == 0
    assert tramo_de(0.5) == 1 and tramo_de(0.6999) == 1
    assert tramo_de(0.7) is None and tramo_de(0.95) is None and tramo_de(0.2999) is None
    assert ETIQUETAS == ("si", "otra", "no", "dudo") and MINIMO_CONCLUYENTE == 5
    print("tramos ok")


def probar_intervalo_wilson() -> None:
    """Plan v1 de #44 + AC-003: intervalo de Wilson al 95 %, con las cifras que da el plan v1.1
    (20 de 20 -> limite inferior ~84 %; 19 de 20 -> ~76 %)."""
    lo, hi = intervalo_wilson(20, 20)
    assert abs(lo - 0.8389) < 5e-4 and abs(hi - 1.0) < 1e-9
    lo, hi = intervalo_wilson(19, 20)
    assert abs(lo - 0.7639) < 5e-4 and abs(hi - 0.9911) < 5e-4
    lo, hi = intervalo_wilson(8, 10)
    assert abs(lo - 0.4902) < 5e-4 and abs(hi - 0.9433) < 5e-4
    lo, hi = intervalo_wilson(0, 10)
    assert lo == 0.0 and abs(hi - 0.2775) < 5e-4
    assert intervalo_wilson(0, 0) == (None, None)
    for k, n in ((1, 3), (5, 5), (0, 1)):
        lo, hi = intervalo_wilson(k, n)
        assert 0.0 <= lo <= k / n <= hi <= 1.0
    print("intervalo de Wilson ok")


def probar_candidatos_y_muestra() -> None:
    """Plan v1 de #44 + AC-003: solo entran los hallazgos que la vision confirmo, de dent, scratch y
    crack, con score por debajo del umbral actual de su clase y dentro de un tramo; la muestra es
    determinista, tiene como mucho 10 por clase y tramo y la tanda 1 es el tramo alto."""
    salidas = salidas_sinteticas()
    cands = candidatos_a_etiquetar(salidas)
    por = {}
    for c in cands:
        por.setdefault((c["category"], tramo_de(c["score"])), []).append(c)
    assert {k: len(v) for k, v in por.items()} == {("dent", 0): 12, ("dent", 1): 12, ("scratch", 0): 3, ("scratch", 1): 4}, {k: len(v) for k, v in por.items()}
    assert all(c["vision_verdict"] == "confirmado" and c["score"] < CATEGORY_REVIEW_THRESHOLD[c["category"]] for c in cands)
    assert all("image_id" in c for c in cands), "cada candidata lleva su imagen"
    # con un umbral menor, sale lo que ya pasa el umbral nuevo (>= 0,6 en dent)
    cands_06 = candidatos_a_etiquetar(salidas, umbrales={"dent": 0.6, "scratch": 0.7, "crack": 0.7})
    assert max(c["score"] for c in cands_06 if c["category"] == "dent") < 0.6

    muestra = elegir_muestra(cands, por_tramo=10, semilla=42)
    cuenta = {}
    for m in muestra:
        cuenta[(m["category"], m["tramo"])] = cuenta.get((m["category"], m["tramo"]), 0) + 1
    assert cuenta == {("dent", "0,5-0,7"): 10, ("dent", "0,3-0,5"): 10, ("scratch", "0,5-0,7"): 4, ("scratch", "0,3-0,5"): 3}, cuenta
    assert len(muestra) == 27 and len({m["finding_id"] for m in muestra}) == 27
    assert [m["tanda"] for m in muestra] == sorted(m["tanda"] for m in muestra), "primero la tanda 1"
    assert {m["tanda"] for m in muestra if m["tramo"] == "0,5-0,7"} == {1} and {m["tanda"] for m in muestra if m["tramo"] == "0,3-0,5"} == {2}
    for clave in ("finding_id", "image_id", "category", "score", "tramo", "tanda", "vision_verdict", "pieza_id", "vision_description", "crop_image_path"):
        assert clave in muestra[0], clave
    assert elegir_muestra(cands, 10, 42) == muestra, "misma semilla, misma muestra y mismo orden"
    assert elegir_muestra(cands, 10, 43) != muestra, "otra semilla, otra muestra"
    assert len(elegir_muestra(cands, por_tramo=2, semilla=42)) == 2 * 2 + 2 * 2
    assert elegir_muestra([], 10, 42) == []
    print("candidatas y muestra ok")


def probar_leer_etiquetas() -> None:
    """Plan v1 de #44 + AC-003: el CSV de etiquetas (solo ids y etiquetas) se lee y se valida."""
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        bueno = d / "ok.csv"
        bueno.write_text("finding_id,etiqueta\r\n82-1,si\r\n\r\n82-2,dudo\r\n103-7,otra\r\n", encoding="utf-8")
        assert leer_etiquetas(bueno) == {"82-1": "si", "82-2": "dudo", "103-7": "otra"}
        bom = d / "bom.csv"
        bom.write_text("finding_id,etiqueta\n5-1,no\n", encoding="utf-8-sig")
        assert leer_etiquetas(bom) == {"5-1": "no"}
        vacio = d / "vacio.csv"
        vacio.write_text("finding_id,etiqueta\n", encoding="utf-8")
        assert leer_etiquetas(vacio) == {}

        def falla(texto: str, esperado: str) -> None:
            ruta = d / "malo.csv"
            ruta.write_text(texto, encoding="utf-8")
            try:
                leer_etiquetas(ruta)
            except EtiquetasNoValidas as e:
                assert esperado in str(e), (esperado, str(e))
            else:
                raise AssertionError(f"debia fallar: {texto!r}")

        falla("finding_id,etiqueta\n82-1,si\n82-2,quizas\n", "quizas")
        falla("finding_id,etiqueta\n82-1,si\n82-2,quizas\n", "linea 3")
        falla("finding_id,etiqueta\n82-1,si\n82-1,no\n", "duplicad")
        falla("id,label\n82-1,si\n", "cabecera")
        falla("finding_id,etiqueta\n82-1\n", "linea 2")
        falla("", "cabecera")
    print("lectura de etiquetas ok")


def probar_tabla_precision() -> None:
    """Plan v1 de #44 + AC-003: precision de `confirmado` por clase y tramo con n e intervalo, celdas
    con menos de 5 casos no concluyentes, `dudo` aparte y comparacion con `is_true_positive`."""
    salidas = salidas_sinteticas()
    cands = candidatos_a_etiquetar(salidas)
    dent1 = sorted((c for c in cands if c["category"] == "dent" and tramo_de(c["score"]) == 1), key=lambda c: c["finding_id"])
    dent0 = sorted((c for c in cands if c["category"] == "dent" and tramo_de(c["score"]) == 0), key=lambda c: c["finding_id"])
    etiquetas = {c["finding_id"]: "si" for c in dent1[:8]}
    etiquetas[dent1[8]["finding_id"]] = "otra"
    etiquetas[dent1[9]["finding_id"]] = "no"
    etiquetas[dent1[10]["finding_id"]] = "dudo"
    etiquetas[dent1[11]["finding_id"]] = "dudo"
    for c, e in zip(dent0[:3], ("si", "no", "otra")):
        etiquetas[c["finding_id"]] = e
    is_tp = {c["finding_id"]: True for c in dent1}
    for c in dent1[:3] + dent0[:2]:
        is_tp[c["finding_id"]] = False  # confirmados que PIIA1 daba por fallo: 3 si, 1 no... se cuentan abajo
    is_tp.update({c["finding_id"]: False for c in dent0})

    filas = tabla_precision(salidas, etiquetas, is_tp)
    por = {(f["clase"], f["tramo"]): f for f in filas}
    assert [f["clase"] for f in filas[:3]] == ["dent", "dent", "dent"] and set(por) >= {("dent", "0,3-0,5"), ("dent", "0,5-0,7"), ("dent", "total"), ("scratch", "total"), ("crack", "0,3-0,5")}
    f = por[("dent", "0,5-0,7")]
    assert (f["etiquetados"], f["si"], f["otra"], f["no"], f["dudo"]) == (10, 8, 1, 1, 2), f
    assert f["precision_estricta"] == 0.8 and f["precision_dano_real"] == 0.9
    assert f["intervalo_estricta"] == intervalo_wilson(8, 10) and f["intervalo_dano_real"] == intervalo_wilson(9, 10)
    assert f["concluyente"] is True
    # tres etiquetados (y ninguno `dudo`): menos de 5 casos -> no concluyente
    g = por[("dent", "0,3-0,5")]
    assert (g["etiquetados"], g["si"], g["otra"], g["no"], g["dudo"]) == (3, 1, 1, 1, 0)
    assert g["concluyente"] is False and abs(g["precision_estricta"] - 1 / 3) < 1e-9
    # total por clase
    t = por[("dent", "total")]
    assert (t["etiquetados"], t["si"], t["dudo"]) == (13, 9, 2) and t["intervalo_estricta"] == intervalo_wilson(9, 13)
    # clase sin etiquetas
    s = por[("scratch", "0,5-0,7")]
    assert s["etiquetados"] == 0 and s["precision_estricta"] is None and s["intervalo_estricta"] == (None, None) and s["concluyente"] is False
    # comparacion con is_true_positive: confirmados con is_tp falso y cuantos eran dano real
    assert f["confirmados_is_tp_falso"] == 3 and f["de_ellos_si"] == 3 and f["de_ellos_otra"] == 0
    assert g["confirmados_is_tp_falso"] == 3 and g["de_ellos_si"] == 1 and g["de_ellos_otra"] == 1
    sin_tp = {(x["clase"], x["tramo"]): x for x in tabla_precision(salidas, etiquetas)}
    assert "confirmados_is_tp_falso" not in sin_tp[("dent", "0,5-0,7")]

    texto = formatear_tabla(filas)
    assert "dent" in texto and "0,5-0,7" in texto and "no concluyente" in texto and "80 %" in texto

    def falla(etiq: dict[str, str], esperado: str) -> None:
        try:
            tabla_precision(salidas, etiq)
        except EtiquetasNoValidas as e:
            assert esperado in str(e), (esperado, str(e))
        else:
            raise AssertionError(f"debia fallar: {etiq}")

    falla({"9999-1": "si"}, "9999-1")  # no existe en las salidas
    lampara = next(h["finding_id"] for s_ in salidas for h in s_["findings"] if h["category"] == "lamp broken")
    falla({lampara: "si"}, "clase")  # fuera de dent, scratch y crack
    firme = next(h["finding_id"] for s_ in salidas for h in s_["findings"] if h["score"] >= 0.7 and h["category"] == "dent")
    falla({firme: "si"}, "tramo")  # ya pasa el umbral: no pertenece a la muestra
    falla({dent1[0]["finding_id"]: "quizas"}, "etiqueta")
    print("tabla de precision ok")


def _recortes_falsos(base: Path, salidas: list[dict]) -> None:
    for s in salidas:
        for h in s["findings"]:
            ruta = base / h["crop_image_path"]
            ruta.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (40, 30), (200, 80, 80)).save(ruta, "JPEG")


def probar_pagina() -> None:
    """Plan v1 de #44 + AC-003: la pagina de etiquetado es un solo archivo, sin red ni rutas privadas,
    con los recortes incrustados, las cuatro etiquetas con su tecla y la descarga del CSV."""
    salidas = salidas_sinteticas()
    muestra = elegir_muestra(candidatos_a_etiquetar(salidas), 10, 42)[:6]
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "salidas"
        _recortes_falsos(base, salidas)
        destino = Path(tmp) / "salida" / "etiquetar.html"
        assert generar_pagina(muestra, base, destino) == destino and destino.exists()
        html = destino.read_text(encoding="utf-8")
        assert html.count("data:image/jpeg;base64,") == len(muestra), "un recorte incrustado por hallazgo"
        for m in muestra:
            assert m["finding_id"] in html
        for etiqueta in ETIQUETAS:
            assert f'data-etiqueta="{etiqueta}"' in html, etiqueta
        for tecla in ("s", "o", "n", "d"):
            assert f"'{tecla}'" in html, tecla
        assert "finding_id,etiqueta" in html and "Descargar CSV" in html and "localStorage" in html
        assert "http://" not in html and "https://" not in html, "debe funcionar sin red"
        assert str(tmp) not in html and "C:\\" not in html and "/Users/" not in html and "Luc" + "ía" not in html, "sin rutas ni nombres privados"
        # la respuesta de la IA va aparte: se muestra despues del recorte
        assert "Ver qué dice la IA" in html
        # sin hallazgos no hay pagina
        try:
            generar_pagina([], base, Path(tmp) / "vacia.html")
        except EtiquetasNoValidas:
            pass
        else:
            raise AssertionError("una muestra vacia no debe generar pagina")
    print("pagina de etiquetado ok")


def probar_cli() -> None:
    """Plan v1 de #44 + AC-003: `muestra` escribe la pagina y la lista; `tabla` imprime la tabla;
    la pagina no se escribe dentro de `entregas/` (llevaria recortes de CarDD a git)."""
    salidas = salidas_sinteticas()
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        sal = d / "salidas"
        _recortes_falsos(sal, salidas)
        for s in salidas:
            (sal / f"{s['image_id']:06d}.json").write_text(json.dumps(s), encoding="utf-8")
        (sal / "resumen_lote.json").write_text("{}", encoding="utf-8")
        pagina, lista = d / "p.html", d / "muestra.json"
        with contextlib.redirect_stdout(io.StringIO()) as out:
            assert main(["muestra", "--salidas", str(sal), "--pagina", str(pagina), "--muestra-json", str(lista)]) == 0
        assert pagina.exists() and "27" in out.getvalue()
        guardada = json.loads(lista.read_text(encoding="utf-8"))
        assert len(guardada) == 27 and guardada[0]["tanda"] == 1
        assert all("crop_image_path" in m and not Path(m["crop_image_path"]).is_absolute() for m in guardada)

        etiquetas = d / "e.csv"
        etiquetas.write_text("finding_id,etiqueta\n" + "\n".join(f"{m['finding_id']},si" for m in guardada[:10]) + "\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            assert main(["tabla", "--salidas", str(sal), "--etiquetas", str(etiquetas)]) == 0
        assert "dent" in out.getvalue() and "100 %" in out.getvalue()

        malo = d / "malo.csv"
        malo.write_text("finding_id,etiqueta\n9999-1,si\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            assert main(["tabla", "--salidas", str(sal), "--etiquetas", str(malo)]) != 0

        prohibido = RAIZ / "entregas" / "no-debe-existir" / "p.html"
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            assert main(["muestra", "--salidas", str(sal), "--pagina", str(prohibido), "--muestra-json", str(d / "m2.json")]) != 0
        assert not prohibido.exists() and not prohibido.parent.exists()
    print("linea de comandos ok")


def salidas_validacion() -> list[dict]:
    """Las seis clases, cada una con 8 rechazados por la vision, 8 confirmados con score por encima del umbral
    de su clase y ruido que no debe entrar (confirmados por debajo del umbral, inciertos)."""
    hallazgos: list[dict] = []
    n = 0
    for clase, umbral in CATEGORY_REVIEW_THRESHOLD.items():
        for i in range(8):
            n += 1
            hallazgos.append(hallazgo(500 + n // 4, n, clase, round(0.2 + 0.01 * i, 4), "rechazado"))
            n += 1
            hallazgos.append(hallazgo(500 + n // 4, n, clase, round(umbral + 0.02 + 0.01 * i, 4), "confirmado"))
        n += 1
        hallazgos.append(hallazgo(500 + n // 4, n, clase, round(umbral - 0.1, 4), "confirmado"))
        n += 1
        hallazgos.append(hallazgo(500 + n // 4, n, clase, 0.4, "incierto"))
    por_imagen: dict[int, list[dict]] = {}
    for h in hallazgos:
        por_imagen.setdefault(int(h["finding_id"].split("-")[0]), []).append(h)
    return [{"image_id": i, "resumen_filtro_previo": {}, "findings": f} for i, f in sorted(por_imagen.items())]


def probar_muestra_validacion() -> None:
    """Plan v1.2 de #44 + AC-009: la muestra de validacion mezcla, por clase, rechazados por la vision y
    confirmados con score alto; es determinista, no repite lo ya etiquetado y no filtra el veredicto."""
    salidas = salidas_validacion()
    por_id = {h["finding_id"]: h for s in salidas for h in s["findings"]}
    muestra = elegir_muestra_validacion(salidas, por_clase=5, semilla=42)
    assert len(muestra) == 60, len(muestra)
    for clase in CATEGORY_REVIEW_THRESHOLD:
        de_clase = [m for m in muestra if m["category"] == clase]
        veredictos = [por_id[m["finding_id"]]["vision_verdict"] for m in de_clase]
        assert veredictos.count("rechazado") == 5 and veredictos.count("confirmado") == 5, (clase, veredictos)
        for m in de_clase:
            h = por_id[m["finding_id"]]
            assert h["vision_verdict"] == "rechazado" or h["score"] >= CATEGORY_REVIEW_THRESHOLD[clase]
    assert all(m["tramo"] == "validación" and m["tanda"] == 1 for m in muestra), "el tramo no debe revelar el veredicto"
    ordenados = sorted(por_id[m["finding_id"]]["vision_verdict"] for m in muestra)
    assert [por_id[m["finding_id"]]["vision_verdict"] for m in muestra] != ordenados, "el orden debe mezclar los dos tipos"
    assert elegir_muestra_validacion(salidas, por_clase=5, semilla=42) == muestra, "determinista"
    assert [m["finding_id"] for m in elegir_muestra_validacion(salidas, por_clase=5, semilla=7)] != [m["finding_id"] for m in muestra]
    ya = {m["finding_id"] for m in muestra[:20]}
    otra = elegir_muestra_validacion(salidas, excluidos=ya, por_clase=5, semilla=42)
    assert not ({m["finding_id"] for m in otra} & ya), "no repite lo ya etiquetado"
    # cada grupo (clase y tipo) tiene 8 candidatos; sin los excluidos da min(5, 8 - excluidos del grupo)
    esperados = 0
    for clase in CATEGORY_REVIEW_THRESHOLD:
        for tipo in ("rechazado", "confirmado"):
            excluidos_grupo = sum(1 for i in ya if por_id[i]["category"] == clase and por_id[i]["vision_verdict"] == tipo)
            esperados += min(5, 8 - excluidos_grupo)
    assert len(otra) == esperados, (len(otra), esperados)
    pocas = elegir_muestra_validacion(salidas, por_clase=50, semilla=42)
    assert len(pocas) == 6 * 8 * 2, "con menos candidatos que cupo toma todos"
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        _recortes_falsos(base, salidas)
        generar_pagina(muestra, base, base / "validacion.html", "etiquetas_validacion_44.csv")
        html = (base / "validacion.html").read_text(encoding="utf-8")
        assert "etiquetas_validacion_44.csv" in html and "etiquetas_44.csv" not in html
        assert html.count("data:image/jpeg;base64,") == 60 and "http://" not in html and "https://" not in html
        assert "const CIEGO = false;" in html and '"veredicto"' in html, "la pagina normal sigue ofreciendo ver a la IA"
        # AC-009: la persona etiqueta en las mismas condiciones que el juez (solo recorte y clase): sin score, sin veredicto ni descripcion
        generar_pagina(muestra, base, base / "ciega.html", "etiquetas_validacion_44.csv", ciego=True)
        ciega = (base / "ciega.html").read_text(encoding="utf-8")
        assert "const CIEGO = true;" in ciega and ciega.count("data:image/jpeg;base64,") == 60
        for prohibido in ('"veredicto"', '"descripcion"', '"score"', '"pieza"', "rechazado", "confirmado"):
            assert prohibido not in ciega, f"la pagina ciega no debe llevar {prohibido}"
        for h in por_id.values():
            if h.get("vision_description"):
                assert h["vision_description"] not in ciega, "la descripcion de la vision no debe estar en la pagina ciega"
        with contextlib.redirect_stdout(io.StringIO()):
            (base / "sal").mkdir()
            for s in salidas:
                (base / "sal" / f"{s['image_id']:06d}.json").write_text(json.dumps(s), encoding="utf-8")
            shutil.copytree(base / "crops", base / "sal" / "crops")
            excluir = base / "humanas.csv"
            excluir.write_text("finding_id,etiqueta" + chr(10) + "".join(f"{i},si" + chr(10) for i in sorted(ya)), encoding="utf-8")
            assert main(["validacion", "--salidas", str(base / "sal"), "--excluir", str(excluir), "--pagina", str(base / "v.html"), "--muestra-json", str(base / "v.json")]) == 0
        lista = json.loads((base / "v.json").read_text(encoding="utf-8"))
        assert len(lista) == esperados and not ({m["finding_id"] for m in lista} & ya), (len(lista), esperados)
        assert "etiquetas_validacion_44.csv" in (base / "v.html").read_text(encoding="utf-8")
        assert "const CIEGO = true;" in (base / "v.html").read_text(encoding="utf-8"), "la pagina de validacion es ciega"
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            assert main(["validacion", "--salidas", str(base / "sal"), "--pagina", str(RAIZ / "entregas" / "x" / "v.html")]) == 2
        assert "entregas" in err.getvalue()
    print("muestra de validacion ok")


def probar_con_datos_reales() -> None:
    """Plan v1 de #44 + AC-003: con las salidas reales del lote de la #43 (fuera de git) la muestra
    y la pagina se generan; se salta si no estan."""
    sal = RAIZ / "piia2_detecciones" / "salida_agente1"
    if not (sal / "resumen_lote.json").exists():
        print("(salidas reales del lote no encontradas: se salta la comprobacion con datos reales)")
        return
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        with contextlib.redirect_stdout(io.StringIO()):
            assert main(["muestra", "--salidas", str(sal), "--pagina", str(d / "p.html"), "--muestra-json", str(d / "m.json")]) == 0
        muestra = json.loads((d / "m.json").read_text(encoding="utf-8"))
        html = (d / "p.html").read_text(encoding="utf-8")
        assert 0 < len(muestra) <= 60 and html.count("data:image/jpeg;base64,") == len(muestra)
        assert all(m["category"] in ("dent", "scratch", "crack") and m["vision_verdict"] == "confirmado" and m["score"] < 0.7 for m in muestra)
    print(f"datos reales ok: {len(muestra)} hallazgos de la muestra y pagina generada con los recortes reales")


def main_pruebas() -> None:
    probar_tramos()
    probar_intervalo_wilson()
    probar_candidatos_y_muestra()
    probar_leer_etiquetas()
    probar_tabla_precision()
    probar_pagina()
    probar_cli()
    probar_muestra_validacion()
    probar_con_datos_reales()
    print("Todo ok: etiquetado.")


if __name__ == "__main__":
    main_pruebas()
