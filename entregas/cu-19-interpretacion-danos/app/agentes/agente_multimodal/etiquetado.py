"""Etiquetado manual y precision por tramo de score (Issue #44, AC-003).

`is_true_positive` no es una vara fiable en `dent`, `scratch` y `crack` (CarDD
no anota todos los danos), asi que la precision de lo que la vision confirma se
estima con etiquetas manuales. Este modulo:

  * elige la muestra a etiquetar: hallazgos que la vision confirmo, de esas
    tres clases, con score por debajo del umbral actual de su clase (los que ya
    pasan el umbral no cambian de nivel si el umbral baja) y dentro de dos
    tramos de score (0,3-0,5 y 0,5-0,7), hasta N por clase y tramo;
  * genera una pagina de un solo archivo para etiquetarla (recorte primero, la
    respuesta de la IA despues) que guarda las marcas en el navegador y baja un
    CSV con solo ids y etiquetas (`finding_id,etiqueta`);
  * calcula, con ese CSV, la precision de `confirmado` por clase y tramo con
    intervalo de Wilson al 95 %, marca como no concluyente toda celda con menos
    de 5 casos y la compara con `is_true_positive`.

La pagina lleva los recortes de CarDD incrustados: no se escribe dentro de
`entregas/` (iria a git) sino, por defecto, en `piia2_detecciones/`, ignorada.

    python etiquetado.py muestra --salidas ../../../../../piia2_detecciones/salida_agente1_500
    python etiquetado.py tabla --salidas <carpeta de salidas> --etiquetas <csv> [--resultados <resultados_modelo.json>]
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import random
import sys
from collections import Counter
from math import sqrt
from pathlib import Path
from typing import Any

from confianza import CATEGORY_REVIEW_THRESHOLD

CLASES_ETIQUETADAS = ("dent", "scratch", "crack")
TRAMOS = ((0.3, 0.5), (0.5, 0.7))
ETIQUETAS = ("si", "otra", "no", "dudo")
MINIMO_CONCLUYENTE = 5
CABECERA_CSV = "finding_id,etiqueta"
# la tanda 1 es el tramo alto (el mas cercano al umbral actual); la 2 solo si la 1 no deja clara la conclusion
TANDA_DE_TRAMO = {1: 1, 0: 2}


class EtiquetasNoValidas(ValueError):
    """El fichero de etiquetas o una etiqueta no cumple el formato o no encaja en la muestra."""


def _raiz_repo() -> Path:
    return Path(__file__).resolve().parents[5]


def _nombre_tramo(i: int) -> str:
    lo, hi = TRAMOS[i]
    return f"{lo:.1f}-{hi:.1f}".replace(".", ",")


def tramo_de(score: float, tramos: tuple[tuple[float, float], ...] = TRAMOS) -> int | None:
    """Indice del tramo [inferior, superior) al que pertenece el score, o None."""
    for i, (inferior, superior) in enumerate(tramos):
        if inferior <= score < superior:
            return i
    return None


def intervalo_wilson(aciertos: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    """Intervalo de Wilson para una proporcion (95 % con z = 1,96). Sin casos, (None, None)."""
    if n == 0:
        return (None, None)
    p = aciertos / n
    denominador = 1 + z * z / n
    centro = p + z * z / (2 * n)
    margen = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (centro - margen) / denominador), min(1.0, (centro + margen) / denominador))


def _clave_id(finding_id: str) -> tuple:
    """Orden natural de un `finding_id` ("82-3"): por imagen y por indice, no por texto."""
    partes = finding_id.split("-")
    try:
        return tuple(int(p) for p in partes)
    except ValueError:
        return (10**9, finding_id)


def candidatos_a_etiquetar(salidas: list[dict[str, Any]], umbrales: dict[str, float] | None = None) -> list[dict[str, Any]]:
    """Hallazgos que la vision confirmo, de `dent`, `scratch` o `crack`, con score por debajo del
    umbral de su clase y dentro de un tramo. Cada uno lleva su `image_id`."""
    umbrales = CATEGORY_REVIEW_THRESHOLD if umbrales is None else umbrales
    candidatos = []
    for salida in salidas:
        for h in salida["findings"]:
            clase = h["category"]
            if clase not in CLASES_ETIQUETADAS or h["vision_verdict"] != "confirmado":
                continue
            if h["score"] >= umbrales[clase] or tramo_de(h["score"]) is None:
                continue
            candidatos.append({**h, "image_id": salida["image_id"]})
    return candidatos


def elegir_muestra(candidatos: list[dict[str, Any]], por_tramo: int = 10, semilla: int = 42) -> list[dict[str, Any]]:
    """Hasta `por_tramo` hallazgos por clase y tramo, deterministas segun la semilla. Orden: tanda 1
    (tramo 0,5-0,7) y luego tanda 2 (0,3-0,5); dentro de cada tanda, por clase."""
    grupos: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for c in candidatos:
        grupos.setdefault((c["category"], tramo_de(c["score"])), []).append(c)
    muestra = []
    for (clase, tramo), grupo in grupos.items():
        grupo = sorted(grupo, key=lambda c: _clave_id(c["finding_id"]))
        elegidos = random.Random(f"{semilla}|{clase}|{tramo}").sample(grupo, min(por_tramo, len(grupo)))
        for orden, c in enumerate(elegidos):
            muestra.append(
                {
                    "finding_id": c["finding_id"],
                    "image_id": c["image_id"],
                    "category": clase,
                    "score": c["score"],
                    "tramo": _nombre_tramo(tramo),
                    "tanda": TANDA_DE_TRAMO[tramo],
                    "vision_verdict": c["vision_verdict"],
                    "pieza_id": c.get("pieza_id"),
                    "vision_description": c.get("vision_description", ""),
                    "crop_image_path": c["crop_image_path"],
                    "_orden": (TANDA_DE_TRAMO[tramo], CLASES_ETIQUETADAS.index(clase), orden),
                }
            )
    muestra.sort(key=lambda m: m["_orden"])
    for m in muestra:
        del m["_orden"]
    return muestra


def leer_etiquetas(ruta: Any) -> dict[str, str]:
    """Lee el CSV `finding_id,etiqueta`. Admite BOM, finales de linea de Windows y lineas en blanco."""
    texto = Path(ruta).read_bytes().decode("utf-8-sig")
    lineas = texto.splitlines()
    if not lineas or lineas[0].strip() != CABECERA_CSV:
        raise EtiquetasNoValidas(f"la cabecera debe ser {CABECERA_CSV!r}")
    etiquetas: dict[str, str] = {}
    for numero, linea in enumerate(lineas[1:], start=2):
        if not linea.strip():
            continue
        campos = [c.strip() for c in linea.split(",")]
        if len(campos) != 2 or not campos[0]:
            raise EtiquetasNoValidas(f"linea {numero}: se esperaban dos campos (finding_id,etiqueta): {linea!r}")
        finding_id, etiqueta = campos
        if etiqueta not in ETIQUETAS:
            raise EtiquetasNoValidas(f"linea {numero}: etiqueta no valida {etiqueta!r} (admitidas: {', '.join(ETIQUETAS)})")
        if finding_id in etiquetas:
            raise EtiquetasNoValidas(f"linea {numero}: finding_id duplicado {finding_id!r}")
        etiquetas[finding_id] = etiqueta
    return etiquetas


def _fila(clase: str, tramo: str, etiquetas: list[str], is_tp: list[bool | None] | None) -> dict[str, Any]:
    cuenta = Counter(etiquetas)
    si, otra, no, dudo = (cuenta[e] for e in ETIQUETAS)
    n = si + otra + no
    fila: dict[str, Any] = {
        "clase": clase,
        "tramo": tramo,
        "etiquetados": n,
        "si": si,
        "otra": otra,
        "no": no,
        "dudo": dudo,
        "precision_estricta": si / n if n else None,
        "intervalo_estricta": intervalo_wilson(si, n),
        "precision_dano_real": (si + otra) / n if n else None,
        "intervalo_dano_real": intervalo_wilson(si + otra, n),
        "concluyente": n >= MINIMO_CONCLUYENTE,
    }
    if is_tp is not None:
        falsos = [e for e, tp in zip(etiquetas, is_tp) if e != "dudo" and tp is False]
        fila["confirmados_is_tp_falso"] = len(falsos)
        fila["de_ellos_si"] = falsos.count("si")
        fila["de_ellos_otra"] = falsos.count("otra")
        fila["sin_dato_is_tp"] = sum(1 for e, tp in zip(etiquetas, is_tp) if e != "dudo" and tp is None)
    return fila


def tabla_precision(
    salidas: list[dict[str, Any]], etiquetas: dict[str, str], is_tp: dict[str, bool] | None = None
) -> list[dict[str, Any]]:
    """Precision de `confirmado` por clase y tramo de score con intervalo de Wilson. Una fila por clase y
    tramo y una de total por clase; `dudo` se cuenta aparte y no entra en el denominador. Con `is_tp`
    (por `finding_id`) compara con `is_true_positive`."""
    indice = {h["finding_id"]: h for s in salidas for h in s["findings"]}
    celdas: dict[tuple[str, str], list[tuple[str, bool | None]]] = {}
    for finding_id, etiqueta in etiquetas.items():
        if etiqueta not in ETIQUETAS:
            raise EtiquetasNoValidas(f"{finding_id}: etiqueta no valida {etiqueta!r}")
        h = indice.get(finding_id)
        if h is None:
            raise EtiquetasNoValidas(f"{finding_id}: no existe en las salidas")
        if h["category"] not in CLASES_ETIQUETADAS:
            raise EtiquetasNoValidas(f"{finding_id}: la clase {h['category']!r} no se etiqueta (solo {', '.join(CLASES_ETIQUETADAS)})")
        tramo = tramo_de(h["score"])
        if tramo is None:
            raise EtiquetasNoValidas(f"{finding_id}: el score {h['score']:.2f} queda fuera de los tramos {_nombre_tramo(0)} y {_nombre_tramo(1)}")
        if h["vision_verdict"] != "confirmado":
            raise EtiquetasNoValidas(f"{finding_id}: la vision no lo confirmo ({h['vision_verdict']}); la muestra solo lleva confirmados")
        celdas.setdefault((h["category"], _nombre_tramo(tramo)), []).append((etiqueta, None if is_tp is None else is_tp.get(finding_id)))
    filas = []
    for clase in CLASES_ETIQUETADAS:
        todas: list[tuple[str, bool | None]] = []
        for i in range(len(TRAMOS)):
            marcas = celdas.get((clase, _nombre_tramo(i)), [])
            todas += marcas
            filas.append(_fila(clase, _nombre_tramo(i), [e for e, _ in marcas], None if is_tp is None else [t for _, t in marcas]))
        filas.append(_fila(clase, "total", [e for e, _ in todas], None if is_tp is None else [t for _, t in todas]))
    return filas


def _pct(x: float | None) -> str:
    return "-" if x is None else f"{round(x * 100)} %"


def _ic(par: tuple[float | None, float | None]) -> str:
    return "-" if par[0] is None else f"{round(par[0] * 100)}-{round(par[1] * 100)} %"


def formatear_tabla(filas: list[dict[str, Any]]) -> str:
    """La tabla en Markdown, lista para pegar en la PR o en la spec."""
    con_tp = "confirmados_is_tp_falso" in filas[0]
    cabecera = ["Clase", "Tramo", "n", "sí", "otra", "no", "dudo", "Precisión (sí)", "IC 95 %", "Precisión (daño real)", "IC 95 %", "Conclusión"]
    if con_tp:
        cabecera += ["is_tp falso", "de ellos sí", "de ellos otra"]
    lineas = ["| " + " | ".join(cabecera) + " |", "|" + "---|" * len(cabecera)]
    for f in filas:
        conclusion = "concluyente" if f["concluyente"] else ("sin etiquetas" if f["etiquetados"] == 0 else "no concluyente")
        celdas = [f["clase"], f["tramo"], f["etiquetados"], f["si"], f["otra"], f["no"], f["dudo"], _pct(f["precision_estricta"]),
                  _ic(f["intervalo_estricta"]), _pct(f["precision_dano_real"]), _ic(f["intervalo_dano_real"]), conclusion]
        if con_tp:
            celdas += [f["confirmados_is_tp_falso"], f["de_ellos_si"], f["de_ellos_otra"]]
        lineas.append("| " + " | ".join(str(c) for c in celdas) + " |")
    lineas.append("")
    lineas.append(f"`n` no cuenta los `dudo`. «No concluyente»: menos de {MINIMO_CONCLUYENTE} casos. Intervalo de Wilson al 95 %. "
                  "«Precisión (sí)» cuenta solo `si`; «daño real» cuenta `si` y `otra`.")
    return "\n".join(lineas)


_PAGINA = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Etiquetado de hallazgos (#44)</title>
<style>
  :root { color-scheme: light dark; --fondo:#f6f7f9; --tarjeta:#fff; --texto:#1b2230; --suave:#5b6577; --borde:#d5dae3; --si:#1f8a4c; --otra:#2f6fb5; --no:#c0392b; --dudo:#8a6d1f; }
  @media (prefers-color-scheme: dark) { :root { --fondo:#14171d; --tarjeta:#1d222b; --texto:#e8ebf1; --suave:#9aa4b6; --borde:#323a48; } }
  body { margin:0; font:16px/1.45 system-ui, sans-serif; background:var(--fondo); color:var(--texto); }
  main { max-width:760px; margin:0 auto; padding:16px; }
  h1 { font-size:1.15rem; margin:0 0 4px; }
  .suave { color:var(--suave); font-size:.9rem; }
  .barra { height:8px; background:var(--borde); border-radius:4px; margin:10px 0 14px; overflow:hidden; }
  .barra > div { height:100%; background:var(--si); width:0; transition:width .15s; }
  .tarjeta { background:var(--tarjeta); border:1px solid var(--borde); border-radius:10px; padding:14px; }
  .recorte { display:flex; justify-content:center; background:#0001; border-radius:8px; padding:8px; min-height:200px; align-items:center; }
  .recorte img { max-width:100%; max-height:62vh; image-rendering:auto; }
  .meta { margin:10px 0 4px; font-weight:600; }
  .botones { display:grid; grid-template-columns:repeat(4,1fr); gap:8px; margin:12px 0; }
  .botones button { font:inherit; padding:12px 6px; border-radius:8px; border:2px solid var(--borde); background:var(--tarjeta); color:var(--texto); cursor:pointer; }
  .botones button[data-etiqueta="si"] { border-color:var(--si); } .botones button[data-etiqueta="otra"] { border-color:var(--otra); }
  .botones button[data-etiqueta="no"] { border-color:var(--no); } .botones button[data-etiqueta="dudo"] { border-color:var(--dudo); }
  .botones button.activa { color:#fff; } .botones button.activa[data-etiqueta="si"] { background:var(--si); } .botones button.activa[data-etiqueta="otra"] { background:var(--otra); }
  .botones button.activa[data-etiqueta="no"] { background:var(--no); } .botones button.activa[data-etiqueta="dudo"] { background:var(--dudo); }
  .fila { display:flex; gap:8px; flex-wrap:wrap; margin:8px 0; }
  .fila button { font:inherit; padding:8px 12px; border-radius:8px; border:1px solid var(--borde); background:var(--tarjeta); color:var(--texto); cursor:pointer; }
  #ia { display:none; margin-top:8px; padding:10px; border-left:4px solid var(--otra); background:#2f6fb512; border-radius:4px; }
  #resumen { margin-top:14px; }
  code { font-size:.85rem; }
</style>
</head>
<body>
<main>
  <h1>Etiquetado de hallazgos (Issue #44)</h1>
  <div class="suave">Mira primero el recorte. Pregunta: ¿hay un daño de la clase indicada dentro de la caja? <b>s</b> sí · <b>o</b> hay un daño de otra clase · <b>n</b> no · <b>d</b> dudo · <span id="ayuda-ia"><b>espacio</b> ver qué dice la IA · </span><b>← →</b> moverte. Las marcas se guardan en este navegador.</div>
  <div class="barra"><div id="avance"></div></div>
  <div class="tarjeta">
    <div class="suave" id="posicion"></div>
    <div class="recorte"><img id="imagen" alt="recorte del hallazgo"></div>
    <div class="meta" id="meta"></div>
    <div class="botones">
      <button data-etiqueta="si">Sí (s)</button>
      <button data-etiqueta="otra">Otra clase (o)</button>
      <button data-etiqueta="no">No (n)</button>
      <button data-etiqueta="dudo">Dudo (d)</button>
    </div>
    <div class="fila">
      <button id="anterior">← Anterior</button>
      <button id="siguiente">Siguiente →</button>
      <button id="ver">Ver qué dice la IA (espacio)</button>
    </div>
    <div id="ia"></div>
  </div>
  <div id="resumen"></div>
  <div class="fila">
    <button id="descargar">Descargar CSV</button>
    <button id="pendiente">Ir al primero sin marcar</button>
    <button id="borrar">Borrar todas las marcas</button>
  </div>
  <p class="suave">El CSV solo lleva <code>finding_id,etiqueta</code>, sin imágenes. Guárdalo donde diga el README del agente.</p>
</main>
<script>
const MUESTRA = __DATOS__;
const CLAVE = '__CLAVE__';
const CIEGO = __CIEGO__;
const TECLAS = {'s': 'si', 'o': 'otra', 'n': 'no', 'd': 'dudo'};
let marcas = {};
let actual = 0;
try { marcas = JSON.parse(localStorage.getItem(CLAVE) || '{}'); } catch (e) { marcas = {}; }
function guardar() { try { localStorage.setItem(CLAVE, JSON.stringify(marcas)); } catch (e) {} }
function porcentaje(x) { return Math.round(x * 100); }
function pintar() {
  const m = MUESTRA[actual];
  document.getElementById('imagen').src = m.img;
  document.getElementById('posicion').textContent = 'Hallazgo ' + (actual + 1) + ' de ' + MUESTRA.length + ' · tanda ' + m.tanda + ' · ' + m.id;
  document.getElementById('meta').textContent = CIEGO ? 'Clase de la caja: ' + m.clase : 'Clase de la caja: ' + m.clase + ' · score ' + m.score.toFixed(2).replace('.', ',') + ' · tramo ' + m.tramo;
  const ia = document.getElementById('ia');
  ia.style.display = 'none';
  ia.textContent = CIEGO ? '' : 'La IA dice: ' + m.veredicto + (m.pieza ? ' · pieza ' + m.pieza : '') + (m.descripcion ? ' · ' + m.descripcion : '');
  document.querySelectorAll('.botones button').forEach(function (b) { b.classList.toggle('activa', marcas[m.id] === b.dataset.etiqueta); });
  const hechas = Object.keys(marcas).length;
  document.getElementById('avance').style.width = porcentaje(hechas / MUESTRA.length) + '%';
  const cuenta = {si: 0, otra: 0, no: 0, dudo: 0};
  Object.values(marcas).forEach(function (e) { cuenta[e] += 1; });
  document.getElementById('resumen').textContent = 'Marcados ' + hechas + ' de ' + MUESTRA.length + ' · sí ' + cuenta.si + ' · otra ' + cuenta.otra + ' · no ' + cuenta.no + ' · dudo ' + cuenta.dudo;
}
function marcar(etiqueta) {
  marcas[MUESTRA[actual].id] = etiqueta;
  guardar();
  if (actual < MUESTRA.length - 1) { actual += 1; }
  pintar();
}
function ir(delta) { actual = Math.min(MUESTRA.length - 1, Math.max(0, actual + delta)); pintar(); }
function csv() { return '__CABECERA__\\n' + MUESTRA.filter(function (m) { return marcas[m.id]; }).map(function (m) { return m.id + ',' + marcas[m.id]; }).join('\\n') + '\\n'; }
document.querySelectorAll('.botones button').forEach(function (b) { b.addEventListener('click', function () { marcar(b.dataset.etiqueta); }); });
document.getElementById('anterior').addEventListener('click', function () { ir(-1); });
document.getElementById('siguiente').addEventListener('click', function () { ir(1); });
document.getElementById('ver').addEventListener('click', function () { const ia = document.getElementById('ia'); ia.style.display = ia.style.display === 'block' ? 'none' : 'block'; });
document.getElementById('pendiente').addEventListener('click', function () { const i = MUESTRA.findIndex(function (m) { return !marcas[m.id]; }); if (i >= 0) { actual = i; pintar(); } });
document.getElementById('borrar').addEventListener('click', function () { if (confirm('¿Borrar todas las marcas de este navegador?')) { marcas = {}; guardar(); pintar(); } });
document.getElementById('descargar').addEventListener('click', function () {
  const enlace = document.createElement('a');
  enlace.href = URL.createObjectURL(new Blob([csv()], {type: 'text/csv;charset=utf-8'}));
  enlace.download = '__ARCHIVO__';
  enlace.click();
});
document.addEventListener('keydown', function (ev) {
  if (ev.ctrlKey || ev.metaKey || ev.altKey) { return; }
  const tecla = ev.key.length === 1 ? ev.key.toLowerCase() : ev.key;
  if (TECLAS[tecla]) { marcar(TECLAS[tecla]); ev.preventDefault(); }
  else if (tecla === ' ') { if (!CIEGO) { document.getElementById('ver').click(); } ev.preventDefault(); }
  else if (tecla === 'ArrowLeft') { ir(-1); } else if (tecla === 'ArrowRight') { ir(1); }
});
if (CIEGO) { document.getElementById('ver').style.display = 'none'; document.getElementById('ayuda-ia').style.display = 'none'; }
pintar();
</script>
</body>
</html>
"""


