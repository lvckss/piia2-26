"""Agente 2 — costes y cobertura (Issue #30).

Convierte los hallazgos del Agente 1 en dos presupuestos con la herramienta de
costes de la empresa y calcula perdida total, cobertura e indemnizacion
estimada. Todo es determinista: no usa ningun modelo de lenguaje ni red.

Plan: entregas/cu-19-interpretacion-danos/specs/30-costes-cobertura.md
Contrato de entrada y salida: ADR 0002 y app/agentes/ejemplos_contrato/.
Herramienta y datos de la empresa: ADR 0004 (piia2_paquete_datos/, fuera de git).
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path


def _raiz_repo() -> Path:
    for carpeta in [Path(__file__).resolve(), *Path(__file__).resolve().parents]:
        if (carpeta / ".git").exists():
            return carpeta
    raise RuntimeError("No se encontro la raiz del repo (.git)")


PAQUETE = _raiz_repo() / "piia2_paquete_datos"
if not (PAQUETE / "scripts" / "estimar_coste.py").is_file():
    raise ImportError(
        f"No se encuentra el paquete de datos de la empresa en {PAQUETE}. "
        "Extrae piia2_paquete_datos.zip en la raiz del repo (esta en .gitignore)."
    )
sys.path.insert(0, str(PAQUETE / "scripts"))
from estimar_coste import estimar_coste, valor_venal  # noqa: E402


def _leer_csv(nombre: str, clave: str) -> dict[str, dict]:
    with open(PAQUETE / "data" / nombre, encoding="utf-8") as f:
        return {fila[clave]: fila for fila in csv.DictReader(f)}


POLIZAS = _leer_csv("polizas.csv", "poliza_id")
PIEZAS = _leer_csv("piezas.csv", "pieza_id")
VEHICULOS = _leer_csv("vehiculos.csv", "vehiculo_id")

ROLES = ("propio", "tercero_perjudicado")
CAMPOS_OBLIGATORIOS = ("vehiculo_id", "region", "tipo_taller", "acabado", "tipo_pieza", "rol", "edad_anios", "km")
# Textos de motivo tal como los usa el generador de siniestros de la empresa
# (piia2_paquete_datos/scripts/generate_claims.py), para que la evaluacion
# de AC-011 compare cosas comparables.
MOTIVO_TERCERO = "Daños a tercero: RC obligatoria (acción directa, LRCSCVM art. 7)"
MOTIVO_SIN_DANOS = "Sin daños presupuestables"


def validar_contexto(contexto: dict) -> None:
    """Lanza ValueError si el contexto del siniestro no es valido, nombrando
    el campo (specs/30-costes-cobertura.md#AC-010)."""
    for campo in CAMPOS_OBLIGATORIOS:
        if campo not in contexto:
            raise ValueError(f"falta el campo obligatorio del contexto: {campo}")
    if contexto["rol"] not in ROLES:
        raise ValueError(f"rol no valido: {contexto['rol']!r} (debe ser {' o '.join(ROLES)})")
    if contexto["vehiculo_id"] not in VEHICULOS:
        raise ValueError(f"vehiculo_id no esta en el catalogo de la empresa: {contexto['vehiculo_id']!r}")
    for campo in ("edad_anios", "km"):
        valor = contexto[campo]
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor) or valor < 0:
            raise ValueError(f"{campo} debe ser un numero finito y no negativo: {valor!r}")
    if contexto["rol"] == "propio":
        if "poliza_id" not in contexto:
            raise ValueError("falta el campo obligatorio del contexto: poliza_id (rol propio)")
        if contexto["poliza_id"] not in POLIZAS:
            raise ValueError(f"poliza_id no esta en polizas.csv: {contexto['poliza_id']!r}")


