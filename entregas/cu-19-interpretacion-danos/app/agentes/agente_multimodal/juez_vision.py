"""Juez de hallazgos con un modelo de vision (Issue #44, AC-008 y AC-009 del plan v1.2).

Etiquetar a mano los ~3.700 hallazgos de las 500 imagenes no cabe en el calendario,
asi que un modelo mas fuerte hace de juez con las mismas condiciones que una
persona: ve **solo el recorte** y la clase de la caja, responde a la misma pregunta
(«¿hay un dano de esa clase dentro de la caja?») con `si`, `otra`, `no` o `dudo`, y
**no ve** el veredicto ni la descripcion de la vision que se esta evaluando. Sus
etiquetas son del modelo, no verdad humana: se validan con etiquetas humanas
(`acuerdo`: acuerdo exacto, kappa de Cohen y matriz) y asi se declaran.

    # en seco (por defecto): cuenta hallazgos, cache y llamadas por pagar
    python juez_vision.py juzgar --salidas <carpeta de salidas> --todos --modelo ID
    python juez_vision.py juzgar --salidas <carpeta> --ids etiquetas_humanas.csv --modelo ID --esfuerzo xhigh --ejecutar
    python juez_vision.py acuerdo --humanas humanas.csv --juez piia2_detecciones/juez/<modelo>/etiquetas_juez.csv

Escribe, por defecto en `piia2_detecciones/juez/<modelo>/` (ignorada por git):
`etiquetas_juez.csv` (`finding_id,etiqueta`, el mismo formato que las humanas),
`detalle_juez.json` (etiqueta y motivo por hallazgo) y `resumen_juez.json`.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import re
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from PIL import Image

from agente1 import crear_cliente_openai, resolver_modelo
from etiquetado import CABECERA_CSV, ETIQUETAS, EtiquetasNoValidas, _clave_id, _leer_salidas, intervalo_wilson, leer_etiquetas

MAX_FALLOS_SEGUIDOS = 5  # fallos seguidos de la API tras los que se aborta la pasada

# definiciones breves de cada clase (CarDD); son parte del protocolo: cambiarlas cambia la clave de cache
DEFINICIONES_CLASE = {
    "dent": "abolladura: hundimiento o deformacion de la chapa",
    "scratch": "aranazo o rozadura en la pintura o la superficie",
    "crack": "grieta o rotura (de plastico, chapa o cristal)",
    "glass shatter": "cristal roto o astillado",
    "lamp broken": "faro o piloto roto",
    "tire flat": "neumatico pinchado o desinflado",
}

PROMPT_JUEZ = """\
Eres un perito de danos de vehiculos y vas a etiquetar un recorte de una fotografia. Un detector automatico ha marcado esta zona como un posible dano de tipo '{categoria}'{definicion}.

Pregunta: ¿hay un dano de ESA clase dentro del recorte? El recorte puede mostrar solo parte del dano; responde segun lo que se ve.

