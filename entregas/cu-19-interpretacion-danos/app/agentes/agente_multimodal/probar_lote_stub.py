"""Prueba generar_lote.py sin API Key real ni el paquete `openai`: usa el
cliente falso de probar_vision_stub.py, un mini-export sintetico de
detecciones y fotos grises en un directorio temporal. Cada prueba cita el AC
del plan de la Issue #43 (referencia: PLAN + AC-00X).

PLAN = Plan v1 de #43,
https://github.com/lvckss/piia2-26/issues/43#issuecomment-6237143949"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image

from agente1 import analizar_imagen
from analizar_detecciones import CLASES, cargar
from evaluar_vision import ruta_foto
from generar_lote import (
    elegir_lote, fotos_que_faltan, generar_lote, llamadas_previstas, main, rutas_por_defecto, validar_salida_agente1,
)
from probar_vision_stub import MINI_CATALOGO, ClienteFalso
from seleccion import seleccionar_candidatos

N_IMAGENES = 18
RAIZ_REPO = Path(__file__).resolve().parents[5]


def _pred(clase: str, score: float, acierto: bool, indice: int) -> dict[str, Any]:
    return {
        "instance_index": indice,
        "damage_class": clase,
        "category_id": 1,
        "score": score,
        "bbox_xywh": [20.0 + 5 * indice, 10.0, 60.0, 40.0],
        "area": 2400.0,
        "is_true_positive": acierto,
        "best_iou": 0.7 if acierto else 0.1,
    }


def _imagen(k: int) -> dict[str, Any]:
    """Imagen k: un acierto de PIIA-1 de la clase k % 6 y un falso positivo de
    otra clase. 18 imagenes -> 3 aciertos por clase."""
    acierto = CLASES[(k - 1) % 6]
    falso = CLASES[k % 6]
    return {
        "image_id": k,
        "image_file": f"{k:06d}.jpg",
        "image_path": f"/content/drive/MyDrive/CarDD/{k:06d}.jpg",
        "image_width": 200,
        "image_height": 100,
        "split": "val" if k % 2 else "test",
        "predictions": [_pred(acierto, 0.9, True, 1), _pred(falso, 0.4, False, 2)],
        "ground_truth": [],
    }


def montar_datos(tmp: Path, sin_foto: tuple[int, ...] = ()) -> tuple[Path, Path, list[dict[str, Any]]]:
    """Escribe el mini-export y las fotos grises. Devuelve (export, cardd, imagenes)."""
    export, cardd = tmp / "export", tmp / "cardd"
    export.mkdir()
    imagenes = [_imagen(k) for k in range(1, N_IMAGENES + 1)]
    for img in imagenes:
        (export / f"{img['image_id']:06d}.json").write_text(json.dumps(img), encoding="utf-8")
        carpeta = cardd / f"{img['split']}2017"
        carpeta.mkdir(parents=True, exist_ok=True)
        if img["image_id"] not in sin_foto:
            Image.new("RGB", (200, 100), "gray").save(carpeta / img["image_file"])
    return export, cardd, imagenes


def _aciertos_por_clase(lote: list[dict[str, Any]]) -> Counter:
    cuenta: Counter = Counter()
    for img in lote:
        candidatas, _ = seleccionar_candidatos(img["predictions"])
        cuenta.update(p["damage_class"] for p in candidatas if p["is_true_positive"])
    return cuenta


def probar_ac001_seleccion_reproducible() -> None:
    """PLAN + AC-001: lote reproducible con cobertura de las 6 clases."""
    with tempfile.TemporaryDirectory() as tmp:
        export, cardd, imagenes = montar_datos(Path(tmp), sin_foto=(7,))
        lote = elegir_lote(imagenes, n=12, min_aciertos=2, seed=42)
        ids = [i["image_id"] for i in lote]
        assert len(ids) == len(set(ids)) == 12, ids
        cuenta = _aciertos_por_clase(lote)
        assert all(cuenta[c] >= 2 for c in CLASES), cuenta
        # repetir la peticion da la misma lista en el mismo orden
        assert ids == [i["image_id"] for i in elegir_lote(imagenes, n=12, min_aciertos=2, seed=42)]
        # la foto que falta se lista, no se sustituye por otra imagen en silencio
        faltan = fotos_que_faltan(imagenes, cardd)
        assert faltan == ["000007.jpg"], faltan
        assert len(elegir_lote(imagenes, n=12, min_aciertos=2, seed=42)) == 12


def _ejecutar_main(argv: list[str], clave: str | None = None, fabrica: Any = None) -> tuple[int, str, list[int]]:
    """Llama a main() capturando la consola. Devuelve (codigo, texto, clientes_creados)."""
    creados: list[int] = []

    def crear_cliente() -> ClienteFalso:
        creados.append(1)
        return (fabrica or ClienteFalso)()

    anterior = os.environ.pop("OPENAI_API_KEY", None)
    if clave is not None:
        os.environ["OPENAI_API_KEY"] = clave
    salida = io.StringIO()
    try:
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(salida):
            codigo = main(argv, crear_cliente=crear_cliente, catalogo=MINI_CATALOGO)
    finally:
        os.environ.pop("OPENAI_API_KEY", None)
        if anterior is not None:
            os.environ["OPENAI_API_KEY"] = anterior
    return codigo, salida.getvalue(), creados


def probar_ac002_plan_sin_gastar_y_tope() -> None:
    """PLAN + AC-002: sin --ejecutar solo se planifica; el tope corta antes de gastar."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        export, cardd, imagenes = montar_datos(tmp_dir, sin_foto=(7,))
        salida, cache = tmp_dir / "salida", tmp_dir / "cache"
        base = [
            "--detecciones", str(export), "--cardd", str(cardd), "--salida", str(salida),
            "--cache-dir", str(cache), "--n-imagenes", "12", "--min-aciertos", "2",
        ]
        lote = elegir_lote(imagenes, n=12, min_aciertos=2, seed=42)
        esperadas = sum(len(seleccionar_candidatos(i["predictions"])[0]) for i in lote)
        assert llamadas_previstas(lote) == esperadas

        # sin --ejecutar y sin OPENAI_API_KEY: plan, codigo 0, nada creado, 0 clientes
        codigo, texto, creados = _ejecutar_main(base)
        assert codigo == 0, texto
        assert creados == [], "el modo plan creo un cliente"
        assert not salida.exists() and not cache.exists(), "el modo plan escribio ficheros"
        assert "12 imagenes" in texto and f"Llamadas previstas: {esperadas}" in texto, texto
        assert "Fotos locales que faltan: 1" in texto or "faltan: 1" in texto, texto
        assert "no se ha llamado a la api" in texto.lower(), texto

        # con --ejecutar y un tope por debajo de lo previsto: aborta antes de la primera llamada
        codigo, texto, creados = _ejecutar_main(base + ["--ejecutar", "--max-llamadas", str(esperadas - 1)], clave="clave-de-prueba")
        assert codigo != 0, texto
        assert creados == [], "se creo el cliente antes de comprobar el tope"
        assert not salida.exists(), "se escribio algo antes de comprobar el tope"
        assert "max-llamadas" in texto, texto


