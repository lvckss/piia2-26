"""Prueba la categoria del vehiculo del Agente 1 (Issue #28, ADR 0001) sin API Key ni red.

Cada prueba lleva en su nombre y su docstring la referencia `28-categoria-vehiculo.md#AC-0XX` de la
spec `entregas/cu-19-interpretacion-danos/specs/28-categoria-vehiculo.md`. Se ejecuta desde esta carpeta
con `python probar_vehiculo_stub.py`.

Las pruebas pasan por `analizar_imagen` (seam S1) con un cliente falso (seam S2) que distingue la consulta de
categoria del vehiculo (lleva UNA imagen) de las consultas por hallazgo (llevan DOS) y responde a la primera
con el texto guionizado de cada caso. AC-004 lee `vehiculos.csv` del paquete de la empresa (seam S3).
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops

import analizar_detecciones
import evaluar_vision
from agente1 import analizar_imagen
from catalogo import datos_empresa_dir, lista_piezas_para_prompt
from hallazgos import cargar_detecciones, construir_hallazgos
from probar_vision_stub import MINI_CATALOGO, RESPUESTAS_POR_CLASE, ClienteFalso, _Eleccion, _Mensaje, _Respuesta, _Uso
from recorte import generar_recortes, imagen_con_caja
from vision import PROMPT_TEMPLATE, _jpeg_base64, analizar_hallazgo, enriquecer_con_vision

EJEMPLO = Path(__file__).parent / "ejemplos" / "ejemplo_3_mixto_dificil.json"
CATEGORIAS = ("A", "B", "C", "SUV-B", "SUV-C", "FURG", "C-PREMIUM", "D-PREMIUM")
CLAVES_VEHICULO = {"categoria", "vehiculo_id_referencia", "confianza", "descripcion", "modelo"}


def _imagenes(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [parte for parte in messages[0]["content"] if parte["type"] == "image_url"]


class ClienteVehiculo(ClienteFalso):
    """Como ClienteFalso para los hallazgos; la consulta de categoria (una sola imagen) se guarda en
    `consultas_vehiculo` y se responde con `respuesta` (texto) o se lanza si `respuesta` es una excepcion."""

    def __init__(self, respuesta: str | Exception) -> None:
        super().__init__()
        self.respuesta = respuesta
        self.consultas_vehiculo: list[dict[str, Any]] = []

    def create(self, model: str, messages: list[dict[str, Any]], response_format: dict) -> _Respuesta:
        if len(_imagenes(messages)) != 1:
            return super().create(model, messages, response_format)
        self.consultas_vehiculo.append({"model": model, "messages": messages, "response_format": response_format})
        if isinstance(self.respuesta, Exception):
            raise self.respuesta
        return _Respuesta([_Eleccion(_Mensaje(self.respuesta))], _Uso(900, 60))


# (clase, score) de las predicciones de una imagen con N hallazgos candidatos tras el filtro previo (2 mejores por clase)
PREDICCIONES = {
    0: [],
    1: [("lamp broken", 0.91)],
    5: [("lamp broken", 0.91), ("lamp broken", 0.80), ("dent", 0.70), ("dent", 0.60), ("tire flat", 0.50)],
}


def _deteccion(n: int, ancho: int, alto: int) -> dict[str, Any]:
    """JSON de PIIA-1 de una imagen con `n` hallazgos candidatos (0, 1 o 5)."""
    predicciones = [
        {"instance_index": i + 1, "damage_class": clase, "category_id": 1, "score": score,
         "bbox_xywh": [100.0 * (i + 1), 100.0, 200.0, 150.0], "area": 30000.0}
        for i, (clase, score) in enumerate(PREDICCIONES[n])
    ]
    return {"image_id": 7, "variant": "baseline", "strategy_name": "baseline_prompt", "image_path": "no-se-usa.jpg",
            "image_width": ancho, "image_height": alto, "num_predictions": len(predicciones), "predictions": predicciones}


def _analizar(respuesta: str | Exception, cache_dir: Path | None = None, n: int | None = None,
              tam_foto: tuple[int, int] | None = None) -> tuple[dict, dict, ClienteVehiculo]:
    """Ejecuta el Agente 1 sobre una foto gris sintetica y devuelve (resultado, JSON guardado en disco, cliente).
    Sin `n`, usa el ejemplo de 3 hallazgos; con `n` (0, 1 o 5), una imagen con ese numero de hallazgos candidatos."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        if n is None:
            ruta = EJEMPLO
            deteccion = json.loads(EJEMPLO.read_text(encoding="utf-8"))
            tam = tam_foto or (deteccion["image_width"], deteccion["image_height"])
        else:
            tam = tam_foto or (2400, 1600)
            ruta = tmp_dir / "deteccion.json"
            ruta.write_text(json.dumps(_deteccion(n, *tam)), encoding="utf-8")
        foto = tmp_dir / "foto.jpg"
        Image.new("RGB", tam, "gray").save(foto)
        salida = tmp_dir / "salida" / "hallazgos.json"
        cliente = ClienteVehiculo(respuesta)
        resultado = analizar_imagen(
            ruta, cliente, tmp_dir / "crops", modelo="modelo-falso", image_path=foto, output_path=salida,
            catalogo=MINI_CATALOGO, cache_dir=cache_dir,
        )
        guardado = json.loads(salida.read_text(encoding="utf-8"))
    return resultado, guardado, cliente


