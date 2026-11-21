"""Prueba la herramienta de validacion manual de la categoria del vehiculo (AC-011 de
`entregas/cu-19-interpretacion-danos/specs/28-categoria-vehiculo.md`) sin API Key ni red. Se ejecuta desde esta
carpeta con `python probar_evaluar_vehiculo_stub.py`.

AC-011 se valida con el modelo real y la mirada de una persona; esto solo comprueba la parte determinista que la
rodea: que la muestra es la prevista (`random.Random(28).sample(sorted(ids), 20)`), que la plantilla no revela la
respuesta del modelo, que se hace una consulta por foto con cache, que los juicios se leen y validan, y que el
informe da la tasa de coincidencia, la matriz de confusion, la referencia de la categoria mas frecuente y el limite
de 20 fotos. Cada prueba lleva la referencia `28-categoria-vehiculo.md#AC-011`.
"""

from __future__ import annotations

import contextlib
import csv
import io
import json
import random
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any

from PIL import Image

import evaluar_vehiculo as ev
from probar_vision_stub import _Eleccion, _Mensaje, _Respuesta, _Uso
from vehiculo import CATEGORIAS, DESCONOCIDO, PROMPT_VEHICULO

CLAVES_VEHICULO = {"categoria", "vehiculo_id_referencia", "confianza", "descripcion", "modelo"}


def _export(n: int = 40) -> list[dict[str, Any]]:
    """`n` imagenes con la forma que necesita la herramienta del export de PIIA-1 (ids no consecutivos)."""
    return [
        {"image_id": 10 + 3 * i, "image_file": f"{10 + 3 * i:06d}.jpg", "split": "val" if i % 2 else "test"}
        for i in range(n)
    ]


def _cardd(carpeta: Path, imagenes: list[dict[str, Any]]) -> Path:
    """Un CarDD falso con una foto (grande, de un color distinto cada una, para que no compartan cache) por imagen,
    en `<split>2017/<fichero>`."""
    for img in imagenes:
        destino = carpeta / f"{img['split']}2017" / img["image_file"]
        destino.parent.mkdir(parents=True, exist_ok=True)
        i = img["image_id"]
        Image.new("RGB", (1400, 900), (i % 251, (i * 7) % 251, (i * 13) % 251)).save(destino)
    return carpeta


class ClienteCategorias:
    """Cliente falso de la consulta de categoria: guarda cada peticion y contesta con `respuesta(n)`, donde `n` es
    el numero de la llamada (desde 1); si devuelve una excepcion, la lanza."""

    def __init__(self, respuesta=None) -> None:
        self.chat = self
        self.completions = self
        self.peticiones: list[dict[str, Any]] = []
        self.respuesta = respuesta or (lambda n: {"categoria": "C", "confianza": "media", "descripcion": f"Compacto {n}."})

    def create(self, model: str, messages: list[dict[str, Any]], response_format: dict) -> _Respuesta:
        self.peticiones.append({"model": model, "messages": messages})
        contenido = self.respuesta(len(self.peticiones))
        if isinstance(contenido, Exception):
            raise contenido
        return _Respuesta([_Eleccion(_Mensaje(json.dumps(contenido)))], _Uso(900, 60))


def _imagenes_de(peticion: dict[str, Any]) -> list[dict[str, Any]]:
    return [p for p in peticion["messages"][0]["content"] if p["type"] == "image_url"]


def _muestra_de_prueba() -> list[dict[str, Any]]:
    return ev.elegir_muestra(_export(), ev.N_MUESTRA, ev.SEMILLA)


def _escribir_juicios(ruta: Path, juicios: dict[int, str], delimitador: str = ";", bom: bool = True) -> None:
    with open(ruta, "w", encoding="utf-8-sig" if bom else "utf-8", newline="") as f:
        escritor = csv.writer(f, delimiter=delimitador)
        escritor.writerow(["image_id", "foto", "categoria_humana"])
        for image_id, categoria in juicios.items():
            escritor.writerow([image_id, f"{image_id:06d}.jpg", categoria])


