"""Adaptadores de los proveedores reales; no altera umbrales ni cálculos."""
from __future__ import annotations

import copy
import csv
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from workflow import FlowError

AGENTS = Path(__file__).resolve().parent.parent
for component in ("agente_multimodal", "agente_recuperacion", "agente_redactor"):
    sys.path.insert(0, str(AGENTS / component))

from configuracion_rag import load_environment


class ProductionPipeline:
    def __init__(self):
        load_environment()
        mode = os.environ.get("PERITAJE_DETECTION_SOURCE", "api")
        if mode not in {"api", "export"}:
            raise FlowError("CONTRATO_INVALIDO", "PERITAJE_DETECTION_SOURCE debe ser api o export.", status=503)
        self.archive = None
        if mode == "export":
            from exportados import ExportStore
            self.archive = ExportStore(os.environ.get("PERITAJE_EXPORT_DIR", AGENTS.parent / "bd/subset_500"), os.environ.get("PERITAJE_DATASET_DIR", AGENTS.parent / "bd/clean_data"))

    def prepare(self, image, filename):
        archive = getattr(self, "archive", None)
        return archive.prepare(image, filename) if archive else None

    def preview(self, detection, size):
        """Solo datos de entrada ya disponibles, sin veredictos del modelo."""
        from hallazgos import construir_hallazgos
        candidates = construir_hallazgos(detection)["findings"]
        return {"image_width": size[0], "image_height": size[1], "findings": [
            {key: finding[key] for key in ("finding_id", "category", "score", "bbox_xywh")}
            for finding in candidates
        ]}

    def preflight(self):
        if not os.environ.get("OPENAI_API_KEY") or not os.environ.get("OPENAI_MODEL"):
            raise FlowError("VISION_NO_DISPONIBLE", "Falta configurar OPENAI_API_KEY u OPENAI_MODEL en el servidor.", stage="agente1", status=503)
        self.catalogues()

    def catalogues(self):
        from catalogo import cargar_catalogo
        # Reutiliza la resolución del paquete que utiliza el Agente 1.
        cargar_catalogo()
        from costes_y_cobertura import PAQUETE

        def rows(name):
            with (PAQUETE / "data" / name).open(encoding="utf-8-sig", newline="") as stream:
                return list(csv.DictReader(stream))

        def options(values):
            return [{"id": value, "nombre": value.replace("_", " ")} for value in sorted(set(values))]

        tariffs = rows("tarifas.csv")
        result = {
            "vehiculos": [{"id": v["vehiculo_id"], "nombre": f'{v["marca"]} {v["modelo"]}'} for v in rows("vehiculos.csv")],
            "polizas": [{"id": p["poliza_id"], "nombre": p["producto"]} for p in rows("polizas.csv")],
            "regiones": options(t["region"] for t in tariffs),
            "tipos_taller": options(t["tipo_taller"] for t in tariffs),
            "acabados": options(p["acabado"] for p in rows("pintura.csv")),
            "tipos_pieza": options(["oem", "aftermarket"]),
        }
        if getattr(self, "archive", None):
            result.update(fuente_detecciones="documentos", imagenes_exportadas=self.archive.catalogue())
        else:
            result["fuente_detecciones"] = "api"
        return result

    def detect(self, path):
        boundary = f"piia2-{uuid.uuid4().hex}"
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="imagen.png"\r\nContent-Type: image/png\r\n\r\n'.encode()
                + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode())
        url = os.environ.get("ML_API_URL", "http://127.0.0.1:8001").rstrip("/") + "/v1/damage-assessment"
        request = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        try:
            with urllib.request.urlopen(request, timeout=float(os.environ.get("ML_API_TIMEOUT", "180"))) as response:
                return json.load(response)
        except (TimeoutError, urllib.error.URLError) as exc:
            raise FlowError("ML_NO_DISPONIBLE", "No se pudo contactar con el detector de daños. Comprueba que la API ML esté iniciada.", stage="piia1", status=503, retryable=True) from exc

    def analyze(self, detection, folder):
        from agente1 import analizar_imagen, crear_cliente_openai
        try:
            with crear_cliente_openai() as client:
                return analizar_imagen(detection, client, folder / "crops", cache_dir=folder / "cache-vision")
        except Exception as exc:
            # Solo se muestra el identificador configurado, nunca la respuesta privada.
            if getattr(exc, "status_code", None) in (403, 404):
                raise FlowError("VISION_NO_DISPONIBLE", f'El proveedor no permite utilizar el modelo configurado ({os.environ["OPENAI_MODEL"]}). Revisa su disponibilidad en la cuenta.', stage="agente1", status=503) from exc
            if getattr(exc, "status_code", None) == 401:
                raise FlowError("VISION_NO_DISPONIBLE", "OpenAI rechaza la credencial configurada. Revisa OPENAI_API_KEY en el servidor.", stage="agente1", status=503) from exc
            raise

    def costs(self, analysis, context, folder):
        from agente2 import agente2
        return agente2(analysis, context, cache_dir=folder / "cache-rag")

    def report(self, analysis, costs, day):
        from informe import generar_informe
        # Los enlaces de recortes locales sirven a la CLI, no al navegador.
        # Conservar el original para los agentes y no publicar rutas del host.
        public = copy.deepcopy(analysis)
        for finding in public["findings"]:
            finding.pop("crop_image_path", None)
        return generar_informe(public, costs, hoy=day)

    def verify(self, markdown, costs):
        from informe import comprobar_cifras
        return comprobar_cifras(markdown, costs)