Responde SOLO con un objeto JSON: {{"etiqueta": "si" | "otra" | "no" | "dudo", "motivo": "una frase en espanol"}}
- "si": hay un dano de la clase indicada.
- "otra": hay un dano real, pero de otra clase (por ejemplo, una rotura donde se indico una abolladura).
- "no": no hay ningun dano en la zona (reflejo, sombra, suciedad, una junta o la forma normal del vehiculo).
- "dudo": con esta imagen no se puede decidir."""


class LimiteDeLlamadas(RuntimeError):
    """Las llamadas por pagar superan el tope `--max-llamadas`: no se hace ninguna."""


class JuezAbortado(RuntimeError):
    """Demasiados fallos seguidos de la API. `parcial` lleva lo conseguido hasta entonces."""

    def __init__(self, mensaje: str, parcial: dict[str, Any]) -> None:
        super().__init__(mensaje)
        self.parcial = parcial


_CERROJO_USO = threading.Lock()


def construir_prompt(categoria: str) -> str:
    definicion = DEFINICIONES_CLASE.get(categoria)
    return PROMPT_JUEZ.format(categoria=categoria, definicion=f" ({definicion})" if definicion else "")


def _jpeg_base64(imagen: Image.Image) -> str:
    buffer = io.BytesIO()
    imagen.convert("RGB").save(buffer, format="JPEG", quality=90)
    return base64.standard_b64encode(buffer.getvalue()).decode("utf-8")


def _extraer_json(texto: str) -> dict[str, Any]:
    for candidato in (texto, *re.findall(r"\{.*\}", texto or "", flags=re.DOTALL)):
        try:
            datos = json.loads(candidato)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(datos, dict):
            return datos
    return {}


def parsear_juicio(texto: str) -> dict[str, str] | None:
    """La etiqueta y el motivo de la respuesta, o None si no trae una de las cuatro etiquetas validas."""
    datos = _extraer_json(texto)
    etiqueta = datos.get("etiqueta")
    if etiqueta not in ETIQUETAS:
        return None
    return {"etiqueta": etiqueta, "motivo": str(datos.get("motivo") or "").strip()}


def _clave_cache(modelo: str, esfuerzo: str | None, prompt: str, recorte_b64: str) -> str:
    return hashlib.sha256("|".join((modelo, esfuerzo or "", prompt, recorte_b64)).encode("utf-8")).hexdigest()


def _preparar(recorte: Path, categoria: str, modelo: str, esfuerzo: str | None) -> tuple[str, str, str]:
    with Image.open(recorte) as imagen:
        recorte_b64 = _jpeg_base64(imagen)
    prompt = construir_prompt(categoria)
    return prompt, recorte_b64, _clave_cache(modelo, esfuerzo, prompt, recorte_b64)


def _sumar(uso: dict[str, int] | None, **cantidades: int) -> None:
    if uso is None:
        return
    with _CERROJO_USO:
        for clave, valor in cantidades.items():
            uso[clave] = uso.get(clave, 0) + valor


def juzgar_hallazgo(
    client: Any,
    modelo: str,
    esfuerzo: str | None,
    recorte: Path,
    categoria: str,
    cache_dir: Any,
    uso: dict[str, int] | None,
    formato_json: bool = True,
) -> dict[str, str] | None:
    """El juicio de un hallazgo: `{"etiqueta", "motivo"}`, o None si la respuesta no trae una etiqueta
    valida (no se guarda en la cache, asi se reintenta). Las excepciones de la API se propagan."""
    prompt, recorte_b64, clave = _preparar(Path(recorte), categoria, modelo, esfuerzo)
    ruta_cache = None if cache_dir is None else Path(cache_dir) / f"{clave}.json"
    if ruta_cache is not None and ruta_cache.exists():
        juicio = parsear_juicio(json.loads(ruta_cache.read_text(encoding="utf-8"))["respuesta"])
        if juicio is not None:
            _sumar(uso, desde_cache=1)
            return juicio

    peticion: dict[str, Any] = {
        "model": modelo,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{recorte_b64}"}},
                ],
            }
        ],
    }
    if formato_json:
        peticion["response_format"] = {"type": "json_object"}
    if esfuerzo:
        peticion["reasoning_effort"] = esfuerzo
    respuesta = client.chat.completions.create(**peticion)
    texto = respuesta.choices[0].message.content or ""

    tokens = getattr(respuesta, "usage", None)
    _sumar(
        uso,
        llamadas=1,
        prompt_tokens=int(getattr(tokens, "prompt_tokens", 0) or 0),
        completion_tokens=int(getattr(tokens, "completion_tokens", 0) or 0),
    )
    juicio = parsear_juicio(texto)
    if juicio is not None and ruta_cache is not None:
        ruta_cache.parent.mkdir(parents=True, exist_ok=True)
        ruta_cache.write_text(json.dumps({"modelo": modelo, "esfuerzo": esfuerzo, "respuesta": texto}, ensure_ascii=False), encoding="utf-8")
    return juicio


def _plan(hallazgos: list[dict[str, Any]], salida_dir: Path, modelo: str, esfuerzo: str | None, cache_dir: Any) -> dict[str, int]:
    en_cache = por_pagar = 0
    for h in hallazgos:
        recorte = salida_dir / h["crop_image_path"]
        if not recorte.is_file():
            continue
        clave = _preparar(recorte, h["category"], modelo, esfuerzo)[2]
        if cache_dir is not None and (Path(cache_dir) / f"{clave}.json").exists():
            en_cache += 1
        else:
            por_pagar += 1
    return {"en_alcance": len(hallazgos), "en_cache": en_cache, "por_pagar": por_pagar}


def juzgar_lote(
    hallazgos: list[dict[str, Any]],
    salida_dir: Any,
    client: Any,
    modelo: str,
    esfuerzo: str | None,
    cache_dir: Any,
    max_llamadas: int,
    ejecutar: bool = False,
    hilos: int = 1,
    formato_json: bool = True,
    progreso: Callable[[int, int, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Juzga los hallazgos. Sin `ejecutar` solo devuelve el plan (en alcance, en cache y por pagar). Si lo
    por pagar supera `max_llamadas` no hace ninguna llamada. Un fallo de un hallazgo (respuesta sin
    etiqueta valida, recorte ausente o error de la API) queda en `fallos` y la pasada sigue; tras
    `MAX_FALLOS_SEGUIDOS` errores seguidos de la API se aborta con `JuezAbortado`."""
    salida_dir = Path(salida_dir)
    plan = _plan(hallazgos, salida_dir, modelo, esfuerzo, cache_dir)
    resultado: dict[str, Any] = {"plan": plan, "etiquetas": {}, "detalle": {}, "fallos": [], "uso": {"llamadas": 0, "prompt_tokens": 0, "completion_tokens": 0, "desde_cache": 0}}
    if not ejecutar:
        return resultado
    if plan["por_pagar"] > max_llamadas:
        raise LimiteDeLlamadas(f"{plan['por_pagar']} llamadas por pagar superan el tope --max-llamadas={max_llamadas}; sube el tope a conciencia o reduce el alcance")

    def trabajo(h: dict[str, Any]) -> tuple[str, dict[str, str] | None, str | None, bool]:
        """(finding_id, juicio, motivo del fallo, fallo de la API)"""
        recorte = salida_dir / h["crop_image_path"]
        if not recorte.is_file():
            return h["finding_id"], None, f"falta el recorte {h['crop_image_path']}", False
        try:
            juicio = juzgar_hallazgo(client, modelo, esfuerzo, recorte, h["category"], cache_dir, resultado["uso"], formato_json)
        except Exception as error:  # un fallo de la API no tira la pasada
            return h["finding_id"], None, f"{type(error).__name__}: {error}", True
        if juicio is None:
            return h["finding_id"], None, "respuesta sin etiqueta valida", False
        return h["finding_id"], juicio, None, False

    seguidos = 0
    lote = max(1, hilos) * 4 if hilos > 1 else 1
    hechos = 0
    ejecutor = ThreadPoolExecutor(max_workers=hilos) if hilos > 1 else None
    try:
        for inicio in range(0, len(hallazgos), lote):
            tanda = hallazgos[inicio : inicio + lote]
            resultados = list(ejecutor.map(trabajo, tanda)) if ejecutor else [trabajo(tanda[0])]
            for finding_id, juicio, motivo, fallo_api in resultados:
                hechos += 1
                if juicio is not None:
                    resultado["etiquetas"][finding_id] = juicio["etiqueta"]
                    resultado["detalle"][finding_id] = {"etiqueta": juicio["etiqueta"], "motivo": juicio["motivo"]}
                    seguidos = 0
                else:
                    resultado["fallos"].append({"finding_id": finding_id, "motivo": motivo})
                    seguidos = seguidos + 1 if fallo_api else 0
                if progreso is not None:
                    progreso(hechos, len(hallazgos), resultado)
            if seguidos >= MAX_FALLOS_SEGUIDOS:
                raise JuezAbortado(f"{seguidos} fallos seguidos de la API: se aborta la pasada; lo juzgado hasta ahora queda en la cache", resultado)
    finally:
        if ejecutor:
            ejecutor.shutdown(wait=True)
    return resultado