def probar_ac011_muestra_reproducible() -> None:
    """28-categoria-vehiculo.md#AC-011: la muestra es `random.Random(28).sample(sorted(ids), 20)` y otra semilla da otra."""
    imagenes = _export(500)
    esperada = random.Random(28).sample(sorted(i["image_id"] for i in imagenes), 20)
    muestra = ev.elegir_muestra(imagenes, 20, 28)
    assert [i["image_id"] for i in muestra] == esperada, ([i["image_id"] for i in muestra], esperada)
    assert len(set(esperada)) == 20
    # el orden de entrada no cambia la muestra: se ordena por id antes de muestrear
    assert [i["image_id"] for i in ev.elegir_muestra(imagenes[::-1], 20, 28)] == esperada
    otra = [i["image_id"] for i in ev.elegir_muestra(imagenes, 20, 29)]
    assert otra != esperada, "otra semilla debe dar otra muestra"
    assert ev.N_MUESTRA == 20 and ev.SEMILLA == 28


def probar_ac011_plantilla_ciega_y_fotos() -> None:
    """28-categoria-vehiculo.md#AC-011: la persona juzga sin ver la respuesta: la plantilla solo tiene
    `image_id`, `foto` y una columna vacia, y las fotos se copian con el nombre del export."""
    muestra = _muestra_de_prueba()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        cardd = _cardd(tmp_dir / "cardd", muestra)
        salida = tmp_dir / "salida"
        resumen = ev.preparar_muestra(muestra, cardd, salida)
        assert resumen == {"fotos_copiadas": 20, "faltan": [], "plantilla_conservada": False}, resumen
        for img in muestra:
            assert (salida / "fotos" / img["image_file"]).exists(), img["image_file"]
        with open(salida / "plantilla_juicio.csv", encoding="utf-8-sig", newline="") as f:
            filas = list(csv.reader(f, delimiter=";"))
        assert filas[0] == ["image_id", "foto", "categoria_humana"], filas[0]
        assert sorted(int(f[0]) for f in filas[1:]) == sorted(i["image_id"] for i in muestra)
        assert all(f[2] == "" for f in filas[1:]), "la plantilla no puede venir rellena"
        assert not (salida / "respuestas_modelo.json").exists(), "la plantilla no depende de la respuesta del modelo"
        # la guia es la misma que ve el modelo: cada categoria y `desconocido`, tomadas de PROMPT_VEHICULO
        guia = ev.guia_de_categorias()
        for categoria in (*CATEGORIAS, DESCONOCIDO):
            assert f'"{categoria}"' in guia, categoria
            assert f'"{categoria}"' in PROMPT_VEHICULO
        assert guia.strip() in PROMPT_VEHICULO, "la guia debe copiar las definiciones del prompt, no reescribirlas"
        assert (salida / "guia_categorias.txt").read_text(encoding="utf-8").strip() == guia.strip()
        # una foto que falta se avisa, sin excepcion
        (cardd / f"{muestra[0]['split']}2017" / muestra[0]["image_file"]).unlink()
        assert ev.preparar_muestra(muestra, cardd, tmp_dir / "otra")["faltan"] == [muestra[0]["image_file"]]


def probar_ac011_no_pisa_los_juicios_ya_escritos() -> None:
    """28-categoria-vehiculo.md#AC-011: repetir `muestra` no borra los juicios que la persona ya ha escrito (son
    horas de trabajo a ciegas); una plantilla vacia, en cambio, se puede volver a crear."""
    muestra = _muestra_de_prueba()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        cardd, salida = _cardd(tmp_dir / "cardd", muestra), tmp_dir / "salida"
        ev.preparar_muestra(muestra, cardd, salida)
        plantilla = salida / "plantilla_juicio.csv"
        vacia = plantilla.read_bytes()
        assert ev.preparar_muestra(muestra, cardd, salida)["plantilla_conservada"] is False, "una plantilla vacia se recrea"
        assert plantilla.read_bytes() == vacia

        _escribir_juicios(plantilla, {i["image_id"]: "C" for i in muestra})
        escrita = plantilla.read_bytes()
        resumen = ev.preparar_muestra(muestra, cardd, salida)
        assert resumen["plantilla_conservada"] is True and plantilla.read_bytes() == escrita, "se han pisado los juicios"

        plantilla.write_bytes(b"esto no es una plantilla\n")  # ilegible: mejor no tocarla
        assert ev.preparar_muestra(muestra, cardd, salida)["plantilla_conservada"] is True
        assert plantilla.read_bytes() == b"esto no es una plantilla\n"


