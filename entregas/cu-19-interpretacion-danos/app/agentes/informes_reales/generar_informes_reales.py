"""Primeros 30 informes reales en linea de comandos (Issue #84).

Encadena las salidas reales del Agente 1 guardadas en
ejemplos_contrato/agente1_real/ con el Agente 2 (costes y cobertura) y el
Agente 3 (informe). Sin API, sin RAG y sin web.

Plan: https://github.com/lvckss/piia2-26/issues/84#issuecomment-6802745988
"""

from __future__ import annotations

import random

# Regla provisional del coche con categoria `desconocido`: el de menor coste
# (decision con el profesorado del 2026-11-10, registrada en la #34). Su sitio
# definitivo es la funcion del orquestador de la #34.
VEHICULO_DESCONOCIDO = "V14"
CAMPOS_CONTEXTO = ("region", "tipo_taller", "acabado", "tipo_pieza", "rol")


def _contexto(siniestro: dict, vehiculo_id: str) -> dict:
    """Solo los campos de contexto del siniestro (regla 1 del plan); sus danos y
    su coche no se usan. Con tercero no hay poliza."""
    contexto = {"vehiculo_id": vehiculo_id, **{c: siniestro[c] for c in CAMPOS_CONTEXTO},
                "edad_anios": int(siniestro["edad_anios"]), "km": int(siniestro["km"])}
    if siniestro["rol"] == "propio":
        contexto["poliza_id"] = siniestro["poliza_id"]
    return contexto


def preparar_casos(salidas: list[dict], siniestros: list[dict], semilla: int = 84) -> list[dict]:
    """Un caso por salida del Agente 1, en orden de `image_id`: un siniestro
    distinto elegido con random.Random(semilla) sobre los siniestros ordenados
    por `siniestro_id`, y el coche de referencia del Agente 1 o V14 con
    `desconocido` (plan #84, AC-003)."""
    ordenadas = sorted(salidas, key=lambda s: s["image_id"])
    elegidos = random.Random(semilla).sample(sorted(siniestros, key=lambda s: s["siniestro_id"]), len(ordenadas))
    casos = []
    for salida, siniestro in zip(ordenadas, elegidos):
        vehiculo = salida["vehiculo"]
        vehiculo_id = vehiculo["vehiculo_id_referencia"] or VEHICULO_DESCONOCIDO
        casos.append({"image_id": salida["image_id"], "siniestro_id": siniestro["siniestro_id"],
                      "categoria": vehiculo["categoria"], "salida_agente1": salida,
                      "contexto": _contexto(siniestro, vehiculo_id)})
    return casos
