"""Prueba que las salidas versionadas del Agente 1 reflejan las equivalencias de reglas de coste (#88, slice 5).

Plan v1: specs/88-equivalencias-reglas-coste.md#AC-007 (y AC-004 para la imagen 1248). Decision: ADR 0008.

Sin API ni red. Usa el catalogo de la empresa (piia2_paquete_datos/, fuera de git; PIIA2_DATOS_DIR lo
sustituye): si falta, avisa y se salta, como el resto de pruebas con datos que no se versionan.

Se ejecuta desde esta carpeta:  python probar_datos_equivalencias_stub.py
"""

from __future__ import annotations

import json
from pathlib import Path

from catalogo import cargar_catalogo, combinacion_valida
from confianza import decidir_tier

AQUI = Path(__file__).resolve().parent
VERSIONADAS = AQUI.parent / "ejemplos_contrato" / "agente1_real"
# Las dos unicas salidas versionadas con un hallazgo que gana regla por una equivalencia (AC-007):
# 381-14 (grieta en el neumatico, tire_flat) y 1248-9 (cristal roto en el piloto, lamp_broken).
GANAN_REGLA = {"381-14", "1248-9"}


def _catalogo():
    try:
        return cargar_catalogo()
    except FileNotFoundError:
        print("(catalogo real no encontrado: se salta la comprobacion de las salidas versionadas)")
        return None


def _hallazgos():
    for ruta in sorted(VERSIONADAS.glob("*.json")):
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        if isinstance(datos, dict) and "findings" in datos:
            for f in datos["findings"]:
                yield ruta.stem, f


def probar_ac007_regla_coste_aplicable_coincide_con_el_catalogo_en_las_30() -> None:
    """AC-007: en las 30 salidas versionadas, `regla_coste_aplicable` de cada hallazgo con pieza y severidad
    es lo que da el catalogo con las equivalencias; solo 381-14 y 1248-9 cambian respecto a antes."""
    catalogo = _catalogo()
    if catalogo is None:
        return
    total = 0
    distintos = []
    for stem, f in _hallazgos():
        total += 1
        if f.get("pieza_id") is None or not f.get("severidad"):
            continue
        esperado = combinacion_valida(catalogo, f["clase_tool"], f["pieza_id"], f["severidad"])
        if f["regla_coste_aplicable"] is not esperado:
            distintos.append((f["finding_id"], f["regla_coste_aplicable"], esperado))
    assert total == 234, total
    assert distintos == [], f"salidas desactualizadas respecto al catalogo con equivalencias: {distintos}"


def probar_ac007_solo_cambian_381_14_y_1248_9() -> None:
    """AC-007: los unicos hallazgos de las 30 que ganan regla por equivalencia son 381-14 y 1248-9 (el resto
    de las salidas, entre ellas 003478, no cambia)."""
    catalogo = _catalogo()
    if catalogo is None:
        return
    ganan = set()
    for _, f in _hallazgos():
        if f.get("vision_verdict") == "rechazado" or f.get("pieza_id") is None or not f.get("severidad"):
            continue
        propia = (f["clase_tool"], catalogo.piezas[f["pieza_id"]]["zona_tipo"], f["severidad"]) in catalogo.reglas
        if not propia and combinacion_valida(catalogo, f["clase_tool"], f["pieza_id"], f["severidad"]):
            ganan.add(f["finding_id"])
    assert ganan == GANAN_REGLA, ganan


def probar_ac007_el_tier_sigue_siendo_el_de_decidir_tier() -> None:
    """AC-007: el `confidence_tier` de cada hallazgo es el que sale de `decidir_tier` con su regla; ninguno
    de los dos que ganan regla pasa a `confirmed` (381-14 sigue `incierto`; 1248-9 tiene score 0,54 < 0,6)."""
    for _, f in _hallazgos():
        esperado = decidir_tier(f["category"], f["score"], f["vision_verdict"], f["pieza_id"], f["regla_coste_aplicable"])
        assert f["confidence_tier"] == esperado, (f["finding_id"], f["confidence_tier"], esperado)
        if f["finding_id"] in GANAN_REGLA:
            assert f["confidence_tier"] == "needs_review", f["finding_id"]


def main() -> None:
    probar_ac007_regla_coste_aplicable_coincide_con_el_catalogo_en_las_30()
    probar_ac007_solo_cambian_381_14_y_1248_9()
    probar_ac007_el_tier_sigue_siendo_el_de_decidir_tier()
    print("\nTodo ok: las salidas versionadas reflejan las equivalencias de reglas de coste.")


if __name__ == "__main__":
    main()