def _imagen_enviada(parte: dict[str, Any]) -> Image.Image:
    """Decodifica la imagen (data URL en base64) que el cliente falso recibio en una consulta."""
    datos = parte["image_url"]["url"].split(",", 1)[1]
    imagen = Image.open(io.BytesIO(base64.b64decode(datos)))
    imagen.load()
    return imagen


def _respuesta(categoria: Any, confianza: Any = "media", descripcion: str = "Turismo de color gris.") -> str:
    return json.dumps({"categoria": categoria, "confianza": confianza, "descripcion": descripcion})


def _vehiculos_csv() -> list[dict[str, str]] | None:
    ruta = datos_empresa_dir() / "vehiculos.csv"
    if not ruta.exists():
        return None
    with open(ruta, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def probar_ac002_respuestas_invalidas() -> None:
    """28-categoria-vehiculo.md#AC-002: categoria fuera de la lista, no JSON, JSON sin `categoria` o vacia."""
    invalidas = {
        "categoria inventada": _respuesta("Z-INVENTADA", "alta"),
        "categoria que no es texto": _respuesta(5, "alta"),
        "categoria que es una lista": _respuesta(["A"], "alta"),
        "texto que no es JSON": "esto no es un json",
        "JSON sin `categoria`": json.dumps({"confianza": "alta", "descripcion": "x"}),
        "cadena vacia": "",
    }
    for nombre, texto in invalidas.items():
        resultado, _, _ = _analizar(texto)
        vehiculo = resultado["vehiculo"]
        assert vehiculo["categoria"] == "desconocido", (nombre, vehiculo)
        assert vehiculo["confianza"] == "baja", (nombre, vehiculo)
        assert vehiculo["vehiculo_id_referencia"] is None, (nombre, vehiculo)


def probar_ac003_confianza_normalizada() -> None:
    """28-categoria-vehiculo.md#AC-003: `desconocido` con confianza `alta` y confianza fuera de alta/media/baja."""
    resultado, _, _ = _analizar(_respuesta("desconocido", "alta"))
    assert resultado["vehiculo"]["categoria"] == "desconocido"
    assert resultado["vehiculo"]["confianza"] == "baja", resultado["vehiculo"]

    for rara in ("muy alta", "ALTA", "", 5, None):
        resultado, _, _ = _analizar(_respuesta("C", rara))
        assert resultado["vehiculo"]["categoria"] == "C", resultado["vehiculo"]
        assert resultado["vehiculo"]["confianza"] == "baja", (rara, resultado["vehiculo"])

    for valida in ("alta", "media", "baja"):
        resultado, _, _ = _analizar(_respuesta("C", valida))
        assert resultado["vehiculo"]["confianza"] == valida, (valida, resultado["vehiculo"])


def probar_ac004_ocho_categorias() -> None:
    """28-categoria-vehiculo.md#AC-004: cada categoria valida (con y sin bloque ```json) da un coche de referencia
    que existe en `vehiculos.csv` con ese `segmento`; `desconocido` da `null`."""
    vehiculos = _vehiculos_csv()
    if vehiculos is None:
        print("AVISO: falta vehiculos.csv del paquete de la empresa; se salta AC-004 (la PR de entrega debe mostrarlo ejecutado).")
        return
    segmento = {v["vehiculo_id"]: v["segmento"] for v in vehiculos}
    for categoria in CATEGORIAS:
        for envuelta in (False, True):
            texto = _respuesta(categoria)
            if envuelta:
                texto = f"```json\n{texto}\n```"
            resultado, _, _ = _analizar(texto)
            vehiculo = resultado["vehiculo"]
            assert vehiculo["categoria"] == categoria, (categoria, envuelta, vehiculo)
            referencia = vehiculo["vehiculo_id_referencia"]
            assert referencia in segmento, (categoria, envuelta, referencia)
            assert segmento[referencia] == categoria, (categoria, referencia, segmento[referencia])
    for envuelta in (False, True):
        texto = _respuesta("desconocido", "baja")
        resultado, _, _ = _analizar(f"```json\n{texto}\n```" if envuelta else texto)
        assert resultado["vehiculo"]["categoria"] == "desconocido"
        assert resultado["vehiculo"]["vehiculo_id_referencia"] is None


def probar_ac005_forma_del_vehiculo_y_json_en_disco() -> None:
    """28-categoria-vehiculo.md#AC-005 (parte del Agente 1): `vehiculo` tiene exactamente cinco claves, `modelo` es
    el identificador con el que se hizo la consulta y el JSON en disco coincide con el devuelto."""
    descripcion = "SUV grande de color gris, de la gama de un fabricante generalista."
    resultado, guardado, cliente = _analizar(_respuesta("SUV-C", "alta", descripcion))
    vehiculo = resultado["vehiculo"]
    assert set(vehiculo) == CLAVES_VEHICULO, set(vehiculo) ^ CLAVES_VEHICULO
    assert len(cliente.consultas_vehiculo) >= 1, "no se hizo la consulta de categoria"
    assert vehiculo["modelo"] == "modelo-falso" == cliente.consultas_vehiculo[-1]["model"], vehiculo["modelo"]
    assert vehiculo["descripcion"] == descripcion
    assert guardado == resultado, "el JSON guardado no coincide con el devuelto"


def probar_ac001_una_consulta_por_imagen_reducida_y_sin_cajas() -> None:
    """28-categoria-vehiculo.md#AC-001: con N = 0, 1 y 5 hallazgos candidatos, el cliente recibe exactamente UNA
    consulta de categoria, con UNA sola imagen: la foto completa, con el lado largo <= 1024 px y sin la caja roja."""
    for n in (0, 1, 5):
        resultado, _, cliente = _analizar(_respuesta("C"), n=n, tam_foto=(2400, 1600))
        assert len(resultado["findings"]) == n, (n, len(resultado["findings"]))
        assert len(cliente.llamadas) == n, f"debia haber {n} consultas de hallazgo y hubo {len(cliente.llamadas)}"
        assert len(cliente.consultas_vehiculo) == 1, (n, len(cliente.consultas_vehiculo))
        imagenes = _imagenes(cliente.consultas_vehiculo[0]["messages"])
        assert len(imagenes) == 1, (n, len(imagenes))
        enviada = _imagen_enviada(imagenes[0])
        assert max(enviada.size) <= 1024, (n, enviada.size)
        assert abs(enviada.width - 1024) <= 1 and abs(enviada.height - 683) <= 1, (n, enviada.size)  # misma proporcion
        rojo = ImageChops.subtract(enviada.convert("RGB").split()[0], enviada.convert("RGB").split()[1]).getextrema()[1]
        assert rojo < 30, f"la foto enviada tiene pixeles rojos (n={n}): hay una caja dibujada"
    # una foto que ya cabe no se amplia
    _, _, cliente = _analizar(_respuesta("C"), n=1, tam_foto=(800, 600))
    assert _imagen_enviada(_imagenes(cliente.consultas_vehiculo[0]["messages"])[0]).size == (800, 600)


def probar_ac007_error_del_proveedor_se_propaga() -> None:
    """28-categoria-vehiculo.md#AC-007: si el cliente lanza una excepcion en la consulta de categoria, llega al
    llamante de `analizar_imagen`; no se devuelve ningun `vehiculo` ni se escribe un fichero de salida parcial."""
    error = RuntimeError("el proveedor no responde")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        deteccion = json.loads(EJEMPLO.read_text(encoding="utf-8"))
        foto = tmp_dir / "foto.jpg"
        Image.new("RGB", (deteccion["image_width"], deteccion["image_height"]), "gray").save(foto)
        salida = tmp_dir / "salida" / "hallazgos.json"
        try:
            analizar_imagen(EJEMPLO, ClienteVehiculo(error), tmp_dir / "crops", modelo="modelo-falso", image_path=foto,
                            output_path=salida, catalogo=MINI_CATALOGO)
        except RuntimeError as capturado:
            assert capturado is error, capturado
        else:
            raise AssertionError("la excepcion del proveedor no llego al llamante")
        assert not salida.exists(), "se escribio una salida parcial"
        assert not salida.parent.exists(), "se creo la carpeta de salida sin escribir nada"


def probar_ac008_cache_de_la_consulta() -> None:
    """28-categoria-vehiculo.md#AC-008: con la misma imagen, modelo y prompt y `cache_dir`, la 2.ª ejecucion no hace
    ninguna llamada (ni de categoria ni de hallazgos) y devuelve un `vehiculo` identico; sin `cache_dir`, se repite."""
    primera_respuesta = _respuesta("SUV-C", "alta", "SUV mediano de color gris.")
    with tempfile.TemporaryDirectory() as cache:
        primera, _, c1 = _analizar(primera_respuesta, cache_dir=Path(cache))
        assert len(c1.consultas_vehiculo) == 1 and len(c1.llamadas) == 3, (len(c1.consultas_vehiculo), len(c1.llamadas))
        # si la 2.ª ejecucion llegara al cliente, este contestaria otra categoria y el `vehiculo` seria distinto
        segunda, _, c2 = _analizar(_respuesta("B", "baja", "Otro coche."), cache_dir=Path(cache))
        assert c2.consultas_vehiculo == [] and c2.llamadas == [], (len(c2.consultas_vehiculo), len(c2.llamadas))
        assert segunda["vehiculo"] == primera["vehiculo"], (primera["vehiculo"], segunda["vehiculo"])
    _, _, a = _analizar(primera_respuesta)
    _, _, b = _analizar(primera_respuesta)
    assert len(a.consultas_vehiculo) == 1 and len(b.consultas_vehiculo) == 1, "sin cache_dir la consulta debe repetirse"


def _flujo_de_main(tmp_dir: Path, foto: Path) -> dict[str, Any]:
    """Los pasos de `analizar_imagen` anteriores a la categoria del vehiculo, tal como los hacia `main`."""
    deteccion = cargar_detecciones(EJEMPLO)
    deteccion["image_path"] = str(foto)
    hallazgos = construir_hallazgos(deteccion)
    generar_recortes(deteccion, hallazgos, tmp_dir / "crops")
    return hallazgos


def probar_ac006_findings_y_claves_intactos() -> None:
    """28-categoria-vehiculo.md#AC-006: con las mismas respuestas del modelo y los mismos datos, `image_id`,
    `resumen_filtro_previo` y `findings` son identicos a los del flujo de `main` (sin consulta de categoria) y
    `vehiculo` es la unica clave nueva del nivel superior."""
    deteccion = json.loads(EJEMPLO.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        foto = tmp_dir / "foto.jpg"
        Image.new("RGB", (deteccion["image_width"], deteccion["image_height"]), "gray").save(foto)
        esperado = _flujo_de_main(tmp_dir, foto)
        enriquecer_con_vision(esperado, ClienteFalso(), "modelo-falso", foto, MINI_CATALOGO)
        resultado = analizar_imagen(EJEMPLO, ClienteVehiculo(_respuesta("C")), tmp_dir / "crops", modelo="modelo-falso",
                                    image_path=foto, catalogo=MINI_CATALOGO)
    assert set(resultado) - set(esperado) == {"vehiculo"}, set(resultado) ^ set(esperado)
    assert {k: v for k, v in resultado.items() if k != "vehiculo"} == esperado


class _ClienteProhibido:
    """Falla si se le llama: demuestra que la respuesta salio de la cache."""

    def __init__(self) -> None:
        self.chat = self
        self.completions = self

    def create(self, **peticion: Any) -> Any:
        raise AssertionError("se llamo al modelo: la clave de la cache de los hallazgos ha cambiado")


def probar_ac006_cache_de_hallazgo_de_main_sigue_acertando() -> None:
    """28-categoria-vehiculo.md#AC-006: una entrada de cache de un hallazgo guardada con la clave de `main`
    (sha256 de modelo, prompt, foto con caja y recorte) sigue acertando: la clave no ha cambiado."""
    deteccion = json.loads(EJEMPLO.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        foto = tmp_dir / "foto.jpg"
        Image.new("RGB", (deteccion["image_width"], deteccion["image_height"]), "gray").save(foto)
        finding = _flujo_de_main(tmp_dir, foto)["findings"][0]
        assert finding["category"] == "lamp broken"
        with Image.open(foto) as imagen:
            imagen.load()
            prompt = PROMPT_TEMPLATE.format(categoria=finding["category"], piezas=lista_piezas_para_prompt(MINI_CATALOGO))
            contexto = _jpeg_base64(imagen_con_caja(imagen, finding["bbox_xywh"]))
            with Image.open(finding["crop_image_path"]) as recorte:
                recorte_b64 = _jpeg_base64(recorte)
            # la formula de `main`, escrita aqui a mano a proposito: si cambia en el codigo, esta prueba lo detecta
            clave = hashlib.sha256("|".join(("modelo-falso", prompt, contexto, recorte_b64)).encode("utf-8")).hexdigest()
            cache = tmp_dir / "cache"
            cache.mkdir()
            (cache / f"{clave}.json").write_text(
                json.dumps({"modelo": "modelo-falso", "respuesta": json.dumps(RESPUESTAS_POR_CLASE["lamp broken"])}),
                encoding="utf-8",
            )
            resultado = analizar_hallazgo(_ClienteProhibido(), "modelo-falso", imagen, finding, MINI_CATALOGO, cache)
    assert resultado["vision_verdict"] == "confirmado" and resultado["pieza_id"] == "FARO_DEL_D", resultado


def probar_ac006_evaluar_vision_no_consulta_el_vehiculo() -> None:
    """28-categoria-vehiculo.md#AC-006: `evaluar_vision.py` y `analizar_detecciones.py` no hacen consultas de
    vehiculo (la consulta vive en `analizar_imagen`), asi que su recuento de llamadas y su gasto estimado no varian.
    El recuento con datos reales lo comprueba `probar_evaluar_vision_stub.py` (llamadas del cliente == previstas)."""
    for modulo in (evaluar_vision, analizar_detecciones):
        codigo = Path(modulo.__file__).read_text(encoding="utf-8").lower()
        assert "vehiculo" not in codigo, f"{Path(modulo.__file__).name} menciona el vehiculo"


PRUEBAS = (
    probar_ac001_una_consulta_por_imagen_reducida_y_sin_cajas,
    probar_ac002_respuestas_invalidas,
    probar_ac003_confianza_normalizada,
    probar_ac004_ocho_categorias,
    probar_ac005_forma_del_vehiculo_y_json_en_disco,
    probar_ac006_findings_y_claves_intactos,
    probar_ac006_cache_de_hallazgo_de_main_sigue_acertando,
    probar_ac006_evaluar_vision_no_consulta_el_vehiculo,
    probar_ac007_error_del_proveedor_se_propaga,
    probar_ac008_cache_de_la_consulta,
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
    print(f"\nTodo ok: categoria del vehiculo ({len(PRUEBAS)} pruebas).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
