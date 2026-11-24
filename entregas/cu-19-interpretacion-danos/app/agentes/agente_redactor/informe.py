"""Agente 3 — informe de peritaje en markdown (Issue #31).

Redacta el informe a partir de la salida del Agente 1 (hallazgos) y de la del
Agente 2 (costes, cobertura y normativa). Todas las cifras salen de los JSON:
ninguna se calcula ni se escribe a mano, y no se usa ningun modelo de lenguaje.

Plan: entregas/cu-19-interpretacion-danos/specs/31-informe-peritaje.md
Contrato de entrada: ADR 0002 y app/agentes/ejemplos_contrato/.
Catalogo de la empresa: piia2_paquete_datos/ (fuera de git).
Equivalencias de reglas de coste: ADR 0008 y specs/88-equivalencias-reglas-coste.md.
Justificaciones de la normativa (#97, ADR 0009): las redacta un LLM en el Agente 2; aqui solo se
muestran y se comprueba su forma.
"""

from __future__ import annotations

import csv
import re
import sys
from datetime import date
from pathlib import Path


def _raiz_repo() -> Path:
    for carpeta in [Path(__file__).resolve(), *Path(__file__).resolve().parents]:
        if (carpeta / ".git").exists():
            return carpeta
    raise RuntimeError("No se encontro la raiz del repo (.git)")


PAQUETE = _raiz_repo() / "piia2_paquete_datos"
DATA = PAQUETE / "data"
if not all((DATA / n).is_file() for n in ("piezas.csv", "vehiculos.csv", "polizas.csv", "reglas_dano.csv")):
    raise ImportError(
        f"No se encuentra el paquete de datos de la empresa en {PAQUETE}. "
        "Extrae piia2_paquete_datos.zip en la raiz del repo (esta en .gitignore)."
    )


def _leer_csv(nombre: str, clave: str) -> dict[str, dict]:
    with open(DATA / nombre, encoding="utf-8") as f:
        return {fila[clave]: fila for fila in csv.DictReader(f)}


PIEZAS = _leer_csv("piezas.csv", "pieza_id")
VEHICULOS = _leer_csv("vehiculos.csv", "vehiculo_id")
POLIZAS = _leer_csv("polizas.csv", "poliza_id")
with open(DATA / "reglas_dano.csv", encoding="utf-8") as _f:
    REGLAS = {(r["clase_cardd"], r["zona_tipo"], r["severidad"]): r["accion"] for r in csv.DictReader(_f)}

# Equivalencias de reglas de coste (#88, ADR 0008): la reparacion que se muestra es la de la regla con la
# que el Agente 2 ha presupuestado el dano. Modulo comun de app/agentes/comun, sin paquete Python.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "comun"))
from equivalencias import cargar_equivalencias, regla_efectiva  # noqa: E402

EQUIVALENCIAS = cargar_equivalencias()

AVISO_LEGAL = ("Informe generado automáticamente con datos sintéticos de prototipo. Las cifras son "
               "orientativas y no vinculantes, y no sustituyen a una valoración pericial.")
# Texto de referencia de la #32 (specs/32-rag-normativa.md, «Contrato propuesto de diagnóstico»)
AVISO_PRELIMINAR = ("Informe preliminar: no se han recuperado fuentes suficientes para respaldar las "
                    "conclusiones indicadas sobre cobertura e indemnización. Estas conclusiones requieren revisión.")
ESTADOS_RAG = ("recuperadas", "parcial", "sin_resultados", "error", "no_aplica")
# Justificaciones con LLM de la normativa (#97, ADR 0009; specs/97-justificacion-llm-normativa.md).
AVISO_JUSTIFICACION = ("Informe preliminar: no se ha podido redactar la justificación de algunas fuentes; "
                       "se muestran sus citas sin justificación y requieren revisión.")
