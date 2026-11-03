"""Agente 3 — informe de peritaje en markdown (Issue #31).

Redacta el informe a partir de la salida del Agente 1 (hallazgos) y de la del
Agente 2 (costes, cobertura y normativa). Todas las cifras salen de los JSON:
ninguna se calcula ni se escribe a mano, y no se usa ningun modelo de lenguaje.

Plan: entregas/cu-19-interpretacion-danos/specs/31-informe-peritaje.md
Contrato de entrada: ADR 0002 y app/agentes/ejemplos_contrato/.
Catalogo de la empresa: piia2_paquete_datos/ (fuera de git).
"""

from __future__ import annotations

import csv
import re
from datetime import date
from pathlib import Path


def _raiz_repo() -> Path:
    for carpeta in [Path(__file__).resolve(), *Path(__file__).resolve().parents]:
        if (carpeta / ".git").exists():
            return carpeta
    raise RuntimeError("No se encontro la raiz del repo (.git)")


DATA = _raiz_repo() / "piia2_paquete_datos" / "data"


def _leer_csv(nombre: str, clave: str) -> dict[str, dict]:
    with open(DATA / nombre, encoding="utf-8") as f:
        return {fila[clave]: fila for fila in csv.DictReader(f)}


PIEZAS = _leer_csv("piezas.csv", "pieza_id")
VEHICULOS = _leer_csv("vehiculos.csv", "vehiculo_id")
POLIZAS = _leer_csv("polizas.csv", "poliza_id")
with open(DATA / "reglas_dano.csv", encoding="utf-8") as _f:
    REGLAS = {(r["clase_cardd"], r["zona_tipo"], r["severidad"]): r["accion"] for r in csv.DictReader(_f)}

AVISO_LEGAL = ("Informe generado automáticamente con datos sintéticos de prototipo. Las cifras son "
               "orientativas y no vinculantes, y no sustituyen a una valoración pericial.")
POLIZA_TERCERO = "Terceros (RC obligatoria)"

ACCION_TEXTO = {
    "sustituir": "Sustituir la pieza",
    "sustituir_pintar": "Sustituir la pieza y pintarla",
    "reparar_pintar": "Reparar (desabollar) y pintar",
    "reparar_plastico_pintar": "Reparar el plástico y pintar",
    "pintar_panel": "Pintar el panel",
    "pulido": "Pulir / repasar",
    "reparar_impacto": "Reparar el impacto con resina",
    "reparar_pinchazo": "Reparar el pinchazo",
    "sustituir_neumatico": "Sustituir el neumático y alinear",
}
CLASE_TEXTO = {
    "dent": "abolladura", "scratch": "arañazo", "crack": "grieta",
    "glass_shatter": "rotura de cristal", "lamp_broken": "óptica rota", "tire_flat": "neumático pinchado",
}
MOTIVO_FUERA = {
    "rechazado_por_vision": "rechazado por la visión: el modelo no ve el daño (probable falso positivo)",
    "sin_pieza_o_severidad": "no se pudo identificar la pieza o la severidad",
    "sin_regla_de_coste": "no hay regla de coste para esta combinación de daño, pieza y severidad",
}
CONCEPTOS = [
    ("Piezas", "piezas"), ("Mano de obra de chapa", "mano_obra_chapa"),
    ("Mano de obra de pintura", "mano_obra_pintura"), ("Mano de obra de mecánica", "mano_obra_mecanica"),
    ("Materiales de pintura", "materiales_pintura"), ("Otros", "otros"),
]
NINGUNO = "_Ninguno._"


def eur(x: float) -> str:
    """1233.55 -> '1.233,55 €' (formato espanol). Es la unica funcion que
    escribe importes, para que `comprobar_cifras` los reconozca todos."""
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def _decimal(x: float) -> str:
    """0.28 -> '0,28'."""
    return f"{x:.2f}".replace(".", ",")


def _porcentaje(x: float) -> str:
    """0.9 -> '90 %'."""
    return f"{x * 100:.0f} %"


def _si_no(valor: bool) -> str:
    return "Sí" if valor else "No"


def _pieza(f: dict) -> str:
    return PIEZAS[f["pieza_id"]]["nombre"] if f["pieza_id"] else "—"


def _reparacion(f: dict) -> str:
    if not f["pieza_id"] or not f["severidad"]:
        return "—"
    accion = REGLAS.get((f["clase_tool"], PIEZAS[f["pieza_id"]]["zona_tipo"], f["severidad"]))
    return ACCION_TEXTO.get(accion, "—")


def _motivos_pendiente(f: dict) -> str:
    motivos = []
    if f["score_tier"] == "needs_review":
        motivos.append(f"score de detección bajo ({_decimal(f['score'])})")
    if f["vision_verdict"] != "confirmado":
        motivos.append(f"la visión lo ve {f['vision_verdict']}")
    if f["regla_coste_aplicable"] is not True:
        motivos.append("sin regla de coste")
    return "; ".join(motivos) or "pendiente de verificación"


