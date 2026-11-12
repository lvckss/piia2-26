"""Prueba vision.py y la decision de tier sin API Key real ni el paquete
`openai`: usa un cliente falso que imita la forma de la respuesta del SDK de
OpenAI (`respuesta.choices[0].message.content`). Comprueba que se construye
bien la peticion (2 imagenes + JSON mode), que la respuesta se valida y que el
tier final combina score + veredicto + pieza, no que el modelo acierte (eso
hace falta la API Key real)."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from catalogo import Catalogo, cargar_catalogo
from confianza import decidir_tier
from hallazgos import cargar_detecciones, construir_hallazgos
from recorte import generar_recortes
from vision import analizar_hallazgo, enriquecer_con_vision, parsear_respuesta

# catalogo minimo para las pruebas: no depende de tener el paquete de la empresa
MINI_CATALOGO = Catalogo(
    piezas={
        "FARO_DEL_D": {"nombre": "Faro delantero derecho", "zona_tipo": "optica", "lado": "D"},
        "PARAG_DEL": {"nombre": "Paragolpes delantero", "zona_tipo": "paragolpes_plastico", "lado": "C"},
        "NEUMATICO": {"nombre": "Neumatico", "zona_tipo": "neumatico", "lado": "NA"},
    },
    reglas=frozenset(
        {
            ("lamp_broken", "optica", "grave"),
            ("dent", "paragolpes_plastico", "moderado"),
            ("tire_flat", "neumatico", "moderado"),
        }
    ),
)

RESPUESTAS_POR_CLASE = {
    "lamp broken": {"veredicto": "confirmado", "pieza_id": "FARO_DEL_D", "severidad": "grave",
                    "descripcion": "Faro delantero derecho roto."},
    "tire flat": {"veredicto": "rechazado", "pieza_id": None, "severidad": None,
                  "descripcion": "La rueda se ve sana."},
    "dent": {"veredicto": "confirmado", "pieza_id": "PARAG_DEL", "severidad": "moderado",
             "descripcion": "Abolladura en el paragolpes."},
}


@dataclass
class _Mensaje:
    content: str


@dataclass
class _Eleccion:
    message: _Mensaje


@dataclass
class _Uso:
    prompt_tokens: int
    completion_tokens: int


@dataclass
class _Respuesta:
    choices: list[_Eleccion]
    usage: _Uso


# para clases sin respuesta preparada: la vision no se moja
RESPUESTA_GENERICA = {"veredicto": "incierto", "pieza_id": None, "severidad": None, "descripcion": "No se aprecia con claridad."}


# respuesta a la consulta de categoria del vehiculo (Issue #28): lleva una sola imagen, la de hallazgo lleva dos
RESPUESTA_VEHICULO = {"categoria": "C", "confianza": "media", "descripcion": "Turismo compacto de color gris."}


class ClienteFalso:
    """Imita `OpenAI()`: registra las peticiones, responde un JSON segun la
    clase que aparece en el prompt (o la categoria del vehiculo, si la consulta
    lleva una sola imagen) e informa de tokens (1.500 de entrada y 40 de salida
    por llamada)."""

    def __init__(self) -> None:
        self.llamadas: list[dict] = []
        self.chat = self
        self.completions = self

    def create(self, model: str, messages: list[dict], response_format: dict) -> _Respuesta:
        self.llamadas.append({"model": model, "messages": messages, "response_format": response_format})
        if sum(1 for parte in messages[0]["content"] if parte["type"] == "image_url") == 1:
            return _Respuesta([_Eleccion(_Mensaje(json.dumps(RESPUESTA_VEHICULO)))], _Uso(1500, 40))
        texto_prompt = messages[0]["content"][0]["text"]
        categoria = texto_prompt.split("tipo '")[1].split("'")[0]
        respuesta = RESPUESTAS_POR_CLASE.get(categoria, RESPUESTA_GENERICA)
        return _Respuesta([_Eleccion(_Mensaje(json.dumps(respuesta)))], _Uso(1500, 40))


def probar_decidir_tier() -> None:
    assert decidir_tier("lamp broken", 0.95, "confirmado", "FARO_DEL_D", True) == "confirmed"
    # el score pasa pero la vision lo rechaza o no lo ve claro -> a revisar
    assert decidir_tier("lamp broken", 0.95, "rechazado", None, None) == "needs_review"
    assert decidir_tier("lamp broken", 0.95, "incierto", "FARO_DEL_D", True) == "needs_review"
    # la vision lo confirma pero el score no llega -> a revisar (la vision no rescata scores bajos)
    assert decidir_tier("lamp broken", 0.40, "confirmado", "FARO_DEL_D", True) == "needs_review"
    # umbrales calibrados en la #44 (D-6): dent, scratch y crack desde 0,3; lamp broken, glass shatter y tire flat siguen en 0,6
    for clase in ("dent", "scratch", "crack"):
        assert decidir_tier(clase, 0.30, "confirmado", "PARAG_DEL", True) == "confirmed", clase
        assert decidir_tier(clase, 0.29, "confirmado", "PARAG_DEL", True) == "needs_review", clase
    for clase in ("lamp broken", "glass shatter", "tire flat"):
        assert decidir_tier(clase, 0.60, "confirmado", "FARO_DEL_D", True) == "confirmed", clase
        assert decidir_tier(clase, 0.59, "confirmado", "FARO_DEL_D", True) == "needs_review", clase
    # sin pieza o sin regla de coste no se puede presupuestar
    assert decidir_tier("lamp broken", 0.95, "confirmado", None, None) == "needs_review"
    assert decidir_tier("lamp broken", 0.95, "confirmado", "PARAG_DEL", False) == "needs_review"
    assert decidir_tier("lamp broken", 0.95, None, None, None) == "needs_review"


def probar_parseo() -> None:
    ok = parsear_respuesta(json.dumps(RESPUESTAS_POR_CLASE["lamp broken"]), MINI_CATALOGO, "lamp_broken")
    assert ok["vision_verdict"] == "confirmado" and ok["pieza_id"] == "FARO_DEL_D"
    assert ok["regla_coste_aplicable"] is True

    # JSON envuelto en un bloque de codigo
    con_vallas = "```json\n" + json.dumps(RESPUESTAS_POR_CLASE["lamp broken"]) + "\n```"
    assert parsear_respuesta(con_vallas, MINI_CATALOGO, "lamp_broken")["pieza_id"] == "FARO_DEL_D"

    # respuesta que no es JSON -> incierto, nunca un crash ni una invencion
    basura = parsear_respuesta("no puedo ayudar con eso", MINI_CATALOGO, "lamp_broken")
    assert basura["vision_verdict"] == "incierto" and basura["pieza_id"] is None

    # pieza inventada por el modelo -> se descarta
    inventada = parsear_respuesta(
        json.dumps({"veredicto": "confirmado", "pieza_id": "PUERTA_VOLADORA", "severidad": "grave"}),
        MINI_CATALOGO, "lamp_broken",
    )
    assert inventada["pieza_id"] is None and inventada["regla_coste_aplicable"] is None

    # pieza valida pero sin regla para esa clase y severidad
    sin_regla = parsear_respuesta(
        json.dumps({"veredicto": "confirmado", "pieza_id": "FARO_DEL_D", "severidad": "leve"}),
        MINI_CATALOGO, "lamp_broken",
    )
    assert sin_regla["regla_coste_aplicable"] is False

    # un rechazo no arrastra pieza ni severidad
    rechazo = parsear_respuesta(
        json.dumps({"veredicto": "rechazado", "pieza_id": "FARO_DEL_D", "severidad": "grave"}),
        MINI_CATALOGO, "lamp_broken",
    )
    assert rechazo["pieza_id"] is None and rechazo["severidad"] is None


def probar_catalogo_real() -> None:
    try:
        catalogo = cargar_catalogo()
    except FileNotFoundError:
        print("(catalogo real no encontrado: extrae piia2_paquete_datos.zip en la raiz del repo)")
        return
    assert len(catalogo.piezas) == 35 and len(catalogo.reglas) == 45, (len(catalogo.piezas), len(catalogo.reglas))
    print("catalogo real ok: 35 piezas, 45 reglas")


def probar_enriquecer() -> None:
    ejemplo_path = Path(__file__).parent / "ejemplos" / "ejemplo_3_mixto_dificil.json"
    deteccion = cargar_detecciones(ejemplo_path)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        foto = tmp_dir / "foto.jpg"
        Image.new("RGB", (deteccion["image_width"], deteccion["image_height"]), "gray").save(foto)
        deteccion["image_path"] = str(foto)

        hallazgos = construir_hallazgos(deteccion)
        generar_recortes(deteccion, hallazgos, tmp_dir / "crops")

        cliente = ClienteFalso()
        cache = tmp_dir / "cache"
        enriquecer_con_vision(hallazgos, cliente, "modelo-falso", foto, MINI_CATALOGO, cache_dir=cache)

        assert len(cliente.llamadas) == 3

        # contador de coste: tokens facturados, y la cache no cuenta
        uso: dict[str, int] = {}
        from vision import analizar_hallazgo
        with Image.open(foto) as img:
            analizar_hallazgo(cliente, "modelo-falso", img, hallazgos["findings"][0], MINI_CATALOGO, cache_dir=tmp_dir / "cache2", uso=uso)
            analizar_hallazgo(cliente, "modelo-falso", img, hallazgos["findings"][0], MINI_CATALOGO, cache_dir=tmp_dir / "cache2", uso=uso)
        assert uso == {"llamadas": 1, "prompt_tokens": 1500, "completion_tokens": 40}, uso
        cliente.llamadas.pop()  # la llamada extra de esta comprobacion no cuenta para lo de abajo
        for llamada in cliente.llamadas:
            assert llamada["model"] == "modelo-falso"
            assert llamada["response_format"] == {"type": "json_object"}
            contenido = llamada["messages"][0]["content"]
            assert [c["type"] for c in contenido] == ["text", "image_url", "image_url"]
            assert all(c["image_url"]["url"].startswith("data:image/jpeg;base64,") for c in contenido[1:])

        # misma consulta otra vez: sale de la cache, no vuelve a llamar al modelo
        hallazgos2 = construir_hallazgos(deteccion)
        generar_recortes(deteccion, hallazgos2, tmp_dir / "crops")
        enriquecer_con_vision(hallazgos2, cliente, "modelo-falso", foto, MINI_CATALOGO, cache_dir=cache)
        assert len(cliente.llamadas) == 3, "la cache no evito las llamadas repetidas"
        assert hallazgos2["findings"] == hallazgos["findings"]

    por_clase = {f["category"]: f for f in hallazgos["findings"]}
    lamp, tire, dent = por_clase["lamp broken"], por_clase["tire flat"], por_clase["dent"]

    assert lamp["confidence_tier"] == "confirmed" and lamp["pieza_id"] == "FARO_DEL_D"
    assert tire["vision_verdict"] == "rechazado" and tire["confidence_tier"] == "needs_review"
    # la vision confirma el dent y su score (0.68) pasa el umbral de su clase (0.3, calibrado en la #44; con 0.7 quedaba en revision)
    assert dent["vision_verdict"] == "confirmado" and dent["score_tier"] == "confirmed"
    assert dent["confidence_tier"] == "confirmed"

    for f in hallazgos["findings"]:
        print(f"  {f['category']:12s} score={f['score']:.2f} vision={f['vision_verdict']:10s} "
              f"pieza={str(f['pieza_id']):11s} -> {f['confidence_tier']}")


# --- Issue #54, slice 3 (Agente 1): descripciones corruptas, cache y daños de otro vehiculo ------------------
# Plan v1.1: https://github.com/lvckss/piia2-26/issues/54#issuecomment-6806386857 (AC-005, AC-006 y AC-013)

# restos reales de la salida del modelo (1008-19 y 1281-8 de las 30 salidas versionadas): alfabetos ajenos y razonamiento
CORRUPTA_ALFABETOS = (
    "La zona marcada muestra el contorno y la sombra del paso de rueda, sin una abolladura visible."
    "】【。} પડી karto? Wait final produced malformed? It says JSON but Spanish sentence ending."
)
CORRUPTA_RAZONAMIENTO = "Abolladura leve en el paragolpes. Wait no. Need ensure the JSON is valid."
DESCRIPCION_NORMAL = "Abolladura leve (≥ 3 cm) en el paragolpes; reparación estimada en 120 € a 45°: “pintar” el panel. El niño señaló el daño."
DESCRIPCION_OTRO_VEHICULO = (
    "En la esquina delantera izquierda del vehículo oscuro del fondo, el faro parece estar roto o sin su cubierta, "
    "con elementos internos expuestos."
)


def _respuesta_json(descripcion: str, veredicto: str = "confirmado", pieza: str | None = "PARAG_DEL",
                    severidad: str | None = "moderado") -> str:
    return json.dumps({"veredicto": veredicto, "pieza_id": pieza, "severidad": severidad, "descripcion": descripcion})


class ClienteSecuencia(ClienteFalso):
    """Como `ClienteFalso`, pero contesta con los textos dados, en orden (la ultima se repite)."""

    def __init__(self, textos: list[str]) -> None:
        super().__init__()
        self.textos = list(textos)

    def create(self, model: str, messages: list[dict], response_format: dict) -> _Respuesta:
        self.llamadas.append({"model": model, "messages": messages, "response_format": response_format})
        texto = self.textos.pop(0) if len(self.textos) > 1 else self.textos[0]
        return _Respuesta([_Eleccion(_Mensaje(texto))], _Uso(1500, 40))


def _hallazgo_de_prueba(tmp: str):
    carpeta = Path(tmp)
    recorte = carpeta / "recorte.jpg"
    Image.new("RGB", (40, 40), "gray").save(recorte)
    finding = {"category": "dent", "bbox_xywh": [10, 10, 40, 40], "crop_image_path": str(recorte)}
    return Image.new("RGB", (200, 150), "gray"), finding


def probar_ac005_descripcion_corrupta_no_se_acepta() -> None:
    """AC-005: JSON valido con alfabetos ajenos o restos de razonamiento -> incierto, sin pieza ni severidad y sin
    el texto corrupto; una descripcion normal (ñ, tildes, €, °, ≥, comillas) se acepta sin cambios."""
    for corrupta in (CORRUPTA_ALFABETOS, CORRUPTA_RAZONAMIENTO):
        r = parsear_respuesta(_respuesta_json(corrupta), MINI_CATALOGO, "dent")
        assert r["vision_verdict"] == "incierto", r
        assert r["pieza_id"] is None and r["severidad"] is None and r["regla_coste_aplicable"] is None, r
        for resto in ("Wait", "malformed", "Need ensure", "】", "પ"):
            assert resto not in r["vision_description"], (resto, r["vision_description"])
    normal = parsear_respuesta(_respuesta_json(DESCRIPCION_NORMAL), MINI_CATALOGO, "dent")
    assert normal["vision_verdict"] == "confirmado" and normal["pieza_id"] == "PARAG_DEL", normal
    assert normal["vision_description"] == DESCRIPCION_NORMAL, normal["vision_description"]


def probar_ac005_reintenta_una_vez_sin_cache() -> None:
    """AC-005: con una respuesta corrupta se repite la consulta una vez; si la segunda es buena se usa, y si
    persiste el hallazgo queda incierto tras exactamente dos llamadas."""
    with tempfile.TemporaryDirectory() as tmp:
        imagen, finding = _hallazgo_de_prueba(tmp)
        buena = _respuesta_json(DESCRIPCION_NORMAL)
        mala = _respuesta_json(CORRUPTA_ALFABETOS)

        cliente = ClienteSecuencia([mala, buena])
        uso: dict[str, int] = {}
        r = analizar_hallazgo(cliente, "modelo-falso", imagen, finding, MINI_CATALOGO, cache_dir=Path(tmp) / "c1", uso=uso)
        assert len(cliente.llamadas) == 2 and uso.get("llamadas") == 2, (len(cliente.llamadas), uso)
        assert r["vision_verdict"] == "confirmado" and r["vision_description"] == DESCRIPCION_NORMAL, r

        siempre_mala = ClienteSecuencia([mala])
        r2 = analizar_hallazgo(siempre_mala, "modelo-falso", imagen, finding, MINI_CATALOGO, cache_dir=Path(tmp) / "c2")
        assert len(siempre_mala.llamadas) == 2, len(siempre_mala.llamadas)
        assert r2["vision_verdict"] == "incierto" and r2["pieza_id"] is None and "Wait" not in r2["vision_description"], r2


def probar_ac006_cache_con_respuesta_corrupta() -> None:
    """AC-006: una respuesta corrupta guardada en la cache se descarta y se vuelve a consultar; la valida se sirve
    de la cache sin llamada nueva."""
    with tempfile.TemporaryDirectory() as tmp:
        imagen, finding = _hallazgo_de_prueba(tmp)
        cache = Path(tmp) / "cache"
        buena = _respuesta_json(DESCRIPCION_NORMAL)

        cliente = ClienteSecuencia([buena])
        analizar_hallazgo(cliente, "modelo-falso", imagen, finding, MINI_CATALOGO, cache_dir=cache)
        assert len(cliente.llamadas) == 1
        (entrada,) = list(cache.glob("*.json"))
        # la cache pasa a contener una respuesta corrupta para esa misma consulta
        entrada.write_text(json.dumps({"modelo": "modelo-falso", "respuesta": _respuesta_json(CORRUPTA_ALFABETOS)}), encoding="utf-8")

        r = analizar_hallazgo(cliente, "modelo-falso", imagen, finding, MINI_CATALOGO, cache_dir=cache)
        assert len(cliente.llamadas) == 2, "la respuesta corrupta de la cache no se volvio a consultar"
        assert r["vision_verdict"] == "confirmado" and r["vision_description"] == DESCRIPCION_NORMAL, r
        assert json.loads(entrada.read_text(encoding="utf-8"))["respuesta"] == buena, "la cache no se corrigio"

        analizar_hallazgo(cliente, "modelo-falso", imagen, finding, MINI_CATALOGO, cache_dir=cache)
        assert len(cliente.llamadas) == 2, "la respuesta valida debia servirse de la cache"


def probar_ac006_una_respuesta_corrupta_no_se_guarda() -> None:
    """AC-006: una respuesta que sigue corrupta tras el reintento no se guarda en la cache."""
    with tempfile.TemporaryDirectory() as tmp:
        imagen, finding = _hallazgo_de_prueba(tmp)
        cache = Path(tmp) / "cache"
        analizar_hallazgo(ClienteSecuencia([_respuesta_json(CORRUPTA_RAZONAMIENTO)]), "modelo-falso", imagen, finding,
                          MINI_CATALOGO, cache_dir=cache)
        assert not list(cache.glob("*.json")), "se guardo una respuesta corrupta"


def probar_ac013_confirmado_en_otro_vehiculo_queda_incierto() -> None:
    """AC-013: un `confirmado` cuya descripcion situa el daño en otro vehiculo o en el fondo pasa a `incierto`
    y conserva su descripcion; una descripcion normal sigue `confirmado`."""
    r = parsear_respuesta(_respuesta_json(DESCRIPCION_OTRO_VEHICULO, pieza="FARO_DEL_D", severidad="grave"), MINI_CATALOGO, "lamp_broken")
    assert r["vision_verdict"] == "incierto", r
    assert r["vision_description"] == DESCRIPCION_OTRO_VEHICULO, r["vision_description"]
    normal = parsear_respuesta(_respuesta_json("Faro delantero derecho roto, con el cristal desprendido.", pieza="FARO_DEL_D", severidad="grave"),
                               MINI_CATALOGO, "lamp_broken")
    assert normal["vision_verdict"] == "confirmado", normal
    # una mencion al fondo sin otro vehiculo no cambia nada, ni un rechazo
    fondo = parsear_respuesta(_respuesta_json("Faro del vehículo roto; al fondo se ve un árbol.", pieza="FARO_DEL_D", severidad="grave"),
                              MINI_CATALOGO, "lamp_broken")
    assert fondo["vision_verdict"] == "confirmado", fondo
    rechazo = parsear_respuesta(_respuesta_json(DESCRIPCION_OTRO_VEHICULO, veredicto="rechazado", pieza=None, severidad=None),
                                MINI_CATALOGO, "lamp_broken")
    assert rechazo["vision_verdict"] == "rechazado", rechazo


def main() -> None:
    probar_decidir_tier()
    probar_parseo()
    probar_catalogo_real()
    probar_enriquecer()
    probar_ac005_descripcion_corrupta_no_se_acepta()
    probar_ac005_reintenta_una_vez_sin_cache()
    probar_ac006_cache_con_respuesta_corrupta()
    probar_ac006_una_respuesta_corrupta_no_se_guarda()
    probar_ac013_confirmado_en_otro_vehiculo_queda_incierto()
    print("\nTodo ok: peticion bien formada, respuesta validada, cache y tier combinado.")


if __name__ == "__main__":
    main()