ESTADOS_JUSTIFICACION = ("generada", "descartada", "no_generada")
# Un importe en euros en cualquier formato: el texto de una justificacion no puede llevar ninguno (AC-003).
_NUMERO = r"\d{1,3}(?:[.\s]\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?"
_IMPORTE_TEXTO = re.compile(rf"(?:{_NUMERO})\s*(?:€|eur\b|euros?\b)|(?:€|\b(?:eur|euros?))\s*(?:{_NUMERO})", re.IGNORECASE)
ESTADOS_PRELIMINARES = ("parcial", "sin_resultados", "error")
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
    "rechazado_por_vision": "la visión no confirma el daño",
    "sin_pieza_o_severidad": "no se pudo identificar la pieza o la severidad",
    "sin_regla_de_coste": "la tabla de reparaciones de la empresa no prevé esta combinación de daño, pieza y severidad",
}
CONCEPTOS = [
    ("Piezas", "piezas"), ("Mano de obra de chapa", "mano_obra_chapa"),
    ("Mano de obra de pintura", "mano_obra_pintura"), ("Mano de obra de mecánica", "mano_obra_mecanica"),
    ("Materiales de pintura", "materiales_pintura"), ("Otros", "otros"),
]
NINGUNO = "_Ninguno._"
# Issue #54, slice 2 (plan v1.1): https://github.com/lvckss/piia2-26/issues/54#issuecomment-6806386857
# AC-011: el sistema solo juzga lo que encuentra el detector de danos; se dice aparte del aviso legal.
# Plan v1.2 de la #54, AC-014: sin jerga para el lector («el detector de daños» y no el nombre interno).
AVISO_DETECTOR = ("Solo se analizan los daños que ha encontrado el detector en la foto; puede haber otros que no "
                  "aparezcan en este informe.")
# Plan v1.2 de la #54 (https://github.com/lvckss/piia2-26/issues/54#issuecomment-7107366100), slice 8.
# AC-014: sigla que se desarrolla la primera vez que aparece fuera de las citas literales.
SIGLAS = {"LRCSCVM": "Ley sobre responsabilidad civil y seguro en la circulación de vehículos a motor"}
# AC-019: las fuentes explican; la cobertura la calcula la herramienta de costes.
FRASE_FUENTES = ("La cobertura y la indemnización las calcula la herramienta de costes a partir de la póliza; "
                 "las fuentes siguientes son explicativas.")
# AC-021: procedencia del vehiculo (spec 34 v1.7, `contexto.vehiculo_origen`), con la frase literal de la spec 34.
ORIGENES_VEHICULO = ("referencia_confirmada", "seleccion_usuario", "minimo_por_defecto")
VEHICULO_POR_DEFECTO = "V14"
FRASE_VEHICULO_POR_DEFECTO = (
    "Vehículo no identificado en la imagen: el presupuesto usa el vehículo de menor coste del catálogo. "
    "Es una estimación a la baja: si el taller encuentra un importe mayor, avisará a la aseguradora para revisarlo.")
# AC-003: hallazgos fuera del coste que no son falsos positivos y que una persona debe revisar.
MOTIVOS_REVISION_HUMANA = ("sin_pieza_o_severidad", "sin_regla_de_coste")
# Issue #54, slice 1 (plan v1): https://github.com/lvckss/piia2-26/issues/54#issuecomment-6805208293
# AC-001: nombres legibles de `tipo_taller`; los que no estan aqui se muestran tal cual.
TALLER_TEXTO = {"concertado_aseguradora": "concertado con la aseguradora"}


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


def _clase(f: dict) -> str:
    return CLASE_TEXTO.get(f["clase_tool"], f["category"])


def _pieza(f: dict) -> str:
    return PIEZAS[f["pieza_id"]]["nombre"] if f["pieza_id"] else "—"


def _reparacion(f: dict) -> str:
    """Accion de la regla efectiva (specs/88-equivalencias-reglas-coste.md#AC-005): la propia del dano o,
    si no la tiene, la de su equivalente. El informe no menciona la equivalencia."""
    if not f["pieza_id"] or not f["severidad"]:
        return "—"
    zona = PIEZAS[f["pieza_id"]]["zona_tipo"]
    efectiva = regla_efectiva(f["clase_tool"], zona, f["severidad"], REGLAS, EQUIVALENCIAS)
    if efectiva is None:
        return "—"
    clase, severidad = efectiva
    return ACCION_TEXTO.get(REGLAS[(clase, zona, severidad)], "—")


def _motivos_pendiente(f: dict) -> str:
    motivos = []
    if f["score_tier"] == "needs_review":
        motivos.append(f"score de detección bajo ({_decimal(f['score'])})")
    if f["vision_verdict"] != "confirmado":
        motivos.append(f"la visión lo ve {f['vision_verdict']}")
    if f["regla_coste_aplicable"] is not True:
        motivos.append("la tabla de reparaciones de la empresa no la prevé")
    return "; ".join(motivos) or "pendiente de verificación"