def _generar(tmp: Path, export: Path, cardd: Path, imagenes: list[dict[str, Any]], cliente: ClienteFalso,
             salida: Path, cache: Path, precios: tuple[float, float] | None = None) -> dict[str, Any]:
    lote = elegir_lote(imagenes, n=6, min_aciertos=1, seed=42)
    return generar_lote(lote, export, cardd, salida, cliente, "modelo-falso", MINI_CATALOGO, cache, precios)


def _sin_ruta_de_recorte(salida_agente1: dict[str, Any]) -> dict[str, Any]:
    copia = json.loads(json.dumps(salida_agente1))
    for f in copia["findings"]:
        f.pop("crop_image_path")
    return copia


def probar_ac003_un_json_por_imagen_con_cache() -> None:
    """PLAN + AC-003: un JSON por imagen == analizar_imagen (salvo la ruta del recorte) y la cache evita repetir."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        export, cardd, imagenes = montar_datos(tmp_dir)
        salida, cache = tmp_dir / "salida", tmp_dir / "cache"
        cliente = ClienteFalso()
        resumen = _generar(tmp_dir, export, cardd, imagenes, cliente, salida, cache)
        lote = elegir_lote(imagenes, n=6, min_aciertos=1, seed=42)
        assert len(lote) == 6 and resumen["imagenes"] == 6

        guardados: dict[str, bytes] = {}
        for img in lote:
            ruta = salida / f"{img['image_id']:06d}.json"
            assert ruta.exists(), f"falta {ruta.name}"
            guardados[ruta.name] = ruta.read_bytes()
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            assert datos["image_id"] == img["image_id"]
            for f in datos["findings"]:
                assert not Path(f["crop_image_path"]).is_absolute(), f["crop_image_path"]
                assert (salida / f["crop_image_path"]).exists(), "el recorte no esta donde dice el JSON"

        # mismo resultado que analizar_imagen sobre la foto local (salvo la ruta del recorte)
        primera = lote[0]
        referencia_cliente = ClienteFalso()
        referencia = analizar_imagen(
            export / f"{primera['image_id']:06d}.json", referencia_cliente, tmp_dir / "crops_ref",
            modelo="modelo-falso", image_path=ruta_foto(cardd, primera), catalogo=MINI_CATALOGO, cache_dir=cache,
        )
        assert referencia_cliente.llamadas == [], "analizar_imagen no uso la cache"
        guardado = json.loads((salida / f"{primera['image_id']:06d}.json").read_text(encoding="utf-8"))
        assert _sin_ruta_de_recorte(guardado) == _sin_ruta_de_recorte(referencia)

        # segunda pasada con la misma cache: 0 llamadas y ficheros identicos byte a byte
        segundo = ClienteFalso()
        _generar(tmp_dir, export, cardd, imagenes, segundo, salida, cache)
        assert segundo.llamadas == [], "la cache no evito las llamadas"
        for nombre, contenido in guardados.items():
            assert (salida / nombre).read_bytes() == contenido, f"{nombre} cambio en la segunda pasada"


def probar_ac005_uso_y_coste() -> None:
    """PLAN + AC-005: llamadas y tokens realmente facturados; euros solo con precios."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        export, cardd, imagenes = montar_datos(tmp_dir)
        salida, cache = tmp_dir / "salida", tmp_dir / "cache"
        cliente = ClienteFalso()
        resumen = _generar(tmp_dir, export, cardd, imagenes, cliente, salida, cache)
        n = len(cliente.llamadas)
        assert n > 0
        assert resumen["modelo"] == "modelo-falso" and resumen["hallazgos"] == n
        assert resumen["llamadas_facturadas"] == n and resumen["hallazgos_desde_cache"] == 0
        assert resumen["tokens_entrada"] == 1500 * n and resumen["tokens_salida"] == 40 * n, resumen
        assert resumen["coste_eur"] is None and "sin precios" in resumen["coste_nota"], resumen
        assert resumen["duracion_s"] >= 0
        en_disco = json.loads((salida / "resumen_lote.json").read_text(encoding="utf-8"))
        assert en_disco == resumen, "el resumen en disco no coincide con el devuelto"

        # segunda pasada: todo sale de la cache y no se factura nada
        cacheado = _generar(tmp_dir, export, cardd, imagenes, ClienteFalso(), salida, cache)
        assert cacheado["llamadas_facturadas"] == 0 and cacheado["hallazgos_desde_cache"] == n
        assert cacheado["tokens_entrada"] == cacheado["tokens_salida"] == 0

        # con precios por millon de tokens, el coste se calcula; sin ellos no hay ninguno por defecto
        con_precios = _generar(tmp_dir, export, cardd, imagenes, ClienteFalso(), tmp_dir / "otra", tmp_dir / "otra_cache", (2.0, 8.0))
        esperado = (1500 * n * 2.0 + 40 * n * 8.0) / 1_000_000
        assert abs(con_precios["coste_eur"] - esperado) < 1e-12, (con_precios["coste_eur"], esperado)


