"""Download a verified CARDD archive without replacing existing local data."""

import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from urllib.parse import urlparse
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DESTINATION = ROOT / "entregas/cu-19-interpretacion-danos/app/bd"
METADATA = Path(__file__).with_name("cardd-dataset.json")
MARKER = ".cardd-install.json"
DIRECTORIES = ("rawdata", "clean_data")


class DatasetError(Exception):
    """An actionable preparation error, reported by the CLI without a traceback."""


def archive_path(name):
    path = PurePosixPath(name)
    if (not name or "\\" in name or path.is_absolute() or ".." in path.parts
            or not path.parts or path.parts[0] not in DIRECTORIES):
        raise DatasetError(f"Entrada no permitida en el paquete: {name!r}")
    return path.as_posix()


def download(url, output):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise DatasetError("La URL debe ser HTTP(S), o usa --archive para un archivo local.")
    if parsed.hostname == "drive.google.com":
        if "/folders/" in parsed.path:
            raise DatasetError("Drive requiere un enlace de archivo .tar.gz, no de carpeta.")
        if importlib.util.find_spec("gdown") is None:
            raise DatasetError(
                "Falta gdown. Instálalo en tu entorno con: "
                "python -m pip install -r scripts/requirements-cardd.txt"
            )
        result = subprocess.run([
            sys.executable, "-m", "gdown", "--fuzzy", "--no-cookies",
            "--output", str(output), url,
        ])
        if result.returncode or not output.is_file():
            raise DatasetError(
                "Fallo al descargar desde Drive. Comprueba el enlace de archivo, "
                "los permisos de descarga y los límites de Drive; también puedes usar --archive."
            )
    else:
        try:
            with urlopen(url, timeout=60) as response, output.open("wb") as target:
                shutil.copyfileobj(response, target)
        except OSError as error:
            raise DatasetError("Fallo de descarga HTTP(S). Comprueba la URL y la conexión.") from error


def unpack(archive, stage):
    files = {}
    seen = set()
    try:
        # Streaming avoids decompressing the multi-GB package twice. Everything
        # remains in staging until both the archive and dataset are validated.
        with tarfile.open(archive, "r|gz") as source:
            for member in source:
                name = archive_path(member.name)
                if name in seen:
                    raise DatasetError(f"Entrada duplicada en el paquete: {name}")
                seen.add(name)
                target = stage / name
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                elif member.type in {tarfile.REGTYPE, tarfile.AREGTYPE}:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with source.extractfile(member) as content, target.open("xb") as output:
                        shutil.copyfileobj(content, output)
                    files[name] = member.size
                else:
                    raise DatasetError(f"Entrada no permitida en el paquete: {name!r}")
    except (tarfile.TarError, EOFError) as error:
        raise DatasetError("El archivo tar.gz es inválido o está incompleto.") from error
    return files


def validate_dataset(stage):
    excel = stage / "rawdata/image_info.xlsx"
    if not excel.is_file() or not excel.stat().st_size:
        raise DatasetError("Falta rawdata/image_info.xlsx o está vacío.")
    counts = {"images": 0, "thumbnails": 0}
    for split in ("train", "test", "val"):
        annotation = stage / f"rawdata/instances_{split}.json"
        if not annotation.is_file():
            raise DatasetError(f"Falta {annotation.name}.")
        try:
            data = json.loads(annotation.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError) as error:
            raise DatasetError(f"JSON inválido: {annotation.name}.") from error
        if not isinstance(data, dict) or not isinstance(data.get("images"), list) or not data["images"]:
            raise DatasetError(f"JSON COCO sin lista de imágenes válida: {annotation.name}.")
        for image in data["images"]:
            name = image.get("file_name") if isinstance(image, dict) else None
            if (not isinstance(name, str) or not name or name in {".", ".."}
                    or "/" in name or "\\" in name):
                raise DatasetError(f"file_name no permitido en {annotation.name}: {name!r}")
            if not (stage / "clean_data" / split / "fullsize" / name).is_file():
                raise DatasetError(f"Falta la imagen referenciada: {split}/fullsize/{name}.")
            counts["images"] += 1
        counts["thumbnails"] += sum(
            path.is_file() for path in (stage / "clean_data" / split / "thumbnails").glob("*.webp")
        )
    return counts