def probar_ac011_una_consulta_por_foto_con_cache() -> None:
    """28-categoria-vehiculo.md#AC-011: una consulta de categoria por foto (una imagen, el prompt de la #28), la
    respuesta se guarda y una segunda ejecucion con la misma cache no vuelve a facturar."""
    muestra = _muestra_de_prueba()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        cardd, cache, salida = _cardd(tmp_dir / "cardd", muestra), tmp_dir / "cache", tmp_dir / "salida"
        cliente = ClienteCategorias()
        resumen = ev.consultar_muestra(muestra, cardd, cliente, "modelo-falso", cache, salida)
        assert resumen["consultadas"] == 20 and resumen["fallos"] == [], resumen
        assert resumen["llamadas_facturadas"] == 20 and len(cliente.peticiones) == 20
        assert resumen["tokens_entrada"] == 20 * 900 and resumen["tokens_salida"] == 20 * 60
        for peticion in cliente.peticiones:
            assert len(_imagenes_de(peticion)) == 1
            assert peticion["messages"][0]["content"][0]["text"] == PROMPT_VEHICULO
            assert peticion["model"] == "modelo-falso"
        guardado = json.loads((salida / "respuestas_modelo.json").read_text(encoding="utf-8"))
        assert guardado["modelo"] == "modelo-falso" and guardado["n"] == 20
        assert sorted(int(k) for k in guardado["respuestas"]) == sorted(i["image_id"] for i in muestra)
        for vehiculo in guardado["respuestas"].values():
            assert set(vehiculo) == CLAVES_VEHICULO, set(vehiculo)

        segundo = ClienteCategorias()
        resumen2 = ev.consultar_muestra(muestra, cardd, segundo, "modelo-falso", cache, salida)
        assert resumen2["llamadas_facturadas"] == 0 and segundo.peticiones == [], "la cache debe evitar el gasto"
        assert json.loads((salida / "respuestas_modelo.json").read_text(encoding="utf-8")) == guardado


def probar_ac011_un_fallo_no_tumba_la_muestra() -> None:
    """28-categoria-vehiculo.md#AC-011: si el proveedor falla en una foto se anota y se sigue; al repetir solo se
    factura la que faltaba."""
    muestra = _muestra_de_prueba()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        cardd, cache, salida = _cardd(tmp_dir / "cardd", muestra), tmp_dir / "cache", tmp_dir / "salida"
        cliente = ClienteCategorias(lambda n: TimeoutError("timeout simulado") if n == 3 else {"categoria": "B", "confianza": "alta", "descripcion": "x"})
        resumen = ev.consultar_muestra(muestra, cardd, cliente, "modelo-falso", cache, salida)
        assert resumen["consultadas"] == 19 and len(resumen["fallos"]) == 1, resumen
        fallo = resumen["fallos"][0]
        assert fallo["image_id"] in {i["image_id"] for i in muestra} and "timeout simulado" in fallo["motivo"], fallo
        guardado = json.loads((salida / "respuestas_modelo.json").read_text(encoding="utf-8"))
        assert len(guardado["respuestas"]) == 19 and str(fallo["image_id"]) not in guardado["respuestas"]

        reintento = ClienteCategorias()
        resumen2 = ev.consultar_muestra(muestra, cardd, reintento, "modelo-falso", cache, salida)
        assert resumen2["consultadas"] == 20 and resumen2["fallos"] == []
        assert resumen2["llamadas_facturadas"] == 1 and len(reintento.peticiones) == 1, "solo la que fallo se vuelve a pagar"


