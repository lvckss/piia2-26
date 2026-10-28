"""Prueba recorte.py contra fotos reales del CarDD_COCO copiado en local
(en vez del placeholder gris que usa recorte.py). Los bboxes de los JSON de
ejemplo se escribieron a mano para probar classify_confidence, no salen de
correr SAM3 sobre estas fotos concretas -- esto valida que el recorte no
rompe con fotos reales (tamano, orientacion, formato), no que caiga sobre
un dano real."""

from __future__ import annotations

from pathlib import Path

from hallazgos import cargar_detecciones, construir_hallazgos
from recorte import generar_recortes

AGENTE_DIR = Path(__file__).resolve().parent
EJEMPLOS_DIR = AGENTE_DIR / "ejemplos"
CROPS_DIR = EJEMPLOS_DIR / "crops_reales"

SPLITS = ["train2017", "val2017", "test2017"]


def _find_repo_root(start: Path) -> Path:
    for candidato in [start, *start.parents]:
        if (candidato / ".git").exists():
            return candidato
    raise RuntimeError(f"No se encontro la raiz del repo (.git) subiendo desde {start}")


def _buscar_imagen_real(cardd_coco_dir: Path, image_id: int) -> Path | None:
    nombre = f"{image_id:06d}.jpg"
    for split in SPLITS:
        candidato = cardd_coco_dir / split / nombre
        if candidato.exists():
            return candidato
    return None


def main() -> None:
    repo_root = _find_repo_root(AGENTE_DIR)
    cardd_coco_dir = repo_root / "CarDD_release" / "CarDD_COCO"

    if not cardd_coco_dir.exists():
        print(f"No existe {cardd_coco_dir} -- copia ahi el CarDD_release primero.")
        return

    ejemplo_paths = sorted(EJEMPLOS_DIR.glob("*.json"))
    encontrados = 0

    for ejemplo_path in ejemplo_paths:
        deteccion = cargar_detecciones(ejemplo_path)
        imagen_real = _buscar_imagen_real(cardd_coco_dir, deteccion["image_id"])

        if imagen_real is None:
            print(f"[falta] image_id={deteccion['image_id']} (para {ejemplo_path.name}) -> saltado")
            continue

        deteccion["image_path"] = str(imagen_real)
        hallazgos = construir_hallazgos(deteccion)
        generar_recortes(deteccion, hallazgos, CROPS_DIR)
        encontrados += 1

        print(f"--- {ejemplo_path.name} ({imagen_real.relative_to(repo_root)}) ---")
        for finding in hallazgos["findings"]:
            print(
                f"  {finding['category']:15s} score={finding['score']:.2f} "
                f"-> {finding['confidence_tier']:13s} "
                f"crop guardado en {Path(finding['crop_image_path']).name}"
            )

    if encontrados == 0:
        print(f"\nNinguna de las 3 imagenes de ejemplo esta en {cardd_coco_dir}.")
    else:
        print(f"\n{encontrados}/{len(ejemplo_paths)} ejemplos probados con foto real.")
        print(f"Recortes guardados en: {CROPS_DIR}")


if __name__ == "__main__":
    main()