def _tabla_hallazgos(hallazgos: list[dict], con_motivo: bool = False) -> list[str]:
    if not hallazgos:
        return [NINGUNO]
    ultima = "Por qué está pendiente" if con_motivo else "Score"
    filas = [f"| ID | Pieza | Daño | Severidad | Reparación | {ultima} |", "|---|---|---|---|---|---|"]
    if con_motivo:
        for f in hallazgos:
            filas.append(f"| {f['finding_id']} | {_pieza(f)} | {_clase(f)} | "
                         f"{f['severidad'] or '—'} | {_reparacion(f)} | {_motivos_pendiente(f)} |")
    else:
        # #54 AC-004: los confirmados con la misma pieza, dano, severidad y reparacion van en una sola fila.
        grupos: dict[tuple, list[dict]] = {}
        for f in hallazgos:
            grupos.setdefault((_pieza(f), _clase(f), f["severidad"] or "—", _reparacion(f)), []).append(f)
        for (pieza, clase, severidad, reparacion), iguales in grupos.items():
            ids = ", ".join(f["finding_id"] for f in iguales)
            scores = "; ".join(_decimal(f["score"]) for f in iguales)
            filas.append(f"| {ids} | {pieza} | {clase} | {severidad} | {reparacion} | {scores} |")
    imagenes = " ".join(f"![{f['finding_id']}]({f['crop_image_path']})" for f in hallazgos if f.get("crop_image_path"))
    return filas + ([""] + [imagenes] if imagenes else [])


def _bloque_literal(texto: str) -> list[str]:
    """El extracto tal cual, en un bloque de codigo dentro del elemento de la
    lista, para que sus lineas (p. ej. «# Fuente: ...» de los preambulos
    legales) no se interpreten como Markdown del informe
    (specs/31-informe-peritaje.md#AC-001 y AC-005)."""
    racha = max((len(r) for r in re.findall(r"`+", texto)), default=0)
    valla = "`" * max(3, racha + 1)
    return [f"  {valla}text", *(f"  {linea}" for linea in texto.split("\n")), f"  {valla}"]


def _linea_perdida_total(agente2: dict, cob_c: dict, cob_p: dict) -> str:
    """Linea de perdida total del «Resumen». Con umbral 0 (polizas sin perdida total, P-TERC-*) no se escribe
    «umbral 0 %», sino que no aplica (#54 AC-002)."""
    venal = eur(agente2["valor_venal_eur"])
    if not agente2["umbral_perdida_total"]:
        return f"- Pérdida total (valor venal {venal}): no aplica, porque la póliza no fija un umbral de pérdida total."
    return (f"- Pérdida total (valor venal {venal}, umbral {_porcentaje(agente2['umbral_perdida_total'])}): "
            f"{_si_no(cob_c['perdida_total'])} con los confirmados; {_si_no(cob_p['perdida_total'])} incluyendo los pendientes.")


def _detecciones(n: int) -> str:
    return "1 detección requiere" if n == 1 else f"{n} detecciones requieren"


def _resumen_revision(revision: list[dict], presupuestables: int) -> list[str]:
    """Lineas del «Resumen» sobre lo que requiere revision humana (#54 AC-003); vacio si no hay nada, para
    que el «Resumen» no cambie."""
    if not revision:
        return []
    lineas = [f"- {_detecciones(len(revision))} revisión humana (ver «Detecciones no incluidas en el coste»)."]
    if not presupuestables:
        lineas.append("- Ningún hallazgo es presupuestable: el coste es 0,00 € porque todas las detecciones "
                      "quedan fuera del coste.")
    return lineas


def _detecciones_fuera(fuera: list[dict], por_id: dict) -> list[str]:
    """Los rechazados con su texto de siempre y, aparte, los que requieren revision humana (#54 AC-003)."""
    if not fuera:
        return [NINGUNO]
    linea = lambda x: f"- {x['finding_id']} ({_clase(por_id[x['finding_id']])}): {MOTIVO_FUERA[x['motivo']]}."
    otros = [linea(x) for x in fuera if x["motivo"] not in MOTIVOS_REVISION_HUMANA]
    revision = [linea(x) for x in fuera if x["motivo"] in MOTIVOS_REVISION_HUMANA]
    if not revision:
        return otros
    return otros + ([""] if otros else []) + [
        "**Requieren revisión humana:** no se han podido presupuestar, pero la visión no los ha descartado.",
        "", *revision]