def probar_ac011_lectura_y_validacion_de_juicios() -> None:
    """28-categoria-vehiculo.md#AC-011: el CSV de juicios se lee con `;` (Excel en espanol) o con `,`, con o sin BOM,
    normaliza mayusculas; si falta un juicio o la categoria no existe, dice cual."""
    juicios = {10: "B", 13: "suv-c", 16: "Desconocido", 19: " C-premium ", 22: "FURG"}
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "j.csv"
        esperado = {10: "B", 13: "SUV-C", 16: "desconocido", 19: "C-PREMIUM", 22: "FURG"}
        for delimitador, bom in ((";", True), (",", False), (";", False), (",", True)):
            _escribir_juicios(ruta, juicios, delimitador, bom)
            assert ev.leer_juicios(ruta) == esperado, (delimitador, bom)

        _escribir_juicios(ruta, {**juicios, 25: "", 28: "  "})
        try:
            ev.leer_juicios(ruta)
            raise AssertionError("debia fallar: hay juicios sin rellenar")
        except ev.JuiciosNoValidos as error:
            assert "25" in str(error) and "28" in str(error), error

        _escribir_juicios(ruta, {**juicios, 31: "sedan"})
        try:
            ev.leer_juicios(ruta)
            raise AssertionError("debia fallar: categoria inexistente")
        except ev.JuiciosNoValidos as error:
            texto = str(error)
            assert "31" in texto and "sedan" in texto and "SUV-B" in texto and "desconocido" in texto, texto


def _caso_metricas(modelo_por_humano: list[tuple[str, str]]) -> dict[str, Any]:
    ids = [100 + i for i in range(len(modelo_por_humano))]
    juicios = {i: humano for i, (humano, _) in zip(ids, modelo_por_humano)}
    respuestas = {
        i: {"categoria": modelo, "confianza": "media", "descripcion": f"Coche {i}.", "vehiculo_id_referencia": None, "modelo": "m"}
        for i, (_, modelo) in zip(ids, modelo_por_humano)
    }
    return ev.evaluar(respuestas, juicios)


def probar_ac011_tasa_matriz_y_referencia() -> None:
    """28-categoria-vehiculo.md#AC-011: coincidencia exacta, matriz de confusion y tasa de predecir siempre la
    categoria mas frecuente de la muestra (calculada con los juicios de la persona)."""
    pares = (
        [("B", "B")] * 6 + [("B", "C")] * 2          # 8 B, 2 mal
        + [("C", "C")] * 4 + [("C", "B")]            # 5 C, 1 mal
        + [("SUV-C", "SUV-C")] * 3 + [("SUV-C", "SUV-B")]  # 4 SUV-C, 1 mal
        + [("FURG", "FURG")] * 2                     # 2 FURG
        + [("desconocido", "desconocido")]           # 1 desconocido
    )
    assert len(pares) == 20
    r = _caso_metricas(pares)
    assert r["n"] == 20 and r["aciertos"] == 16 and abs(r["tasa"] - 0.8) < 1e-9, (r["aciertos"], r["tasa"])
    assert r["matriz"]["B"]["B"] == 6 and r["matriz"]["B"]["C"] == 2
    assert r["matriz"]["C"]["B"] == 1 and r["matriz"]["SUV-C"]["SUV-B"] == 1
    assert sum(sum(fila.values()) for fila in r["matriz"].values()) == 20
    assert r["referencia"] == {"categoria": "B", "aciertos": 8, "tasa": 0.4, "empate": []}, r["referencia"]
    assert abs(r["error_en_puntos"] - 5.0) < 1e-9
    assert [f["coincide"] for f in r["filas"]].count(False) == 4
    assert r["filas"] == sorted(r["filas"], key=lambda f: f["image_id"])

    # empate: se elige la primera en el orden del catalogo y se avisa
    empatados = _caso_metricas([("C", "C")] * 3 + [("B", "B")] * 3 + [("A", "A")])
    assert empatados["referencia"]["categoria"] == "B" and empatados["referencia"]["empate"] == ["B", "C"], empatados["referencia"]

    # los juicios y las respuestas deben ser de las mismas fotos
    try:
        ev.evaluar({1: {"categoria": "B", "confianza": "alta", "descripcion": ""}}, {1: "B", 2: "C"})
        raise AssertionError("debia fallar: falta la respuesta del modelo de una foto juzgada")
    except ValueError as error:
        assert "2" in str(error), error