def _kappa(po: float, pe: float) -> float | None:
    return None if pe >= 1 else (po - pe) / (1 - pe)


def acuerdo(humanas: dict[str, str], juez: dict[str, str]) -> dict[str, Any]:
    """Acuerdo entre las etiquetas humanas y las del juez sobre los hallazgos que tienen las dos. Los
    `dudo` (de cualquiera) quedan fuera y se cuentan aparte. `otra` cuenta como «daño real» (`si` u
    `otra`) frente a `no` en el acuerdo binario."""
    comunes = sorted(set(humanas) & set(juez), key=_clave_id)
    dudo_humano = sum(humanas[i] == "dudo" for i in comunes)
    dudo_juez = sum(juez[i] == "dudo" for i in comunes)
    validos = [i for i in comunes if humanas[i] != "dudo" and juez[i] != "dudo"]
    n = len(validos)
    matriz = {h: {j: 0 for j in ("si", "otra", "no")} for h in ("si", "otra", "no")}
    for i in validos:
        matriz[humanas[i]][juez[i]] += 1
    coinciden = sum(matriz[e][e] for e in matriz)
    real = lambda e: e in ("si", "otra")  # noqa: E731
    humano_real = [i for i in validos if real(humanas[i])]
    humano_no = [i for i in validos if not real(humanas[i])]
    coinciden_real = sum(real(humanas[i]) == real(juez[i]) for i in validos)
    resultado: dict[str, Any] = {
        "comunes": len(comunes),
        "n": n,
        "dudo_humano": dudo_humano,
        "dudo_juez": dudo_juez,
        "sin_juzgar": len(set(humanas) - set(juez)),
        "sin_humano": len(set(juez) - set(humanas)),
        "coinciden": coinciden,
        "acuerdo": coinciden / n if n else None,
        "intervalo_acuerdo": intervalo_wilson(coinciden, n),
        "matriz": matriz,
        "acuerdo_dano_real": coinciden_real / n if n else None,
        "humano_no": len(humano_no),
        "humano_no_juez_no": sum(not real(juez[i]) for i in humano_no),
        "humano_no_juez_real": sum(real(juez[i]) for i in humano_no),
        "humano_real": len(humano_real),
        "humano_real_juez_no": sum(not real(juez[i]) for i in humano_real),
        "kappa": None,
        "kappa_dano_real": None,
    }
    if n:
        po = coinciden / n
        pe = sum((sum(matriz[e].values()) / n) * (sum(matriz[h][e] for h in matriz) / n) for e in matriz)
        resultado["kappa"] = _kappa(po, pe)
        ph, pj = len(humano_real) / n, sum(real(juez[i]) for i in validos) / n
        resultado["kappa_dano_real"] = _kappa(coinciden_real / n, ph * pj + (1 - ph) * (1 - pj))
    return resultado


