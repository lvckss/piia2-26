"""Justificacion con un LLM de la normativa recuperada por el RAG (Issue #97, slice 1).

Para cada tema con pasajes en `normativa` (salida de `agente2()`, #32), un LLM recibe SOLO el tema y
sus pasajes y devuelve un texto breve con las citas literales en las que se apoya. El codigo comprueba
la respuesta antes de aceptarla: citas literales del mismo tema (la fuente la pone el codigo), texto
sin importes en euros y sin terminos de validacion. Nunca cambia cifras: no recibe el calculo.

Plan: entregas/cu-19-interpretacion-danos/specs/97-justificacion-llm-normativa.md (AC-001 a AC-005,
AC-007 y la cache de AC-010). Decision: docs/adr/0009-justificacion-llm-normativa.md. Proveedor, clave,
cache y gasto: ADR 0003 (el cliente se recibe como parametro; pruebas sin red con un cliente falso).
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

PROMPT_SISTEMA = (
    "Redactas, en español, una justificación breve (como mucho tres frases) de lo que dicen unos pasajes "
    "de una póliza de seguro o de la legislación sobre un tema. Usa solo la información de los pasajes, sin "
    "añadir nada. No escribas ningún importe en euros. No digas que algo está verificado, validado o "
    "garantizado. Responde solo con un objeto JSON con dos claves: \"texto\" (la justificación) y \"citas\" "
    "(lista de fragmentos copiados literalmente de los pasajes que la apoyan; al menos uno)."
)

MOTIVO_SIN_CLAVE = "No se ha podido pedir la justificación: falta la clave del modelo (OPENAI_API_KEY)."
MOTIVO_SIN_AUTORIZACION = "No se ha pedido la justificación: no hay autorización de gasto para llamar al modelo."
MOTIVO_PROVEEDOR = "El modelo no respondió (error del proveedor o tiempo agotado)."
MOTIVO_MAL_FORMADA = "La respuesta del modelo no tenía el formato esperado (texto y citas)."

# Un importe en euros en cualquier formato: «300 €», «1.500 EUR», «1500 EUR», «300,00 euros», «€ 300»...
_NUMERO = r"\d{1,3}(?:[.\s]\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?"
_IMPORTE = re.compile(rf"(?:{_NUMERO})\s*(?:€|\beur\b|\beuros?\b)|(?:€|\beur\b)\s*(?:{_NUMERO})", re.IGNORECASE)
# Raices que presentarian el texto como validacion juridica (spec 97, AC-004; spec 31, AC-014).
_VALIDACION = re.compile(r"verific|valid|garantiz", re.IGNORECASE)


def _normalizar(texto: str) -> str:
    """Colapsa los espacios en blanco consecutivos (unica normalizacion admitida al comparar citas)."""
    return re.sub(r"\s+", " ", texto).strip()


def _por_tema(normativa: list[dict]) -> dict[str, list[dict]]:
    """Pasajes por tema, en el orden en que aparece cada tema. Una entrada sin `tema` o sin `extracto`
    es un error del codigo que la produce y se propaga (KeyError)."""
    temas: dict[str, list[dict]] = {}
    for n in normativa:
        tema, extracto = n["tema"], n["extracto"]
        if extracto.strip():
            temas.setdefault(tema, []).append(n)
    return temas


def _mensajes(tema: str, pasajes: list[dict]) -> list[dict]:
    """Solo el tema y sus extractos (AC-007): ni fuentes, ni otros temas, ni datos del calculo."""
    entrada = {"tema": tema, "pasajes": [p["extracto"] for p in pasajes]}
    return [{"role": "system", "content": PROMPT_SISTEMA},
            {"role": "user", "content": json.dumps(entrada, ensure_ascii=False)}]


def _leer_respuesta(texto: str) -> dict | None:
    """El JSON del modelo con `texto` (cadena no vacia) y `citas` (lista), o None si no tiene esa forma."""
    try:
        datos = json.loads(texto)
    except (TypeError, ValueError):
        return None
    if not isinstance(datos, dict):
        return None
    if not isinstance(datos.get("texto"), str) or not datos["texto"].strip() or not isinstance(datos.get("citas"), list):
        return None
    return datos


def _comprobar(tema: str, pasajes: list[dict], datos: dict) -> dict:
    """Acepta (`generada`) o descarta (`descartada`, con motivo) la respuesta de un tema."""
    texto = datos["texto"].strip()
    importe = _IMPORTE.search(texto)
    if importe:
        return _descartada(tema, f"El texto contiene un importe («{importe.group(0)}»); los importes solo pueden "
                                 "aparecer en las citas.")
    termino = _VALIDACION.search(texto)
    if termino:
        return _descartada(tema, "El texto se presenta como validación jurídica (verificar, validar o garantizar).")
    if not datos["citas"]:
        return _descartada(tema, "La justificación no aporta ninguna cita.")

    citas = []
    for cita in datos["citas"]:
        extracto = cita.get("extracto") if isinstance(cita, dict) else cita
        extracto = _normalizar(extracto) if isinstance(extracto, str) else ""
        pasaje = next((p for p in pasajes if extracto and extracto in _normalizar(p["extracto"])), None)
        if pasaje is None:
            return _descartada(tema, f"La cita «{extracto[:80]}» no aparece literalmente en los pasajes de este tema.")
        citas.append({"extracto": extracto, "fuente": pasaje["fuente"]})
    return {"tema": tema, "estado": "generada", "texto": texto, "citas": citas}


def _descartada(tema: str, motivo: str) -> dict:
    return {"tema": tema, "estado": "descartada", "motivo": motivo}


def _no_generada(tema: str, motivo: str) -> dict:
    return {"tema": tema, "estado": "no_generada", "motivo": motivo}


def _consultar(cliente: Any, modelo: str, mensajes: list[dict], uso: dict[str, int] | None) -> str:
    respuesta = cliente.chat.completions.create(model=modelo, messages=mensajes,
                                                response_format={"type": "json_object"})
    texto = respuesta.choices[0].message.content or ""
    if uso is not None:
        tokens = getattr(respuesta, "usage", None)
        uso["llamadas"] = uso.get("llamadas", 0) + 1
        uso["prompt_tokens"] = uso.get("prompt_tokens", 0) + int(getattr(tokens, "prompt_tokens", 0) or 0)
        uso["completion_tokens"] = uso.get("completion_tokens", 0) + int(getattr(tokens, "completion_tokens", 0) or 0)
    return texto


def justificar_normativa(normativa: list[dict], *, cliente: Any, modelo: str, cache_dir: str | Path | None = None,
                         autorizado: bool = False, uso: dict[str, int] | None = None) -> list[dict]:
    """Justificaciones por tema a partir de `normativa` (lista de `{tema, extracto, fuente}`).

    Devuelve una lista con un elemento por tema que tiene pasajes, en el orden de `normativa`:
    - `{"tema", "estado": "generada", "texto", "citas": [{"extracto", "fuente"}, ...]}`;
    - `{"tema", "estado": "descartada", "motivo"}` si la respuesta no pasa la comprobacion;
    - `{"tema", "estado": "no_generada", "motivo"}` si no se pudo pedir o recibir: sin `cliente` (no hay
      `OPENAI_API_KEY`), sin `autorizado` (gasto), error o tiempo agotado del proveedor, o respuesta sin
      el formato esperado.
    Con `cache_dir`, las respuestas validas se guardan por modelo y mensaje y no se vuelven a pagar; lo que
    sale de la cache no necesita cliente ni autorizacion. `uso` acumula llamadas y tokens pagados.
    No modifica la entrada. Un error del propio codigo (por ejemplo, una entrada sin `tema`) se propaga."""
    resultado = []
    for tema, pasajes in _por_tema(normativa).items():
        mensajes = _mensajes(tema, pasajes)
        clave = hashlib.sha256(f"{modelo}|{json.dumps(mensajes, ensure_ascii=False, sort_keys=True)}".encode("utf-8"))
        ruta_cache = Path(cache_dir) / f"{clave.hexdigest()}.json" if cache_dir is not None else None

        datos = None
        if ruta_cache is not None and ruta_cache.exists():
            datos = _leer_respuesta(json.loads(ruta_cache.read_text(encoding="utf-8"))["respuesta"])
        if datos is None:
            if cliente is None:
                resultado.append(_no_generada(tema, MOTIVO_SIN_CLAVE))
                continue
            if not autorizado:
                resultado.append(_no_generada(tema, MOTIVO_SIN_AUTORIZACION))
                continue
            try:
                texto = _consultar(cliente, modelo, mensajes, uso)
            except Exception:  # noqa: BLE001 - cualquier fallo del proveedor deja el tema sin justificar
                resultado.append(_no_generada(tema, MOTIVO_PROVEEDOR))
                continue
            datos = _leer_respuesta(texto)
            if datos is None:
                resultado.append(_no_generada(tema, MOTIVO_MAL_FORMADA))
                continue
            if ruta_cache is not None:
                ruta_cache.parent.mkdir(parents=True, exist_ok=True)
                ruta_cache.write_text(json.dumps({"modelo": modelo, "respuesta": texto}, ensure_ascii=False),
                                      encoding="utf-8")
        resultado.append(_comprobar(tema, pasajes, datos))
    return resultado
