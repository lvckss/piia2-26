"""Pruebas del paso de justificacion con LLM (Issue #97, slice 1), sin API Key ni red.

Cada prueba cita su criterio: specs/97-justificacion-llm-normativa.md#AC-0XX.
El cliente del modelo es falso (ADR 0003: el cliente se recibe como parametro).
No necesita el paquete de la empresa: los pasajes se copian aqui.

Se ejecuta desde esta carpeta:  python probar_justificacion.py
Ejecuta todas las pruebas, informa de cada una y termina con codigo 1 si
alguna falla.
"""

from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

import justificacion_llm
from justificacion_llm import justificar_normativa

FR300 = "docs/polizas_sinteticas/P-TR-FR300.md"
DANOS_PROPIOS = ("2.3 **Daños propios por colisión, vuelco, atropello de animales y actos vandálicos** "
                 "con franquicia de 300 EUR por siniestro.")
LUNAS = ("2.2 **Rotura de lunas** (parabrisas, lunas laterales y luneta) con límite de 1500 EUR por "
         "anualidad y franquicia de 0 EUR.")
PERDIDA_TOTAL = "5.1 Habrá pérdida total cuando el coste de reparación (sin IVA) alcance o supere el 75 % del valor venal."

NORMATIVA = [
    {"tema": "cobertura de daños propios", "extracto": DANOS_PROPIOS, "fuente": f"{FR300}#2. Coberturas incluidas"},
    {"tema": "pérdida total", "extracto": PERDIDA_TOTAL, "fuente": f"{FR300}#5. Pérdida total"},
]


class _Respuesta:
    def __init__(self, texto: str) -> None:
        self.choices = [type("C", (), {"message": type("M", (), {"content": texto})()})()]
        self.usage = type("U", (), {"prompt_tokens": 100, "completion_tokens": 20})()


class ClienteFalso:
    """Imita `client.chat.completions.create`: responde por tema con lo guionizado y registra las llamadas.
    Una respuesta que es una excepcion se lanza en lugar de devolverse."""

    def __init__(self, por_tema: dict[str, object]) -> None:
        self.por_tema = por_tema
        self.llamadas: list[dict] = []
        self.chat = type("Chat", (), {"completions": self})()

    def create(self, model: str, messages: list[dict], response_format: dict) -> _Respuesta:
        self.llamadas.append({"model": model, "messages": messages, "response_format": response_format})
        tema = json.loads(messages[-1]["content"])["tema"]
        respuesta = self.por_tema[tema]
        if isinstance(respuesta, BaseException):
            raise respuesta
        return _Respuesta(respuesta if isinstance(respuesta, str) else json.dumps(respuesta, ensure_ascii=False))


def _justificar(cliente, normativa=None, **kw):
    kw.setdefault("autorizado", True)
    return justificar_normativa(copy.deepcopy(NORMATIVA if normativa is None else normativa),
                                cliente=cliente, modelo="modelo-falso", **kw)


def _por_tema(justificaciones):
    return {j["tema"]: j for j in justificaciones}


BIEN_DANOS = {"texto": "La póliza cubre los daños propios por colisión, vuelco, atropello de animales y actos "
                       "vandálicos, con una franquicia por siniestro.",
              "citas": ["Daños propios por colisión, vuelco, atropello de animales y actos vandálicos",
                        "con franquicia de 300 EUR por siniestro"]}
BIEN_PT = {"texto": "Hay pérdida total cuando la reparación sin IVA alcanza el umbral fijado sobre el valor venal.",
           "citas": ["Habrá pérdida total cuando el coste de reparación (sin IVA) alcance o supere el 75 % del valor venal."]}


# --- specs/97-justificacion-llm-normativa.md#AC-001 --------------------------
def probar_97_ac001_justificacion_generada_con_fuente_del_codigo():
    """AC-001: texto sin importes y dos citas literales -> `generada`; cada cita lleva la fuente del
    pasaje que la contiene, aunque el modelo devuelva otra."""
    con_fuente_inventada = {"texto": BIEN_DANOS["texto"],
                            "citas": [{"extracto": BIEN_DANOS["citas"][0], "fuente": "inventada.md"},
                                      BIEN_DANOS["citas"][1]]}
    r = _por_tema(_justificar(ClienteFalso({"cobertura de daños propios": con_fuente_inventada,
                                            "pérdida total": BIEN_PT})))
    j = r["cobertura de daños propios"]
    assert j["estado"] == "generada", j
    assert j["texto"] == BIEN_DANOS["texto"], j
    # v1.3 (AC-020): las dos citas caen en la misma frase del pasaje, que se guarda una sola vez y completa
    assert [c["extracto"] for c in j["citas"]] == [DANOS_PROPIOS], j
    assert all(c["fuente"] == f"{FR300}#2. Coberturas incluidas" for c in j["citas"]), j
    assert set(j) == {"tema", "estado", "texto", "citas"}, j
    assert r["pérdida total"]["estado"] == "generada", r["pérdida total"]


