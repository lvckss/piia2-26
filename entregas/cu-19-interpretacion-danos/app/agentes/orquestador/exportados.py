"""#34 UI v2 AC-016/017: lector de predicciones, nunca ejecuta inferencia ML."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

from workflow import FlowError, adapt_detection, normalize_image


class ExportStore:
    def __init__(self, documents, images):
        self.images = Path(images)
        self.records = {}
        for path in sorted(Path(documents).glob("[0-9]*.json")):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                name = record["image_file"]
                image_id = record["image_id"]
                valid = (isinstance(name, str) and re.fullmatch(r"[0-9]{6}\.(?:jpg|jpeg|png)", name)
                         and type(image_id) is int and image_id > 0
                         and path.stem == f"{image_id:06d}" == Path(name).stem
                         and record["split"] in ("train", "val", "test")
                         and all(type(record[k]) is int and record[k] > 0 for k in ("image_width", "image_height"))
                         and isinstance(record["predictions"], list))
                if not valid or name in self.records:
                    raise ValueError("documento incompatible")
                self.records[name] = record
            except (ValueError, KeyError, TypeError) as exc:
                raise FlowError("CONTRATO_INVALIDO", "El lote de detecciones contiene un documento incompatible.", stage="piia1", status=503) from exc
        if not self.records:
            raise FlowError("CONTRATO_INVALIDO", "No se encuentran documentos de detecciones en el lote configurado.", stage="piia1", status=503)

    def original(self, record):
        return self.images / record["split"] / "fullsize" / record["image_file"]

    def catalogue(self):
        images = []
        for record in self.records.values():
            if not self.original(record).is_file():
                continue
            relative = f'{record["split"]}/fullsize/{record["image_file"]}'
            images.append({"id": record["image_id"], "id_externo": record["image_id"], "file_name": record["image_file"], "split": record["split"], "ruta_imagen": relative, "ruta_thumbnail": relative.replace("/fullsize/", "/thumbnails/"), "width": record["image_width"], "height": record["image_height"], "numero_instancias": len(record["predictions"]), "numero_categorias": len({p["damage_class"] for p in record["predictions"]}), "labels": sorted({p["damage_class"] for p in record["predictions"]})})
        return images

    def prepare(self, image, filename):
        if filename not in self.records:
            raise FlowError("PERITAJE_ENTRADA_INVALIDA", "Esta imagen no tiene documento de detecciones. Selecciona una imagen del lote disponible.", status=422)
        record = self.records[filename]
        original_path = self.original(record)
        if not original_path.is_file():
            raise FlowError("PERITAJE_ENTRADA_INVALIDA", "No está disponible el original asociado al documento de detecciones.", status=422)
        mime = "image/png" if original_path.suffix == ".png" else "image/jpeg"
        with normalize_image(original_path.read_bytes(), mime) as original:
            size = (record["image_width"], record["image_height"])
            if image.size != size or original.size != size or hashlib.sha256(image.tobytes()).digest() != hashlib.sha256(original.tobytes()).digest():
                raise FlowError("PERITAJE_ENTRADA_INVALIDA", "La imagen no coincide con el original del documento de detecciones.", status=422)
        try:
            items, indices = [], []
            for prediction in record["predictions"]:
                index = prediction["instance_index"]
                if type(index) is not int or index <= 0 or index in indices:
                    raise ValueError("índice inválido")
                indices.append(index)
                x, y, w, h = prediction["bbox_xywh"]
                items.append({"damage_class": prediction["damage_class"], "score": prediction["score"], "bbox": {"x": x, "y": y, "width": w, "height": h}})
            # El mismo validador de geometría del transporte ML; no filtra datos.
            clean = adapt_detection({"vehicle_damage_assessment": items}, record["image_id"], Path("imagen.png"), size)
            for prediction, index in zip(clean["predictions"], indices):
                prediction["instance_index"] = index
            clean.pop("image_path")
            return copy.deepcopy(clean)
        except (ValueError, KeyError, TypeError) as exc:
            raise FlowError("CONTRATO_INVALIDO", "El documento de detecciones no respeta el formato esperado.", stage="piia1", status=502) from exc