def elegir_muestra_validacion(salidas: list[dict[str, Any]], excluidos: Any = frozenset(), por_clase: int = 5, semilla: int = 42,
                              umbrales: dict[str, float] | None = None) -> list[dict[str, Any]]:
    """Muestra para validar a un modelo juez contra personas (AC-009): por clase, hasta `por_clase` hallazgos
    que la vision rechazo y hasta `por_clase` que confirmo con score por encima del umbral de su clase, sin
    los `excluidos` (ya etiquetados). Cubre las seis clases y los dos extremos, que la muestra de la tabla de
    precision (solo confirmados entre 0,3 y 0,7) no tiene. El tramo no revela el veredicto y el orden mezcla
    los dos tipos de forma determinista segun la semilla."""
    umbrales = CATEGORY_REVIEW_THRESHOLD if umbrales is None else umbrales
    excluidos = set(excluidos)
    grupos: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for salida in salidas:
        for h in salida["findings"]:
            if h["finding_id"] in excluidos or h["category"] not in umbrales:
                continue
            if h["vision_verdict"] == "rechazado":
                tipo = "rechazado"
            elif h["vision_verdict"] == "confirmado" and h["score"] >= umbrales[h["category"]]:
                tipo = "alto"
            else:
                continue
            grupos.setdefault((h["category"], tipo), []).append({**h, "image_id": salida["image_id"]})
    muestra = []
    for (clase, tipo), grupo in grupos.items():
        grupo = sorted(grupo, key=lambda c: _clave_id(c["finding_id"]))
        for c in random.Random(f"{semilla}|validacion|{clase}|{tipo}").sample(grupo, min(por_clase, len(grupo))):
            muestra.append(
                {
                    "finding_id": c["finding_id"],
                    "image_id": c["image_id"],
                    "category": clase,
                    "score": c["score"],
                    "tramo": "validación",
                    "tanda": 1,
                    "vision_verdict": c["vision_verdict"],
                    "pieza_id": c.get("pieza_id"),
                    "vision_description": c.get("vision_description", ""),
                    "crop_image_path": c["crop_image_path"],
                }
            )
    muestra.sort(key=lambda m: hashlib.sha1(f"{semilla}|{m['finding_id']}".encode("utf-8")).hexdigest())
    return muestra