def _arrastres(escenarios: dict) -> list[dict]:
    """Arrastres de los dos escenarios, sin repetir pieza y origen."""
    vistos, lista = set(), []
    for nombre in ("confirmados", "con_pendientes"):
        for a in escenarios[nombre]["estimacion"]["arrastres_posibles"]:
            if (a["pieza_id"], a["origen"]) not in vistos:
                vistos.add((a["pieza_id"], a["origen"]))
                lista.append(a)
    return lista


def validar_entradas(agente1: dict, agente2: dict) -> None:
    """Lanza ValueError si las salidas de los Agentes 1 y 2 no son coherentes,
    nombrando el identificador (specs/31-informe-peritaje.md#AC-011)."""
    if agente1["image_id"] != agente2["image_id"]:
        raise ValueError(f"image_id distintos: Agente 1 {agente1['image_id']!r}, Agente 2 {agente2['image_id']!r}")
    ids = {f["finding_id"] for f in agente1["findings"]}
    fuera = [x["finding_id"] for x in agente2["hallazgos_fuera_del_coste"]]
    listas = {f"escenarios.{n}.hallazgos_incluidos": e["hallazgos_incluidos"] for n, e in agente2["escenarios"].items()}
    listas["hallazgos_fuera_del_coste"] = fuera
    for nombre, lista in listas.items():
        repetidos = sorted({fid for fid in lista if lista.count(fid) > 1})
        if repetidos:
            raise ValueError(f"finding_id repetido en {nombre}: {', '.join(repetidos)}")
    en_coste = {fid for n, e in agente2["escenarios"].items() for fid in e["hallazgos_incluidos"]}
    en_los_dos = sorted(en_coste & set(fuera))
    if en_los_dos:
        raise ValueError(f"finding_id a la vez en un escenario de coste y fuera del coste: {', '.join(en_los_dos)}")
    en_agente2 = sorted(en_coste) + fuera
    for fid in en_agente2:
        if fid not in ids:
            raise ValueError(f"finding_id del Agente 2 que no esta en el Agente 1: {fid!r}")
    sin_grupo = sorted(ids - set(en_agente2))
    if sin_grupo:
        raise ValueError(f"hallazgos del Agente 1 sin grupo en el Agente 2: {', '.join(sin_grupo)}")
    if agente2["contexto"]["vehiculo_id"] not in VEHICULOS:
        raise ValueError(f"vehiculo_id no esta en el catalogo de la empresa: {agente2['contexto']['vehiculo_id']!r}")
    piezas = [f["pieza_id"] for f in agente1["findings"] if f["pieza_id"]]
    for e in agente2["escenarios"].values():
        piezas += [p for a in e["estimacion"]["arrastres_posibles"] for p in (a["pieza_id"], a["origen"])]
    for pieza in piezas:
        if pieza not in PIEZAS:
            raise ValueError(f"pieza_id no esta en el catalogo de la empresa: {pieza!r}")
    if "diagnostico_rag" in agente2:
        _validar_diagnostico(agente2["diagnostico_rag"])
    _validar_origen_vehiculo(agente1, agente2["contexto"])
    if "justificaciones" in agente2:
        _validar_justificaciones(agente2["justificaciones"])


def _validar_justificaciones(justificaciones: list) -> None:
    """`justificaciones` opcional, con la forma del ADR 0009 (specs/97-justificacion-llm-normativa.md#AC-009).
    Una `generada` con importes en el texto es una entrada mal formada: el texto del LLM no puede
    llevar importes, que solo aparecen en las citas literales y en el calculo."""
    if not isinstance(justificaciones, list):
        raise ValueError("justificaciones debe ser una lista")
    for n, j in enumerate(justificaciones):
        campo = f"justificaciones[{n}]"
        if not isinstance(j, dict) or not isinstance(j.get("tema"), str) or not j["tema"]:
            raise ValueError(f"{campo} sin tema")
        if j.get("estado") not in ESTADOS_JUSTIFICACION:
            raise ValueError(f"{campo}.estado no valido: {j.get('estado')!r} (debe ser {', '.join(ESTADOS_JUSTIFICACION)})")
        if j["estado"] != "generada":
            if not isinstance(j.get("motivo"), str) or not j["motivo"]:
                raise ValueError(f"{campo}.motivo vacio")
            continue
        if not isinstance(j.get("texto"), str) or not j["texto"].strip():
            raise ValueError(f"{campo}.texto vacio")
        if _IMPORTE_TEXTO.search(j["texto"]):
            raise ValueError(f"{campo}.texto contiene un importe: {_IMPORTE_TEXTO.search(j['texto']).group(0)!r}")
        citas = j.get("citas")
        if not isinstance(citas, list) or not citas or not all(
                isinstance(c, dict) and isinstance(c.get("extracto"), str) and c["extracto"]
                and isinstance(c.get("fuente"), str) and c["fuente"] for c in citas):
            raise ValueError(f"{campo}.citas debe ser una lista no vacia de {{extracto, fuente}}")