def probar_ac011_descripciones_con_datos_personales() -> None:
    """28-categoria-vehiculo.md#AC-011: ninguna descripcion puede llevar una matricula legible ni datos personales;
    la herramienta marca las que lo parecen para que la persona las revise (las demas, no)."""
    marcadas = (
        "Turismo compacto gris, matricula 1234 BCD.",
        "Turismo gris con la matricula M-1234-AB visible.",
        "Utilitario con una persona al lado.",
        "Coche del propietario, un hombre mayor.",
    )
    limpias = (
        "SUV mediano de color gris, parece un Peugeot 3008.",
        "Berlina premium azul, quizas un BMW Serie 3.",
        "Furgoneta blanca, Renault Kangoo.",
        "Utilitario rojo, seat Ibiza o similar.",
        "",
    )
    for texto in marcadas:
        assert ev.datos_sospechosos(texto), f"debia marcarse: {texto!r}"
    for texto in limpias:
        assert ev.datos_sospechosos(texto) == [], f"no debia marcarse: {texto!r} -> {ev.datos_sospechosos(texto)}"


def probar_ac011_informe() -> None:
    """28-categoria-vehiculo.md#AC-011: el informe da la tabla por imagen, la tasa, la matriz, la referencia, el
    limite de 20 fotos y las descripciones a revisar, en el formato de la PR de entrega."""
    pares = [("B", "B")] * 6 + [("B", "C")] * 2 + [("C", "C")] * 4 + [("C", "B")] + [("SUV-C", "SUV-C")] * 3 + [("SUV-C", "SUV-B")] + [("FURG", "FURG")] * 2 + [("desconocido", "desconocido")]
    r = _caso_metricas(pares)
    r["filas"][0]["descripcion"] = "Turismo gris con la matricula 1234 BCD."
    r["sospechosas"] = [
        {"image_id": r["filas"][0]["image_id"], "motivos": ev.datos_sospechosos(r["filas"][0]["descripcion"]), "descripcion": r["filas"][0]["descripcion"]}
    ]
    texto = ev.informe_markdown(r, "gpt-ejemplo", 28)
    for esperado in (
        "gpt-ejemplo", "28", "16 de 20", "80,0 %",                # modelo, semilla, tasa
        "8 de 20", "40,0 %", "`B`",                                # referencia de la categoria mas frecuente
        "un error son 5 puntos",                                   # limite de la muestra
        "Matriz de confusi",                                       # matriz
        "| 100 |", "| 119 |",                                      # tabla por imagen
        "1234 BCD",                                                # descripcion a revisar
    ):
        assert esperado in texto, f"falta {esperado!r} en el informe:\n{texto}"
    assert "No se fija umbral" in texto or "sin umbral" in texto.lower(), "debe recordar que no hay umbral de aceptacion"
    limpio = ev.informe_markdown(_caso_metricas(pares), "gpt-ejemplo", 28)
    assert "Ninguna descripci" in limpio, "sin sospechosas debe decirlo"


