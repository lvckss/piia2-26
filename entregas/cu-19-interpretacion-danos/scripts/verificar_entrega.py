"""Verificación de la Entrega 2 (Issue #49): AC-001, AC-002 y AC-004.

Plan vigente: https://github.com/lvckss/piia2-26/issues/49#issuecomment-6590271954

Usa solo la biblioteca estándar. Por defecto verifica la carpeta del caso que contiene
este script; `--snapshot CARPETA` verifica otra copia (por ejemplo, la rama `entrega-2`).

    python scripts/verificar_entrega.py generar   [--snapshot CARPETA]
    python scripts/verificar_entrega.py comprobar [--snapshot CARPETA] [--ac 001 002 004]

`generar` crea en `decisions/` una copia de cada ADR Aceptado de `docs/adr/` (el registro
canónico), con una nota de cabecera y los enlaces reescritos para que resuelvan desde
`decisions/`. `comprobar` sale con 1 si algún AC falla.
"""

from __future__ import annotations

import argparse
import difflib
import os
import re
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote

CASO = Path(os.path.abspath(__file__)).parents[1]

ADR_NOMBRE = re.compile(r"^\d{4}-.+\.md$")
KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
ENLACE = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
ESQUEMA = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")
VALLA = re.compile(r"^\s*(```|~~~)")
CODIGO_EN_LINEA = re.compile(r"(`[^`]*`)")


# --- lectura y enlaces ------------------------------------------------------------------

def absoluta(ruta: Path) -> Path:
    return Path(os.path.abspath(ruta))


def leer(ruta: Path) -> str:
    return ruta.read_bytes().decode("utf-8").replace("\r\n", "\n")


def escribir(ruta: Path, texto: str) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(texto.encode("utf-8"))


def separar(destino: str) -> tuple[str, str]:
    """Separa la ruta del sufijo (`#ancla` o `?consulta`)."""
    m = re.search(r"[#?]", destino)
    return (destino, "") if m is None else (destino[:m.start()], destino[m.start():])


def es_relativo(destino: str) -> bool:
    return bool(destino) and not ESQUEMA.match(destino) and not destino.startswith(("#", "/", "?"))


def recorrer(texto: str, transformar=None) -> tuple[str, list[str]]:
    """Recorre los enlaces fuera de bloques y fragmentos de código.

    Devuelve el texto (con `transformar(destino)` aplicado a cada destino, si se da) y la
    lista de destinos originales."""
    destinos: list[str] = []
    salida: list[str] = []
    en_bloque = False

    def sustituir(m: re.Match) -> str:
        destinos.append(m.group(1))
        if transformar is None:
            return m.group(0)
        antes = m.group(0)[: m.start(1) - m.start(0)]
        despues = m.group(0)[m.end(1) - m.start(0):]
        return antes + transformar(m.group(1)) + despues

    for linea in texto.split("\n"):
        if VALLA.match(linea):
            en_bloque = not en_bloque
            salida.append(linea)
        elif en_bloque:
            salida.append(linea)
        else:
            partes = CODIGO_EN_LINEA.split(linea)
            salida.append("".join(p if i % 2 else ENLACE.sub(sustituir, p) for i, p in enumerate(partes)))
    return "\n".join(salida), destinos


def objetivo(base: Path, destino: str) -> Path:
    ruta, _ = separar(destino)
    return Path(os.path.normpath(base / unquote(ruta)))


def dentro(ruta: Path, caso: Path) -> bool:
    try:
        ruta.relative_to(caso)
        return True
    except ValueError:
        return False


def existe_exacto(ruta: Path, caso: Path) -> bool:
    """Existe con las mayúsculas exactas, como en GitHub (Windows las confunde)."""
    actual = caso
    for parte in ruta.relative_to(caso).parts:
        try:
            if parte not in os.listdir(actual):
                return False
        except (FileNotFoundError, NotADirectoryError):
            return False
        actual = actual / parte
    return True


# --- ADRs y copias ---------------------------------------------------------------------

def es_aceptado(texto: str) -> bool:
    return re.search(r"^- Estado: Aceptado\b", texto, re.M) is not None


def leer_adrs(carpeta: Path, solo_aceptados: bool) -> dict[str, str]:
    if not carpeta.is_dir():
        return {}
    adrs = {p.name: leer(p) for p in sorted(carpeta.iterdir()) if p.is_file() and ADR_NOMBRE.match(p.name)}
    return {n: t for n, t in adrs.items() if es_aceptado(t)} if solo_aceptados else adrs