# --- specs/97-justificacion-llm-normativa.md#AC-002 --------------------------
def probar_97_ac002_cita_no_literal_se_descarta():
    """AC-002: una cita que no esta en los pasajes del tema (o que solo esta en los de otro tema)
    deja ese tema `descartada`; el otro tema queda `generada`."""
    for cita_mala in ("Cubre cualquier daño sin franquicia", BIEN_PT["citas"][0]):
        mala = {"texto": "La póliza cubre los daños propios.", "citas": [cita_mala]}
        r = _por_tema(_justificar(ClienteFalso({"cobertura de daños propios": mala, "pérdida total": BIEN_PT})))
        j = r["cobertura de daños propios"]
        assert j["estado"] == "descartada", j
        assert "cita" in j["motivo"].lower() and cita_mala[:20] in j["motivo"], j
        assert "texto" not in j and "citas" not in j, j
        assert r["pérdida total"]["estado"] == "generada", r


def probar_97_ac002_cita_con_espacios_distintos_es_literal():
    """AC-002 (normalizacion): una cita que solo cambia espacios en blanco consecutivos se acepta."""
    con_espacios = {"texto": "La póliza fija una franquicia por siniestro.",
                    "citas": ["con  franquicia de 300 EUR\npor siniestro"]}
    j = _por_tema(_justificar(ClienteFalso({"cobertura de daños propios": con_espacios,
                                            "pérdida total": BIEN_PT})))["cobertura de daños propios"]
    assert j["estado"] == "generada", j


ART7 = ("Artículo 7. Obligaciones del asegurador y del perjudicado.\n1. El asegurador, dentro del ámbito del "
        "aseguramiento obligatorio y con cargo al seguro de suscripción obligatoria, habrá de satisfacer al "
        "perjudicado el importe de los daños sufridos en su persona y en sus bienes.")
TEMA_LEGAL = "Responsabilidad civil obligatoria de terceros perjudicados: legislación"
LEGAL = [{"tema": TEMA_LEGAL, "extracto": ART7, "fuente": "docs/legal/BOE-A-2004-18911.txt#seccion-9-ventana-0"}]


def _legal(cita: str):
    """Justificacion del tema legal con una sola cita, para probar la comparacion de citas."""
    respuesta = {"texto": "El asegurador debe satisfacer al perjudicado los daños.", "citas": [cita]}
    return _justificar(ClienteFalso({TEMA_LEGAL: respuesta}), normativa=LEGAL)[0]


def probar_97_ac002_cita_con_otra_mayuscula_es_literal():
    """AC-002 (v1.2, sin distinguir mayusculas): el modelo cita «el asegurador, dentro del…» con minuscula y
    el pasaje dice «El asegurador, dentro del…»; se acepta y la cita guardada es el texto literal del pasaje."""
    j = _legal("el asegurador, dentro del ámbito del aseguramiento obligatorio")
    assert j["estado"] == "generada", j
    frase = ART7.split("\n")[1]  # la frase completa del pasaje, con su «1. El» en mayuscula
    assert j["citas"] == [{"extracto": frase, "fuente": LEGAL[0]["fuente"]}], j


def probar_97_ac002_cita_sin_enfasis_markdown_es_literal():
    """AC-002 (v1.2, sin marcas de enfasis): el pasaje de la poliza dice «**Rotura de lunas** (parabrisas…)» y el
    modelo cita «Rotura de lunas (parabrisas…)» sin los asteriscos; se acepta y se guarda el texto literal."""
    normativa = [{"tema": "rotura de lunas", "extracto": LUNAS, "fuente": f"{FR300}#2. Coberturas incluidas"}]
    respuesta = {"texto": "La póliza cubre la rotura de lunas.",
                 "citas": ["Rotura de lunas (parabrisas, lunas laterales y luneta)"]}
    j = _justificar(ClienteFalso({"rotura de lunas": respuesta}), normativa=normativa)[0]
    assert j["estado"] == "generada", j
    assert j["citas"][0]["extracto"] == LUNAS, j  # v1.3: la frase completa, con sus asteriscos tal cual
    assert j["citas"][0]["extracto"] in LUNAS, "la cita guardada debe estar tal cual en el pasaje"