def _validar_origen_vehiculo(agente1: dict, ctx: dict) -> None:
    """`contexto.vehiculo_origen` opcional (spec 34 v1.7; plan v1.2 de la #54, AC-021): si viene, solo admite tres
    valores y debe ser coherente con el coche usado; un valor invalido no equivale a su ausencia."""
    if "vehiculo_origen" not in ctx:
        return
    origen = ctx["vehiculo_origen"]
    if origen not in ORIGENES_VEHICULO:
        raise ValueError(f"contexto.vehiculo_origen no valido: {origen!r} (debe ser {', '.join(ORIGENES_VEHICULO)})")
    if origen == "minimo_por_defecto" and ctx["vehiculo_id"] != VEHICULO_POR_DEFECTO:
        raise ValueError(f"contexto.vehiculo_origen minimo_por_defecto exige vehiculo_id {VEHICULO_POR_DEFECTO}, "
                         f"no {ctx['vehiculo_id']!r}")
    if origen == "referencia_confirmada":
        referencia = (agente1.get("vehiculo") or {}).get("vehiculo_id_referencia")
        if referencia is None or referencia != ctx["vehiculo_id"]:
            raise ValueError(f"contexto.vehiculo_origen referencia_confirmada exige que vehiculo_id "
                             f"({ctx['vehiculo_id']!r}) sea la referencia del Agente 1 ({referencia!r})")


def _validar_diagnostico(diagnostico: dict) -> None:
    """`diagnostico_rag` opcional, con la forma del contrato de la #32
    (specs/31-informe-peritaje.md#AC-015). Solo se presenta, no se recalcula."""
    if diagnostico.get("estado") not in ESTADOS_RAG:
        raise ValueError(f"diagnostico_rag.estado no valido: {diagnostico.get('estado')!r} (debe ser {', '.join(ESTADOS_RAG)})")
    consultas = diagnostico.get("consultas")
    if not isinstance(consultas, list):
        raise ValueError("diagnostico_rag.consultas debe ser una lista")
    for n, consulta in enumerate(consultas):
        if not consulta.get("tema"):
            raise ValueError(f"diagnostico_rag.consultas[{n}] sin tema")
        if not isinstance(consulta.get("incidencias", []), list):
            raise ValueError(f"diagnostico_rag.consultas[{n}].incidencias debe ser una lista")


def _consultas_sin_fuentes(diagnostico: dict | None) -> list[str]:
    """Por cada consulta que no termino en `recuperadas`: su tema y el mensaje
    de cada incidencia (o «sin resultados»). Nunca `codigo`, `etapa` ni
    `reintentable` (specs/31-informe-peritaje.md#AC-014)."""
    if not diagnostico or diagnostico["estado"] not in ESTADOS_PRELIMINARES:
        return []
    lineas = []
    for c in diagnostico["consultas"]:
        if c["estado"] != "recuperadas":
            motivo = " ".join(i["mensaje"] for i in c.get("incidencias", [])) or "sin resultados"
            lineas.append(f"- Sin fuentes para «{c['tema']}»: {motivo}")
    return lineas


def _linea_vehiculo(veh: dict, ctx: dict, agente1: dict) -> str:
    """La linea «Vehículo» de la cabecera, con su procedencia si viene (#54 AC-021); sin ella, la de siempre."""
    nombre = f"{veh['marca']} {veh['modelo']}"
    origen = ctx.get("vehiculo_origen")
    if origen == "referencia_confirmada":
        categoria = (agente1.get("vehiculo") or {}).get("categoria", "")
        nombre += f" (coche de referencia de la categoría {categoria} que propone la visión, confirmado)"
    elif origen == "seleccion_usuario":
        nombre += " (elegido por la persona usuaria)"
    elif origen == "minimo_por_defecto":
        nombre += ", el de menor coste del catálogo, porque no se reconoció la categoría del vehículo"
    return f"- **Vehículo:** {nombre}"


