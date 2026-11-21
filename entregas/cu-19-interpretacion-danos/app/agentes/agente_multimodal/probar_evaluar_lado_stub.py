"""Prueba `evaluar_lado.py` sin API ni red (Issue #54, slice 5, AC-012).

Plan v1.1: https://github.com/lvckss/piia2-26/issues/54#issuecomment-6806386857 (AC-012)
Criterio de adopcion: https://github.com/lvckss/piia2-26/issues/54#issuecomment-6820567012

Comprueba el calculo del acierto de lado y de las dos condiciones de adopcion con datos sinteticos y que `ejecutar`
llama al modelo una vez por hallazgo con el prompt de la variante; no comprueba si el modelo acierta (eso lo mide la
ejecucion real, una sola vez)."""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

from PIL import Image

from evaluar_lado import (
    ACIERTOS_MINIMOS,
    CAMBIOS_DE_VEREDICTO_MAXIMOS,
    ejecutar,
    evaluar,
    lado_de_pieza,
    lado_verdadero,
    main,
    wilson,
)
from probar_vision_stub import MINI_CATALOGO, ClienteFalso


def probar_ac012_lado_de_pieza_y_lado_verdadero() -> None:
    assert lado_de_pieza("FARO_DEL_I") == "I" and lado_de_pieza("PILOTO_TRAS_D") == "D"
    assert lado_de_pieza("PARAG_DEL") is None and lado_de_pieza("NEUMATICO") is None and lado_de_pieza(None) is None
    # `si` conserva el lado de la base, `no` es el contrario, `nose` no tiene lado verdadero
    assert lado_verdadero("si", "I") == "I" and lado_verdadero("si", "D") == "D"
    assert lado_verdadero("no", "I") == "D" and lado_verdadero("no", "D") == "I"
    assert lado_verdadero("nose", "I") is None and lado_verdadero("si", None) is None


def probar_ac012_wilson() -> None:
    assert tuple(round(100 * v) for v in wilson(18, 29)) == (44, 77), wilson(18, 29)
    assert tuple(round(100 * v) for v in wilson(24, 29)) == (65, 92), wilson(24, 29)
    assert wilson(0, 0) == (0.0, 0.0)


def _escenario(imagenes: int = 6):
    """36 hallazgos laterales sinteticos: 18 con el lado bien (`si`), 11 al reves (`no`) y 7 indecidibles (`nose`),
    repartidos entre `imagenes` imagenes. En la base todos llevan una pieza del lado izquierdo."""
    base, etiquetas = {}, {}
    k = 0
    for lado, n in (("si", 18), ("no", 11), ("nose", 7)):
        for _ in range(n):
            k += 1
            fid = f"{k % imagenes + 1}-{k}"
            base[fid] = {"finding_id": fid, "pieza_id": "FARO_DEL_I", "vision_verdict": "confirmado"}
            etiquetas[fid] = {"lado": lado}
    return base, etiquetas


def _ids(etiquetas: dict, lado: str) -> list[str]:
    return [f for f, e in etiquetas.items() if e["lado"] == lado]


