from __future__ import annotations

import csv
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

# El modulo comun de equivalencias de reglas de coste (#88, ADR 0008) no esta en un paquete: se anade
# su carpeta a sys.path, como hace costes_y_cobertura.py con los scripts del paquete de la empresa.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "comun"))
from equivalencias import Equivalencia, cargar_equivalencias, regla_efectiva  # noqa: E402


@dataclass(frozen=True)
class Catalogo:
    # pieza_id -> fila de piezas.csv (nombre, zona_tipo, lado, ...)
    piezas: dict[str, dict[str, str]]
    # (clase_cardd, zona_tipo, severidad) de reglas_dano.csv: las combinaciones
    # para las que la tool de costes sabe calcular una reparacion
    reglas: frozenset[tuple[str, str, str]]
    # equivalencias de reglas de coste (comun/equivalencias_reglas.csv): una combinacion sin regla propia
    # usa la de una vecina que si la tiene (ADR 0008). Vacio = solo cuentan las reglas propias.
    equivalencias: dict[tuple[str, str], Equivalencia] = field(default_factory=dict)


def _find_repo_root(start: Path) -> Path:
    for candidato in [start, *start.parents]:
        if (candidato / ".git").exists():
            return candidato
    raise RuntimeError(f"No se encontro la raiz del repo (.git) subiendo desde {start}")


def datos_empresa_dir() -> Path:
    """Carpeta `data/` del paquete de la empresa (piia2_paquete_datos.zip
    extraido en la raiz del repo). Se puede cambiar con PIIA2_DATOS_DIR."""
    en_entorno = os.environ.get("PIIA2_DATOS_DIR")
    if en_entorno:
        return Path(en_entorno)
    return _find_repo_root(Path(__file__).resolve().parent) / "piia2_paquete_datos" / "data"


def cargar_catalogo(data_dir: str | Path | None = None) -> Catalogo:
    data_dir = Path(data_dir) if data_dir is not None else datos_empresa_dir()

    with open(data_dir / "piezas.csv", encoding="utf-8") as f:
        piezas = {fila["pieza_id"]: fila for fila in csv.DictReader(f)}

    with open(data_dir / "reglas_dano.csv", encoding="utf-8") as f:
        reglas = frozenset(
            (fila["clase_cardd"], fila["zona_tipo"], fila["severidad"])
            for fila in csv.DictReader(f)
        )

    # una tabla ausente o mal formada lanza un error claro: no se ignora en silencio (AC-009)
    return Catalogo(piezas=piezas, reglas=reglas, equivalencias=cargar_equivalencias())


def clase_a_tool(damage_class: str) -> str:
    """Nombre de clase de PIIA-1 ('lamp broken') -> el de la tool de costes
    ('lamp_broken')."""
    return damage_class.replace(" ", "_")


def combinacion_valida(
    catalogo: Catalogo, clase_tool: str, pieza_id: str, severidad: str
) -> bool:
    """True si la tool de costes tiene una regla para esta clase de dano sobre
    esta pieza y severidad, propia o por una equivalencia (ADR 0008). Si no la
    tiene, `estimar_coste` no calcula nada para ese dano y solo devuelve una
    linea de aviso. El hallazgo no cambia: la equivalencia se aplica al consumir."""
    pieza = catalogo.piezas.get(pieza_id)
    if pieza is None:
        return False
    return regla_efectiva(clase_tool, pieza["zona_tipo"], severidad, catalogo.reglas, catalogo.equivalencias) is not None


def lista_piezas_para_prompt(catalogo: Catalogo) -> str:
    lados = {"I": "izquierdo", "D": "derecho", "C": "central", "NA": "-"}
    return "\n".join(
        f"  - {pieza_id}: {fila['nombre']} (lado {lados.get(fila['lado'], fila['lado'])})"
        for pieza_id, fila in catalogo.piezas.items()
    )
