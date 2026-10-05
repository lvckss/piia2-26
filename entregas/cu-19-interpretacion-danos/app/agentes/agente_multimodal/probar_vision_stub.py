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
from vision import enriquecer_con_vision, parsear_respuesta

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
class _Respuesta:
    choices: list[_Eleccion]


class ClienteFalso:
    """Imita `OpenAI()`: registra las peticiones y responde un JSON segun la
    clase que aparece en el prompt."""

    def __init__(self) -> None:
        self.llamadas: list[dict] = []
        self.chat = self
        self.completions = self

    def create(self, model: str, messages: list[dict], response_format: dict) -> _Respuesta:
        self.llamadas.append({"model": model, "messages": messages, "response_format": response_format})
        texto_prompt = messages[0]["content"][0]["text"]
        categoria = texto_prompt.split("tipo '")[1].split("'")[0]
        return _Respuesta([_Eleccion(_Mensaje(json.dumps(RESPUESTAS_POR_CLASE[categoria])))])


def probar_decidir_tier() -> None:
    assert decidir_tier("lamp broken", 0.95, "confirmado", "FARO_DEL_D", True) == "confirmed"
    # el score pasa pero la vision lo rechaza o no lo ve claro -> a revisar
    assert decidir_tier("lamp broken", 0.95, "rechazado", None, None) == "needs_review"
    assert decidir_tier("lamp broken", 0.95, "incierto", "FARO_DEL_D", True) == "needs_review"
    # la vision lo confirma pero el score no llega -> a revisar (la vision no rescata scores bajos)
    assert decidir_tier("lamp broken", 0.40, "confirmado", "FARO_DEL_D", True) == "needs_review"
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
    # la vision confirma el dent, pero su score (0.68) no llega al umbral de su clase (0.7)
    assert dent["vision_verdict"] == "confirmado" and dent["score_tier"] == "needs_review"
    assert dent["confidence_tier"] == "needs_review"

    for f in hallazgos["findings"]:
        print(f"  {f['category']:12s} score={f['score']:.2f} vision={f['vision_verdict']:10s} "
              f"pieza={str(f['pieza_id']):11s} -> {f['confidence_tier']}")


def main() -> None:
    probar_decidir_tier()
    probar_parseo()
    probar_catalogo_real()
    probar_enriquecer()
    print("\nTodo ok: peticion bien formada, respuesta validada, cache y tier combinado.")


if __name__ == "__main__":
    main()
