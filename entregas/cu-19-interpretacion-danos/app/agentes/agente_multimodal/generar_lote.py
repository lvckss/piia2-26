"""Genera la salida real del Agente 1 para un lote reproducible de imagenes de
CarDD (Issue #43). Elige las imagenes del export de PIIA-1, ejecuta
`agente1.analizar_imagen` sobre cada una con cache y guarda un JSON por imagen.

POR DEFECTO NO LLAMA A LA API: solo planifica (cuantas llamadas haria). Para
ejecutarlo de verdad hay que anadir `--ejecutar` (y tener OPENAI_API_KEY y
OPENAI_MODEL en el entorno).

    python generar_lote.py                       # plan, no gasta nada
    python generar_lote.py --n-imagenes 3 --min-aciertos 1 --ejecutar   # prueba barata
    python generar_lote.py --ejecutar            # el lote completo (30 imagenes)
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from agente1 import analizar_imagen, crear_cliente_openai, resolver_modelo
from analizar_detecciones import CLASES, cargar
from catalogo import cargar_catalogo
from confianza import decidir_tier
from evaluar_vision import elegir_imagenes, ruta_foto
from seleccion import seleccionar_candidatos
from vision import SEVERIDADES, VEREDICTOS


def _raiz_repo() -> Path:
    return Path(__file__).resolve().parents[5]


def elegir_lote(imagenes: list[dict[str, Any]], n: int, min_aciertos: int, seed: int) -> list[dict[str, Any]]:
    """Elige `n` imagenes del export con al menos `min_aciertos` aciertos de
    PIIA-1 por clase entre sus candidatas. Determinista."""
    elegidas, _ = elegir_imagenes(imagenes, n, min_aciertos, seed)
    return elegidas


def fotos_que_faltan(imagenes: list[dict[str, Any]], cardd_dir: Path) -> list[str]:
    """Nombres de las fotos del lote que no estan en el CarDD local."""
    return [i["image_file"] for i in imagenes if not ruta_foto(cardd_dir, i).exists()]


def llamadas_previstas(imagenes: list[dict[str, Any]]) -> int:
    """Una llamada al modelo por cada hallazgo candidato (tras el filtro previo)."""
    return sum(len(seleccionar_candidatos(i["predictions"])[0]) for i in imagenes)


class FotoNoEncontrada(Exception):
    """La foto local de CarDD de una imagen del lote no esta en disco."""


class SalidaNoValida(Exception):
    """La salida del Agente 1 de una imagen no cumple el contrato."""


class ClienteContador:
    """Envuelve un cliente de OpenAI (o uno falso) y suma el uso de lo que de
    verdad le llega: las respuestas servidas desde la cache de `vision.py` no
    pasan por aqui, asi que no cuentan. No toca el codigo del Agente 1."""

    def __init__(self, cliente: Any) -> None:
        self._cliente = cliente
        self.llamadas = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.chat = self
        self.completions = self

    def create(self, **peticion: Any) -> Any:
        inicio = time.time()
        respuesta = self._cliente.chat.completions.create(**peticion)
        uso = getattr(respuesta, "usage", None)
        entrada = int(getattr(uso, "prompt_tokens", 0) or 0)
        salida = int(getattr(uso, "completion_tokens", 0) or 0)
        self.llamadas += 1
        self.prompt_tokens += entrada
        self.completion_tokens += salida
        # una linea por llamada facturada, para ver que va avanzando
        print(
            f"    llamada {self.llamadas} ({time.time() - inicio:.1f} s): "
            f"{entrada} tokens de entrada, {salida} de salida",
            flush=True,
        )
        return respuesta


CAMPOS_SALIDA = frozenset({"image_id", "resumen_filtro_previo", "findings"})
# los 13 campos de un finding del contrato Agente 1 -> Agente 2/3
CAMPOS_FINDING = frozenset({
    "finding_id", "category", "clase_tool", "score", "score_tier", "confidence_tier", "bbox_xywh",
    "vision_verdict", "pieza_id", "severidad", "regla_coste_aplicable", "vision_description", "crop_image_path",
})
TIERS = ("confirmed", "needs_review")
AVISO_MUESTRA = (
    "El lote se eligio para cubrir las 6 clases con aciertos de PIIA-1 (usa `is_true_positive`), "
    "asi que no es representativo de la distribucion real: no extrapoles estos repartos."
)


def _campos_distintos(nombre: str, datos: dict[str, Any], esperados: frozenset[str]) -> list[str]:
    errores = []
    if esperados - datos.keys():
        errores.append(f"{nombre}: faltan campos {sorted(esperados - datos.keys())}")
    if datos.keys() - esperados:
        errores.append(f"{nombre}: sobran campos {sorted(datos.keys() - esperados)}")
    return errores


def _errores_de_finding(finding: dict[str, Any], catalogo: Any, carpeta_recortes: Path | None) -> list[str]:
    nombre = f"finding {finding.get('finding_id', '?')}"
    errores = _campos_distintos(nombre, finding, CAMPOS_FINDING)

    veredicto = finding.get("vision_verdict")
    if veredicto not in VEREDICTOS:
        errores.append(f"{nombre}: vision_verdict={veredicto!r} fuera de {list(VEREDICTOS)}")
    severidad = finding.get("severidad")
    if severidad is not None and severidad not in SEVERIDADES:
        errores.append(f"{nombre}: severidad={severidad!r} fuera de {list(SEVERIDADES)} y null")
    pieza = finding.get("pieza_id")
    if pieza is not None and pieza not in catalogo.piezas:
        errores.append(f"{nombre}: pieza_id={pieza!r} no esta en el catalogo")
    if finding.get("regla_coste_aplicable") not in (True, False, None):
        errores.append(f"{nombre}: regla_coste_aplicable={finding.get('regla_coste_aplicable')!r} no es booleano ni null")
    if veredicto == "rechazado":
        for campo in ("pieza_id", "severidad", "regla_coste_aplicable"):
            if finding.get(campo) is not None:
                errores.append(f"{nombre}: veredicto 'rechazado' pero {campo}={finding[campo]!r} (debe ser null)")

    tier = finding.get("confidence_tier")
    if tier not in TIERS:
        errores.append(f"{nombre}: confidence_tier={tier!r} fuera de {list(TIERS)}")
    elif CAMPOS_FINDING <= finding.keys():
        esperado = decidir_tier(
            finding["category"], finding["score"], veredicto, pieza, finding["regla_coste_aplicable"]
        )
        if tier != esperado:
            errores.append(f"{nombre}: confidence_tier={tier!r} no coincide con el que sale de decidir_tier ({esperado!r})")

    if carpeta_recortes is not None and finding.get("crop_image_path"):
        if not (Path(carpeta_recortes) / finding["crop_image_path"]).exists():
            errores.append(f"{nombre}: crop_image_path={finding['crop_image_path']!r} no existe")
    return errores


def validar_salida_agente1(
    salida: dict[str, Any],
    catalogo: Any,
    nombre_fichero: str | None = None,
    carpeta_recortes: Path | None = None,
) -> list[str]:
    """Comprueba que `salida` cumple el contrato Agente 1 -> Agente 2/3
    (`specs/piia2-arquitectura-multiagente.md`). Devuelve la lista de errores
    (vacia si es valida). `nombre_fichero` comprueba que el `image_id` coincide
    con el nombre del fichero; `carpeta_recortes` que cada recorte existe."""
    if not isinstance(salida, dict):
        return ["la salida no es un objeto JSON"]
    errores = _campos_distintos("salida", salida, CAMPOS_SALIDA)

    if nombre_fichero is not None and "image_id" in salida:
        try:
            if int(Path(nombre_fichero).stem) != salida["image_id"]:
                errores.append(f"image_id={salida['image_id']!r} no coincide con el nombre del fichero {nombre_fichero}")
        except ValueError:
            errores.append(f"el nombre del fichero {nombre_fichero} no es un image_id")

    findings = salida.get("findings")
    resumen = salida.get("resumen_filtro_previo")
    if isinstance(findings, list) and isinstance(resumen, dict) and "candidatas" in resumen:
        if resumen["candidatas"] != len(findings):
            errores.append(
                f"resumen_filtro_previo.candidatas={resumen['candidatas']!r} pero hay {len(findings)} findings"
            )
    for finding in findings if isinstance(findings, list) else []:
        errores.extend(_errores_de_finding(finding, catalogo, carpeta_recortes))
    return errores


def _escribir_json(ruta: Path, datos: Any) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(datos, ensure_ascii=False, indent=2))


def _recortes_relativos(salida_agente1: dict[str, Any], salida_dir: Path) -> None:
    """`crop_image_path` se guarda relativo a la carpeta de salida, para que el
    JSON no lleve rutas de esta maquina."""
    for finding in salida_agente1["findings"]:
        finding["crop_image_path"] = Path(finding["crop_image_path"]).relative_to(salida_dir).as_posix()


def generar_lote(
    lote: list[dict[str, Any]],
    detecciones_dir: Path,
    cardd_dir: Path,
    salida_dir: Path,
    cliente: Any,
    modelo: str,
    catalogo: Any,
    cache_dir: Path,
    precios: tuple[float, float] | None = None,
    validar: Callable[..., list[str]] = validar_salida_agente1,
) -> dict[str, Any]:
    """Ejecuta el Agente 1 sobre cada imagen del lote y guarda
    `<salida>/<image_id:06d>.json` (como el export) y `<salida>/resumen_lote.json`.
    `precios` = (entrada, salida) en euros por millon de tokens; sin ellos no
    se calcula coste. Devuelve el resumen."""
    detecciones_dir, cardd_dir, salida_dir = Path(detecciones_dir), Path(cardd_dir), Path(salida_dir)
    salida_dir.mkdir(parents=True, exist_ok=True)
    contador = ClienteContador(cliente)
    inicio = time.time()
    hallazgos = 0
    fallos: list[dict[str, Any]] = []
    por_clase: dict[str, Counter] = {clase: Counter() for clase in CLASES}
    reparto_tier: Counter = Counter({tier: 0 for tier in TIERS})
    reparto_veredicto: Counter = Counter({veredicto: 0 for veredicto in VEREDICTOS})
    descartados = 0

    for k, img in enumerate(lote, start=1):
        nombre = f"{img['image_id']:06d}.json"
        try:
            foto = ruta_foto(cardd_dir, img)
            if not foto.exists():
                raise FotoNoEncontrada(f"foto no encontrada: {img['image_file']}")
            resultado = analizar_imagen(
                detecciones_dir / f"{Path(img['image_file']).stem}.json",
                contador,
                salida_dir / "crops",
                modelo=modelo,
                image_path=foto,
                catalogo=catalogo,
                cache_dir=cache_dir,
            )
            _recortes_relativos(resultado, salida_dir)
            errores = validar(resultado, catalogo, nombre, salida_dir)
            if errores:
                raise SalidaNoValida("salida no valida segun el validador: " + "; ".join(errores[:3]))
        except Exception as error:  # una imagen que falla no tira el lote
            motivo = str(error) if isinstance(error, (FotoNoEncontrada, SalidaNoValida)) else f"{type(error).__name__}: {error}"
            fallos.append({"image_id": img["image_id"], "image_file": img["image_file"], "motivo": motivo})
            print(f"  [{k}/{len(lote)}] imagen {img['image_id']}: FALLO - {motivo}", flush=True)
            continue

        _escribir_json(salida_dir / nombre, resultado)
        hallazgos += len(resultado["findings"])
        descartados += sum(resultado["resumen_filtro_previo"]["descartadas_por_clase"].values())
        for finding in resultado["findings"]:
            tier, veredicto = finding["confidence_tier"], finding["vision_verdict"]
            reparto_tier[tier] += 1
            reparto_veredicto[veredicto] += 1
            clase = por_clase.setdefault(finding["category"], Counter())
            clase["hallazgos"] += 1
            clase[tier] += 1
            clase[veredicto] += 1
        print(
            f"  [{k}/{len(lote)}] imagen {img['image_id']}: {len(resultado['findings'])} hallazgos "
            f"(llamadas facturadas hasta ahora: {contador.llamadas})",
            flush=True,
        )

    if precios is None:
        coste, nota = None, "sin precios: pasa --precio-entrada y --precio-salida (euros por millon de tokens)"
    else:
        coste = (contador.prompt_tokens * precios[0] + contador.completion_tokens * precios[1]) / 1_000_000
        nota = f"calculado con {precios[0]} (entrada) y {precios[1]} (salida) euros por millon de tokens"
    columnas = ("hallazgos", *TIERS, *VEREDICTOS)
    resumen = {
        "modelo": modelo,
        "imagenes": len(lote),
        "imagenes_ok": len(lote) - len(fallos),
        "fallos": fallos,
        "hallazgos": hallazgos,
        "llamadas_facturadas": contador.llamadas,
        "hallazgos_desde_cache": hallazgos - contador.llamadas,
        "tokens_entrada": contador.prompt_tokens,
        "tokens_salida": contador.completion_tokens,
        "coste_eur": coste,
        "coste_nota": nota,
        "reparto_tier": dict(reparto_tier),
        "reparto_veredicto": dict(reparto_veredicto),
        "por_clase": {clase: {c: cuenta[c] for c in columnas} for clase, cuenta in por_clase.items()},
        "descartados_por_filtro_previo": descartados,
        "aviso_muestra": AVISO_MUESTRA,
        "duracion_s": round(time.time() - inicio, 1),
    }
    _escribir_json(salida_dir / "resumen_lote.json", resumen)
    return resumen


def rutas_por_defecto() -> dict[str, Path]:
    """Donde se lee y se escribe si no se indica otra cosa. Lo que se escribe
    (salidas, recortes, resumen y cache) cae bajo `piia2_detecciones/`, que esta
    en `.gitignore`: ni las fotos y recortes de CarDD ni la cache entran en git."""
    raiz = _raiz_repo()
    return {
        "detecciones": raiz / "piia2_detecciones" / "baseline_500",
        "cardd": raiz / "CarDD_release" / "CarDD_COCO",
        "salida": raiz / "piia2_detecciones" / "salida_agente1",
        "cache": raiz / "piia2_detecciones" / "cache_vision",
    }


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    rutas = rutas_por_defecto()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--detecciones", type=Path, default=rutas["detecciones"])
    ap.add_argument("--cardd", type=Path, default=rutas["cardd"])
    ap.add_argument("--salida", type=Path, default=rutas["salida"])
    ap.add_argument("--cache-dir", type=Path, default=rutas["cache"])
    ap.add_argument("--n-imagenes", type=int, default=30)
    ap.add_argument("--min-aciertos", type=int, default=3, help="aciertos minimos de PIIA-1 por clase en el lote")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--max-llamadas", type=int, default=300, help="tope de llamadas (proteccion de presupuesto)")
    ap.add_argument("--modelo", help="id del modelo (o variable OPENAI_MODEL)")
    ap.add_argument("--precio-entrada", type=float, help="euros por millon de tokens de entrada (opcional)")
    ap.add_argument("--precio-salida", type=float, help="euros por millon de tokens de salida (opcional)")
    ap.add_argument("--ejecutar", action="store_true", help="hacer las llamadas de verdad (gasta presupuesto)")
    return ap.parse_args(argv)


def _imprimir_resumen(resumen: dict[str, Any], salida_dir: Path) -> None:
    print(f"\nResumen del lote (modelo {resumen['modelo']}, {resumen['duracion_s']} s)")
    print(f"  Imagenes: {resumen['imagenes']} | Hallazgos: {resumen['hallazgos']}")
    print(
        f"  Llamadas facturadas: {resumen['llamadas_facturadas']} | "
        f"Hallazgos servidos desde cache: {resumen['hallazgos_desde_cache']}"
    )
    print(f"  Tokens de entrada: {resumen['tokens_entrada']} | de salida: {resumen['tokens_salida']}")
    if resumen["coste_eur"] is None:
        print(f"  Coste: {resumen['coste_nota']}")
    else:
        print(f"  Coste: {resumen['coste_eur']:.4f} EUR ({resumen['coste_nota']})")
    print("\nReparto de los hallazgos")
    print("  Nivel de confianza: " + " | ".join(f"{k}: {v}" for k, v in resumen["reparto_tier"].items()))
    print("  Veredicto de la vision: " + " | ".join(f"{k}: {v}" for k, v in resumen["reparto_veredicto"].items()))
    print(f"  {'clase':14s} {'hallaz.':>7s} {'confirmed':>9s} {'needs_rev':>9s} {'confirm.':>8s} {'rechaz.':>7s} {'incier.':>7s}")
    for clase, c in resumen["por_clase"].items():
        print(
            f"  {clase:14s} {c['hallazgos']:>7d} {c['confirmed']:>9d} {c['needs_review']:>9d} "
            f"{c['confirmado']:>8d} {c['rechazado']:>7d} {c['incierto']:>7d}"
        )
    print(f"  Descartados por el filtro previo: {resumen['descartados_por_filtro_previo']}")
    print(f"  AVISO: {resumen['aviso_muestra']}")
    if resumen["fallos"]:
        print(f"\nFALLOS: {len(resumen['fallos'])} de {resumen['imagenes']} imagenes sin salida")
        for fallo in resumen["fallos"]:
            print(f"  imagen {fallo['image_id']} ({fallo['image_file']}): {fallo['motivo']}")
        print("  Corrige la causa y vuelve a ejecutar: lo ya consultado sale de la cache y no se factura.")
    print(f"\n  Resumen guardado en {salida_dir / 'resumen_lote.json'}")


def main(
    argv: list[str] | None = None,
    crear_cliente: Callable[[], Any] | None = None,
    catalogo: Any = None,
) -> int:
    """Devuelve el codigo de salida: 0 si todo fue bien, distinto de 0 si no."""
    args = _argumentos(argv)
    imagenes = cargar(args.detecciones)
    lote = elegir_lote(imagenes, args.n_imagenes, args.min_aciertos, args.seed)
    llamadas = llamadas_previstas(lote)
    faltan = fotos_que_faltan(lote, args.cardd)

    print(f"{len(lote)} imagenes elegidas (semilla {args.seed}) | Fotos locales que faltan: {len(faltan)}")
    print(f"Llamadas previstas: {llamadas}")
    if faltan:
        print("AVISO: faltan fotos:", faltan[:5], "..." if len(faltan) > 5 else "")

    if not args.ejecutar:
        print("\nPLAN SOLO: no se ha llamado a la API. Anade --ejecutar para hacerlo de verdad.")
        return 0
    if llamadas > args.max_llamadas:
        print(
            f"{llamadas} llamadas previstas superan --max-llamadas={args.max_llamadas}. "
            "Reduce --n-imagenes o sube el tope a conciencia."
        )
        return 2
    if (args.precio_entrada is None) != (args.precio_salida is None):
        print("Pasa los dos precios (--precio-entrada y --precio-salida) o ninguno.")
        return 2

    try:
        modelo = resolver_modelo(args.modelo)
        catalogo = catalogo or cargar_catalogo()
        cliente = (crear_cliente or crear_cliente_openai)()
    except (RuntimeError, FileNotFoundError) as error:
        print(f"ERROR: {error}")
        return 2

    precios = None if args.precio_entrada is None else (args.precio_entrada, args.precio_salida)
    print(f"\nEjecutando con {modelo}: una linea por imagen (lo servido desde cache no se factura)", flush=True)
    resumen = generar_lote(lote, args.detecciones, args.cardd, args.salida, cliente, modelo, catalogo, args.cache_dir, precios)
    _imprimir_resumen(resumen, args.salida)
    return 1 if resumen["fallos"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