def probar_ac012_evaluar_cuenta_aciertos_y_condiciones() -> None:
    base, etiquetas = _escenario()
    al_reves = _ids(etiquetas, "no")

    # variante identica a la linea base: 18 de 29, sin cambios, no se adopta
    r = evaluar(base, copy.deepcopy(base), etiquetas)
    assert r["decidibles"] == 29 and r["aciertos_base"] == 18 and r["aciertos_variante"] == 18, r
    assert r["cambios_de_veredicto"] == 0 and r["condicion_lado"] is False and r["adoptar"] is False, r

    # corrige 6 de los 11 sin romper ningun acierto: 24 de 29 y se adopta
    v = copy.deepcopy(base)
    for fid in al_reves[:6]:
        v[fid]["pieza_id"] = "FARO_DEL_D"
    r = evaluar(base, v, etiquetas)
    assert ACIERTOS_MINIMOS == 24
    assert r["aciertos_variante"] == 24 and r["condicion_lado"] is True and r["adoptar"] is True, r

    # con 5 correcciones (23 de 29) no se cumple
    v5 = copy.deepcopy(base)
    for fid in al_reves[:5]:
        v5[fid]["pieza_id"] = "FARO_DEL_D"
    assert evaluar(base, v5, etiquetas)["adoptar"] is False

    # romper un acierto se descuenta: 6 correcciones y 1 acierto roto = 23
    roto = copy.deepcopy(v)
    roto[_ids(etiquetas, "si")[0]]["pieza_id"] = "FARO_DEL_D"
    assert evaluar(base, roto, etiquetas)["aciertos_variante"] == 23

    # incierto, sin pieza o una pieza sin lado no cuentan como acierto (no se gana diciendo «no lo se»)
    trampa = copy.deepcopy(base)
    trampa[al_reves[0]].update({"pieza_id": None, "vision_verdict": "incierto"})
    trampa[al_reves[1]]["pieza_id"] = "PARAG_DEL"
    r = evaluar(base, trampa, etiquetas)
    assert r["aciertos_variante"] == 18, r


def probar_ac012_evaluar_veredictos_indecidibles_e_imagenes() -> None:
    base, etiquetas = _escenario()
    al_reves = _ids(etiquetas, "no")
    indecidibles = _ids(etiquetas, "nose")
    assert CAMBIOS_DE_VEREDICTO_MAXIMOS == 25

    arreglada = copy.deepcopy(base)
    for fid in al_reves[:6]:
        arreglada[fid]["pieza_id"] = "FARO_DEL_D"
    cambiables = list(arreglada)

    # 25 veredictos distintos: aun se adopta; 26: ya no, aunque el lado cumpla
    for n, adopta in ((25, True), (26, False)):
        v = copy.deepcopy(arreglada)
        for fid in cambiables[:n]:
            v[fid]["vision_verdict"] = "incierto"
        r = evaluar(base, v, etiquetas)
        assert r["cambios_de_veredicto"] == n, r
        assert r["condicion_veredictos"] is adopta and r["condicion_lado"] is True and r["adoptar"] is adopta, r

    # indecidibles que pasan a incierto
    v = copy.deepcopy(base)
    for fid in indecidibles[:3]:
        v[fid].update({"vision_verdict": "incierto", "pieza_id": None})
    assert evaluar(base, v, etiquetas)["indecidibles_a_incierto"] == 3

    # imagenes con algun lado al reves: la base los tiene en las 6; la variante que corrige los 11, en ninguna
    r0 = evaluar(base, copy.deepcopy(base), etiquetas)
    assert r0["imagenes"] == 6 and r0["imagenes_con_error_base"] == 6 and r0["imagenes_con_error_variante"] == 6, r0
    todo = copy.deepcopy(base)
    for fid in al_reves:
        todo[fid]["pieza_id"] = "FARO_DEL_D"
    assert evaluar(base, todo, etiquetas)["imagenes_con_error_variante"] == 0