def probar_ejecucion_completa_por_consola() -> None:
    """PLAN + AC-003 y AC-005 por la linea de comandos; precondiciones de la ejecucion real."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        export, cardd, imagenes = montar_datos(tmp_dir)
        salida, cache = tmp_dir / "salida", tmp_dir / "cache"
        def argv(salida_: Path, cache_: Path) -> list[str]:
            return [
                "--detecciones", str(export), "--cardd", str(cardd), "--salida", str(salida_),
                "--cache-dir", str(cache_), "--n-imagenes", "6", "--min-aciertos", "1",
            ]

        base = argv(salida, cache)
        # sin modelo (ni --modelo ni OPENAI_MODEL): no se crea cliente ni se gasta nada
        modelo_anterior = os.environ.pop("OPENAI_MODEL", None)
        try:
            codigo, texto, creados = _ejecutar_main(base + ["--ejecutar"], clave="clave-de-prueba")
            assert codigo != 0 and creados == [] and not salida.exists(), texto
            assert "OPENAI_MODEL" in texto, texto
        finally:
            if modelo_anterior is not None:
                os.environ["OPENAI_MODEL"] = modelo_anterior

        codigo, texto, creados = _ejecutar_main(base + ["--ejecutar", "--modelo", "modelo-falso"], clave="clave-de-prueba")
        assert codigo == 0, texto
        assert len(creados) == 1
        resumen = json.loads((salida / "resumen_lote.json").read_text(encoding="utf-8"))
        n = resumen["llamadas_facturadas"]
        assert n > 0 and f"Llamadas facturadas: {n}" in texto, texto
        assert f"Tokens de entrada: {1500 * n}" in texto and f"de salida: {40 * n}" in texto, texto
        assert "sin precios" in texto, texto

        # con precios la consola da el coste en euros
        codigo, texto, _ = _ejecutar_main(
            argv(tmp_dir / "otra", tmp_dir / "otra_cache")
            + ["--ejecutar", "--modelo", "modelo-falso", "--precio-entrada", "2", "--precio-salida", "8"],
            clave="clave-de-prueba",
        )
        assert codigo == 0, texto
        coste = json.loads((tmp_dir / "otra" / "resumen_lote.json").read_text(encoding="utf-8"))["coste_eur"]
        assert abs(coste - (1500 * n * 2 + 40 * n * 8) / 1_000_000) < 1e-12, coste
        assert "Coste" in texto and "sin precios" not in texto, texto


def _salida_valida_del_agente1(tmp_dir: Path) -> dict[str, Any]:
    """Salida real del Agente 1 (con cliente falso) sobre el ejemplo 3: 3 hallazgos,
    uno `confirmed`, otro rechazado por la vision y otro `needs_review` por score."""
    ejemplo = Path(__file__).parent / "ejemplos" / "ejemplo_3_mixto_dificil.json"
    deteccion = json.loads(ejemplo.read_text(encoding="utf-8"))
    foto = tmp_dir / "foto.jpg"
    Image.new("RGB", (deteccion["image_width"], deteccion["image_height"]), "gray").save(foto)
    return analizar_imagen(ejemplo, ClienteFalso(), tmp_dir / "crops", modelo="modelo-falso",
                           image_path=foto, catalogo=MINI_CATALOGO)


def probar_ac004_validador_de_contrato() -> None:
    """PLAN + AC-004: el validador acepta una salida correcta y senala cada incumplimiento."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        valida = _salida_valida_del_agente1(tmp_dir)
        assert validar_salida_agente1(valida, MINI_CATALOGO, "000160.json", tmp_dir) == []
        assert validar_salida_agente1(valida, MINI_CATALOGO) == [], "sin nombre ni carpeta tambien valida"

        def con(cambio: Any) -> dict[str, Any]:
            copia = json.loads(json.dumps(valida))
            cambio(copia)
            return copia

        rechazado = next(i for i, f in enumerate(valida["findings"]) if f["vision_verdict"] == "rechazado")
        casos = {
            "falta un campo": (con(lambda s: s["findings"][0].pop("score")), "score"),
            "sobra un campo": (con(lambda s: s["findings"][0].update(extra=1)), "extra"),
            "veredicto fuera de la lista": (con(lambda s: s["findings"][0].update(vision_verdict="quizas")), "vision_verdict"),
            "nivel incoherente": (con(lambda s: s["findings"][0].update(
                confidence_tier="needs_review" if s["findings"][0]["confidence_tier"] == "confirmed" else "confirmed")), "confidence_tier"),
            "pieza fuera del catalogo": (con(lambda s: s["findings"][0].update(pieza_id="PUERTA_VOLADORA")), "pieza_id"),
            "rechazado con pieza": (con(lambda s: s["findings"][rechazado].update(pieza_id="NEUMATICO")), "pieza_id"),
            "severidad invalida": (con(lambda s: s["findings"][0].update(severidad="catastrofico")), "severidad"),
            "falta una clave de la salida": (con(lambda s: s.pop("resumen_filtro_previo")), "resumen_filtro_previo"),
            "candidatas no coincide con los findings": (con(lambda s: s["resumen_filtro_previo"].update(candidatas=99)), "candidatas"),
        }
        for nombre, (salida_mala, campo) in casos.items():
            errores = validar_salida_agente1(salida_mala, MINI_CATALOGO)
            assert errores, f"el validador acepto una salida con: {nombre}"
            assert any(campo in e for e in errores), f"{nombre}: los errores no nombran '{campo}': {errores}"

        # el nombre del fichero debe corresponder al image_id y el recorte debe existir
        assert any("image_id" in e for e in validar_salida_agente1(valida, MINI_CATALOGO, "000999.json"))
        sin_recorte = con(lambda s: s["findings"][0].update(crop_image_path="crops/no_existe.jpg"))
        assert any("crop_image_path" in e for e in validar_salida_agente1(sin_recorte, MINI_CATALOGO, None, tmp_dir))