def nota(nombre: str) -> str:
    return (f"> **Copia de [`docs/adr/{nombre}`](../docs/adr/{nombre}).** El registro canónico de los ADRs "
            "es `docs/adr/`; esta copia está en `decisions/` porque la entrega la pide y no se edita aquí.")


def a_copia(texto: str, caso: Path, copiados: set[str]) -> str:
    """Reescribe los enlaces relativos de un ADR de `docs/adr/` para que resuelvan desde `decisions/`."""
    origen, destino = caso / "docs" / "adr", caso / "decisions"

    def reescribir(d: str) -> str:
        if not es_relativo(d) or not separar(d)[0]:
            return d
        ruta, sufijo = separar(d)
        meta = objetivo(origen, d)
        nuevo = meta.name if meta.parent == origen and meta.name in copiados else \
            PurePosixPath(Path(os.path.relpath(meta, destino)).as_posix())
        nuevo = str(nuevo)
        return (quote(nuevo, safe="/.-_~") if unquote(ruta) != ruta else nuevo) + sufijo

    return recorrer(texto, reescribir)[0]


def canonico(texto: str, base: Path, caso: Path, copiados: set[str]) -> str:
    """Sustituye cada destino relativo por el recurso al que apunta, para comparar enlaces
    por su significado y no por cómo están escritos."""
    def canon(d: str) -> str:
        if not es_relativo(d) or not separar(d)[0]:
            return d
        meta = objetivo(base, d)
        if meta.parent in (caso / "docs" / "adr", caso / "decisions") and meta.name in copiados:
            return "ADR:" + meta.name + separar(d)[1]
        return ("CASO:" + meta.relative_to(caso).as_posix() if dentro(meta, caso) else "FUERA:" + str(meta)) \
            + separar(d)[1]

    return recorrer(texto, canon)[0]


def generar(caso: Path = CASO) -> list[str]:
    """Crea en `decisions/` una copia de cada ADR Aceptado de `docs/adr/` y devuelve sus nombres."""
    caso = absoluta(caso)
    originales = leer_adrs(caso / "docs" / "adr", solo_aceptados=True)
    for nombre, texto in originales.items():
        lineas = a_copia(texto, caso, set(originales)).split("\n")
        lineas[1:1] = ["", nota(nombre)]  # tras el título; la línea en blanco original queda debajo
        escribir(caso / "decisions" / nombre, "\n".join(lineas))
    return sorted(originales)


# --- comprobaciones ---------------------------------------------------------------------

def comprobar_copias(caso: Path = CASO) -> list[str]:
    """AC-002: una copia por ADR Aceptado, idéntica al original salvo la nota y los enlaces."""
    caso = absoluta(caso)
    aceptados = leer_adrs(caso / "docs" / "adr", solo_aceptados=True)
    copias = leer_adrs(caso / "decisions", solo_aceptados=False)
    copiados = set(aceptados)
    errores = [f"falta la copia decisions/{n} del ADR Aceptado docs/adr/{n}" for n in aceptados if n not in copias]
    errores += [f"decisions/{n} no está Aceptado en docs/adr/ (o no existe allí) y no debe tener copia"
                for n in copias if n not in aceptados]
    for nombre in sorted(set(copias) & set(aceptados)):
        lineas = copias[nombre].split("\n")
        if len(lineas) < 4 or lineas[1] != "" or lineas[2] != nota(nombre):
            errores.append(f"decisions/{nombre}: falta o difiere la nota de cabecera")
            continue
        sin_nota = "\n".join(lineas[:1] + lineas[3:])
        a = canonico(aceptados[nombre], caso / "docs" / "adr", caso, copiados).split("\n")
        b = canonico(sin_nota, caso / "decisions", caso, copiados).split("\n")
        if a != b:
            n = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
            errores.append(f"decisions/{nombre}: el contenido difiere del original (línea {n + 1} del ADR)")
        if not es_aceptado(copias[nombre]):
            errores.append(f"decisions/{nombre}: no conserva «Estado: Aceptado»")
    return errores


def documentos_con_enlaces(caso: Path) -> list[Path]:
    """README, ARCHITECTURE, specs, decisions y docs de la carpeta del caso."""
    ficheros = [caso / "README.md", caso / "ARCHITECTURE.md"]
    for carpeta in ("specs", "decisions"):
        ficheros += sorted((caso / carpeta).glob("*.md")) if (caso / carpeta).is_dir() else []
    if (caso / "docs").is_dir():
        ficheros += sorted((caso / "docs").rglob("*.md"))
    return [f for f in ficheros if f.is_file()]


