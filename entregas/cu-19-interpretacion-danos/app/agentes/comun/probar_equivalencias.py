"""Pruebas del módulo común de equivalencias de reglas de coste (#88, slice 1).

Cada prueba cita su criterio: specs/88-equivalencias-reglas-coste.md#AC-0XX.
AC-001 usa el reglas_dano.csv real de la empresa (piia2_paquete_datos/, fuera de
git) y se salta con un aviso si falta; el resto no necesita el paquete, API Key
ni red. El AC-009 de esta slice cubre solo la carga de la tabla; el determinismo
de `generar_informe` se prueba en la slice 4 (probar_informe.py).

Se ejecuta desde esta carpeta:  python probar_equivalencias.py
Ejecuta todas las pruebas, informa de cada una y termina con codigo 1 si
alguna falla.
"""

from __future__ import annotations

import csv
import os
import sys
import tempfile
import traceback
from pathlib import Path

import equivalencias
from equivalencias import SEVERIDADES, cargar_equivalencias, regla_efectiva

AQUI = Path(__file__).resolve().parent

CABECERA = "clase_origen,zona_tipo,clase_destino,severidad_minima,motivo"

# Reglas de prueba con la misma forma que reglas_dano.csv: (clase, zona, severidad).
# Solo contienen los destinos de las cuatro equivalencias iniciales y un caso ajeno.
REGLAS_PRUEBA = frozenset(
    (clase, zona, severidad)
    for clase, zona in (
        ("lamp_broken", "optica"),
        ("glass_shatter", "cristal"),
        ("tire_flat", "neumatico"),
        ("crack", "retrovisor"),
    )
    for severidad in SEVERIDADES
) | {("scratch", "retrovisor", "leve")}


def _reglas_de_la_empresa():
    """(clase, zona, severidad) de reglas_dano.csv del paquete, o None si falta."""
    en_entorno = os.environ.get("PIIA2_DATOS_DIR")
    if en_entorno:
        data = Path(en_entorno)
    else:
        raiz = next((c for c in [AQUI, *AQUI.parents] if (c / ".git").exists()), None)
        if raiz is None:
            return None
        data = raiz / "piia2_paquete_datos" / "data"
    ruta = data / "reglas_dano.csv"
    if not ruta.is_file():
        return None
    with open(ruta, encoding="utf-8", newline="") as f:
        return frozenset((r["clase_cardd"], r["zona_tipo"], r["severidad"]) for r in csv.DictReader(f))


def _escribir(carpeta: str, filas: list[str], nombre: str = "tabla.csv") -> Path:
    ruta = Path(carpeta) / nombre
    ruta.write_text("\n".join(filas) + "\n", encoding="utf-8", newline="\n")
    return ruta


def _falla_con(excepcion, llamada, *fragmentos):
    """Comprueba que `llamada` lanza `excepcion` y que su mensaje contiene cada fragmento."""
    try:
        llamada()
    except excepcion as error:
        mensaje = str(error)
        for fragmento in fragmentos:
            assert fragmento in mensaje, f"el mensaje {mensaje!r} no contiene {fragmento!r}"
        return
    raise AssertionError(f"se esperaba {excepcion.__name__} y no se lanzó ningún error")


def probar_ac001_tabla_coherente_con_las_reglas_de_la_empresa():
    """specs/88-equivalencias-reglas-coste.md#AC-001"""
    reglas = _reglas_de_la_empresa()
    if reglas is None:
        print("AVISO: falta reglas_dano.csv del paquete de la empresa; se salta AC-001 "
              "(la PR de entrega debe mostrarlo ejecutado).")
        return
    tabla = cargar_equivalencias()
    assert tabla, "la tabla de equivalencias no puede estar vacia"

    with open(equivalencias.RUTA_TABLA, encoding="utf-8", newline="") as f:
        filas = list(csv.DictReader(f))
    claves = [(fila["clase_origen"], fila["zona_tipo"]) for fila in filas]
    assert len(claves) == len(set(claves)), f"hay filas duplicadas: {claves}"
    assert len(filas) == len(tabla)

    for (origen, zona), equivalencia in tabla.items():
        assert equivalencia.motivo.strip(), f"{origen}/{zona}: falta el motivo"
        for severidad in SEVERIDADES:
            assert (origen, zona, severidad) not in reglas, \
                f"{origen}/{zona}/{severidad} ya tiene regla propia en reglas_dano.csv"
            efectiva = max(severidad, equivalencia.severidad_minima or severidad, key=SEVERIDADES.index)
            assert (equivalencia.clase_destino, zona, efectiva) in reglas, \
                f"{origen}/{zona}/{severidad}: el destino {equivalencia.clase_destino}/{zona}/{efectiva} no existe"


def probar_ac002_cuatro_equivalencias_iniciales():
    """specs/88-equivalencias-reglas-coste.md#AC-002 (equivalencias y severidad mínima)"""
    tabla = cargar_equivalencias()
    casos = [
        (("glass_shatter", "optica", "moderado"), ("lamp_broken", "moderado")),
        (("lamp_broken", "cristal", "grave"), ("glass_shatter", "grave")),
        (("crack", "neumatico", "leve"), ("tire_flat", "moderado")),
        (("crack", "neumatico", "grave"), ("tire_flat", "grave")),
        (("lamp_broken", "retrovisor", "leve"), ("crack", "leve")),
    ]
    for (clase, zona, severidad), esperado in casos:
        obtenido = regla_efectiva(clase, zona, severidad, REGLAS_PRUEBA, tabla)
        assert obtenido == esperado, f"{clase}/{zona}/{severidad}: se esperaba {esperado}, salió {obtenido}"


