"""Composición de costes, recuperación normativa y justificación (#32, #97).

Plan: specs/32-rag-normativa.md#AC-006, AC-007 y AC-008; y
specs/97-justificacion-llm-normativa.md#AC-006. La selección de temas usa los
resultados de costes y los hallazgos incluidos, sin recalcular el siniestro.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

from costes_y_cobertura import PIEZAS, estimar_siniestro
from normativa_rag import RagError, buscar_normativa
from justificacion_llm import justificar_normativa


_MOTIVO_SIN_COBERTURA = "Póliza sin cobertura de daños propios para este siniestro"
_MOTIVO_LUNAS = "Cobertura de lunas"
_MOTIVO_PERDIDA_TOTAL = "Pérdida total"
_ROL_TERCERO = "tercero_perjudicado"

_TEMA_COLISION = "Daños propios por colisión: cobertura y franquicia"
_TEMA_CRISTAL = "Daños de cristal: cobertura, franquicia y límite de lunas"
_TEMA_PERDIDA_TOTAL = "Pérdida total: criterio y regla de indemnización"
_TEMA_SIN_COBERTURA = "Cobertura de daños propios: cláusula aplicable a este siniestro"
_TEMA_TERCERO = "Responsabilidad civil obligatoria de terceros perjudicados: legislación"


def _hallazgos_por_id(salida_agente1: dict) -> dict[str, dict]:
    return {hallazgo["finding_id"]: hallazgo for hallazgo in salida_agente1["findings"]}


def _temas_aplicables(salida_agente1: dict, contexto: dict, salida_costes: dict) -> list[str]:
    escenarios = salida_costes["escenarios"]
    hallazgos = _hallazgos_por_id(salida_agente1)
    temas: list[str] = []

    def agregar(tema: str) -> None:
        if tema not in temas:
            temas.append(tema)

    for escenario in (escenarios["confirmados"], escenarios["con_pendientes"]):
        incluidos = escenario["hallazgos_incluidos"]
        if not incluidos:
            continue
        cobertura = escenario["cobertura"]
        motivo = cobertura["motivo"]
        if contexto["rol"] == _ROL_TERCERO:
            agregar(_TEMA_TERCERO)
            continue

        danos = [hallazgos[fid] for fid in incluidos]
        hay_cristal_por_pieza = any(PIEZAS[h["pieza_id"]]["zona_tipo"] == "cristal" for h in danos)
        if hay_cristal_por_pieza or motivo == _MOTIVO_LUNAS:
            agregar(_TEMA_CRISTAL)
        if any(PIEZAS[h["pieza_id"]]["zona_tipo"] != "cristal" for h in danos):
            agregar(_TEMA_COLISION)
        if cobertura["perdida_total"] or motivo == _MOTIVO_PERDIDA_TOTAL:
            agregar(_TEMA_PERDIDA_TOTAL)
        if motivo == _MOTIVO_SIN_COBERTURA:
            agregar(_TEMA_SIN_COBERTURA)

    return temas


def _autorizacion_de_gasto() -> bool:
    """Solo autoriza el LLM cuando la consulta RAG tiene permiso y presupuesto finito."""
    if os.environ.get("RAG_QUERY_EXECUTE") != "1":
        return False
    try:
        presupuesto = float(os.environ["RAG_QUERY_MAX_COST_USD"])
    except (KeyError, ValueError):
        return False
    return math.isfinite(presupuesto) and presupuesto >= 0


def _cliente_openai() -> Any | None:
    """Crea el cliente bajo demanda; importar el módulo no lee secretos ni accede a red."""
    from configuracion_rag import load_environment

    load_environment()
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    from openai import OpenAI

    return OpenAI()


def _incidencia(error: Exception) -> dict:
    if isinstance(error, RagError):
        return {
            "codigo": error.code,
            "etapa": error.stage,
            "mensaje": str(error),
            "reintentable": error.retryable,
        }
    return {
        "codigo": "EJECUCION_NO_AUTORIZADA",
        "etapa": "configuracion",
        "mensaje": str(error),
        "reintentable": False,
    }


def _estado_agregado(consultas: list[dict]) -> str:
    if not consultas:
        return "no_aplica"
    estados = [consulta["estado"] for consulta in consultas]
    con_fuentes = sum(estado == "recuperadas" for estado in estados)
    if con_fuentes == len(estados):
        return "recuperadas"
    if con_fuentes:
        return "parcial"
    if any(estado == "error" for estado in estados):
        return "error"
    return "sin_resultados"


def agente2(
    salida_agente1: dict,
    contexto: dict,
    *,
    cliente: Any | None = None,
    modelo: str | None = None,
    autorizado: bool | None = None,
    cache_dir: str | Path | None = None,
    uso: dict[str, int] | None = None,
) -> dict:
    """Calcula el siniestro y añade normativa, diagnóstico y justificaciones.

    Las dos entradas posicionales mantienen el contrato de #30. Los argumentos
    keyword-only permiten inyectar un cliente/modelo en pruebas. La ejecución
    normal hereda la autorización RAG y solo crea el cliente si está autorizada.
    """
    salida_costes = estimar_siniestro(salida_agente1, contexto)
    temas = _temas_aplicables(salida_agente1, contexto, salida_costes)
    poliza_id = "" if contexto["rol"] == _ROL_TERCERO else contexto["poliza_id"]
    normativa: list[dict] = []
    consultas: list[dict] = []

    for tema in temas:
        try:
            resultados = buscar_normativa(tema, k=4, poliza_id=poliza_id)
        except (RagError, PermissionError) as error:
            incidencia = _incidencia(error)
            consultas.append({
                "tema": tema,
                "estado": "error",
                "fuentes": [],
                "incidencias": [incidencia],
            })
            continue

        # El retriever devuelve ya `{tema, extracto, fuente}`; copiar cada fila
        # evita que consumidores muten objetos compartidos con un fake o caché.
        filas = [dict(resultado) for resultado in resultados]
        normativa.extend(filas)
        consultas.append({
            "tema": tema,
            "estado": "recuperadas" if filas else "sin_resultados",
            "fuentes": list(dict.fromkeys(fila["fuente"] for fila in filas)),
            "incidencias": [],
        })

    diagnostico = {"estado": _estado_agregado(consultas), "consultas": consultas}
    resultado = dict(salida_costes)
    resultado["normativa"] = normativa
    resultado["diagnostico_rag"] = diagnostico

    if cliente is None and autorizado is None:
        autorizado = _autorizacion_de_gasto()
    elif autorizado is None:
        autorizado = _autorizacion_de_gasto()

    if autorizado and cliente is None and normativa:
        cliente = _cliente_openai()
    if modelo is None:
        # El nombre no tiene un default implícito: se usa exactamente el
        # configurado para el proveedor, como fija el ADR 0003.
        modelo = os.environ.get("OPENAI_MODEL")
    if cache_dir is None:
        cache_dir = Path(__file__).resolve().parents[3] / ".cache-rag" / "justificaciones"

    resultado["justificaciones"] = justificar_normativa(
        normativa,
        cliente=cliente,
        modelo=modelo or "",
        cache_dir=cache_dir,
        autorizado=bool(autorizado),
        uso=uso,
    )
    return resultado
