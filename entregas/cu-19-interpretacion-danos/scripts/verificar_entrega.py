"""Verificación de la Entrega 2 (Issue #49): AC-001, AC-002 y AC-004.

Esqueleto de la fase Red: las funciones existen pero aún no hacen nada.
"""

from pathlib import Path

CASO = Path(__file__).resolve().parents[1]


def generar(caso: Path = CASO) -> list[str]:
    """Crea en `decisions/` una copia de cada ADR Aceptado de `docs/adr/`."""
    raise NotImplementedError


def comprobar_copias(caso: Path = CASO) -> list[str]:
    """AC-002: devuelve los errores de las copias de `decisions/` (vacío si es correcto)."""
    raise NotImplementedError


def comprobar_enlaces(caso: Path = CASO) -> tuple[int, int, list[str]]:
    """AC-004: devuelve (documentos, enlaces, errores)."""
    raise NotImplementedError


def comprobar_estructura(caso: Path = CASO) -> list[str]:
    """AC-001: devuelve los errores de la estructura mínima de la entrega."""
    raise NotImplementedError


def main(argv: list[str] | None = None) -> int:
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit(main())