def _tabla_hallazgos(hallazgos: list[dict], con_motivo: bool = False) -> list[str]:
    if not hallazgos:
        return [NINGUNO]
    ultima = "Por qué está pendiente" if con_motivo else "Score"
    filas = [f"| ID | Pieza | Daño | Severidad | Reparación | {ultima} |", "|---|---|---|---|---|---|"]
    for f in hallazgos:
        final = _motivos_pendiente(f) if con_motivo else _decimal(f["score"])
        filas.append(f"| {f['finding_id']} | {_pieza(f)} | {CLASE_TEXTO.get(f['clase_tool'], f['category'])} | "
                     f"{f['severidad'] or '—'} | {_reparacion(f)} | {final} |")
    imagenes = " ".join(f"![{f['finding_id']}]({f['crop_image_path']})" for f in hallazgos if f.get("crop_image_path"))
    return filas + ([""] + [imagenes] if imagenes else [])


def _arrastres(escenarios: dict) -> list[dict]:
    """Arrastres de los dos escenarios, sin repetir pieza y origen."""
    vistos, lista = set(), []
    for nombre in ("confirmados", "con_pendientes"):
        for a in escenarios[nombre]["estimacion"]["arrastres_posibles"]:
            if (a["pieza_id"], a["origen"]) not in vistos:
                vistos.add((a["pieza_id"], a["origen"]))
                lista.append(a)
    return lista


def generar_informe(agente1: dict, agente2: dict, hoy: str | None = None) -> str:
    """Informe de peritaje en markdown (specs/31-informe-peritaje.md#AC-001).
    TODAS las cifras salen de `agente2`: ninguna se calcula aqui."""
    hoy = hoy or date.today().isoformat()
    ctx = agente2["contexto"]
    veh = VEHICULOS[ctx["vehiculo_id"]]
    esc_c, esc_p = agente2["escenarios"]["confirmados"], agente2["escenarios"]["con_pendientes"]
    est_c, est_p = esc_c["estimacion"], esc_p["estimacion"]
    cob_c, cob_p = esc_c["cobertura"], esc_p["cobertura"]
    por_id = {f["finding_id"]: f for f in agente1["findings"]}
    confirmados = [por_id[i] for i in esc_c["hallazgos_incluidos"]]
    pendientes = [por_id[i] for i in esc_p["hallazgos_incluidos"] if i not in esc_c["hallazgos_incluidos"]]
    fuera = agente2["hallazgos_fuera_del_coste"]
    detecciones = agente1.get("resumen_filtro_previo", {}).get("detecciones_totales", len(agente1["findings"]))
    tercero = ctx["rol"] == "tercero_perjudicado"
    poliza = POLIZA_TERCERO if tercero else POLIZAS[ctx["poliza_id"]]["producto"]

    md = [
        f"# Informe de peritaje — imagen {agente2['image_id']}",
        "",
        f"- **Fecha:** {hoy}",
        f"- **Vehículo:** {veh['marca']} {veh['modelo']}",
        f"- **Taller:** {ctx['tipo_taller']} ({ctx['region']})",
        f"- **Póliza:** {poliza}",
    ]
    if tercero:
        md.append("- **Perjudicado:** un tercero (reclamación por responsabilidad civil)")
    md += [
        "",
        f"> {AVISO_LEGAL}",
        "",
        "## Resumen",
        "",
        f"- {detecciones} detecciones de PIIA-1 frente a {len(agente1['findings'])} hallazgos analizados: "
        f"{len(confirmados)} confirmados, {len(pendientes)} pendientes de revisión y {len(fuera)} no incluidos en el coste.",
        f"- Coste **solo con los daños confirmados**: {eur(est_c['subtotal_sin_iva_eur'])} sin IVA "
        f"({eur(est_c['total_con_iva_eur'])} con IVA).",
        f"- Coste **incluyendo los pendientes**: {eur(est_p['subtotal_sin_iva_eur'])} sin IVA "
        f"({eur(est_p['total_con_iva_eur'])} con IVA).",
        f"- Pérdida total (valor venal {eur(agente2['valor_venal_eur'])}, umbral {_porcentaje(agente2['umbral_perdida_total'])}): "
        f"{_si_no(cob_c['perdida_total'])} con los confirmados; {_si_no(cob_p['perdida_total'])} incluyendo los pendientes.",
        f"- Indemnización estimada: {eur(cob_c['indemnizacion_estimada_eur'])} con los confirmados; "
        f"{eur(cob_p['indemnizacion_estimada_eur'])} incluyendo los pendientes.",
        "",
        "## Daños confirmados",
        "",
        *_tabla_hallazgos(confirmados),
        "",
        "## Daños pendientes de revisión",
        "",
        "Entran en el segundo presupuesto, pero **no están confirmados**: requieren verificación humana.",
        "",
        *_tabla_hallazgos(pendientes, con_motivo=True),
        "",
        "## Detecciones no incluidas en el coste",
        "",
        *([f"- {x['finding_id']} ({por_id[x['finding_id']]['category']}): {MOTIVO_FUERA[x['motivo']]}." for x in fuera]
          or [NINGUNO]),
        "",
        "## Desglose del coste",
        "",
        "| Concepto | Solo confirmados | Con pendientes |",
        "|---|---:|---:|",
        *[f"| {nombre} | {eur(est_c['desglose'][k])} | {eur(est_p['desglose'][k])} |" for nombre, k in CONCEPTOS],
        f"| **Subtotal sin IVA** | **{eur(est_c['subtotal_sin_iva_eur'])}** | **{eur(est_p['subtotal_sin_iva_eur'])}** |",
        f"| IVA | {eur(est_c['iva_eur'])} | {eur(est_p['iva_eur'])} |",
        f"| **Total con IVA** | **{eur(est_c['total_con_iva_eur'])}** | **{eur(est_p['total_con_iva_eur'])}** |",
        "",
        "## Posibles daños asociados (no incluidos en el coste)",
        "",
    ]
    arrastres = _arrastres(agente2["escenarios"])
    if arrastres:
        md += ["En impactos de esta gravedad suelen verse afectadas también estas piezas; hay que revisarlas en taller:", ""]
        md += [f"- {PIEZAS[a['pieza_id']]['nombre']} (probabilidad {_porcentaje(a['probabilidad'])}, "
               f"por el daño en {PIEZAS[a['origen']]['nombre'].lower()})" for a in arrastres]
    else:
        md.append("_Ninguno previsto._")

    md += [
        "",
        "## Cobertura e indemnización",
        "",
        f"Póliza: {poliza}.",
        "",
        "| | Solo confirmados | Con pendientes |",
        "|---|---|---|",
        f"| Cubierto | {_si_no(cob_c['cubierto'])} | {_si_no(cob_p['cubierto'])} |",
        f"| Motivo | {cob_c['motivo']} | {cob_p['motivo']} |",
        f"| Franquicia | {eur(cob_c['franquicia_eur'])} | {eur(cob_p['franquicia_eur'])} |",
        f"| Pérdida total | {_si_no(cob_c['perdida_total'])} | {_si_no(cob_p['perdida_total'])} |",
        f"| Indemnización estimada | {eur(cob_c['indemnizacion_estimada_eur'])} | {eur(cob_p['indemnizacion_estimada_eur'])} |",
        "",
        "## Fuentes consultadas",
        "",
    ]
    md += [f"- {n['tema']}: «{n['extracto']}» ({n['fuente']})" for n in agente2["normativa"]] or ["_Sin fuentes._"]
    return "\n".join(md) + "\n"


