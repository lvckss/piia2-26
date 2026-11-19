"""Equivalencias de reglas de coste para las combinaciones sin regla propia.

Plan: specs/88-equivalencias-reglas-coste.md (AC-001, AC-002 y AC-009).
Decisión: docs/adr/0008-equivalencias-reglas-coste.md.

Cuando una combinación (clase, zona, severidad) no tiene regla en
`reglas_dano.csv` de la empresa, la tabla `equivalencias_reglas.csv` indica qué
combinación vecina, que sí la tiene, se usa en su lugar. La regla de la empresa
siempre prevalece y no se crea ninguna acción nueva. Solo biblioteca estándar.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

SEVERIDADES = ("leve", "moderado", "grave")
COLUMNAS = ("clase_origen", "zona_tipo", "clase_destino", "severidad_minima", "motivo")
RUTA_TABLA = Path(__file__).resolve().with_name("equivalencias_reglas.csv")


@dataclass(frozen=True)
class Equivalencia:
    clase_origen: str
    zona_tipo: str
    clase_destino: str
    severidad_minima: str  # "" si no hay mínima
    motivo: str


def cargar_equivalencias(ruta=None) -> dict[tuple[str, str], Equivalencia]:
    """Lee la tabla y devuelve `(clase_origen, zona_tipo) -> Equivalencia`.

    Una tabla ausente o una fila mal formada lanzan un error con la ruta y, si
    procede, el número de fila: la tabla nunca se ignora en silencio.
    """
    ruta = Path(ruta) if ruta is not None else RUTA_TABLA
    if not ruta.is_file():
        raise FileNotFoundError(f"Falta la tabla de equivalencias de reglas de coste: {ruta}")
    tabla: dict[tuple[str, str], Equivalencia] = {}
    # utf-8-sig: el mismo texto con o sin marca BOM (por ejemplo, guardado desde Excel en Windows).
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        lector = csv.DictReader(f)
        faltan = [c for c in COLUMNAS if c not in (lector.fieldnames or [])]
        if faltan:
            raise ValueError(f"{ruta}: faltan columnas en la cabecera: {', '.join(faltan)}")
        for fila in lector:
            donde = f"{ruta}, fila {lector.line_num}"
            if None in fila:
                raise ValueError(f"{donde}: tiene más columnas de las esperadas")
            if any(fila[c] is None for c in COLUMNAS):
                raise ValueError(f"{donde}: tiene menos columnas de las esperadas")
            valores = {c: fila[c].strip() for c in COLUMNAS}
            vacias = [c for c in COLUMNAS if c != "severidad_minima" and not valores[c]]
            if vacias:
                raise ValueError(f"{donde}: campos vacíos: {', '.join(vacias)}")
            if valores["severidad_minima"] and valores["severidad_minima"] not in SEVERIDADES:
                raise ValueError(f"{donde}: severidad_minima {valores['severidad_minima']!r} no es una de "
                                 f"{', '.join(SEVERIDADES)}")
            clave = (valores["clase_origen"], valores["zona_tipo"])
            if clave in tabla:
                raise ValueError(f"{donde}: la combinación {clave[0]}/{clave[1]} está duplicada")
            tabla[clave] = Equivalencia(**valores)
    return tabla


def regla_efectiva(clase, zona_tipo, severidad, reglas, equivalencias):
    """Regla de la empresa que se aplica a `(clase, zona_tipo, severidad)`.

    `reglas` es el conjunto (o diccionario) de claves `(clase, zona_tipo, severidad)`
    de `reglas_dano.csv`. Devuelve `(clase, severidad)` tal cual si la combinación
    tiene regla propia; `(clase_destino, severidad_efectiva)` si no la tiene y hay
    una equivalencia cuyo destino existe; y `None` («sin regla») en cualquier otro caso.
    """
    if (clase, zona_tipo, severidad) in reglas:
        return clase, severidad
    equivalencia = equivalencias.get((clase, zona_tipo))
    if equivalencia is None or severidad not in SEVERIDADES:
        return None
    efectiva = max(severidad, equivalencia.severidad_minima or severidad, key=SEVERIDADES.index)
    if (equivalencia.clase_destino, zona_tipo, efectiva) not in reglas:
        return None
    return equivalencia.clase_destino, efectiva