def generar_pagina(muestra: list[dict[str, Any]], base_recortes: Any, ruta_html: Any, nombre_csv: str = "etiquetas_44.csv",
                   ciego: bool = False) -> Path:
    """Escribe la pagina de etiquetado (un solo archivo, sin red) con los recortes incrustados. Con `ciego` la
    pagina solo lleva recorte y clase (sin score, veredicto, pieza ni descripcion de la vision, ni en pantalla
    ni en el codigo): es lo mismo que ve el modelo juez, para que ambas etiquetas sean comparables."""
    if not muestra:
        raise EtiquetasNoValidas("la muestra esta vacia: no hay hallazgos que etiquetar")
    base = Path(base_recortes)
    elementos = []
    for m in muestra:
        recorte = base / m["crop_image_path"]
        if not recorte.is_file():
            raise EtiquetasNoValidas(f"{m['finding_id']}: falta el recorte {m['crop_image_path']}")
        elemento = {
            "id": m["finding_id"],
            "clase": m["category"],
            "tramo": m["tramo"],
            "tanda": m["tanda"],
            "img": "data:image/jpeg;base64," + base64.b64encode(recorte.read_bytes()).decode("ascii"),
        }
        if not ciego:
            elemento.update(
                {
                    "score": m["score"],
                    "veredicto": m["vision_verdict"],
                    "pieza": m.get("pieza_id"),
                    "descripcion": m.get("vision_description", ""),
                }
            )
        elementos.append(elemento)
    clave = "etiquetas44:" + hashlib.sha1("|".join(m["finding_id"] for m in muestra).encode("utf-8")).hexdigest()[:10]
    datos = json.dumps(elementos, ensure_ascii=False).replace("</", "<\\/")
    html = _PAGINA.replace("__DATOS__", datos).replace("__CLAVE__", clave).replace("__CABECERA__", CABECERA_CSV).replace("__ARCHIVO__", nombre_csv).replace("__CIEGO__", "true" if ciego else "false")
    destino = Path(ruta_html)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    return destino


