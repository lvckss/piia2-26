"""Pruebas del generador de los primeros 30 informes reales (Issue #84).

Cada prueba cita su criterio del plan v1:
https://github.com/lvckss/piia2-26/issues/84#issuecomment-6802745988 (AC-0XX).
Usa las salidas reales de ejemplos_contrato/agente1_real/ y el paquete de la
empresa (piia2_paquete_datos/, fuera de git). No necesita API Key ni red.

Se ejecuta desde esta carpeta:  python probar_informes_reales.py
Ejecuta todas las pruebas, informa de cada una y termina con codigo 1 si
alguna falla.
"""

from __future__ import annotations

import random
import sys
import traceback
from pathlib import Path

import generar_informes_reales
from generar_informes_reales import preparar_casos

PLAN = "https://github.com/lvckss/piia2-26/issues/84#issuecomment-6802745988"
CAMPOS_CONTEXTO = ("region", "tipo_taller", "acabado", "tipo_pieza", "rol", "edad_anios", "km")


def _salida(image_id: int, categoria: str, referencia: str | None) -> dict:
    return {"image_id": image_id, "findings": [], "resumen_filtro_previo": {},
            "vehiculo": {"categoria": categoria, "vehiculo_id_referencia": referencia}}


def _siniestro(sid: str, rol: str, poliza: str) -> dict:
    return {"siniestro_id": sid, "region": "Madrid", "tipo_taller": "oficial", "acabado": "metalizado",
            "tipo_pieza": "oem", "rol": rol, "poliza_id": poliza, "edad_anios": "7", "km": "95000",
            "vehiculo_id": "V01", "danos_json": "[]"}


# --- plan #84, AC-003 --------------------------------------------------------
def probar_ac003_contexto_y_coche_de_cada_caso():
    """AC-003: el contexto toma solo los campos de la regla 1 del siniestro
    asignado (con tercero, sin poliza_id) y el coche es la referencia del
    Agente 1 o V14 con `desconocido`; la asignacion es la de random.Random(84)
    sobre los siniestros ordenados y no repite siniestros."""
    salidas = [_salida(3, "C", "V02"), _salida(1, "desconocido", None), _salida(2, "FURG", "V09")]
    siniestros = [_siniestro(f"S{n:05d}", "tercero_perjudicado" if n % 2 else "propio", "" if n % 2 else "P-TR-FR300")
                  for n in range(10, 0, -1)]
    casos = preparar_casos(salidas, siniestros, semilla=84)

    esperados = random.Random(84).sample(sorted(siniestros, key=lambda s: s["siniestro_id"]), 3)
    assert [c["image_id"] for c in casos] == [1, 2, 3], casos
    assert [c["siniestro_id"] for c in casos] == [s["siniestro_id"] for s in esperados], casos
    assert len({c["siniestro_id"] for c in casos}) == 3
    coches = {c["image_id"]: c["contexto"]["vehiculo_id"] for c in casos}
    assert coches == {1: "V14", 2: "V09", 3: "V02"}, coches
    for caso, sin in zip(casos, esperados):
        ctx = caso["contexto"]
        for campo in CAMPOS_CONTEXTO:
            esperado = int(sin[campo]) if campo in ("edad_anios", "km") else sin[campo]
            assert ctx[campo] == esperado, (campo, ctx[campo], esperado)
        if sin["rol"] == "propio":
            assert ctx["poliza_id"] == sin["poliza_id"], ctx
        else:
            assert "poliza_id" not in ctx, ctx
        assert set(ctx) <= set(CAMPOS_CONTEXTO) | {"vehiculo_id", "poliza_id"}, ctx


PRUEBAS = [
    probar_ac003_contexto_y_coche_de_cada_caso,
]


def main() -> int:
    fallos = 0
    for prueba in PRUEBAS:
        try:
            prueba()
        except Exception:  # noqa: BLE001 - se informa y se sigue con las demas
            fallos += 1
            ultima = traceback.format_exc().strip().splitlines()[-1]
            print(f"FALLA  {prueba.__name__}: {ultima}")
        else:
            print(f"ok     {prueba.__name__}")
    print(f"\n{len(PRUEBAS) - fallos} de {len(PRUEBAS)} pruebas en verde (modulo: {Path(generar_informes_reales.__file__).name})")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