def _pct(x: float | None) -> str:
    return "-" if x is None else f"{round(x * 100)} %"


def _dec(x: float | None) -> str:
    return "-" if x is None else f"{x:.2f}".replace(".", ",")


def formatear_acuerdo(r: dict[str, Any]) -> str:
    """El resultado en Markdown, listo para pegar en la PR o en la spec."""
    lo, hi = r["intervalo_acuerdo"]
    ic = "-" if lo is None else f"{round(lo * 100)}-{round(hi * 100)} %"
    lineas = [
        "| Medida | Valor |",
        "|---|---|",
        f"| Hallazgos con etiqueta humana y del juez | {r['comunes']} |",
        f"| Comparados (sin `dudo`) | {r['n']} |",
        f"| `dudo` del humano / del juez | {r['dudo_humano']} / {r['dudo_juez']} |",
        f"| Acuerdo exacto (`si`, `otra`, `no`) | {_pct(r['acuerdo'])} ({r['coinciden']} de {r['n']}), IC 95 % {ic} |",
        f"| Kappa de Cohen (tres etiquetas) | {_dec(r['kappa'])} |",
        f"| Acuerdo de «daño real» frente a «no» | {_pct(r['acuerdo_dano_real'])}, kappa {_dec(r['kappa_dano_real'])} |",
        f"| Humano «no» y juez «no» | {r['humano_no_juez_no']} de {r['humano_no']} |",
        f"| Humano «daño real» y juez «no» | {r['humano_real_juez_no']} de {r['humano_real']} |",
        "",
        "| humano \\ juez | si | otra | no |",
        "|---|---:|---:|---:|",
    ]
    for h in ("si", "otra", "no"):
        lineas.append(f"| {h} | " + " | ".join(str(r["matriz"][h][j]) for j in ("si", "otra", "no")) + " |")
    lineas.append("")
    lineas.append("Los `dudo` quedan fuera de la comparacion. «Daño real» cuenta `si` y `otra`. Intervalo de Wilson al 95 %.")
    return "\n".join(lineas)