# Un importe seguido de `€`, con o sin separador de miles: el numero entero,
# sin dejarse cifras delante (con `1234,56 €` el patron de la guia daba 234,56).
_IMPORTE = re.compile(r"(?<![\d.,])(\d{1,3}(?:\.\d{3})+|\d+),(\d{2})\s?€")


def importes_en_euros(texto: str) -> list[float]:
    """Todos los importes en euros del texto, como float."""
    return [float(entero.replace(".", "") + "." + dec) for entero, dec in _IMPORTE.findall(texto)]


def _importes_permitidos(obj, en_desglose: bool = False) -> set[float]:
    """Campos monetarios de la salida del Agente 2: las claves terminadas en
    `_eur` (incluido el `importe_eur` de cada linea) y los valores de
    `desglose`. Otros numeros (image_id, km, edad_anios, cantidades,
    probabilidades) no cuentan (specs/31-informe-peritaje.md#AC-013)."""
    permitidos = set()
    if isinstance(obj, dict):
        for clave, valor in obj.items():
            if isinstance(valor, (int, float)) and not isinstance(valor, bool):
                if en_desglose or clave.endswith("_eur"):
                    permitidos.add(round(float(valor), 2))
            else:
                permitidos |= _importes_permitidos(valor, en_desglose=clave == "desglose")
    elif isinstance(obj, list):
        for valor in obj:
            permitidos |= _importes_permitidos(valor)
    return permitidos


def comprobar_cifras(informe: str, agente2: dict) -> list[float]:
    """Importes del informe que NO estan entre los campos monetarios de la
    salida del Agente 2 (lista vacia = ninguna cifra inventada;
    specs/31-informe-peritaje.md#AC-003, AC-004 y AC-013)."""
    permitidos = _importes_permitidos(agente2)
    return [x for x in importes_en_euros(informe) if round(x, 2) not in permitidos]