def probar_97_ac002_otra_mayuscula_no_acepta_otras_palabras():
    """AC-002 (v1.2): ignorar mayusculas y asteriscos no afloja el resto: una palabra distinta, una cita
    que solo tiene asteriscos o un fragmento que no esta siguen `descartada`."""
    for mala in ("el asegurador, fuera del ámbito del aseguramiento obligatorio", "***", "  ** **  ",
                 "el asegurador cubre todo"):
        j = _legal(mala)
        assert j["estado"] == "descartada", (mala, j)
        assert "cita" in j["motivo"].lower(), j


# --- specs/97-justificacion-llm-normativa.md#AC-002 (v1.3) y plan #54 AC-020 ---
def _citar(pasaje: str, *citas: str):
    """Justificacion de un tema con ese pasaje y esas citas; devuelve la justificacion."""
    normativa = [{"tema": "t", "extracto": pasaje, "fuente": "docs/p.md#s"}]
    r = {"texto": "El pasaje describe la cobertura.", "citas": list(citas)}
    return _justificar(ClienteFalso({"t": r}), normativa=normativa)[0]


def probar_97_ac020_cita_corta_se_amplia_a_la_frase_completa():
    """#54 AC-020: las citas cortadas del informe 003806 («franquicia de», «con limite de») se amplian a la frase
    del pasaje, que lleva las cifras (el limite y la franquicia)."""
    for corta in ("franquicia de", "con límite de", "Rotura de lunas"):
        j = _citar(LUNAS, corta)
        assert j["estado"] == "generada", (corta, j)
        assert j["citas"] == [{"extracto": LUNAS, "fuente": "docs/p.md#s"}], (corta, j)
        assert "1500 EUR por anualidad" in j["citas"][0]["extracto"] and "franquicia de 0 EUR" in j["citas"][0]["extracto"]


def probar_97_ac020_frase_completa_no_cambia():
    """#54 AC-020: una cita que ya es la frase completa se guarda igual."""
    j = _citar(LUNAS, LUNAS)
    assert j["citas"] == [{"extracto": LUNAS, "fuente": "docs/p.md#s"}], j


def probar_97_ac020_respeta_salto_de_linea_y_punto_y_coma():
    """#54 AC-020: la frase termina en el salto de linea, en el punto o en el punto y coma; no se mezclan lineas."""
    pasaje = ("2.1 Cobertura de responsabilidad civil obligatoria; no se aplica franquicia a terceros.\n"
              "2.2 Rotura de lunas con limite de 800 EUR por anualidad.")
    assert _citar(pasaje, "no se aplica franquicia")["citas"][0]["extracto"] == "no se aplica franquicia a terceros."
    assert _citar(pasaje, "limite de 800")["citas"][0]["extracto"] == "2.2 Rotura de lunas con limite de 800 EUR por anualidad."


def probar_97_ac020_no_corta_en_abreviaturas_ni_en_numeros():
    """#54 AC-020: «art. 7», «1.» y «2.2» no son final de frase."""
    pasaje = "Conforme al art. 7 de la Ley, el asegurador pagará los daños. Otra frase distinta."
    assert _citar(pasaje, "pagará los daños")["citas"][0]["extracto"] == (
        "Conforme al art. 7 de la Ley, el asegurador pagará los daños.")
    j = _citar("1. El asegurador pagará los daños materiales.", "pagará los daños")
    assert j["citas"][0]["extracto"] == "1. El asegurador pagará los daños materiales.", j


def probar_97_ac020_frase_demasiado_larga_no_se_amplia():
    """#54 AC-020: si la frase pasa de 600 caracteres se guarda la cita literal sin ampliar."""
    larga = "El asegurador pagará " + ", ".join(f"el daño numero {i}" for i in range(80)) + "."
    assert len(larga) > 600
    j = _citar(larga, "el daño numero 40")
    assert j["citas"][0]["extracto"] == "el daño numero 40", j


def probar_97_ac020_cita_ausente_sigue_descartada():
    """#54 AC-020 + AC-002: ampliar solo afecta a las citas que si estan en los pasajes."""
    j = _citar(LUNAS, "franquicia de 9999 EUR")
    assert j["estado"] == "descartada" and "citas" not in j, j