def probar_ac002_la_regla_propia_prevalece_y_no_se_traduce():
    """specs/88-equivalencias-reglas-coste.md#AC-002 (la regla de la empresa va primero)"""
    tabla = cargar_equivalencias()
    assert regla_efectiva("lamp_broken", "optica", "moderado", REGLAS_PRUEBA, tabla) == ("lamp_broken", "moderado")
    # Combinación con equivalencia (glass_shatter/optica) a la que se le añade regla propia:
    # esa severidad no se traduce; las demás severidades siguen traduciéndose.
    con_propia = REGLAS_PRUEBA | {("glass_shatter", "optica", "moderado")}
    assert regla_efectiva("glass_shatter", "optica", "moderado", con_propia, tabla) == ("glass_shatter", "moderado")
    assert regla_efectiva("glass_shatter", "optica", "leve", con_propia, tabla) == ("lamp_broken", "leve")


def probar_ac002_sin_equivalencia_devuelve_sin_regla():
    """specs/88-equivalencias-reglas-coste.md#AC-002 (sin equivalencia: «sin regla»)"""
    tabla = cargar_equivalencias()
    for clase, zona, severidad in (("scratch", "cristal", "leve"), ("scratch", "optica", "moderado"),
                                   ("crack", "estructura", "moderado"), ("glass_shatter", "panel_metalico", "grave")):
        obtenido = regla_efectiva(clase, zona, severidad, REGLAS_PRUEBA, tabla)
        assert obtenido is None, f"{clase}/{zona}/{severidad}: se esperaba sin regla, salió {obtenido}"
    # Una equivalencia cuyo destino no existe en las reglas de la empresa tampoco se aplica.
    sin_destino = REGLAS_PRUEBA - {("lamp_broken", "optica", "moderado")}
    assert regla_efectiva("glass_shatter", "optica", "moderado", sin_destino, tabla) is None
    # Severidad desconocida: no se puede resolver.
    assert regla_efectiva("glass_shatter", "optica", "critico", REGLAS_PRUEBA, tabla) is None


def probar_ac009_tabla_ausente_da_error_con_la_ruta():
    """specs/88-equivalencias-reglas-coste.md#AC-009 (tabla ausente)"""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = Path(carpeta) / "no_existe.csv"
        _falla_con(FileNotFoundError, lambda: cargar_equivalencias(ruta), str(ruta))


def probar_ac009_fila_mal_formada_da_error_con_la_ruta_y_la_fila():
    """specs/88-equivalencias-reglas-coste.md#AC-009 (fila incompleta y otras filas mal formadas)"""
    buena = "glass_shatter,optica,lamp_broken,,Motivo de prueba con acentos: sustitución"
    casos = {
        "destino vacío": [CABECERA, buena, "lamp_broken,cristal,,,Motivo"],
        "motivo vacío": [CABECERA, buena, "lamp_broken,cristal,glass_shatter,,"],
        "fila con menos columnas": [CABECERA, buena, "lamp_broken,cristal"],
        "severidad mínima desconocida": [CABECERA, buena, "lamp_broken,cristal,glass_shatter,critico,Motivo"],
        "fila duplicada": [CABECERA, buena, buena],
    }
    with tempfile.TemporaryDirectory() as carpeta:
        for nombre, filas in casos.items():
            ruta = _escribir(carpeta, filas, "tabla_mala.csv")
            _falla_con(ValueError, lambda ruta=ruta: cargar_equivalencias(ruta), str(ruta), "fila 3")
        # Una cabecera sin una de las columnas obligatorias no tiene fila concreta.
        ruta = _escribir(carpeta, ["clase_origen,zona_tipo,clase_destino,motivo", "a,b,c,d"], "sin_columna.csv")
        _falla_con(ValueError, lambda: cargar_equivalencias(ruta), str(ruta), "severidad_minima")


def probar_ac009_tabla_valida_con_acentos_se_lee_en_utf8():
    """specs/88-equivalencias-reglas-coste.md#AC-009 (lectura fiable en cualquier sistema)"""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = _escribir(carpeta, [CABECERA,
                                   "crack,neumatico,tire_flat,moderado,Una grieta no se repara: sustitución",
                                   "glass_shatter,optica,lamp_broken,,Óptica rota"])
        tabla = cargar_equivalencias(ruta)
        assert set(tabla) == {("crack", "neumatico"), ("glass_shatter", "optica")}
        assert tabla[("crack", "neumatico")].severidad_minima == "moderado"
        assert tabla[("crack", "neumatico")].motivo == "Una grieta no se repara: sustitución"
        assert tabla[("glass_shatter", "optica")].severidad_minima == ""


PRUEBAS = [
    probar_ac001_tabla_coherente_con_las_reglas_de_la_empresa,
    probar_ac002_cuatro_equivalencias_iniciales,
    probar_ac002_la_regla_propia_prevalece_y_no_se_traduce,
    probar_ac002_sin_equivalencia_devuelve_sin_regla,
    probar_ac009_tabla_ausente_da_error_con_la_ruta,
    probar_ac009_fila_mal_formada_da_error_con_la_ruta_y_la_fila,
    probar_ac009_tabla_valida_con_acentos_se_lee_en_utf8,
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
    print(f"\n{len(PRUEBAS) - fallos} de {len(PRUEBAS)} pruebas en verde (modulo: {Path(equivalencias.__file__).name})")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
