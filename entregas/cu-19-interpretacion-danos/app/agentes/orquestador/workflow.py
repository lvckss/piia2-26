"""Dos fases y estado efímero del ADR 0007; Spec 34 AC-001–012.

El pipeline se inyecta por funciones públicas. No calcula importes ni decide
daños: conserva las salidas de los agentes y publica solo tras verificarlas.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import math
import shutil
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 20_000_000
ACTIVE = {"analizando", "generando_informe"}
CATEGORIES = {"A", "B", "C", "SUV-B", "SUV-C", "FURG", "C-PREMIUM", "D-PREMIUM", "desconocido"}
DAMAGE_CLASSES = {"dent", "scratch", "crack", "glass shatter", "lamp broken", "tire flat"}


class FlowError(Exception):
    def __init__(self, code, message, *, stage="entrada", status=400, retryable=False):
        super().__init__(message)
        self.status = status
        self.public = {"codigo": code, "etapa": stage, "mensaje": message, "reintentable": retryable}


def normalize_image(data, mime):
    if not data:
        raise FlowError("PERITAJE_ENTRADA_INVALIDA", "La imagen está vacía.")
    if len(data) > MAX_BYTES:
        raise FlowError("PERITAJE_ENTRADA_INVALIDA", "La imagen supera 10 MiB.", status=413)
    if mime not in {"image/jpeg", "image/png"}:
        raise FlowError("PERITAJE_ENTRADA_INVALIDA", "Selecciona JPEG o PNG.", status=415)
    try:
        with Image.open(io.BytesIO(data)) as original:
            if original.format not in {"PNG", "JPEG"}:
                raise FlowError("PERITAJE_ENTRADA_INVALIDA", "El archivo no es JPEG ni PNG.", status=415)
            if original.width * original.height > MAX_PIXELS:
                raise FlowError("PERITAJE_ENTRADA_INVALIDA", "La imagen supera 20 millones de píxeles.", status=413)
            image = ImageOps.exif_transpose(original).convert("RGB")
            image.load()
            return image
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise FlowError("PERITAJE_ENTRADA_INVALIDA", "No se pudo decodificar la imagen.") from exc


def adapt_detection(response, image_id, path, size):
    """Mantiene clase, score y geometría; asigna índices, sin filtro adicional."""
    def invalid():
        raise FlowError("CONTRATO_INVALIDO", "La respuesta del detector no tiene un formato o geometría válidos.", stage="piia1", status=502)
    if not isinstance(response, dict) or not isinstance(response.get("vehicle_damage_assessment"), list):
        invalid()
    predictions = []
    width, height = size
    for index, item in enumerate(response["vehicle_damage_assessment"], 1):
        if not isinstance(item, dict) or item.get("damage_class") not in DAMAGE_CLASSES:
            invalid()
        bbox = item.get("bbox")
        if not isinstance(bbox, dict) or not all(k in bbox for k in ("x", "y", "width", "height")):
            invalid()
        values = [bbox[k] for k in ("x", "y", "width", "height")]
        score = item.get("score")
        if not all(type(v) in (int, float) and math.isfinite(v) for v in [*values, score]):
            invalid()
        x, y, w, h = values
        if not (0 <= score <= 1 and x >= 0 and y >= 0 and w > 0 and h > 0 and x + w <= width + 1e-6 and y + h <= height + 1e-6):
            invalid()
        predictions.append({"instance_index": index, "damage_class": item["damage_class"], "score": score, "bbox_xywh": values})
    return {"image_id": image_id, "image_path": str(path), "predictions": predictions}


def resolve_context(analysis, body, catalogues):
    if not isinstance(body, dict) or set(body) - {"contexto", "seleccion_vehiculo"}:
        raise FlowError("PERITAJE_ENTRADA_INVALIDA", "Envía solo el contexto y la selección del vehículo.", status=422)
    context = body.get("contexto")
    fields = {"vehiculo_id", "region", "tipo_taller", "acabado", "tipo_pieza", "rol", "edad_anios", "km", "poliza_id"}
    if not isinstance(context, dict) or set(context) - fields:
        raise FlowError("PERITAJE_ENTRADA_INVALIDA", "El contexto contiene campos no admitidos.", status=422)
    context = copy.deepcopy(context)
    for name in ("vehiculo_id", "region", "tipo_taller", "acabado", "tipo_pieza", "rol"):
        if not isinstance(context.get(name), str):
            raise FlowError("PERITAJE_ENTRADA_INVALIDA", f"Selecciona un valor válido para {name}.", status=422)
    for name in ("edad_anios", "km"):
        value = context.get(name)
        if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
            raise FlowError("PERITAJE_ENTRADA_INVALIDA", f"Revisa el campo {name}: debe ser un número no negativo.", status=422)
    if context.get("rol") not in {"propio", "tercero_perjudicado"}:
        raise FlowError("PERITAJE_ENTRADA_INVALIDA", "Revisa el rol en el siniestro.", status=422)
    for name, catalogue in (("region", "regiones"), ("tipo_taller", "tipos_taller"), ("acabado", "acabados"), ("tipo_pieza", "tipos_pieza")):
        if context.get(name) not in {x["id"] for x in catalogues[catalogue]}:
            raise FlowError("PERITAJE_ENTRADA_INVALIDA", f"Selecciona un valor válido para {name}.", status=422)
    if context["rol"] == "propio" and (not isinstance(context.get("poliza_id"), str) or context["poliza_id"] not in {x["id"] for x in catalogues["polizas"]}):
        raise FlowError("PERITAJE_ENTRADA_INVALIDA", "Selecciona una póliza válida.", status=422)
    if context["rol"] == "tercero_perjudicado":
        context.pop("poliza_id", None)
    vehicle = analysis["vehiculo"]
    choice = body.get("seleccion_vehiculo")
    if choice is None and vehicle["categoria"] == "desconocido":
        if context.get("vehiculo_id", "V14") != "V14":
            raise FlowError("PERITAJE_ENTRADA_INVALIDA", "Sin selección, el vehículo desconocido utiliza V14.", status=422)
        vehicle_id, origin = "V14", "minimo_por_defecto"
    else:
        if not isinstance(choice, dict) or set(choice) != {"tipo", "vehiculo_id"}:
            raise FlowError("PERITAJE_ENTRADA_INVALIDA", "Confirma o selecciona el vehículo antes de presupuestar.", status=422)
        vehicle_id, origin = choice["vehiculo_id"], choice["tipo"]
        if not isinstance(origin, str) or origin not in {"referencia_confirmada", "seleccion_usuario"} or vehicle_id != context.get("vehiculo_id"):
            raise FlowError("PERITAJE_ENTRADA_INVALIDA", "La selección del vehículo no coincide con el contexto.", status=422)
        if origin == "referencia_confirmada" and (not vehicle["vehiculo_id_referencia"] or vehicle_id != vehicle["vehiculo_id_referencia"]):
            raise FlowError("PERITAJE_ENTRADA_INVALIDA", "El vehículo confirmado no coincide con la referencia propuesta.", status=422)
    if vehicle_id not in {x["id"] for x in catalogues["vehiculos"]}:
        raise FlowError("PERITAJE_ENTRADA_INVALIDA", "Selecciona un vehículo válido.", status=422)
    context.update(vehiculo_id=vehicle_id, vehiculo_origen=origin)
    return context


@dataclass
class Case:
    id: str
    folder: Path
    fingerprint: str
    image_size: tuple[int, int]
    source_detection: dict | None = None
    state: str = "analizando"
    stage: str = "entrada"
    analysis: dict | None = None
    detections: dict | None = None
    result: dict | None = None
    error: dict | None = None
    last_activity: float = 0
    report_keys: dict = field(default_factory=dict)
    future: object = None
    day: str = field(default_factory=lambda: date.today().isoformat())


class Workflow:
    def __init__(self, pipeline, *, root=None, clock=time.monotonic, ttl=3600, capacity=2):
        self.pipeline, self.clock, self.ttl, self.capacity = pipeline, clock, ttl, capacity
        self.root = Path(root) if root else Path(tempfile.mkdtemp(prefix="piia2-web-"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=capacity, thread_name_prefix="peritaje")
        self.cases, self.keys = {}, {}

    def catalogue(self):
        return copy.deepcopy(self.pipeline.catalogues())

    def cleanup(self):
        with self.lock:
            for case in list(self.cases.values()):
                if case.state not in ACTIVE and self.clock() - case.last_activity >= self.ttl:
                    self._remove(case)

    def _remove(self, case):
        shutil.rmtree(case.folder)
        del self.cases[case.id]
        self.keys = {k: v for k, v in self.keys.items() if v != case.id}

    def _case(self, case_id):
        self.cleanup()
        if case_id not in self.cases:
            raise FlowError("EJECUCION_NO_DISPONIBLE", "La ejecución ya no está disponible. Inicia otro peritaje.", status=404)
        return self.cases[case_id]

    @staticmethod
    def _key(key):
        if not isinstance(key, str) or not 1 <= len(key) <= 200:
            raise FlowError("PERITAJE_ENTRADA_INVALIDA", "Falta una clave de petición válida.")

    def create(self, data, mime, key, filename=None):
        self._key(key)
        fingerprint = hashlib.sha256(mime.encode() + b"\0" + (filename or "").encode() + b"\0" + data).hexdigest()
        with self.lock:
            self.cleanup()
            if key in self.keys:
                case = self.cases[self.keys[key]]
                if case.fingerprint != fingerprint:
                    raise FlowError("IDEMPOTENCIA_CONFLICTO", "La clave ya corresponde a otra imagen.", status=409)
                return self.snapshot(case)
        image = normalize_image(data, mime)
        try:
            prepare = getattr(self.pipeline, "prepare", None)
            source = prepare(image, filename) if prepare else None
            self.pipeline.preflight()
            with self.lock:
                # Another simultaneous request may have reserved the key while decoding.
                if key in self.keys:
                    case = self.cases[self.keys[key]]
                    if case.fingerprint != fingerprint:
                        raise FlowError("IDEMPOTENCIA_CONFLICTO", "La clave ya corresponde a otra imagen.", status=409)
                    return self.snapshot(case)
                if len(self.cases) >= self.capacity:
                    raise FlowError("CAPACIDAD_AGOTADA", "Hay dos casos abiertos. Descarta uno antes de iniciar otro.", status=503, retryable=True)
                case_id = uuid.uuid4().hex
                folder = self.root / case_id
                folder.mkdir()
                try:
                    image.save(folder / "imagen.png", format="PNG")
                except Exception:
                    shutil.rmtree(folder)
                    raise
                case = Case(case_id, folder, fingerprint, image.size, source_detection=source, last_activity=self.clock())
                self.cases[case_id], self.keys[key] = case, case_id
                case.future = self.executor.submit(self._analyze, case)
                return self.snapshot(case)
        finally:
            image.close()

    def _stage(self, case, stage):
        with self.lock:
            case.stage, case.last_activity = stage, self.clock()

    def _fail(self, case, exc):
        if not isinstance(exc, FlowError):
            codes = {"piia1": "ML_NO_DISPONIBLE", "agente1": "VISION_NO_DISPONIBLE", "agente2": "COSTES_ERROR", "agente3": "INFORME_ERROR", "verificacion": "CONTRATO_INVALIDO"}
            exc = FlowError(codes.get(case.stage, "CONTRATO_INVALIDO"), "No se pudo completar la etapa del peritaje. Revisa los servicios y su configuración.", stage=case.stage, status=503)
        with self.lock:
            case.state, case.result, case.error, case.last_activity = "error", None, exc.public, self.clock()

    def _analyze(self, case):
        try:
            path = case.folder / "imagen.png"
            self._stage(case, "piia1")
            if case.source_detection is not None:
                detection = copy.deepcopy(case.source_detection)
                detection["image_path"] = str(path)
            else:
                detection = adapt_detection(self.pipeline.detect(path), case.id, path, case.image_size)
            detection_path = case.folder / "deteccion.json"
            detection_path.write_text(json.dumps(detection), encoding="utf-8")
            preview = getattr(self.pipeline, "preview", None)
            if preview:
                public = preview(detection, case.image_size)
                with self.lock:
                    case.detections = copy.deepcopy(public)
            self._stage(case, "agente1")
            analysis = self.pipeline.analyze(detection_path, case.folder)
            vehicle = analysis.get("vehiculo", {})
            if analysis.get("image_id") != detection["image_id"] or not isinstance(analysis.get("findings"), list) or vehicle.get("categoria") not in CATEGORIES:
                raise FlowError("CONTRATO_INVALIDO", "El análisis de visión no respeta el contrato esperado.", stage="agente1", status=502)
            reference = vehicle.get("vehiculo_id_referencia")
            if (vehicle["categoria"] == "desconocido" and reference is not None) or (vehicle["categoria"] != "desconocido" and not reference):
                raise FlowError("CONTRATO_INVALIDO", "La categoría y la referencia del vehículo no son coherentes.", stage="agente1", status=502)
            with self.lock:
                case.analysis, case.state, case.last_activity = copy.deepcopy(analysis), "esperando_datos", self.clock()
        except Exception as exc:
            self._fail(case, exc)

    def generate(self, case_id, body, key):
        self._key(key)
        try:
            fingerprint = hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()
        except (ValueError, TypeError) as exc:
            raise FlowError("PERITAJE_ENTRADA_INVALIDA", "El contexto debe ser un JSON válido.", status=422) from exc
        with self.lock:
            case = self._case(case_id)
            if key in case.report_keys:
                if case.report_keys[key] != fingerprint:
                    raise FlowError("IDEMPOTENCIA_CONFLICTO", "La clave ya corresponde a otro contexto.", status=409)
                return self.snapshot(case)
            if case.state != "esperando_datos":
                raise FlowError("ESTADO_INVALIDO", "El caso no admite una nueva generación de informe.", status=409)
            context = resolve_context(case.analysis, body, self.catalogue())
            case.report_keys[key] = fingerprint
            case.state, case.last_activity = "generando_informe", self.clock()
            case.future = self.executor.submit(self._report, case, context)
            return self.snapshot(case)

    def _report(self, case, context):
        try:
            self._stage(case, "agente2")
            output = self.pipeline.costs(copy.deepcopy(case.analysis), copy.deepcopy(context), case.folder)
            if output.get("contexto") != context or output.get("image_id") != case.analysis["image_id"]:
                raise FlowError("CONTRATO_INVALIDO", "El presupuesto no conserva el contexto del caso.", stage="agente2", status=502)
            self._stage(case, "agente3")
            markdown = self.pipeline.report(copy.deepcopy(case.analysis), copy.deepcopy(output), case.day)
            if not isinstance(markdown, str):
                raise FlowError("CONTRATO_INVALIDO", "El informe no es un texto válido.", stage="agente3", status=502)
            self._stage(case, "verificacion")
            if self.pipeline.verify(markdown, output):
                raise FlowError("CIFRAS_INCONSISTENTES", "El informe contiene cifras inconsistentes y no se publicará.", stage="verificacion", status=502)
            with self.lock:
                case.result = {"markdown": markdown, "agente2": output, "procedencia": context["vehiculo_origen"]}
                case.state, case.last_activity = "completada", self.clock()
        except Exception as exc:
            self._fail(case, exc)

    @staticmethod
    def snapshot(case):
        analysis = copy.deepcopy(case.analysis)
        if analysis:
            for finding in analysis["findings"]:
                finding.pop("crop_image_path", None)
        return {"ejecucion_id": case.id, "estado": case.state, "etapa": case.stage, "detecciones": copy.deepcopy(case.detections), "analisis": analysis, "resultado": copy.deepcopy(case.result), "error": copy.deepcopy(case.error)}

    def get(self, case_id):
        with self.lock:
            return self.snapshot(self._case(case_id))

    def download(self, case_id):
        with self.lock:
            case = self._case(case_id)
            if case.state != "completada":
                raise FlowError("ESTADO_INVALIDO", "El informe aún no está disponible.", status=409)
            return case.result["markdown"].encode("utf-8")

    def delete(self, case_id):
        with self.lock:
            case = self._case(case_id)
            if case.state in ACTIVE:
                raise FlowError("ESTADO_INVALIDO", "El caso sigue trabajando y todavía no se puede descartar.", status=409)
            self._remove(case)

    def discard_retained(self):
        """Descarta los casos terminados; las consultas activas siguen su curso."""
        with self.lock:
            discarded = []
            for case in list(self.cases.values()):
                if case.state not in ACTIVE:
                    discarded.append(case.id)
                    self._remove(case)
            return {"descartados": discarded, "en_curso": len(self.cases)}

    def close(self):
        self.executor.shutdown(wait=True)
        with self.lock:
            for case in list(self.cases.values()):
                self._remove(case)
        if not any(self.root.iterdir()):
            self.root.rmdir()