def probar_97_ac020_cita_al_inicio_de_una_frase_no_arrastra_la_anterior():
    """#54 AC-020 (revision de Victor en la #113): si la cita empieza justo donde empieza una frase, la frase
    guardada empieza ahi y no incluye la anterior. Es el caso de los informes de tercero (el articulo 7)."""
    pasaje = ("Artículo 7. Obligaciones del asegurador. El asegurador, dentro del ámbito y límites del "
              "aseguramiento obligatorio, deberá satisfacer al perjudicado el importe de los daños. Art. 8 siguiente.")
    j = _citar(pasaje, "el asegurador, dentro del ámbito")
    assert j["estado"] == "generada", j
    assert j["citas"][0]["extracto"] == (
        "El asegurador, dentro del ámbito y límites del aseguramiento obligatorio, deberá satisfacer al "
        "perjudicado el importe de los daños."), j
    # y tras un punto y coma
    pasaje2 = "2.1 Cobertura de lunas; Rotura de parabrisas con límite de 800 EUR por anualidad."
    assert _citar(pasaje2, "rotura de parabrisas")["citas"][0]["extracto"] == (
        "Rotura de parabrisas con límite de 800 EUR por anualidad.")


def probar_97_ac020_enfasis_markdown_al_inicio_de_la_frase_no_arrastra_la_anterior():
    """#54 AC-020 (revision de Lucas en la #113): tras un punto, el enfasis Markdown (`**`) que abre la frase
    siguiente tambien marca el final de la frase anterior; sin ello, una frase previa larga hacia pasar la
    ampliacion de 600 caracteres y se perdian el limite y la franquicia."""
    frase = "**Rotura de lunas** con límite de 800 EUR por anualidad y franquicia de 0 EUR."
    previa = "Condiciones anteriores: " + ("se requiere revisión " * 30) + "."
    assert len(previa) > 600
    j = _citar(previa + " " + frase + " Otra frase.", "Rotura de lunas")
    assert j["estado"] == "generada", j
    assert j["citas"][0]["extracto"] == frase, j
    # caso corto: la frase previa no entra en la cita
    corto = "Una frase previa. " + frase
    assert _citar(corto, "Rotura de lunas")["citas"][0]["extracto"] == frase


# --- specs/97-justificacion-llm-normativa.md#AC-003 --------------------------
def probar_97_ac003_texto_con_importes_se_descarta():
    """AC-003: con pasajes que contienen «1500 EUR» (limite de lunas, ausente del calculo) y «300 EUR»,
    cualquier importe en el texto (aunque este en sus citas) descarta la justificacion; sin importes, `generada`."""
    normativa = [{"tema": "rotura de lunas", "extracto": LUNAS, "fuente": f"{FR300}#2. Coberturas incluidas"},
                 {"tema": "cobertura de daños propios", "extracto": DANOS_PROPIOS,
                  "fuente": f"{FR300}#2. Coberturas incluidas"}]
    citas = ["Rotura de lunas** (parabrisas, lunas laterales y luneta) con límite de 1500 EUR por anualidad"]
    for importe in ("500 €", "1.500 EUR", "1500 EUR", "300,00 euros", "€ 300", "1500 euros",
                    # revision de Lucas en la #101: moneda pegada al numero o escrita delante
                    "1500EUR", "1500euros", "euro 1500", "euros 1500", "€1500", "EUR1500"):
        texto = f"La póliza cubre la rotura de lunas con un límite de {importe} al año."
        r = _por_tema(_justificar(ClienteFalso({"rotura de lunas": {"texto": texto, "citas": citas},
                                                "cobertura de daños propios": BIEN_DANOS}), normativa))
        j = r["rotura de lunas"]
        assert j["estado"] == "descartada", (importe, j)
        assert "importe" in j["motivo"].lower(), (importe, j)
    # sin falsos positivos: palabras como «europeo» o cifras que no son importes no descartan
    for texto in ("La póliza cubre la rotura de lunas con un límite anual.",
                  "Se aplica la normativa europea a la rotura de lunas en 2 supuestos."):
        j = _por_tema(_justificar(ClienteFalso({"rotura de lunas": {"texto": texto, "citas": citas},
                                                "cobertura de daños propios": BIEN_DANOS}), normativa))["rotura de lunas"]
        assert j["estado"] == "generada", (texto, j)
    sin_importe = {"texto": "La póliza cubre la rotura de lunas con un límite anual.", "citas": citas}
    j = _por_tema(_justificar(ClienteFalso({"rotura de lunas": sin_importe, "cobertura de daños propios": BIEN_DANOS}),
                              normativa))["rotura de lunas"]
    assert j["estado"] == "generada", j
    assert j["citas"][0]["extracto"] == LUNAS, j  # v1.3: la cita corta se amplia a la frase completa


