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

import json
import random
import shutil
import subprocess
import sys
import tempfile
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


AGENTES = Path(__file__).resolve().parent.parent
REALES = AGENTES / "ejemplos_contrato" / "agente1_real"
HOY = "2026-11-12"


def _filas_resumen(destino: Path) -> list[str]:
    return [l for l in (destino / "resumen.md").read_text(encoding="utf-8").splitlines()
            if l.startswith("| ") and not l.startswith("| image_id") and not l.startswith("|---")]


# --- plan #84, AC-001 y AC-002 -----------------------------------------------
def probar_ac001_ac002_treinta_informes_y_resumen():
    """AC-001 y AC-002: con las 30 salidas reales salen 30 informes y un
    resumen con una fila por imagen y el reparto propio/tercero; ningun informe
    tiene cifras que no salgan de su salida del Agente 2."""
    sys.path[:0] = [str(AGENTES / "agente_recuperacion"), str(AGENTES / "agente_redactor")]
    from costes_y_cobertura import estimar_siniestro
    from informe import comprobar_cifras

    with tempfile.TemporaryDirectory() as tmp:
        destino = Path(tmp)
        codigo = generar_informes_reales.generar(REALES, destino, hoy=HOY)
        informes = sorted(p.name for p in destino.glob("*.md") if p.name != "resumen.md")
        esperados = sorted(p.stem + ".md" for p in REALES.glob("*.json"))
        assert len(esperados) == 30 and informes == esperados, informes
        filas = _filas_resumen(destino)
        assert len(filas) == 30, filas
        resumen = (destino / "resumen.md").read_text(encoding="utf-8")
        casos = generar_informes_reales.preparar_casos(
            [json.loads(p.read_text(encoding="utf-8")) for p in REALES.glob("*.json")],
            generar_informes_reales.leer_siniestros())
        propios = sum(c["contexto"]["rol"] == "propio" for c in casos)
        assert f"{propios} propios y {30 - propios} de tercero" in resumen, resumen.splitlines()[:8]
        for caso in casos:
            fila = next(f for f in filas if f.startswith(f"| {caso['image_id']:06d} "))
            for dato in (caso["siniestro_id"], caso["categoria"], caso["contexto"]["vehiculo_id"]):
                assert f"| {dato} |" in fila, (dato, fila)
            salida2 = estimar_siniestro(caso["salida_agente1"], caso["contexto"])
            md = (destino / f"{caso['image_id']:06d}.md").read_text(encoding="utf-8")
            assert comprobar_cifras(md, salida2) == [], caso["image_id"]
            columnas = [c.strip() for c in fila.strip().strip("|").split("|")]
            assert columnas[-2:] == ["ninguna", ""], fila
        assert codigo == 0, codigo


# --- plan #84, AC-004 --------------------------------------------------------
def probar_ac004_error_en_una_salida():
    """AC-004: una salida que no pasa la validacion queda en el resumen con su
    image_id, las demas se generan y el codigo de salida es distinto de 0."""
    with tempfile.TemporaryDirectory() as tmp:
        salidas, destino = Path(tmp) / "salidas", Path(tmp) / "destino"
        salidas.mkdir()
        shutil.copy(REALES / "000082.json", salidas / "000082.json")
        rota = json.loads((REALES / "000341.json").read_text(encoding="utf-8"))
        rota["vehiculo"]["vehiculo_id_referencia"] = "V999"
        (salidas / "000341.json").write_text(json.dumps(rota), encoding="utf-8")
        codigo = generar_informes_reales.generar(salidas, destino, hoy=HOY)
        assert codigo != 0, codigo
        assert (destino / "000082.md").is_file() and not (destino / "000341.md").exists()
        fila = next(f for f in _filas_resumen(destino) if f.startswith("| 000341 "))
        assert "V999" in fila, fila


def probar_ac004_paquete_ausente():
    """AC-004: sin piia2_paquete_datos/ el generador falla al importar con un
    error que indica la ruta esperada."""
    with tempfile.TemporaryDirectory() as tmp:
        raiz = Path(tmp)
        (raiz / ".git").mkdir()
        for carpeta, archivo in (("agente_recuperacion", "costes_y_cobertura.py"), ("agente_redactor", "informe.py"),
                                 ("informes_reales", "generar_informes_reales.py")):
            (raiz / "agentes" / carpeta).mkdir(parents=True)
            shutil.copy(AGENTES / carpeta / archivo, raiz / "agentes" / carpeta / archivo)
        r = subprocess.run([sys.executable, "-c", "import generar_informes_reales"],
                           cwd=raiz / "agentes" / "informes_reales", capture_output=True, text=True)
        assert r.returncode != 0, "el modulo importo sin el paquete"
        assert "ImportError" in r.stderr and "piia2_paquete_datos" in r.stderr, r.stderr[-400:]


PRUEBAS = [
    probar_ac003_contexto_y_coche_de_cada_caso,
    probar_ac001_ac002_treinta_informes_y_resumen,
    probar_ac004_error_en_una_salida,
    probar_ac004_paquete_ausente,
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