def clasificar_hallazgos(findings: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Reparte los hallazgos del Agente 1 en tres grupos
    (specs/30-costes-cobertura.md#AC-002):
    - confirmados: entran en los dos escenarios de coste;
    - pendientes: needs_review con pieza, severidad y regla de coste, solo en
      el escenario "con pendientes";
    - fuera: no se pueden presupuestar, con el motivo.
    Un hallazgo `confirmed` ya trae pieza, severidad y regla (lo garantiza
    `decidir_tier` del Agente 1), asi que no se vuelve a comprobar."""
    confirmados, pendientes, fuera = [], [], []
    for f in findings:
        if f["confidence_tier"] == "confirmed":
            confirmados.append(f)
        elif f["vision_verdict"] == "rechazado":
            fuera.append({"finding_id": f["finding_id"], "motivo": "rechazado_por_vision"})
        elif not f["pieza_id"] or not f["severidad"]:
            fuera.append({"finding_id": f["finding_id"], "motivo": "sin_pieza_o_severidad"})
        elif f["regla_coste_aplicable"] is not True:
            fuera.append({"finding_id": f["finding_id"], "motivo": "sin_regla_de_coste"})
        else:
            pendientes.append(f)
    return confirmados, pendientes, fuera


def _danos(hallazgos: list[dict]) -> list[dict]:
    return [{"clase": f["clase_tool"], "pieza_id": f["pieza_id"], "severidad": f["severidad"]} for f in hallazgos]


def umbral_perdida_total(contexto: dict) -> float:
    if contexto["rol"] == "tercero_perjudicado":
        return 1.0
    return float(POLIZAS[contexto["poliza_id"]]["umbral_perdida_total"])


def calcular_cobertura(contexto: dict, estimacion: dict, danos: list[dict]) -> dict:
    """Perdida total, cobertura e indemnizacion. Replica la logica con la que
    la empresa genero sus siniestros (scripts/generate_claims.py)."""
    if not danos:
        return {"cubierto": False, "motivo": MOTIVO_SIN_DANOS, "franquicia_eur": 0.0,
                "perdida_total": False, "indemnizacion_estimada_eur": 0.0}

    subtotal = estimacion["subtotal_sin_iva_eur"]
    total_iva = estimacion["total_con_iva_eur"]
    vv = valor_venal(contexto["vehiculo_id"], contexto["edad_anios"], contexto["km"])
    umbral = umbral_perdida_total(contexto)
    perdida_total = umbral > 0 and subtotal >= umbral * vv
    solo_cristal = all(PIEZAS[d["pieza_id"]]["zona_tipo"] == "cristal" for d in danos)

    if contexto["rol"] == "tercero_perjudicado":
        cubierto, franquicia, motivo = True, 0.0, MOTIVO_TERCERO
        indemnizacion = vv if perdida_total else total_iva
    else:
        poliza = POLIZAS[contexto["poliza_id"]]
        if solo_cristal and poliza["cubre_lunas"] == "1":
            cubierto, motivo = True, "Cobertura de lunas"
            franquicia = float(poliza["franquicia_lunas_eur"])
            indemnizacion = min(total_iva, float(poliza["limite_lunas_anual_eur"])) - franquicia
        elif poliza["cubre_danos_propios_colision"] == "1":
            cubierto = True
            franquicia = float(poliza["franquicia_danos_propios_eur"])
            motivo = "Pérdida total" if perdida_total else "Daños propios por colisión"
            if perdida_total:
                mas_10 = poliza["criterio_indemnizacion_perdida_total"] == "valor_venal_mas_10pct"
                base = vv * (1.10 if mas_10 else 1.0)
            else:
                base = total_iva
            indemnizacion = base - franquicia
        else:
            cubierto, franquicia, indemnizacion = False, 0.0, 0.0
            motivo = "Póliza sin cobertura de daños propios para este siniestro"

    return {
        "cubierto": cubierto,
        "motivo": motivo,
        "franquicia_eur": franquicia,
        "perdida_total": perdida_total,
        "indemnizacion_estimada_eur": round(max(0.0, indemnizacion), 2) if cubierto else 0.0,
    }


def _escenario(contexto: dict, hallazgos: list[dict]) -> dict:
    danos = _danos(hallazgos)
    estimacion = estimar_coste(
        contexto["vehiculo_id"], danos,
        region=contexto["region"], tipo_taller=contexto["tipo_taller"],
        acabado=contexto["acabado"], tipo_pieza=contexto["tipo_pieza"],
    )
    return {
        "hallazgos_incluidos": [f["finding_id"] for f in hallazgos],
        "estimacion": estimacion,
        "cobertura": calcular_cobertura(contexto, estimacion, danos),
    }


def estimar_siniestro(salida_agente1: dict, contexto: dict) -> dict:
    """Salida del Agente 2 para el Agente 3 (contrato del ADR 0002).

    `normativa` va vacia: la rellena el RAG de la #32 en `agente2()`."""
    validar_contexto(contexto)
    confirmados, pendientes, fuera = clasificar_hallazgos(salida_agente1["findings"])
    return {
        "image_id": salida_agente1["image_id"],
        "contexto": dict(contexto),
        "valor_venal_eur": valor_venal(contexto["vehiculo_id"], contexto["edad_anios"], contexto["km"]),
        "umbral_perdida_total": umbral_perdida_total(contexto),
        "escenarios": {
            "confirmados": _escenario(contexto, confirmados),
            "con_pendientes": _escenario(contexto, confirmados + pendientes),
        },
        "hallazgos_fuera_del_coste": fuera,
        "normativa": [],
    }