def comprobar_enlaces(caso: Path = CASO) -> tuple[int, int, list[str]]:
    """AC-004: todos los enlaces relativos resuelven dentro de la carpeta del caso."""
    caso = absoluta(caso)
    documentos = documentos_con_enlaces(caso)
    total, errores = 0, []
    for doc in documentos:
        rel = doc.relative_to(caso).as_posix()
        for destino in recorrer(leer(doc))[1]:
            if not es_relativo(destino) or not separar(destino)[0]:
                continue
            total += 1
            meta = objetivo(doc.parent, destino)
            if not dentro(meta, caso):
                errores.append(f"{rel}: el enlace «{destino}» sale de la carpeta del caso")
            elif not existe_exacto(meta, caso):
                errores.append(f"{rel}: el enlace «{destino}» no existe")
    return len(documentos), total, errores


def comprobar_estructura(caso: Path = CASO) -> list[str]:
    """AC-001: estructura mínima de la entrega."""
    caso = absoluta(caso)
    errores = [f"falta {n}" for n in ("README.md", "ARCHITECTURE.md") if not (caso / n).is_file()]

    def titulo(texto: str, patron: str) -> bool:
        return re.search(rf"^#{{1,4}} .*{patron}", texto, re.M | re.I) is not None

    specs = {p.name: leer(p) for p in sorted((caso / "specs").glob("*.md"))} if (caso / "specs").is_dir() else {}
    funcionales = {n: t for n, t in specs.items() if titulo(t, "Qué construir")}
    if len(funcionales) < 2:
        errores.append(f"specs/ necesita al menos 2 specs funcionales con «Qué construir» (hay {len(funcionales)})")
    for nombre, texto in funcionales.items():
        faltan = [e for e, ok in (("«Por qué»", titulo(texto, "Por qué")),
                                  ("restricciones", titulo(texto, "Restricciones")),
                                  ("criterios con ID", re.search(r"\bAC-\d{3}\b", texto) is not None)) if not ok]
        if faltan:
            errores.append(f"specs/{nombre}: falta {', '.join(faltan)}")

    adrs = {p.name: leer(p) for p in sorted((caso / "decisions").glob("*.md")) if ADR_NOMBRE.match(p.name)} \
        if (caso / "decisions").is_dir() else {}
    if len(adrs) < 2:
        errores.append(f"decisions/ necesita al menos 2 ADRs (hay {len(adrs)})")
    for nombre, texto in adrs.items():
        faltan = [e for e, ok in (("decisión", titulo(texto, "Decisión")),
                                  ("motivación", titulo(texto, "Contexto y motivación|Motivación")),
                                  ("alternativas", titulo(texto, "Alternativas")),
                                  ("referencias", titulo(texto, "Referencias"))) if not ok]
        if faltan:
            errores.append(f"decisions/{nombre}: falta {', '.join(faltan)}")

    for carpeta in ("specs", "decisions"):
        if (caso / carpeta).is_dir():
            errores += [f"{carpeta}/{p.name}: el nombre no está en kebab-case"
                        for p in sorted((caso / carpeta).glob("*.md")) if not KEBAB.match(p.name)]
    return errores


# --- línea de comandos ------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(prog="verificar_entrega.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="orden", required=True)
    for nombre in ("generar", "comprobar"):
        p = sub.add_parser(nombre)
        p.add_argument("--snapshot", type=Path, default=CASO, help="carpeta del caso a tratar")
    sub.choices["comprobar"].add_argument("--ac", nargs="+", choices=["001", "002", "004"],
                                          default=["001", "002", "004"])
    args = ap.parse_args(argv)
    caso = absoluta(args.snapshot)

    if args.orden == "generar":
        for nombre in generar(caso):
            print(f"escrita decisions/{nombre}")
        return 0

    fallos = 0
    for ac in sorted(args.ac):
        if ac == "001":
            errores, detalle = comprobar_estructura(caso), "estructura mínima"
        elif ac == "002":
            errores = comprobar_copias(caso)
            detalle = f"{len(leer_adrs(caso / 'decisions', False))} copias"
        else:
            documentos, enlaces, errores = comprobar_enlaces(caso)
            detalle = f"{enlaces} enlaces relativos en {documentos} documentos"
        print(f"AC-{ac} {'OK' if not errores else 'FALLA'} ({detalle if not errores else f'{len(errores)} errores'})")
        for e in errores:
            print(f"  - {e}")
        fallos += bool(errores)
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