def probar_ac004_los_json_del_lote_validan() -> None:
    """PLAN + AC-004: todo JSON guardado por generar_lote pasa el validador."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        export, cardd, imagenes = montar_datos(tmp_dir)
        salida = tmp_dir / "salida"
        _generar(tmp_dir, export, cardd, imagenes, ClienteFalso(), salida, tmp_dir / "cache")
        ficheros = sorted(p for p in salida.glob("[0-9]*.json"))
        assert len(ficheros) == 6
        for ruta in ficheros:
            errores = validar_salida_agente1(json.loads(ruta.read_text(encoding="utf-8")), MINI_CATALOGO, ruta.name, salida)
            assert errores == [], (ruta.name, errores)


def probar_ac006_repartos() -> None:
    """PLAN + AC-006: repartos por nivel, veredicto y clase iguales al recuento a mano, y aviso de muestra no representativa.

    Con ClienteFalso y las 18 imagenes del mini-export (cada una con un acierto de
    score 0,9 y un falso positivo de score 0,4 de otra clase), el recuento a mano es:
    dent y lamp broken: 6 hallazgos, todos `confirmado`, 3 `confirmed` (los de 0,9);
    tire flat: 6 `rechazado`, 0 `confirmed`; scratch y crack: 6 `incierto` cada una;
    glass shatter: 3 `incierto` (el falso positivo de 0,4 lo descarta el filtro previo: 3 descartados)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        export, cardd, imagenes = montar_datos(tmp_dir)
        lote = elegir_lote(imagenes, n=N_IMAGENES, min_aciertos=1, seed=42)
        resumen = generar_lote(lote, export, cardd, tmp_dir / "salida", ClienteFalso(), "modelo-falso", MINI_CATALOGO, tmp_dir / "cache")
        assert resumen["hallazgos"] == 33, resumen["hallazgos"]
        assert resumen["reparto_tier"] == {"confirmed": 6, "needs_review": 27}, resumen["reparto_tier"]
        assert resumen["reparto_veredicto"] == {"confirmado": 12, "incierto": 15, "rechazado": 6}, resumen["reparto_veredicto"]
        assert resumen["descartados_por_filtro_previo"] == 3
        esperado = {
            "dent": (6, 3, 3, 6, 0, 0), "lamp broken": (6, 3, 3, 6, 0, 0), "tire flat": (6, 0, 6, 0, 6, 0),
            "scratch": (6, 0, 6, 0, 0, 6), "crack": (6, 0, 6, 0, 0, 6), "glass shatter": (3, 0, 3, 0, 0, 3),
        }
        claves = ("hallazgos", "confirmed", "needs_review", "confirmado", "rechazado", "incierto")
        assert set(resumen["por_clase"]) == set(CLASES)
        for clase, cifras in esperado.items():
            assert resumen["por_clase"][clase] == dict(zip(claves, cifras)), (clase, resumen["por_clase"][clase])
        assert "no es representativo" in resumen["aviso_muestra"]

        # tambien por consola
        argv = ["--detecciones", str(export), "--cardd", str(cardd), "--salida", str(tmp_dir / "otra"),
                "--cache-dir", str(tmp_dir / "otra_cache"), "--n-imagenes", str(N_IMAGENES), "--min-aciertos", "1",
                "--ejecutar", "--modelo", "modelo-falso"]
        codigo, texto, _ = _ejecutar_main(argv, clave="clave-de-prueba")
        assert codigo == 0, texto
        assert "no es representativo" in texto.lower(), texto
        assert "confirmed: 6" in texto and "needs_review: 27" in texto, texto
        assert "descartados por el filtro previo: 3" in texto.lower(), texto


