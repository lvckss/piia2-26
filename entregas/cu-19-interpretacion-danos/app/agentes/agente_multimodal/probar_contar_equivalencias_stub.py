"""Prueba contar_equivalencias.py (Issue #88, slice 5, parte del recuento de AC-007) sin API ni red.

Plan v1: specs/88-equivalencias-reglas-coste.md#AC-007. El recuento solo lee las salidas del
Agente 1; no cambia ningun archivo. La actualizacion de las salidas versionadas y de los
ejemplos queda para cuando esten integradas las slices 3 y 4 (ver la PR).

Las pruebas con datos reales usan el paquete de la empresa (piia2_paquete_datos/, fuera de git) y,
la de las 500, las salidas locales de piia2_detecciones/ (tampoco versionadas): si faltan, avisan
y se saltan, y la PR de entrega debe mostrarlas ejecutadas.

Se ejecuta desde esta carpeta:  python probar_contar_equivalencias_stub.py
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
from pathlib import Path

from catalogo import Catalogo, cargar_catalogo
from contar_equivalencias import contar
from contar_equivalencias import main as main_contar
from equivalencias import cargar_equivalencias  # catalogo.py anade app/agentes/comun a sys.path

AQUI = Path(__file__).resolve().parent
VERSIONADAS = AQUI.parent / "ejemplos_contrato" / "agente1_real"

CATALOGO_PRUEBA = Catalogo(
    piezas={
        "PILOTO_TRAS_I": {"nombre": "Piloto trasero izquierdo", "zona_tipo": "optica", "lado": "I"},
        "FARO_DEL_D": {"nombre": "Faro delantero derecho", "zona_tipo": "optica", "lado": "D"},
        "PARABRISAS": {"nombre": "Parabrisas", "zona_tipo": "cristal", "lado": "C"},
    },
    reglas=frozenset({("lamp_broken", "optica", "moderado"), ("lamp_broken", "optica", "grave")}),
    equivalencias=cargar_equivalencias(),
)


def _hallazgo(fid: str, clase_tool: str, veredicto: str, pieza: str | None, severidad: str | None) -> dict:
    return {"finding_id": fid, "category": clase_tool.replace("_", " "), "clase_tool": clase_tool,
            "vision_verdict": veredicto, "pieza_id": pieza, "severidad": severidad}


def _escribir(carpeta: Path, nombre: str, hallazgos: list[dict]) -> None:
    (carpeta / nombre).write_text(json.dumps({"image_id": 1, "findings": hallazgos}), encoding="utf-8")


def probar_ac007_recuento_con_catalogo_de_prueba() -> None:
    """AC-007: cuenta los hallazgos no rechazados con pieza y severidad que no tienen regla propia
    y cuantos de ellos pasan a tener regla por una equivalencia; ningun otro cambia."""
    with tempfile.TemporaryDirectory() as tmp:
        carpeta = Path(tmp)
        _escribir(carpeta, "000001.json", [
            # regla propia: no cuenta como «sin regla propia»
            _hallazgo("1-1", "lamp_broken", "confirmado", "FARO_DEL_D", "moderado"),
            # sin regla propia, con equivalencia (cristal roto en optica -> lamp_broken): gana regla
            _hallazgo("1-2", "glass_shatter", "confirmado", "PILOTO_TRAS_I", "moderado"),
            # rechazado por la vision: no cuenta aunque tenga pieza
            _hallazgo("1-3", "glass_shatter", "rechazado", "PILOTO_TRAS_I", "moderado"),
        ])
        _escribir(carpeta, "000002.json", [
            # sin regla propia y sin equivalencia: se queda sin regla
            _hallazgo("2-1", "scratch", "confirmado", "PARABRISAS", "moderado"),
            # incierto con pieza y severidad: cuenta como no rechazado; gana regla
            _hallazgo("2-2", "glass_shatter", "incierto", "FARO_DEL_D", "grave"),
            # sin pieza: no se puede aplicar ninguna regla, no cuenta
            _hallazgo("2-3", "glass_shatter", "incierto", None, None),
        ])
        # un archivo que no es una salida del Agente 1 (como resumen_lote.json) se omite y se informa
        (carpeta / "resumen_lote.json").write_text(json.dumps({"imagenes": 2}), encoding="utf-8")

        r = contar(carpeta, CATALOGO_PRUEBA)

    assert r["salidas"] == 2 and r["omitidos"] == ["resumen_lote.json"], r
    assert r["hallazgos"] == 6 and r["no_rechazados"] == 5, r
    assert r["con_pieza_y_severidad"] == 4, r
    assert r["sin_regla_propia"] == 3, r          # 1-2, 2-1 y 2-2
    assert r["sin_regla_con_equivalencias"] == 1, r  # solo 2-1
    assert r["ganan_regla"] == 2 and r["pierden_regla"] == 0, r
    assert r["salidas_que_cambian"] == ["000001", "000002"], r


def probar_ac007_las_30_versionadas() -> None:
    """AC-007: de las 30 salidas versionadas cambian solo 000381 y 001248; 003478 no cambia."""
    try:
        catalogo = cargar_catalogo()
    except FileNotFoundError:
        print("(catalogo real no encontrado: se salta el recuento de las 30 salidas versionadas)")
        return
    r = contar(VERSIONADAS, catalogo)
    assert r["salidas"] == 30 and r["omitidos"] == [], r
    assert r["sin_regla_propia"] == 3 and r["sin_regla_con_equivalencias"] == 1 and r["ganan_regla"] == 2, r
    assert r["pierden_regla"] == 0, r
    assert r["salidas_que_cambian"] == ["000381", "001248"], r["salidas_que_cambian"]
    assert "003478" not in r["salidas_que_cambian"]


def probar_ac007_las_500_locales(carpeta: Path | None = None) -> None:
    """AC-007: en las 500 salidas locales, los hallazgos no rechazados con pieza y severidad sin regla
    pasan de 37 a 13; los 24 con equivalencia pasan a tener regla y ninguno pierde la que tenia.
    `carpeta` solo sirve para probar la prueba; por defecto se busca en la raiz del repositorio."""
    if carpeta is None:
        raiz = next((c for c in AQUI.parents if (c / ".git").exists()), None)
        carpeta = raiz / "piia2_detecciones" / "salida_agente1_500" if raiz else Path("no_existe")
    try:
        catalogo = cargar_catalogo()
    except FileNotFoundError:
        print("(catalogo real no encontrado: se salta el recuento de las 500 salidas locales)")
        return
    if not carpeta.is_dir():
        print("(faltan las 500 salidas locales del Agente 1: se salta el recuento; la PR de entrega debe mostrarlo ejecutado)")
        return
    r = contar(carpeta, catalogo)
    if r["salidas"] != 500:
        print(f"(solo hay {r['salidas']} de las 500 salidas locales del Agente 1: se salta el recuento; "
              "la PR de entrega debe mostrarlo ejecutado)")
        return
    assert r["sin_regla_propia"] == 37 and r["sin_regla_con_equivalencias"] == 13 and r["ganan_regla"] == 24, r
    assert r["pierden_regla"] == 0, r


def probar_ac007_las_500_con_copia_parcial_se_salta() -> None:
    """AC-007: si la carpeta de las 500 existe pero no tiene las 500 salidas (una copia parcial), la
    prueba avisa y se salta en lugar de fallar, como el resto de pruebas con datos que no se versionan."""
    with tempfile.TemporaryDirectory() as tmp:
        carpeta = Path(tmp)
        for i in range(3):
            _escribir(carpeta, f"{i:06d}.json", [_hallazgo(f"{i}-1", "scratch", "confirmado", "PARABRISAS", "leve")])
        probar_ac007_las_500_locales(carpeta)  # no debe lanzar AssertionError


def _main_con_salida(argv: list[str]) -> tuple[int, str, str]:
    salida, error = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(error):
        codigo = main_contar(argv)
    return codigo, salida.getvalue(), error.getvalue()


def probar_ac007_carpeta_inexistente_o_vacia_es_un_error() -> None:
    """AC-007: una ruta mal escrita no debe pasar por un recuento correcto de 0 salidas: el script
    termina con codigo distinto de 0 y dice la ruta en stderr, tanto si no existe como si esta vacia."""
    with tempfile.TemporaryDirectory() as tmp:
        inexistente = Path(tmp) / "no_existe"
        codigo, _, error = _main_con_salida([str(inexistente)])
        assert codigo != 0 and str(inexistente) in error, (codigo, error)

        vacia = Path(tmp) / "vacia"
        vacia.mkdir()
        (vacia / "resumen_lote.json").write_text(json.dumps({"imagenes": 0}), encoding="utf-8")
        codigo, _, error = _main_con_salida([str(vacia)])
        assert codigo != 0 and str(vacia) in error, (codigo, error)


def main() -> None:
    probar_ac007_recuento_con_catalogo_de_prueba()
    probar_ac007_las_30_versionadas()
    probar_ac007_las_500_locales()
    probar_ac007_las_500_con_copia_parcial_se_salta()
    probar_ac007_carpeta_inexistente_o_vacia_es_un_error()
    print("\nTodo ok: contar_equivalencias (recuento de hallazgos sin regla, antes y despues de las equivalencias).")


if __name__ == "__main__":
    main()