def _raiz_repo() -> Path:
    return Path(__file__).resolve().parents[5]


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    raiz = _raiz_repo()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="orden", required=True)
    j = sub.add_parser("juzgar", help="etiqueta hallazgos con el modelo juez (en seco por defecto)")
    j.add_argument("--salidas", type=Path, required=True, help="carpeta con las salidas del Agente 1 y su carpeta crops/")
    j.add_argument("--todos", action="store_true", help="juzga todos los hallazgos")
    j.add_argument("--ids", type=Path, default=None, help="CSV (finding_id,etiqueta) con los hallazgos a juzgar, p. ej. las etiquetas humanas")
    j.add_argument("--limite", type=int, default=None, help="solo los N primeros del alcance (pruebas baratas)")
    j.add_argument("--modelo", help="id del modelo juez (o variable OPENAI_MODEL)")
    j.add_argument("--esfuerzo", default=None, help="esfuerzo de razonamiento (reasoning_effort), p. ej. high o xhigh")
    j.add_argument("--sin-formato-json", action="store_true", help="no envia response_format=json_object (si el modelo lo rechaza)")
    j.add_argument("--hilos", type=int, default=1, help="llamadas en paralelo")
    j.add_argument("--max-llamadas", type=int, default=300, help="tope de llamadas por pagar (proteccion de presupuesto)")
    j.add_argument("--cache-dir", type=Path, default=raiz / "piia2_detecciones" / "cache_juez")
    j.add_argument("--salida", type=Path, default=None, help="por defecto piia2_detecciones/juez/<modelo>/")
    j.add_argument("--ejecutar", action="store_true", help="hacer las llamadas de verdad (gasta presupuesto)")
    a = sub.add_parser("acuerdo", help="acuerdo entre las etiquetas humanas y las del juez")
    a.add_argument("--humanas", type=Path, required=True)
    a.add_argument("--juez", type=Path, required=True)
    return ap.parse_args(argv)