def _aviso_vehiculo(veh: dict, ctx: dict) -> list[str]:
    """Con `minimo_por_defecto`, la frase literal de la spec 34 y sus limites (#54 AC-021)."""
    if ctx.get("vehiculo_origen") != "minimo_por_defecto":
        return []
    return ["", f"> {FRASE_VEHICULO_POR_DEFECTO}",
            f"> El cálculo usa el {veh['marca']} {veh['modelo']} ({ctx['vehiculo_id']}), una referencia fija que no "
            "garantiza el mínimo exacto: el valor venal no es el del vehículo real y la pérdida total no es fiable."]


def _resumen_detecciones(detecciones: int, analizados: int) -> list[str]:
    """Las detecciones que no se analizaron las descarto el filtro previo (ADR 0005; #54 AC-015)."""
    if detecciones <= analizados:
        return []
    resto = detecciones - analizados
    sujeto = "La otra detección no se analizó" if resto == 1 else f"Las otras {resto} detecciones no se analizaron"
    return [f"- {sujeto}: el filtro previo las descarta por su clase o por su confianza baja."]


def _celda_cubierto(escenario: dict) -> str:
    """«No aplica» si no hay nada que presupuestar en ese escenario (#54 AC-017)."""
    if not escenario["hallazgos_incluidos"]:
        return "No aplica: no hay daños que presupuestar"
    return _si_no(escenario["cobertura"]["cubierto"])


def _celda_indemnizacion(escenario: dict) -> str:
    """Con cobertura e indemnizacion 0 € porque el coste no supera la franquicia, se dice (#54 AC-017). Se compara
    de forma explicita, para no afirmarlo si la indemnizacion es 0 € por otro motivo. Las cifras no cambian."""
    cobertura = escenario["cobertura"]
    celda = eur(cobertura["indemnizacion_estimada_eur"])
    if (cobertura["cubierto"] and cobertura["indemnizacion_estimada_eur"] == 0
            and escenario["estimacion"]["total_con_iva_eur"] <= cobertura["franquicia_eur"]):
        celda += " (el coste no supera la franquicia)"
    return celda


def _desarrollar_siglas(lineas: list[str]) -> list[str]:
    """Desarrolla cada sigla de SIGLAS la primera vez que aparece fuera de los bloques literales (#54 AC-014)."""
    pendientes, dentro, salida = dict(SIGLAS), False, []
    for linea in lineas:
        if linea.strip().startswith("```"):
            dentro = not dentro
        elif not dentro:
            for sigla, nombre in list(pendientes.items()):
                if sigla in linea:
                    linea = linea.replace(sigla, f"{nombre} ({sigla})", 1)
                    del pendientes[sigla]
        salida.append(linea)
    return salida


def _fuentes(agente2: dict) -> list[str]:
    """Contenido de «Fuentes consultadas» (#54 AC-016 y AC-019; spec 97 AC-008 y AC-009).

    Primero la frase de que las fuentes son explicativas. Con `justificaciones`, una linea por tema: su texto si
    esta `generada`, o «sin justificación» y el motivo si no. Despues, las citas agrupadas por fuente, cada texto
    una sola vez: las de las justificaciones generadas y, para los demas temas (o sin justificaciones), los
    pasajes de la normativa."""
    citas: dict[str, list[str]] = {}
    temas_de: dict[str, list[str]] = {}

    def anotar(fuente: str, extracto: str, tema: str) -> None:
        textos = citas.setdefault(fuente, [])
        if extracto not in textos:
            textos.append(extracto)
        temas = temas_de.setdefault(fuente, [])
        if tema not in temas:
            temas.append(tema)

    lineas = [FRASE_FUENTES, ""]
    justificaciones = agente2.get("justificaciones")
    if justificaciones is None:
        for n in agente2["normativa"]:
            anotar(n["fuente"], n["extracto"], n["tema"])
    else:
        por_tema = {j["tema"]: j for j in justificaciones}
        for tema in dict.fromkeys(n["tema"] for n in agente2["normativa"]):
            j = por_tema.get(tema)
            if j and j["estado"] == "generada":
                lineas.append(f"- **{tema}:** {j['texto']}")
                for c in j["citas"]:
                    anotar(c["fuente"], c["extracto"], tema)
                continue
            lineas.append(f"- **{tema}:** sin justificación: {j['motivo']}" if j else f"- **{tema}**")
            for n in (x for x in agente2["normativa"] if x["tema"] == tema):
                anotar(n["fuente"], n["extracto"], tema)
        lineas += ["", "Citas, por fuente:", ""]
    for fuente, textos in citas.items():
        lineas.append(f"- {fuente} ({'; '.join(temas_de[fuente])}):")
        for texto in textos:
            lineas += _bloque_literal(texto)
        lineas.append("")
    return lineas