def probar_ac011_flujo_completo_por_consola() -> None:
    """28-categoria-vehiculo.md#AC-011: muestra (gratis) -> consultar (plan sin gastar; con --ejecutar, una consulta
    por foto, sin imprimir la categoria) -> la persona rellena la plantilla -> evaluar (rechaza una plantilla
    incompleta y, completa, escribe el informe)."""
    imagenes = _export(40)
    muestra = ev.elegir_muestra(imagenes, 20, 28)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        detecciones = tmp_dir / "detecciones"
        detecciones.mkdir()
        for img in imagenes:
            (detecciones / f"{img['image_id']:06d}.json").write_text(json.dumps(img), encoding="utf-8")
        cardd, salida, cache = _cardd(tmp_dir / "cardd", imagenes), tmp_dir / "salida", tmp_dir / "cache"
        base = ["--detecciones", str(detecciones), "--cardd", str(cardd), "--salida", str(salida)]

        def ejecutar(*args: str, crear_cliente=None) -> tuple[int, str]:
            salida_estandar = io.StringIO()
            with contextlib.redirect_stdout(salida_estandar):
                codigo = ev.main([*args], crear_cliente=crear_cliente)
            return codigo, salida_estandar.getvalue()

        def sin_cliente() -> Any:
            raise AssertionError("el plan no debe crear el cliente ni llamar a la API")

        codigo, texto = ejecutar("muestra", *base)
        assert codigo == 0 and (salida / "plantilla_juicio.csv").exists() and len(list((salida / "fotos").iterdir())) == 20, texto

        codigo, texto = ejecutar("consultar", *base, "--cache-dir", str(cache), "--modelo", "modelo-falso", crear_cliente=sin_cliente)
        assert codigo == 0 and "PLAN SOLO" in texto and "20" in texto, texto
        assert not (salida / "respuestas_modelo.json").exists(), "el plan no escribe nada"

        cliente = ClienteCategorias(lambda n: {"categoria": "SUV-B", "confianza": "alta", "descripcion": "SECRETO descripcion del modelo."})
        codigo, texto = ejecutar("consultar", "--ejecutar", *base, "--cache-dir", str(cache), "--modelo", "modelo-falso", crear_cliente=lambda: cliente)
        assert codigo == 0 and len(cliente.peticiones) == 20, (codigo, len(cliente.peticiones), texto)
        assert "SECRETO" not in texto and "SUV-B" not in texto, "consultar no debe enseñar la respuesta del modelo"

        codigo, texto = ejecutar("evaluar", *base)
        assert codigo == 2 and not (salida / "resultado.md").exists(), "con la plantilla vacia no se evalua"
        assert "categoria_humana" in texto or "sin rellenar" in texto, texto

        ids = [i["image_id"] for i in muestra]
        _escribir_juicios(salida / "plantilla_juicio.csv", {i: ("SUV-B" if k < 15 else "C") for k, i in enumerate(sorted(ids))})
        codigo, texto = ejecutar("evaluar", *base)
        assert codigo == 0 and (salida / "resultado.md").exists(), texto
        informe = (salida / "resultado.md").read_text(encoding="utf-8")
        assert "15 de 20" in informe and "75,0 %" in informe and "modelo-falso" in informe, informe
        assert "15 de 20" in texto, "el informe tambien se imprime para pegarlo en la PR"


PRUEBAS = (
    probar_ac011_muestra_reproducible,
    probar_ac011_plantilla_ciega_y_fotos,
    probar_ac011_no_pisa_los_juicios_ya_escritos,
    probar_ac011_una_consulta_por_foto_con_cache,
    probar_ac011_un_fallo_no_tumba_la_muestra,
    probar_ac011_lectura_y_validacion_de_juicios,
    probar_ac011_tasa_matriz_y_referencia,
    probar_ac011_descripciones_con_datos_personales,
    probar_ac011_informe,
    probar_ac011_flujo_completo_por_consola,
)


def main() -> int:
    fallos = 0
    for prueba in PRUEBAS:
        try:
            prueba()
            print(f"ok     {prueba.__name__}")
        except Exception as e:  # noqa: BLE001 - se informa cada fallo y se sigue con la siguiente prueba
            fallos += 1
            ultima = traceback.extract_tb(e.__traceback__)[-1]
            print(f"FALLA  {prueba.__name__}: {type(e).__name__}: {e} ({ultima.name}, linea {ultima.lineno})")
    if fallos:
        print(f"\n{fallos} de {len(PRUEBAS)} pruebas fallan.")
        return 1
    print(f"\nTodo ok: validacion manual de la categoria del vehiculo ({len(PRUEBAS)} pruebas).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