# --- specs/97-justificacion-llm-normativa.md#AC-004 --------------------------
def probar_97_ac004_terminos_de_validacion_se_descartan():
    """AC-004: «verificado», «validada» o «garantiza» en el texto -> `descartada` con motivo."""
    for palabra in ("verificado", "Validada", "garantiza"):
        texto = f"La cobertura queda {palabra} por la póliza para los daños propios."
        r = _por_tema(_justificar(ClienteFalso({"cobertura de daños propios": {"texto": texto,
                                                                               "citas": BIEN_DANOS["citas"]},
                                                "pérdida total": BIEN_PT})))
        j = r["cobertura de daños propios"]
        assert j["estado"] == "descartada", (palabra, j)
        assert "validación" in j["motivo"].lower() or "valid" in j["motivo"].lower(), (palabra, j)


# --- specs/97-justificacion-llm-normativa.md#AC-005 --------------------------
def probar_97_ac005_sin_clave_o_sin_autorizacion_no_llama():
    """AC-005: sin cliente (no hay OPENAI_API_KEY) o sin autorizacion de gasto, cada tema queda
    `no_generada` con motivo y no se hace ninguna llamada."""
    sin_cliente = _justificar(None)
    assert [j["estado"] for j in sin_cliente] == ["no_generada", "no_generada"], sin_cliente
    assert all("OPENAI_API_KEY" in j["motivo"] for j in sin_cliente), sin_cliente

    cliente = ClienteFalso({"cobertura de daños propios": BIEN_DANOS, "pérdida total": BIEN_PT})
    sin_autorizacion = _justificar(cliente, autorizado=False)
    assert [j["estado"] for j in sin_autorizacion] == ["no_generada", "no_generada"], sin_autorizacion
    assert all("autorización" in j["motivo"] for j in sin_autorizacion), sin_autorizacion
    assert cliente.llamadas == [], cliente.llamadas


def probar_97_ac005_fallos_del_proveedor_y_respuestas_mal_formadas():
    """AC-005: error del proveedor, tiempo agotado, texto que no es JSON y JSON sin `texto` o sin `citas`
    -> `no_generada` con motivo comprensible, sin excepcion; el otro tema no se ve afectado y ningun
    motivo contiene la clave."""
    clave = "sk-prueba-no-debe-salir"
    os.environ["OPENAI_API_KEY"] = clave
    try:
        fallos = [RuntimeError(f"Error 500 del proveedor con la clave {clave}"), TimeoutError("timed out"),
                  "esto no es JSON", {"citas": BIEN_DANOS["citas"]}, {"texto": BIEN_DANOS["texto"]}]
        for fallo in fallos:
            r = _por_tema(_justificar(ClienteFalso({"cobertura de daños propios": fallo, "pérdida total": BIEN_PT})))
            j = r["cobertura de daños propios"]
            assert j["estado"] == "no_generada", (fallo, j)
            assert j["motivo"] and clave not in j["motivo"] and "Traceback" not in j["motivo"], (fallo, j)
            assert r["pérdida total"]["estado"] == "generada", (fallo, r)
    finally:
        del os.environ["OPENAI_API_KEY"]


def probar_97_ac005_error_del_propio_codigo_se_propaga():
    """AC-005: un error inesperado del codigo (no del proveedor), como una entrada sin `tema`, se propaga."""
    try:
        _justificar(ClienteFalso({}), [{"extracto": DANOS_PROPIOS, "fuente": FR300}])
    except KeyError:
        return
    raise AssertionError("una normativa mal formada no puede convertirse en `no_generada`")


# --- specs/97-justificacion-llm-normativa.md#AC-007 --------------------------
def probar_97_ac007_el_mensaje_solo_lleva_tema_y_pasajes():
    """AC-007: cada mensaje al modelo lleva el tema y los extractos de ese tema, y nada mas: ni fuentes,
    ni pasajes de otros temas (ni, por tanto, ningun dato del calculo o del siniestro, que no recibe)."""
    cliente = ClienteFalso({"cobertura de daños propios": BIEN_DANOS, "pérdida total": BIEN_PT})
    normativa = NORMATIVA + [{"tema": "cobertura de daños propios", "extracto": LUNAS, "fuente": "otra.md"}]
    entrada = copy.deepcopy(normativa)
    justificar_normativa(entrada, cliente=cliente, modelo="modelo-falso", autorizado=True)
    assert entrada == normativa, "la entrada no se puede modificar"
    assert len(cliente.llamadas) == 2, cliente.llamadas
    for llamada in cliente.llamadas:
        datos = json.loads(llamada["messages"][-1]["content"])
        assert set(datos) == {"tema", "pasajes"}, datos
        esperados = [n["extracto"] for n in normativa if n["tema"] == datos["tema"]]
        assert datos["pasajes"] == esperados, datos
        todo = json.dumps(llamada["messages"], ensure_ascii=False)
        assert "fuente" not in todo and FR300 not in todo and "otra.md" not in todo, todo