class ClienteQueFallaEnDent(ClienteFalso):
    """Como ClienteFalso, pero la API 'se cae' cuando el hallazgo es un dent."""

    def create(self, model: str, messages: list[dict], response_format: dict):
        if "tipo 'dent'" in messages[0]["content"][0]["text"]:
            raise RuntimeError("fallo simulado de la API")
        return super().create(model, messages, response_format)


def probar_ac007_un_fallo_no_tumba_el_lote() -> None:
    """PLAN + AC-007: foto ausente, foto ilegible, error de la API y salida invalida no tiran el lote."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        export, cardd, imagenes = montar_datos(tmp_dir)
        lote = elegir_lote(imagenes, n=6, min_aciertos=1, seed=42)
        ids = [i["image_id"] for i in lote]
        sin_foto, ilegible, con_salida_invalida = lote[0], lote[2], lote[3]

        def foto(img: dict[str, Any]) -> Path:
            return ruta_foto(cardd, img)

        foto(sin_foto).unlink()
        foto(ilegible).write_bytes(b"esto no es una imagen")
        con_dent = {
            i["image_id"] for i in lote
            if any(p["damage_class"] == "dent" for p in seleccionar_candidatos(i["predictions"])[0])
        }
        propios = {sin_foto["image_id"], ilegible["image_id"], con_salida_invalida["image_id"]}
        por_api = con_dent - propios
        fallan = propios | con_dent
        assert por_api and set(ids) - fallan, "la prueba seria vacua: hace falta al menos un fallo de API y un acierto"

        def validador(salida: dict, catalogo: Any, nombre: str, carpeta: Path) -> list[str]:
            if salida["image_id"] == con_salida_invalida["image_id"]:
                return ["error de prueba en el validador"]
            return validar_salida_agente1(salida, catalogo, nombre, carpeta)

        salida, cache = tmp_dir / "salida", tmp_dir / "cache"
        cliente = ClienteQueFallaEnDent()
        resumen = generar_lote(lote, export, cardd, salida, cliente, "modelo-falso", MINI_CATALOGO, cache, validar=validador)
        assert {f["image_id"] for f in resumen["fallos"]} == fallan, resumen["fallos"]
        assert resumen["imagenes"] == 6 and resumen["imagenes_ok"] == 6 - len(fallan)
        motivos = {f["image_id"]: f["motivo"] for f in resumen["fallos"]}
        assert "foto" in motivos[sin_foto["image_id"]].lower()
        assert "validador" in motivos[con_salida_invalida["image_id"]]
        assert all("fallo simulado de la API" in motivos[i] for i in por_api), motivos
        for i in ids:
            existe = (salida / f"{i:06d}.json").exists()
            assert existe == (i not in fallan), f"imagen {i}: existe={existe}"
        facturadas_1 = resumen["llamadas_facturadas"]

        # por consola: el lote termina, lista los fallos y el codigo es distinto de 0
        argv = ["--detecciones", str(export), "--cardd", str(cardd), "--salida", str(tmp_dir / "otra"),
                "--cache-dir", str(tmp_dir / "otra_cache"), "--n-imagenes", "6", "--min-aciertos", "1",
                "--ejecutar", "--modelo", "modelo-falso"]
        codigo, texto, _ = _ejecutar_main(argv, clave="clave-de-prueba", fabrica=ClienteQueFallaEnDent)
        assert codigo != 0, texto
        assert all(f"imagen {i}" in texto and "fallo" in texto.lower() for i in (sin_foto["image_id"], ilegible["image_id"])), texto

        # tras corregir la causa, solo se factura lo que faltaba: cada hallazgo se paga una unica vez
        Image.new("RGB", (200, 100), "gray").save(foto(sin_foto))
        Image.new("RGB", (200, 100), "gray").save(foto(ilegible))
        recuperado = generar_lote(lote, export, cardd, salida, ClienteFalso(), "modelo-falso", MINI_CATALOGO, cache)
        assert recuperado["fallos"] == [] and recuperado["imagenes_ok"] == 6
        assert facturadas_1 + recuperado["llamadas_facturadas"] == llamadas_previstas(lote), (facturadas_1, recuperado)
        assert recuperado["llamadas_facturadas"] > 0
        assert len(list(salida.glob("[0-9]*.json"))) == 6


def probar_ac008_nada_sensible_en_git_ni_en_lo_escrito() -> None:
    """PLAN + AC-008: rutas por defecto ignoradas por git, sin clave ni rutas absolutas en lo escrito."""
    rutas = rutas_por_defecto()
    raiz = RAIZ_REPO
    for nombre in ("detecciones", "salida", "cache"):
        ruta = rutas[nombre]
        assert raiz / "piia2_detecciones" in ruta.parents, f"{nombre}: {ruta} no esta bajo piia2_detecciones/"
        ignorado = subprocess.run(["git", "check-ignore", "-q", str(ruta / "x.json")], cwd=raiz)
        assert ignorado.returncode == 0, f"git no ignora {ruta}"
    assert rutas["cardd"].parts[-2:] == ("CarDD_release", "CarDD_COCO") or "CarDD_release" in rutas["cardd"].parts

    clave = "clave-de-prueba-9f3a-no-debe-salir"
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        export, cardd, _ = montar_datos(tmp_dir)
        salida, cache = tmp_dir / "salida", tmp_dir / "cache"
        argv = ["--detecciones", str(export), "--cardd", str(cardd), "--salida", str(salida), "--cache-dir", str(cache),
                "--n-imagenes", "6", "--min-aciertos", "1", "--ejecutar", "--modelo", "modelo-falso"]
        codigo, texto, _ = _ejecutar_main(argv, clave=clave)
        assert codigo == 0, texto
        assert clave not in texto, "la clave salio por consola"

        escritos = [p for p in tmp_dir.rglob("*") if p.is_file() and (p.is_relative_to(salida) or p.is_relative_to(cache))]
        assert escritos, "no se escribio nada"
        absoluta = re.compile(r"[A-Za-z]:[\\/]|/Users/|/home/|/content/drive")
        for ruta in escritos:
            if ruta.suffix != ".json":
                continue
            contenido = ruta.read_text(encoding="utf-8")
            assert clave not in contenido, f"la clave esta en {ruta.name}"
            if ruta.parent == salida:  # salidas y resumen: sin rutas de esta maquina
                assert str(tmp_dir) not in contenido and not absoluta.search(contenido), f"ruta absoluta en {ruta.name}"


def probar_ac001_ac002_con_datos_reales() -> None:
    """PLAN + AC-001 y AC-002 con el export de 500 imagenes y las fotos locales (se salta si faltan)."""
    rutas = rutas_por_defecto()
    if not rutas["detecciones"].exists() or not rutas["cardd"].exists():
        print("(faltan las detecciones exportadas o el CarDD local: se salta la prueba con datos reales)")
        return
    imagenes = cargar(rutas["detecciones"])
    lote = elegir_lote(imagenes, n=30, min_aciertos=3, seed=42)
    ids = [i["image_id"] for i in lote]
    assert len(ids) == len(set(ids)) == 30
    cuenta = _aciertos_por_clase(lote)
    assert all(cuenta[c] >= 3 for c in CLASES), cuenta
    assert ids == [i["image_id"] for i in elegir_lote(imagenes, n=30, min_aciertos=3, seed=42)], "no determinista"
    assert fotos_que_faltan(lote, rutas["cardd"]) == [], "faltan fotos locales"
    llamadas = llamadas_previstas(lote)
    assert 0 < llamadas <= 300, f"el lote por defecto ({llamadas} llamadas) no cabe en el tope por defecto"

    # el plan por defecto no escribe nada (la carpeta de salida por defecto no se crea)
    existia = rutas["salida"].exists()
    codigo, texto, creados = _ejecutar_main([])
    assert codigo == 0 and creados == [] and "30 imagenes" in texto, texto
    assert rutas["salida"].exists() == existia, "el modo plan creo la carpeta de salida"
    print(f"datos reales ok: 30 imagenes, {llamadas} llamadas previstas, aciertos por clase {dict(cuenta)}")


def main_pruebas() -> None:
    probar_ac001_ac002_con_datos_reales()
    probar_ac001_seleccion_reproducible()
    probar_ac002_plan_sin_gastar_y_tope()
    probar_ac003_un_json_por_imagen_con_cache()
    probar_ac004_validador_de_contrato()
    probar_ac004_los_json_del_lote_validan()
    probar_ac005_uso_y_coste()
    probar_ac006_repartos()
    probar_ac007_un_fallo_no_tumba_el_lote()
    probar_ac008_nada_sensible_en_git_ni_en_lo_escrito()
    probar_ejecucion_completa_por_consola()
    print("Todo ok: generar_lote.")


if __name__ == "__main__":
    main_pruebas()