def generar_informe(agente1: dict, agente2: dict, hoy: str | None = None) -> str:
    """Informe de peritaje en markdown (specs/31-informe-peritaje.md#AC-001).
    TODAS las cifras salen de `agente2`: ninguna se calcula aqui."""
    validar_entradas(agente1, agente2)
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
        _linea_vehiculo(veh, ctx, agente1),
        f"- **Taller:** {TALLER_TEXTO.get(ctx['tipo_taller'], ctx['tipo_taller'])} ({ctx['region']})",
        f"- **Póliza:** {poliza}",
    ]
    if tercero:
        md.append("- **Perjudicado:** un tercero (reclamación por responsabilidad civil)")
    diagnostico = agente2.get("diagnostico_rag")
    md += ["", f"> {AVISO_LEGAL}", "", AVISO_DETECTOR, *_aviso_vehiculo(veh, ctx)]
    if diagnostico and diagnostico["estado"] in ESTADOS_PRELIMINARES:
        md += ["", f"> **{AVISO_PRELIMINAR}**"]
    revision = [x for x in fuera if x["motivo"] in MOTIVOS_REVISION_HUMANA]
    if any(j["estado"] != "generada" for j in agente2.get("justificaciones", [])):
        md += ["", f"> **{AVISO_JUSTIFICACION}**"]
    md += [
        "",
        "## Resumen",
        "",
        f"- {detecciones} detecciones del detector de daños y {len(agente1['findings'])} hallazgos analizados: "
        f"{len(confirmados)} confirmados, {len(pendientes)} pendientes de revisión y {len(fuera)} fuera del coste.",
        *_resumen_detecciones(detecciones, len(agente1["findings"])),
        *_resumen_revision(revision, presupuestables=len(confirmados) + len(pendientes)),
        f"- Coste **solo con los daños confirmados**: {eur(est_c['subtotal_sin_iva_eur'])} sin IVA "
        f"({eur(est_c['total_con_iva_eur'])} con IVA).",
        f"- Coste **incluyendo los pendientes**: {eur(est_p['subtotal_sin_iva_eur'])} sin IVA "
        f"({eur(est_p['total_con_iva_eur'])} con IVA).",
        _linea_perdida_total(agente2, cob_c, cob_p),
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
        *(["", f"{_detecciones(len(revision))} revisión humana: ver «Detecciones no incluidas en el coste»."]
          if revision and not pendientes else []),
        "",
        "## Detecciones no incluidas en el coste",
        "",
        *_detecciones_fuera(fuera, por_id),
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
        md += [f"- {PIEZAS[a['pieza_id']]['nombre']}: probabilidad {_porcentaje(a['probabilidad'])}, "
               f"por el daño en {PIEZAS[a['origen']]['nombre'].lower()}" for a in arrastres]
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
        f"| Cubierto | {_celda_cubierto(esc_c)} | {_celda_cubierto(esc_p)} |",
        f"| Motivo | {cob_c['motivo']} | {cob_p['motivo']} |",
        f"| Franquicia | {eur(cob_c['franquicia_eur'])} | {eur(cob_p['franquicia_eur'])} |",
        f"| Pérdida total | {_si_no(cob_c['perdida_total'])} | {_si_no(cob_p['perdida_total'])} |",
        f"| Indemnización estimada | {_celda_indemnizacion(esc_c)} | {_celda_indemnizacion(esc_p)} |",
        "",
        "## Fuentes consultadas",
        "",
    ]
    if agente2["normativa"]:
        md += _fuentes(agente2)
    else:
        md.append("_Sin fuentes._")
    sin_fuentes = _consultas_sin_fuentes(diagnostico)
    if sin_fuentes:
        md += ["", "Temas sin fuentes recuperadas (las conclusiones sobre ellos requieren revisión):", "", *sin_fuentes]
    return "\n".join(_desarrollar_siglas(md)) + "\n"


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