# --- specs/97-justificacion-llm-normativa.md#AC-010 (cache) ------------------
def probar_97_ac010_segunda_ejecucion_sale_de_la_cache():
    """AC-010: con la misma normativa, modelo y cache, la segunda ejecucion no llama al cliente y devuelve
    las mismas justificaciones; `uso` solo cuenta las llamadas pagadas."""
    with tempfile.TemporaryDirectory() as cache:
        uso: dict[str, int] = {}
        primero = ClienteFalso({"cobertura de daños propios": BIEN_DANOS, "pérdida total": BIEN_PT})
        a = _justificar(primero, cache_dir=cache, uso=uso)
        segundo = ClienteFalso({})
        b = _justificar(segundo, cache_dir=cache, uso=uso)
    assert a == b, (a, b)
    assert len(primero.llamadas) == 2 and segundo.llamadas == [], (primero.llamadas, segundo.llamadas)
    assert uso == {"llamadas": 2, "prompt_tokens": 200, "completion_tokens": 40}, uso


def probar_97_orden_y_temas():
    """Una justificacion por tema distinto, en el orden en que aparecen en `normativa`; sin pasajes, lista vacia."""
    r = _justificar(ClienteFalso({"cobertura de daños propios": BIEN_DANOS, "pérdida total": BIEN_PT}))
    assert [j["tema"] for j in r] == ["cobertura de daños propios", "pérdida total"], r
    assert justificar_normativa([], cliente=ClienteFalso({}), modelo="m", autorizado=True) == []


PRUEBAS = [
    probar_97_ac001_justificacion_generada_con_fuente_del_codigo,
    probar_97_ac002_cita_no_literal_se_descarta,
    probar_97_ac002_cita_con_espacios_distintos_es_literal,
    probar_97_ac002_cita_con_otra_mayuscula_es_literal,
    probar_97_ac002_cita_sin_enfasis_markdown_es_literal,
    probar_97_ac002_otra_mayuscula_no_acepta_otras_palabras,
    probar_97_ac020_cita_corta_se_amplia_a_la_frase_completa,
    probar_97_ac020_frase_completa_no_cambia,
    probar_97_ac020_respeta_salto_de_linea_y_punto_y_coma,
    probar_97_ac020_no_corta_en_abreviaturas_ni_en_numeros,
    probar_97_ac020_frase_demasiado_larga_no_se_amplia,
    probar_97_ac020_cita_ausente_sigue_descartada,
    probar_97_ac020_cita_al_inicio_de_una_frase_no_arrastra_la_anterior,
    probar_97_ac020_enfasis_markdown_al_inicio_de_la_frase_no_arrastra_la_anterior,
    probar_97_ac003_texto_con_importes_se_descarta,
    probar_97_ac004_terminos_de_validacion_se_descartan,
    probar_97_ac005_sin_clave_o_sin_autorizacion_no_llama,
    probar_97_ac005_fallos_del_proveedor_y_respuestas_mal_formadas,
    probar_97_ac005_error_del_propio_codigo_se_propaga,
    probar_97_ac007_el_mensaje_solo_lleva_tema_y_pasajes,
    probar_97_ac010_segunda_ejecucion_sale_de_la_cache,
    probar_97_orden_y_temas,
]


def main() -> int:
    fallos = 0
    for prueba in PRUEBAS:
        try:
            prueba()
        except Exception:  # noqa: BLE001 - se informa y se sigue con las demas
            fallos += 1
            ultima = traceback.format_exc().strip().splitlines()[-1]
            print(f"FALLA  {prueba.__name__}: {ultima[:200]}")
        else:
            print(f"ok     {prueba.__name__}")
    print(f"\n{len(PRUEBAS) - fallos} de {len(PRUEBAS)} pruebas en verde (modulo: {Path(justificacion_llm.__file__).name})")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