def _leer_salidas(carpeta: Path) -> list[dict[str, Any]]:
    ficheros = sorted(p for p in carpeta.glob("*.json") if p.name != "resumen_lote.json")
    if not ficheros:
        raise EtiquetasNoValidas(f"no hay salidas del Agente 1 (*.json) en {carpeta}")
    return [json.loads(p.read_text(encoding="utf-8")) for p in ficheros]


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    raiz = _raiz_repo()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="orden", required=True)
    m = sub.add_parser("muestra", help="elige la muestra y genera la pagina de etiquetado")
    m.add_argument("--salidas", type=Path, required=True, help="carpeta con las salidas del Agente 1 (un JSON por imagen)")
    m.add_argument("--por-tramo", type=int, default=10)
    m.add_argument("--semilla", type=int, default=42)
    m.add_argument("--pagina", type=Path, default=raiz / "piia2_detecciones" / "etiquetado" / "etiquetar.html")
    m.add_argument("--muestra-json", type=Path, default=None, help="donde guardar la lista de la muestra (por defecto junto a la pagina)")
    v = sub.add_parser("validacion", help="elige hallazgos rechazados y confirmados con score alto para validar a un modelo juez y genera la pagina")
    v.add_argument("--salidas", type=Path, required=True, help="carpeta con las salidas del Agente 1")
    v.add_argument("--excluir", type=Path, default=None, help="CSV de etiquetas ya hechas, cuyos hallazgos no se repiten")
    v.add_argument("--por-clase", type=int, default=5, help="por clase y tipo (rechazados y confirmados altos)")
    v.add_argument("--semilla", type=int, default=42)
    v.add_argument("--pagina", type=Path, default=raiz / "piia2_detecciones" / "etiquetado" / "etiquetar_validacion.html")
    v.add_argument("--muestra-json", type=Path, default=None, help="donde guardar la lista (por defecto junto a la pagina)")
    t = sub.add_parser("tabla", help="precision por clase y tramo a partir del CSV de etiquetas")
    t.add_argument("--salidas", type=Path, required=True)
    t.add_argument("--etiquetas", type=Path, required=True)
    t.add_argument("--resultados", type=Path, default=None, help="resultados_<modelo>.json de evaluar_vision.py, para comparar con is_true_positive")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _argumentos(argv)
    try:
        salidas = _leer_salidas(args.salidas)
        if args.orden in ("muestra", "validacion"):
            destino = args.pagina.resolve()
            if (_raiz_repo() / "entregas").resolve() in (destino, *destino.parents):
                raise EtiquetasNoValidas("la pagina lleva recortes de CarDD: no se escribe dentro de entregas/ (iria a git); usa piia2_detecciones/")
        if args.orden == "validacion":
            excluidos = set(leer_etiquetas(args.excluir)) if args.excluir else set()
            muestra = elegir_muestra_validacion(salidas, excluidos, args.por_clase, args.semilla)
            generar_pagina(muestra, args.salidas, destino, "etiquetas_validacion_44.csv", ciego=True)
            lista = args.muestra_json or destino.with_name("muestra_validacion.json")
            lista.parent.mkdir(parents=True, exist_ok=True)
            lista.write_text(json.dumps(muestra, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            por_clase = Counter(m["category"] for m in muestra)
            print(f"Validacion: {len(muestra)} hallazgos ({', '.join(f'{c}: {n}' for c, n in sorted(por_clase.items()))}), semilla {args.semilla}, {len(excluidos)} excluidos.")
            print(f"Pagina: {destino}\nLista:  {lista}")
            return 0
        if args.orden == "muestra":
            candidatos = candidatos_a_etiquetar(salidas)
            muestra = elegir_muestra(candidatos, args.por_tramo, args.semilla)
            generar_pagina(muestra, args.salidas, destino)
            lista = args.muestra_json or destino.with_name("muestra.json")
            lista.parent.mkdir(parents=True, exist_ok=True)
            lista.write_text(json.dumps(muestra, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            por_clase = Counter(m["category"] for m in muestra)
            print(f"Candidatas: {len(candidatos)}. Muestra: {len(muestra)} hallazgos "
                  f"({', '.join(f'{c}: {por_clase[c]}' for c in CLASES_ETIQUETADAS)}), semilla {args.semilla}.")
            print(f"Pagina: {destino}\nLista:  {lista}")
            return 0
        etiquetas = leer_etiquetas(args.etiquetas)
        is_tp = None
        if args.resultados is not None:
            is_tp = {r["finding_id"]: bool(r["is_tp"]) for r in json.loads(args.resultados.read_text(encoding="utf-8"))}
        print(formatear_tabla(tabla_precision(salidas, etiquetas, is_tp)))
        return 0
    except EtiquetasNoValidas as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