def already_installed(destination, checksum):
    marker = destination / MARKER
    if not marker.exists() and not marker.is_symlink():
        return False
    try:
        if marker.is_symlink():
            raise ValueError("marcador enlazado")
        state = json.loads(marker.read_text(encoding="utf-8"))
        if state["sha256"] != checksum or state["version"] != 1 or not state["files"]:
            raise ValueError("versión diferente")
        for name, size in state["files"].items():
            path = destination / archive_path(name)
            if (not path.is_file() or path.is_symlink() or path.stat().st_size != size
                    or not path.resolve().is_relative_to(destination.resolve())):
                raise ValueError(name)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, DatasetError) as error:
        raise DatasetError(
            "Instalación incompleta, modificada o de otra versión. No se sobrescribe: "
            "conserva o mueve tus carpetas y el marcador .cardd-install.json; "
            "puedes elegir otro --destination."
        ) from error
    print(f"CARDD ya instalado y comprobado en {destination}; no se descarga otra vez.")
    return True


@contextmanager
def installation_lock(destination):
    lock = destination / ".cardd-lock"
    try:
        lock.mkdir()
    except FileExistsError as error:
        raise DatasetError(
            "Hay otra ejecución o un bloqueo .cardd-lock pendiente. "
            "Si ninguna descarga sigue activa, retira ese directorio vacío y repite."
        ) from error
    try:
        yield
    finally:
        lock.rmdir()


def install(args):
    checksum = args.sha256.lower()
    if not re.fullmatch(r"[0-9a-f]{64}", checksum):
        raise DatasetError("El SHA-256 esperado debe contener 64 caracteres hexadecimales.")
    destination = args.destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with installation_lock(destination):
        if already_installed(destination, checksum):
            return
        if any((destination / name).exists() or (destination / name).is_symlink()
               for name in DIRECTORIES):
            raise DatasetError(
                "Hay carpetas rawdata/clean_data existentes sin una instalación validada. "
                "No se sobrescriben: consérvalas o muévelas, o usa otro --destination."
            )
        if not args.archive and not args.url:
            raise DatasetError("Falta la URL: usa --url, CARDD_URL o --archive.")
        with tempfile.TemporaryDirectory(prefix=".cardd-stage-", dir=destination) as temp:
            stage = Path(temp)
            archive = args.archive
            if archive is None:
                archive = stage / "dataset.tar.gz"
                print("Descargando el paquete CARDD…", flush=True)
                download(args.url, archive)
            if not archive.is_file():
                raise DatasetError(f"No existe el archivo local: {archive}")
            print("Comprobando SHA-256…", flush=True)
            with archive.open("rb") as source:
                actual = hashlib.file_digest(source, "sha256").hexdigest()
            if actual != checksum:
                raise DatasetError("SHA-256 incorrecto. No se instala el paquete.")
            print("Extrayendo y comprobando imágenes y anotaciones…", flush=True)
            files = unpack(archive, stage)
            counts = validate_dataset(stage)
            state = {"version": 1, "sha256": checksum, "files": files, **counts}
            (stage / MARKER).write_text(json.dumps(state, sort_keys=True) + "\n", encoding="utf-8")
            moved = []
            try:
                for name in (*DIRECTORIES, MARKER):
                    target = destination / name
                    if target.exists() or target.is_symlink():
                        raise DatasetError(f"El destino cambió durante la extracción: {target}")
                    (stage / name).rename(target)
                    moved.append(name)
            except (OSError, DatasetError):
                for name in reversed(moved):
                    (destination / name).rename(stage / name)
                raise
            print(f"CARDD instalado en {destination}: {counts['images']} imágenes, "
                  f"{counts['thumbnails']} miniaturas. PostgreSQL se carga por separado.")


def main():
    metadata = json.loads(METADATA.read_text(encoding="utf-8"))
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--url", help="Enlace de archivo Drive o URL HTTP(S); alternativa: CARDD_URL.")
    source.add_argument("--archive", type=Path, help="Paquete .tar.gz local, sin descarga.")
    parser.add_argument("--sha256", default=os.environ.get("CARDD_SHA256", metadata["sha256"]),
                        help="SHA-256 esperado; por defecto la versión registrada en el repo.")
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION,
                        help="Destino; por defecto entregas/cu-19-interpretacion-danos/app/bd/.")
    args = parser.parse_args()
    if not args.url:
        args.url = os.environ.get("CARDD_URL")
    try:
        install(args)
    except (DatasetError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nDescarga interrumpida; no se declara una instalación completa.", file=sys.stderr)
        raise SystemExit(130)