def _fixture(tmp: Path) -> dict[str, Path]:
    """2 imagenes con 2 hallazgos cada una (dent y lamp broken), con foto, recortes y detecciones."""
    rutas = {k: tmp / k for k in ("base", "recortes", "detecciones", "cardd", "salida")}
    (rutas["recortes"] / "crops").mkdir(parents=True)
    (rutas["cardd"] / "val2017").mkdir(parents=True)
    rutas["base"].mkdir()
    rutas["detecciones"].mkdir()
    for img_id in (10, 11):
        fichero = f"{img_id:06d}.jpg"
        # imagenes distintas, para que la cache (clave por prompt e imagenes) no confunda hallazgos de fotos distintas
        Image.new("RGB", (200, 150), (img_id * 10, 120, 120)).save(rutas["cardd"] / "val2017" / fichero)
        (rutas["detecciones"] / f"{img_id:06d}.json").write_text(
            json.dumps({"image_id": img_id, "image_file": fichero, "split": "val"}), encoding="utf-8")
        findings = []
        for n, categoria in ((1, "dent"), (2, "lamp broken")):
            recorte = f"crops/{img_id}_{categoria.replace(' ', '_')}_{n}.jpg"
            Image.new("RGB", (40, 40), (img_id * 10, 60 + n * 40, 80)).save(rutas["recortes"] / recorte)
            findings.append({"finding_id": f"{img_id}-{n}", "category": categoria, "bbox_xywh": [10, 10, 40, 40],
                             "crop_image_path": recorte, "pieza_id": "FARO_DEL_I", "vision_verdict": "confirmado"})
        (rutas["base"] / f"{img_id:06d}.json").write_text(json.dumps({"image_id": img_id, "findings": findings}), encoding="utf-8")
    return rutas


def probar_ac012_ejecutar_una_llamada_por_hallazgo_con_el_prompt_de_la_variante() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        r = _fixture(Path(tmp))
        cliente = ClienteFalso()
        resultados = ejecutar(r["base"], r["recortes"], r["detecciones"], r["cardd"], r["salida"], cliente,
                              "modelo-falso", MINI_CATALOGO, Path(tmp) / "cache")
        assert len(cliente.llamadas) == 4, len(cliente.llamadas)
        assert set(resultados) == {"10-1", "10-2", "11-1", "11-2"}, set(resultados)
        for llamada in cliente.llamadas:
            assert "lado_del_coche" in llamada["messages"][0]["content"][0]["text"], "no se uso el prompt de la variante"
        guardado = json.loads((r["salida"] / "resultados_variante.json").read_text(encoding="utf-8"))
        assert set(guardado) == set(resultados) and guardado["10-2"]["pieza_id"] == "FARO_DEL_D", guardado["10-2"]

        # el tope de llamadas se respeta antes de gastar nada
        otro = ClienteFalso()
        try:
            ejecutar(r["base"], r["recortes"], r["detecciones"], r["cardd"], Path(tmp) / "salida2", otro,
                     "modelo-falso", MINI_CATALOGO, Path(tmp) / "cache2", max_llamadas=3)
            raise AssertionError("debia negarse: 4 llamadas previstas con tope 3")
        except ValueError:
            pass
        assert otro.llamadas == []


def probar_ac012_plan_no_llama_a_la_api() -> None:
    def prohibido():
        raise AssertionError("el plan no debe crear el cliente de la API")

    with tempfile.TemporaryDirectory() as tmp:
        r = _fixture(Path(tmp))
        codigo = main(["plan", "--base", str(r["base"]), "--recortes", str(r["recortes"]),
                       "--detecciones", str(r["detecciones"]), "--cardd", str(r["cardd"])], crear_cliente=prohibido)
        assert codigo == 0
        # con una foto que falta, el plan lo dice y termina con codigo distinto de 0
        (r["cardd"] / "val2017" / "000011.jpg").unlink()
        assert main(["plan", "--base", str(r["base"]), "--recortes", str(r["recortes"]),
                     "--detecciones", str(r["detecciones"]), "--cardd", str(r["cardd"])], crear_cliente=prohibido) != 0


def main_pruebas() -> None:
    probar_ac012_lado_de_pieza_y_lado_verdadero()
    probar_ac012_wilson()
    probar_ac012_evaluar_cuenta_aciertos_y_condiciones()
    probar_ac012_evaluar_veredictos_indecidibles_e_imagenes()
    probar_ac012_ejecutar_una_llamada_por_hallazgo_con_el_prompt_de_la_variante()
    probar_ac012_plan_no_llama_a_la_api()
    print("\nTodo ok: evaluar_lado (acierto de lado, condiciones de adopcion, ejecucion y plan).")


if __name__ == "__main__":
    main_pruebas()