def _escribir_salidas(salida: Path, res: dict[str, Any], resumen_extra: dict[str, Any]) -> None:
    salida.mkdir(parents=True, exist_ok=True)
    filas = "".join(f"{i},{res['etiquetas'][i]}\n" for i in sorted(res["etiquetas"], key=_clave_id))
    (salida / "etiquetas_juez.csv").write_text(CABECERA_CSV + "\n" + filas, encoding="utf-8")
    (salida / "detalle_juez.json").write_text(json.dumps({i: res["detalle"][i] for i in sorted(res["detalle"], key=_clave_id)}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    resumen = {
        **resumen_extra,
        "en_alcance": res["plan"]["en_alcance"],
        "etiquetados": len(res["etiquetas"]),
        "reparto": dict(Counter(res["etiquetas"].values())),
        "fallos": res["fallos"],
        "llamadas_facturadas": res["uso"]["llamadas"],
        "desde_cache": res["uso"]["desde_cache"],
        "prompt_tokens": res["uso"]["prompt_tokens"],
        "completion_tokens": res["uso"]["completion_tokens"],
    }
    (salida / "resumen_juez.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None, crear_cliente: Callable[[], Any] | None = None) -> int:
    args = _argumentos(argv)
    try:
        if args.orden == "acuerdo":
            print(formatear_acuerdo(acuerdo(leer_etiquetas(args.humanas), leer_etiquetas(args.juez))))
            return 0
        if not args.todos and args.ids is None:
            raise EtiquetasNoValidas("indica el alcance: --todos (todos los hallazgos) o --ids <csv> (los de un CSV de etiquetas)")
        salidas = _leer_salidas(args.salidas)
        hallazgos = [{**h, "image_id": s["image_id"]} for s in salidas for h in s["findings"]]
        if args.ids is not None:
            pedidos = leer_etiquetas(args.ids)
            existentes = {h["finding_id"] for h in hallazgos}
            if set(pedidos) - existentes:
                raise EtiquetasNoValidas(f"{len(set(pedidos) - existentes)} ids de {args.ids.name} no estan en las salidas, p. ej. {sorted(set(pedidos) - existentes)[:3]}")
            hallazgos = [h for h in hallazgos if h["finding_id"] in pedidos]
        hallazgos.sort(key=lambda h: _clave_id(h["finding_id"]))
        if args.limite is not None:
            hallazgos = hallazgos[: args.limite]
        modelo = resolver_modelo(args.modelo)
        salida = args.salida or (_raiz_repo() / "piia2_detecciones" / "juez" / re.sub(r"[^A-Za-z0-9._-]", "_", modelo))
        cliente = None
        if args.ejecutar:
            cliente = (crear_cliente or crear_cliente_openai)()

        def progreso(hechos: int, total: int, res: dict[str, Any]) -> None:
            if hechos % 25 == 0 or hechos == total:
                print(f"  [{hechos}/{total}] etiquetados {len(res['etiquetas'])} | fallos {len(res['fallos'])} | llamadas facturadas {res['uso']['llamadas']}", flush=True)

        extra = {
            "modelo": modelo,
            "esfuerzo": args.esfuerzo,
            "prompt_sha256": hashlib.sha256(PROMPT_JUEZ.encode("utf-8")).hexdigest(),
            "alcance": "todos" if args.todos else f"ids de {args.ids.name}",
            "hilos": args.hilos,
            "max_llamadas": args.max_llamadas,
            "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        try:
            res = juzgar_lote(hallazgos, args.salidas, cliente, modelo, args.esfuerzo, args.cache_dir, args.max_llamadas, args.ejecutar, args.hilos, not args.sin_formato_json, progreso)
        except JuezAbortado as abortado:
            _escribir_salidas(salida, abortado.parcial, extra)
            print(f"ERROR: {abortado}. Lo parcial esta en {salida}", file=sys.stderr)
            return 2
        plan = res["plan"]
        print(f"Alcance: {plan['en_alcance']} hallazgos | en cache: {plan['en_cache']} | llamadas por pagar: {plan['por_pagar']} (tope {args.max_llamadas})")
        if not args.ejecutar:
            print("\nPLAN SOLO: no se ha llamado a la API. Anade --ejecutar para hacerlo de verdad.")
            return 0
        _escribir_salidas(salida, res, extra)
        reparto = Counter(res["etiquetas"].values())
        print(f"\nEtiquetados {len(res['etiquetas'])} de {plan['en_alcance']} | " + " | ".join(f"{e}: {reparto[e]}" for e in ETIQUETAS))
        print(f"Llamadas facturadas: {res['uso']['llamadas']} | desde cache: {res['uso']['desde_cache']} | tokens de entrada: {res['uso']['prompt_tokens']} | de salida: {res['uso']['completion_tokens']}")
        print(f"Salida: {salida}")
        if res["fallos"]:
            print(f"FALLOS: {len(res['fallos'])} hallazgos sin etiqueta (vuelve a ejecutar para reintentarlos); el primero: {res['fallos'][0]}")
            return 1
        return 0
    except LimiteDeLlamadas as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    except (EtiquetasNoValidas, OSError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
