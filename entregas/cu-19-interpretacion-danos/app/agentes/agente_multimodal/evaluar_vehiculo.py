"""Validacion manual de la categoria del vehiculo (AC-011 de `specs/28-categoria-vehiculo.md`, Issue #28).

El acierto de la categoria no se puede medir contra CarDD (no tiene etiqueta de vehiculo): se valida a mano con 20
fotos elegidas con `random.Random(28).sample(sorted(ids), 20)` del export de 500 imagenes. Una persona dice la
categoria de cada foto SIN ver la respuesta del modelo; luego se compara y se calculan la coincidencia exacta, la
matriz de confusion y la tasa de la referencia «predecir siempre la categoria mas frecuente de la muestra». No se
fija umbral de aceptacion: con esa tabla una persona decide si el prompt basta o hay que ajustarlo (y entonces se
reevalua con otra muestra: otra `--semilla`).

Tres pasos; solo `consultar --ejecutar` gasta (como mucho una llamada por foto; lo ya consultado sale de la cache):

    python evaluar_vehiculo.py muestra                # gratis: copia las fotos y crea la plantilla de juicios
    python evaluar_vehiculo.py consultar              # plan: cuenta las llamadas, NO llama a la API
    python evaluar_vehiculo.py consultar --ejecutar   # las consultas de verdad (OPENAI_API_KEY y OPENAI_MODEL)
    python evaluar_vehiculo.py evaluar                # gratis: compara y escribe resultado.md

Todo lo que escribe cae bajo `piia2_detecciones/ac011_vehiculo_s<semilla>/`, que esta en `.gitignore`: las fotos
de CarDD no entran en git.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from PIL import Image

from agente1 import crear_cliente_openai, resolver_modelo
from analizar_detecciones import cargar
from evaluar_vision import ruta_foto
from generar_lote import rutas_por_defecto
from vehiculo import CATEGORIAS, DESCONOCIDO, PROMPT_VEHICULO, consultar_vehiculo

N_MUESTRA = 20
SEMILLA = 28
ORDEN_CATEGORIAS = (*CATEGORIAS, DESCONOCIDO)
COLUMNAS_PLANTILLA = ("image_id", "foto", "categoria_humana")

# Matriculas espanolas (actual: 4 cifras y 3 consonantes; provincial: letras, 4 cifras y letras) y palabras que
# apuntan a personas o propietarios. Es una red de seguridad: lo que marca lo revisa una persona.
_MATRICULA_ACTUAL = re.compile(r"\b\d{4}\s?-?\s?[B-DF-HJ-NP-TV-Z]{3}\b", re.IGNORECASE)
_MATRICULA_PROVINCIAL = re.compile(r"\b[A-Z]{1,2}\s?-?\s?\d{4}\s?-?\s?[A-Z]{1,2}\b", re.IGNORECASE)
_MENCIONA_MATRICULA = re.compile(r"\bmatr[ií]cula\b", re.IGNORECASE)
_MENCIONA_PERSONAS = re.compile(
    r"\b(persona|personas|hombre|hombres|mujer|mujeres|conductor|conductora|propietari[oa]s?|ni[nñ][oa]s?|peat[oó]n|gente)\b",
    re.IGNORECASE,
)


class JuiciosNoValidos(Exception):
    """El CSV de juicios esta incompleto o tiene categorias que no existen."""


def elegir_muestra(imagenes: list[dict[str, Any]], n: int = N_MUESTRA, semilla: int = SEMILLA) -> list[dict[str, Any]]:
    """`n` imagenes del export con `random.Random(semilla).sample(sorted(ids), n)`: reproducible y sin depender del
    orden en que llegan."""
    por_id = {i["image_id"]: i for i in imagenes}
    return [por_id[i] for i in random.Random(semilla).sample(sorted(por_id), n)]


def guia_de_categorias() -> str:
    """Las definiciones de cada categoria tal como las ve el modelo (copiadas de `PROMPT_VEHICULO`), para que la
    persona y el modelo juzguen con el mismo criterio."""
    lineas = PROMPT_VEHICULO.splitlines()
    inicio = next(i for i, linea in enumerate(lineas) if linea.startswith('- "categoria"')) + 1
    fin = next(i for i, linea in enumerate(lineas) if linea.startswith('- "confianza"'))
    return "\n".join(lineas[inicio:fin])


def _plantilla_con_juicios(ruta: Path) -> bool:
    """True si la plantilla existe y ya tiene alguna categoria escrita (no hay que pisarla)."""
    if not ruta.exists():
        return False
    try:
        return any((fila.get("categoria_humana") or "").strip() for fila in _leer_filas(ruta)[1])
    except JuiciosNoValidos:
        return True  # no sabemos leerla: mejor no tocarla


def preparar_muestra(muestra: list[dict[str, Any]], cardd_dir: Path, salida_dir: Path) -> dict[str, Any]:
    """Copia las fotos de la muestra a `<salida>/fotos/`, escribe `guia_categorias.txt` y la plantilla de juicios
    (`image_id`, `foto`, `categoria_humana` vacia; no lleva nada de la respuesta del modelo). Si la plantilla ya
    tiene juicios no la toca. Una foto que falta se anota en `faltan`."""
    salida_dir = Path(salida_dir)
    fotos = salida_dir / "fotos"
    fotos.mkdir(parents=True, exist_ok=True)
    copiadas, faltan = 0, []
    for img in muestra:
        origen = ruta_foto(Path(cardd_dir), img)
        if origen.exists():
            shutil.copy2(origen, fotos / img["image_file"])
            copiadas += 1
        else:
            faltan.append(img["image_file"])

    (salida_dir / "guia_categorias.txt").write_text(guia_de_categorias() + "\n", encoding="utf-8")
    ruta_plantilla = salida_dir / "plantilla_juicio.csv"
    conservada = _plantilla_con_juicios(ruta_plantilla)
    if not conservada:
        # `;` y BOM: asi Excel en espanol la abre en columnas y respeta las tildes
        with open(ruta_plantilla, "w", encoding="utf-8-sig", newline="") as f:
            escritor = csv.writer(f, delimiter=";")
            escritor.writerow(COLUMNAS_PLANTILLA)
            for img in sorted(muestra, key=lambda i: i["image_id"]):
                escritor.writerow([img["image_id"], img["image_file"], ""])
    return {"fotos_copiadas": copiadas, "faltan": faltan, "plantilla_conservada": conservada}


def _escribir_json(ruta: Path, datos: Any) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def consultar_muestra(
    muestra: list[dict[str, Any]],
    cardd_dir: Path,
    cliente: Any,
    modelo: str,
    cache_dir: Path,
    salida_dir: Path,
    semilla: int = SEMILLA,
) -> dict[str, Any]:
    """Una consulta de categoria por foto (`consultar_vehiculo`, la misma del Agente 1, con cache) y guarda el
    `vehiculo` de cada una en `<salida>/respuestas_modelo.json`. Una foto que falla (ausente, error del
    proveedor) se anota en `fallos` y no tira la muestra; al repetir, lo ya consultado sale de la cache."""
    uso: dict[str, int] = {}
    respuestas: dict[int, dict[str, Any]] = {}
    fallos: list[dict[str, Any]] = []
    for k, img in enumerate(muestra, start=1):
        try:
            foto = ruta_foto(Path(cardd_dir), img)
            if not foto.exists():
                raise FileNotFoundError(f"foto no encontrada: {img['image_file']}")
            with Image.open(foto) as imagen:
                imagen.load()
                respuestas[img["image_id"]] = consultar_vehiculo(cliente, modelo, imagen, cache_dir=cache_dir, uso=uso)
        except Exception as error:  # una foto que falla no tira la muestra
            fallos.append({"image_id": img["image_id"], "image_file": img["image_file"], "motivo": f"{type(error).__name__}: {error}"})
            print(f"  [{k}/{len(muestra)}] imagen {img['image_id']}: FALLO - {type(error).__name__}: {error}", flush=True)
            continue
        # no se imprime la categoria: la persona debe juzgar sin verla
        print(f"  [{k}/{len(muestra)}] imagen {img['image_id']}: consultada (llamadas facturadas hasta ahora: {uso.get('llamadas', 0)})", flush=True)

    _escribir_json(
        Path(salida_dir) / "respuestas_modelo.json",
        {
            "modelo": modelo,
            "semilla": semilla,
            "n": len(muestra),
            "respuestas": {str(i): respuestas[i] for i in sorted(respuestas)},
            "fallos": fallos,
        },
    )
    return {
        "consultadas": len(respuestas),
        "llamadas_facturadas": uso.get("llamadas", 0),
        "tokens_entrada": uso.get("prompt_tokens", 0),
        "tokens_salida": uso.get("completion_tokens", 0),
        "fallos": fallos,
    }


def _leer_filas(ruta_csv: Path) -> tuple[list[str], list[dict[str, str]]]:
    texto = Path(ruta_csv).read_text(encoding="utf-8-sig")
    primera = next(iter(texto.splitlines()), "")
    delimitador = ";" if primera.count(";") >= primera.count(",") else ","  # Excel en espanol guarda con `;`
    lector = csv.DictReader(texto.splitlines(), delimiter=delimitador)
    columnas = lector.fieldnames or []
    faltan = [c for c in ("image_id", "categoria_humana") if c not in columnas]
    if faltan:
        raise JuiciosNoValidos(f"A la plantilla le faltan las columnas {faltan} (cabecera: {columnas}).")
    return columnas, [f for f in lector if (f.get("image_id") or "").strip()]


def leer_juicios(ruta_csv: Path) -> dict[int, str]:
    """Lee la plantilla rellenada (`;` o `,`, con o sin BOM). Devuelve {image_id: categoria} con la categoria en su
    forma canonica (`suv-c` -> `SUV-C`). Si falta algun juicio o una categoria no existe, lanza `JuiciosNoValidos`
    diciendo cuales."""
    _, filas = _leer_filas(ruta_csv)
    canonica = {c.lower(): c for c in ORDEN_CATEGORIAS}
    juicios: dict[int, str] = {}
    vacios: list[str] = []
    invalidos: list[str] = []
    for fila in filas:
        identificador = fila["image_id"].strip()
        valor = (fila.get("categoria_humana") or "").strip()
        if not valor:
            vacios.append(identificador)
        elif valor.lower() not in canonica:
            invalidos.append(f"{identificador} -> {valor!r}")
        else:
            try:
                juicios[int(identificador)] = canonica[valor.lower()]
            except ValueError:
                invalidos.append(f"{identificador!r} no es un image_id")
    errores = []
    if vacios:
        errores.append(f"Sin rellenar (categoria_humana) en las imagenes: {', '.join(vacios)}.")
    if invalidos:
        errores.append(f"Categoria no valida: {'; '.join(invalidos)}. Validas: {', '.join(ORDEN_CATEGORIAS)}.")
    if errores:
        raise JuiciosNoValidos(" ".join(errores))
    return juicios


def datos_sospechosos(descripcion: str) -> list[str]:
    """Motivos por los que una descripcion parece llevar una matricula o datos personales (lista vacia si no).
    Es una red de seguridad automatica; la comprobacion de AC-011 la hace una persona leyendo la tabla."""
    motivos = []
    for patron in (_MATRICULA_ACTUAL, _MATRICULA_PROVINCIAL):
        encontrada = patron.search(descripcion)
        if encontrada:
            motivos.append(f"posible matricula ({encontrada.group(0).strip()})")
    if _MENCIONA_MATRICULA.search(descripcion):
        motivos.append("menciona la matricula")
    encontrada = _MENCIONA_PERSONAS.search(descripcion)
    if encontrada:
        motivos.append(f"menciona personas ({encontrada.group(0)})")
    return motivos


def evaluar(respuestas: dict[int, dict[str, Any]], juicios: dict[int, str]) -> dict[str, Any]:
    """Compara la categoria del modelo con el juicio de la persona. Devuelve la tabla por imagen, la coincidencia
    exacta, la matriz de confusion (juicio humano -> categoria estimada), la tasa de predecir siempre la categoria
    mas frecuente de la muestra y las descripciones que conviene revisar."""
    if set(respuestas) != set(juicios):
        sin_respuesta = sorted(set(juicios) - set(respuestas))
        sin_juicio = sorted(set(respuestas) - set(juicios))
        raise ValueError(
            f"Las respuestas del modelo y los juicios no son de las mismas fotos. Sin respuesta del modelo: {sin_respuesta}; "
            f"sin juicio de la persona: {sin_juicio}."
        )
    filas = [
        {
            "image_id": i,
            "humano": juicios[i],
            "modelo": respuestas[i]["categoria"],
            "confianza": respuestas[i].get("confianza", ""),
            "descripcion": respuestas[i].get("descripcion", ""),
            "coincide": respuestas[i]["categoria"] == juicios[i],
        }
        for i in sorted(juicios)
    ]
    n = len(filas)
    aciertos = sum(f["coincide"] for f in filas)
    matriz: dict[str, dict[str, int]] = {}
    for f in filas:
        matriz.setdefault(f["humano"], {}).setdefault(f["modelo"], 0)
        matriz[f["humano"]][f["modelo"]] += 1

    por_categoria = Counter(f["humano"] for f in filas)
    maximo = max(por_categoria.values())
    empatadas = [c for c in ORDEN_CATEGORIAS if por_categoria[c] == maximo]
    sospechosas = [
        {"image_id": f["image_id"], "motivos": datos_sospechosos(f["descripcion"]), "descripcion": f["descripcion"]}
        for f in filas
        if datos_sospechosos(f["descripcion"])
    ]
    return {
        "n": n,
        "aciertos": aciertos,
        "tasa": aciertos / n,
        "filas": filas,
        "matriz": matriz,
        "referencia": {
            "categoria": empatadas[0],
            "aciertos": maximo,
            "tasa": maximo / n,
            "empate": empatadas if len(empatadas) > 1 else [],
        },
        "error_en_puntos": 100 / n,
        "sospechosas": sospechosas,
    }


def _porcentaje(x: float) -> str:
    return f"{x * 100:.1f}".replace(".", ",") + " %"


def _celda(texto: str) -> str:
    return str(texto).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def informe_markdown(resultado: dict[str, Any], modelo: str, semilla: int) -> str:
    """El resultado en el formato de la tabla de la PR de entrega (con `image_id`, sin fotos)."""
    n, referencia = resultado["n"], resultado["referencia"]
    lineas = [
        "## Validación manual de la categoría del vehículo (AC-011)",
        "",
        f"- **Modelo:** `{modelo}`.",
        f"- **Muestra:** {n} fotos de `baseline_500`, `random.Random({semilla}).sample(sorted(ids), {n})`. "
        "Una persona juzgó la categoría de cada foto sin ver la respuesta del modelo.",
        f"- **Coincidencia exacta:** {resultado['aciertos']} de {n} ({_porcentaje(resultado['tasa'])}).",
        f"- **Referencia, predecir siempre la categoría más frecuente de la muestra (`{referencia['categoria']}`):** "
        f"{referencia['aciertos']} de {n} ({_porcentaje(referencia['tasa'])}).",
    ]
    if referencia["empate"]:
        lineas.append(
            f"  - Hay empate entre {', '.join(f'`{c}`' for c in referencia['empate'])}; la tasa es la misma con cualquiera."
        )
    lineas += [
        f"- **Límite:** con {n} fotos un error son {resultado['error_en_puntos']:g} puntos; la muestra no permite "
        "afinar por categoría. No se fija umbral de aceptación: con esta tabla una persona decide si el prompt basta "
        "o se ajusta (y entonces se reevalúa con otra muestra).",
        "",
        "### Tabla por imagen",
        "",
        "| image_id | Categoría estimada | Confianza | Categoría humana | ¿Coincide? | Descripción del modelo |",
        "|---|---|---|---|---|---|",
    ]
    for f in resultado["filas"]:
        lineas.append(
            f"| {f['image_id']} | `{f['modelo']}` | {f['confianza']} | `{f['humano']}` | "
            f"{'sí' if f['coincide'] else '**no**'} | {_celda(f['descripcion'])} |"
        )

    vistas = [c for c in ORDEN_CATEGORIAS if c in resultado["matriz"] or any(c in fila for fila in resultado["matriz"].values())]
    lineas += [
        "",
        "### Matriz de confusión (filas: juicio de la persona; columnas: categoría estimada)",
        "",
        "| humano \\ modelo | " + " | ".join(f"`{c}`" for c in vistas) + " | Total |",
        "|---|" + "---|" * (len(vistas) + 1),
    ]
    for humano in vistas:
        fila = resultado["matriz"].get(humano, {})
        lineas.append(f"| `{humano}` | " + " | ".join(str(fila.get(c, 0)) if fila.get(c, 0) else "·" for c in vistas) + f" | {sum(fila.values())} |")

    lineas += ["", "### Descripciones a revisar", ""]
    if resultado["sospechosas"]:
        lineas.append("La revisión automática marca estas descripciones; una persona debe leerlas:")
        lineas += [f"- Imagen {s['image_id']} ({'; '.join(s['motivos'])}): «{_celda(s['descripcion'])}»" for s in resultado["sospechosas"]]
    else:
        lineas.append("Ninguna descripción parece contener una matrícula ni datos personales (revisión automática).")
    lineas += [
        "",
        "- [ ] Revisión manual hecha: ninguna descripción de la tabla contiene datos personales ni una matrícula legible.",
        "",
    ]
    return "\n".join(lineas)


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    rutas = rutas_por_defecto()
    comun = argparse.ArgumentParser(add_help=False)
    comun.add_argument("--detecciones", type=Path, default=rutas["detecciones"])
    comun.add_argument("--cardd", type=Path, default=rutas["cardd"])
    comun.add_argument("--salida", type=Path, help="por defecto piia2_detecciones/ac011_vehiculo_s<semilla>")
    comun.add_argument("--n", type=int, default=N_MUESTRA, help="fotos de la muestra (AC-011 pide 20)")
    comun.add_argument("--semilla", type=int, default=SEMILLA, help="otra semilla = otra muestra (para reevaluar tras ajustar el prompt)")

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="orden", required=True)
    sub.add_parser("muestra", parents=[comun], help="copia las fotos y crea la plantilla de juicios (gratis)")
    consultar = sub.add_parser("consultar", parents=[comun], help="una consulta de categoria por foto (plan, o gasto con --ejecutar)")
    consultar.add_argument("--cache-dir", type=Path, default=rutas["cache"])
    consultar.add_argument("--modelo", help="id del modelo (o variable OPENAI_MODEL)")
    consultar.add_argument("--ejecutar", action="store_true", help="hacer las llamadas de verdad (gasta presupuesto)")
    sub.add_parser("evaluar", parents=[comun], help="compara con los juicios y escribe resultado.md (gratis)")
    args = ap.parse_args(argv)
    if args.salida is None:
        args.salida = rutas["salida"].parent / f"ac011_vehiculo_s{args.semilla}"
    return args


def _orden_muestra(args: argparse.Namespace) -> int:
    imagenes = cargar(args.detecciones)
    muestra = elegir_muestra(imagenes, args.n, args.semilla)
    resumen = preparar_muestra(muestra, args.cardd, args.salida)
    print(f"{len(muestra)} fotos elegidas (semilla {args.semilla}) de {len(imagenes)} imagenes del export.")
    print(f"Fotos copiadas a {args.salida / 'fotos'}: {resumen['fotos_copiadas']} | que faltan: {len(resumen['faltan'])}")
    if resumen["faltan"]:
        print("AVISO: faltan fotos:", resumen["faltan"][:5], "..." if len(resumen["faltan"]) > 5 else "")
    if resumen["plantilla_conservada"]:
        print(f"La plantilla {args.salida / 'plantilla_juicio.csv'} ya tiene juicios: NO se ha tocado.")
    else:
        print(f"Plantilla creada: {args.salida / 'plantilla_juicio.csv'}")
    print(
        "\nPara cada foto, escribe en la columna categoria_humana UNA de: "
        + ", ".join(ORDEN_CATEGORIAS)
        + f" (definiciones en {args.salida / 'guia_categorias.txt'}).\n"
        "Juzga SIN ver la respuesta del modelo: no abras respuestas_modelo.json hasta terminar."
    )
    return 1 if resumen["faltan"] else 0


def _orden_consultar(args: argparse.Namespace, crear_cliente: Callable[[], Any] | None) -> int:
    imagenes = cargar(args.detecciones)
    muestra = elegir_muestra(imagenes, args.n, args.semilla)
    faltan = [i["image_file"] for i in muestra if not ruta_foto(args.cardd, i).exists()]
    print(f"{len(muestra)} fotos elegidas (semilla {args.semilla}) | Fotos locales que faltan: {len(faltan)}")
    print(f"Llamadas previstas: hasta {len(muestra)} (una de categoria del vehiculo por foto; lo que ya este en la cache no se factura)")
    if faltan:
        print("AVISO: faltan fotos:", faltan[:5], "..." if len(faltan) > 5 else "")
    if not args.ejecutar:
        print("\nPLAN SOLO: no se ha llamado a la API. Anade --ejecutar para hacerlo de verdad.")
        return 0

    try:
        modelo = resolver_modelo(args.modelo)
        cliente = (crear_cliente or crear_cliente_openai)()
    except (RuntimeError, FileNotFoundError) as error:
        print(f"ERROR: {error}")
        return 2
    print(f"\nEjecutando con {modelo}: una linea por foto (no se muestra la categoria, para juzgar a ciegas)", flush=True)
    resumen = consultar_muestra(muestra, args.cardd, cliente, modelo, args.cache_dir, args.salida, args.semilla)
    print(
        f"\nConsultadas: {resumen['consultadas']} de {len(muestra)} | Llamadas facturadas: {resumen['llamadas_facturadas']} | "
        f"Tokens de entrada: {resumen['tokens_entrada']} | de salida: {resumen['tokens_salida']}"
    )
    print(f"Respuestas guardadas en {args.salida / 'respuestas_modelo.json'}. NO lo abras hasta haber rellenado la plantilla de juicios.")
    if resumen["fallos"]:
        print(f"\nFALLOS: {len(resumen['fallos'])} fotos sin respuesta. Vuelve a ejecutar: lo ya consultado sale de la cache y no se factura.")
        for fallo in resumen["fallos"]:
            print(f"  imagen {fallo['image_id']} ({fallo['image_file']}): {fallo['motivo']}")
        return 1
    return 0


def _orden_evaluar(args: argparse.Namespace) -> int:
    ruta_respuestas, ruta_plantilla = args.salida / "respuestas_modelo.json", args.salida / "plantilla_juicio.csv"
    for ruta, paso in ((ruta_respuestas, "consultar --ejecutar"), (ruta_plantilla, "muestra")):
        if not ruta.exists():
            print(f"ERROR: falta {ruta}. Ejecuta antes `evaluar_vehiculo.py {paso}`.")
            return 2
    datos = json.loads(ruta_respuestas.read_text(encoding="utf-8"))
    if datos["fallos"]:
        print(f"ERROR: la consulta quedo incompleta ({len(datos['fallos'])} fotos sin respuesta). Repite `consultar --ejecutar`.")
        return 2
    try:
        juicios = leer_juicios(ruta_plantilla)
        resultado = evaluar({int(i): v for i, v in datos["respuestas"].items()}, juicios)
    except (JuiciosNoValidos, ValueError) as error:
        print(f"ERROR: {error}")
        return 2
    informe = informe_markdown(resultado, datos["modelo"], datos.get("semilla", args.semilla))
    (args.salida / "resultado.md").write_text(informe, encoding="utf-8")
    print(informe)
    print(f"Informe guardado en {args.salida / 'resultado.md'}")
    return 0


def main(argv: list[str] | None = None, crear_cliente: Callable[[], Any] | None = None) -> int:
    """Devuelve el codigo de salida: 0 si todo fue bien, distinto de 0 si no."""
    args = _argumentos(argv)
    if args.orden == "muestra":
        return _orden_muestra(args)
    if args.orden == "consultar":
        return _orden_consultar(args, crear_cliente)
    return _orden_evaluar(args)


if __name__ == "__main__":
    raise SystemExit(main())
