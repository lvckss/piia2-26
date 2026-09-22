import json
import io
from pathlib import Path
import time
from typing import Iterator
from contextlib import redirect_stdout
import numpy as np
from PIL import Image
from pycocotools.coco import COCO
from tqdm.auto import tqdm

from ml.StrategyPipeline.schemas import GroundTruthInstance, ImageSample


class CarddLoader:
    def __init__(
            self,
            ann_path: str,
            img_dir: str,
            load_image: bool = True,
            verbose: bool = True,
    ) -> None:
        # guarda las rutas base y la configuración de carga
        self.ann_path = Path(ann_path)
        self.img_dir = Path(img_dir)
        self.load_image = load_image
        self.verbose = verbose
        self.dataset_name = self.ann_path.name
        self.is_all_dataset = self.dataset_name == "instances_all.json"

        # abre el json coco y guarda los ids ordenados
        self.coco = self._load_coco_annotations()
        self.image_ids = sorted(self.coco.getImgIds())

        self.image_id_to_idx = {
            image_id: idx
            for idx, image_id in enumerate(self.image_ids)
        }

        # si usamos instances_all, el split se resuelve por imagen
        if self.is_all_dataset:
            self.split = None
            self.image_id_to_split = self._build_image_split_map()
        else:
            # si no, el split se infiere del nombre del json
            self.split = self._infer_split_from_filename()
            self.image_id_to_split = {}

        if self.verbose:
            split_label = "all" if self.is_all_dataset else self.split
            self._log(
                "dataset cargado | "
                f"split={split_label} | "
                f"imagenes={len(self.image_ids)} | "
                f"anotaciones={len(self.coco.anns)} | "
                f"categorias={len(self.coco.cats)}"
            )

    def __len__(self) -> int:
        return len(self.image_ids)

    # si el dataset se creó con un json específico de split, se infiere el split a partir del nombre del archivo (convención propia de nombres de archivos)
    def _infer_split_from_filename(self) -> str:
        stem = self.ann_path.stem

        if stem == "instances_train":
            return "train"
        if stem == "instances_val":
            return "val"
        if stem == "instances_test":
            return "test"

        raise ValueError(
            "No se pudo inferir el split a partir del nombre del archivo de anotaciones. "
            "Usa un nombre compatible como instances_train.json, "
            "instances_val.json, instances_test.json o instances_all.json."
        )

    def _build_image_split_map(self) -> dict[int, str]:
        rawdata_dir = self.ann_path.parent
        split_files = {
            "train": rawdata_dir / "instances_train.json",
            "val": rawdata_dir / "instances_val.json",
            "test": rawdata_dir / "instances_test.json",
        }

        # crea un mapa image_id -> split a partir de los tres json
        image_id_to_split: dict[int, str] = {}

        for split_name, split_path in split_files.items():
            if not split_path.exists():
                raise FileNotFoundError(
                    f"Falta el archivo de anotaciones del split necesario para inferir el split por imagen: {split_path}"
                )

            data = json.loads(split_path.read_text())
            for image_info in data.get("images", []):
                image_id = int(image_info["id"])
                if image_id in image_id_to_split:
                    raise ValueError(f"El id de imagen {image_id} aparece en más de un split.")
                image_id_to_split[image_id] = split_name

        missing_ids = [image_id for image_id in self.image_ids if image_id not in image_id_to_split]
        if missing_ids:
            missing_preview = ", ".join(str(image_id) for image_id in missing_ids[:10])
            raise ValueError(
                "No se pudo inferir el split para todas las imágenes de instances_all.json. "
                f"Faltan los ids de imagen: {missing_preview}"
            )

        return image_id_to_split

    def _load_coco_annotations(self) -> COCO:
        # silencia la salida por defecto de pycocotools y la reemplaza por mensajes más claros
        if self.verbose:
            self._log(f"cargando anotaciones desde {self.ann_path.name}...")

        start = time.perf_counter()
        with redirect_stdout(io.StringIO()):
            coco = COCO(str(self.ann_path))
        elapsed = time.perf_counter() - start

        if self.verbose:
            self._log(f"anotaciones indexadas en {elapsed:.2f}s")

        return coco

    def _log(self, message: str) -> None:
        print(f"[CarddLoader] {message}")

    def _resolve_image_path(self, file_name: str) -> Path:
        # limpia rutas tipo ./000001.jpg a 000001.jpg para evitar problemas de path
        clean_name = file_name.lstrip("./")

        candidates = [
            self.img_dir / clean_name,
            self.img_dir / "images" / clean_name,
        ]

        # prueba primero img_dir y luego img_dir/images
        for candidate in candidates:
            if candidate.exists():
                return candidate

        raise FileNotFoundError(
            f"No se encontró la imagen '{file_name}'. Se comprobó en: "
            + ", ".join(str(path) for path in candidates)
        )

    # devuelve una muestra concreta del dataset usando su índice
    def __getitem__(self, idx: int) -> ImageSample:
        if idx < 0 or idx >= len(self):
            raise IndexError(f"Índice {idx} fuera de rango para un dataset de tamaño {len(self)}")

        # recupera la metadata coco de una imagen concreta
        image_id = self.image_ids[idx]
        image_info = self.coco.loadImgs([image_id])[0]
        sample_split = self.image_id_to_split.get(image_id, self.split)

        image_path = self._resolve_image_path(image_info["file_name"])
        width = int(image_info["width"])
        height = int(image_info["height"])

        # carga todas las anotaciones de esa imagen
        ann_ids = self.coco.getAnnIds(imgIds=[image_id])
        anns = self.coco.loadAnns(ann_ids)

        # convierte cada anotación coco en una instancia de gt del pipeline
        gt_instances = [
            GroundTruthInstance(
                annotation_id=int(ann["id"]),
                category_id=int(ann["category_id"]),
                mask=self.coco.annToMask(ann).astype(bool),
                bbox=tuple(float(x) for x in ann["bbox"]),
                area=float(ann["area"]),
            )
            for ann in anns
        ]

        image = None
        if self.load_image:
            # la imagen solo se carga si el dataset se creó con load_image=True
            image = np.asarray(Image.open(image_path).convert("RGB"))

        # devuelve la muestra ya normalizada para el strategy module
        return ImageSample(
            image_id=image_id,
            image_path=str(image_path),
            image=image,
            width=width,
            height=height,
            split=sample_split,
            corruption=image_info.get("corruption"),
            severity=image_info.get("severity"),
            is_clean=image_info.get("corruption") in (None, "", "clean"),
            gt_instances=gt_instances,
        )

    def get_by_image_id(self, image_id: int) -> ImageSample:
        if image_id not in self.image_id_to_idx:
            raise KeyError(f"image_id no encontrado en el dataset: {image_id}")

        return self[self.image_id_to_idx[image_id]]

    # permite recorrer el dataset muestra a muestra con un for
    def __iter__(self) -> Iterator[ImageSample]:
        with tqdm(total=len(self), desc="Iterando sobre el dataset... ") as pbar:
            for idx in range(len(self)):
                pbar.update(1)
                yield self[idx]
