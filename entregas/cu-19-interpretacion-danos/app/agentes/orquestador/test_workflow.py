"""Spec 34 v1.7 AC-001–012: HTTP real con proveedores inyectados, sin gasto.

Los costes y el informe del smoke usan los agentes reales y datos locales.
"""
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from pipeline import ProductionPipeline
from servidor import create_app
from workflow import FlowError, Workflow, adapt_detection, normalize_image


def image_bytes():
    stream = io.BytesIO()
    Image.new("RGB", (40, 30), "white").save(stream, "PNG")
    return stream.getvalue()


class Pipeline(ProductionPipeline):
    def __init__(self):
        self.calls = []
        self.bad_numbers = False
        self.gate = None
        self.category = "C"
        self.detections = []

    def preflight(self):
        pass

    def detect(self, path):
        self.calls.append("detector")
        if self.gate:
            self.gate.wait(3)
        with Image.open(path) as image:
            assert image.size == (40, 30) and image.format == "PNG"
        return {"vehicle_damage_assessment": self.detections}

    def analyze(self, detection, folder):
        self.calls.append("vision")
        from hallazgos import construir_hallazgos
        result = construir_hallazgos(json.loads(detection.read_text()))
        for finding in result["findings"]:
            finding.update(vision_verdict="confirmado", confidence_tier="confirmed", pieza_id="CAPO", severidad="leve", regla_coste_aplicable=True, vision_description="Abolladura del capó.", crop_image_path=str(folder / "crop.png"))
        result["vehiculo"] = {"categoria": self.category, "vehiculo_id_referencia": "V02" if self.category == "C" else None}
        return result

    def costs(self, analysis, context, folder):
        self.calls.append("costes")
        with patch("agente2.buscar_normativa", return_value=[]):
            from agente2 import agente2
            return agente2(analysis, context, autorizado=False, cache_dir=folder / "cache")

    def report(self, *args):
        self.calls.append("informe")
        return super().report(*args) + ("\n999999999999,00 €" if self.bad_numbers else "")

    def verify(self, *args):
        self.calls.append("verificacion")
        return super().verify(*args)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = Pipeline()
        self.temp = tempfile.TemporaryDirectory()
        self.now = 100
        self.flow = Workflow(self.pipeline, root=Path(self.temp.name) / "cases", clock=lambda: self.now)

    def tearDown(self):
        if self.pipeline.gate:
            self.pipeline.gate.set()
        self.flow.close()
        self.temp.cleanup()

    def create(self, key="imagen"):
        result = self.flow.create(image_bytes(), "image/png", key)
        self.flow.cases[result["ejecucion_id"]].future.result(5)
        return result["ejecucion_id"]

    def body(self, **changes):
        context = {"vehiculo_id": "V02", "region": "Madrid", "tipo_taller": "multimarca", "acabado": "solido", "tipo_pieza": "oem", "rol": "propio", "edad_anios": 5, "km": 60000, "poliza_id": "P-TERC-BASICO"}
        context.update(changes)
        return {"contexto": context, "seleccion_vehiculo": {"tipo": "referencia_confirmada", "vehiculo_id": "V02"}}

    def test_ac005_007_009_real_costs_report_and_exact_download(self):
        case_id = self.create()
        self.assertEqual(self.pipeline.calls, ["detector", "vision"])
        self.flow.generate(case_id, self.body(), "informe")
        self.flow.cases[case_id].future.result(5)
        result = self.flow.get(case_id)
        self.assertEqual(result["estado"], "completada", result)
        self.assertEqual(result["resultado"]["procedencia"], "referencia_confirmada")
        self.assertEqual(self.flow.download(case_id), result["resultado"]["markdown"].encode("utf-8"))
        self.assertEqual(self.pipeline.calls, ["detector", "vision", "costes", "informe", "verificacion"])
        self.assertEqual(result["resultado"]["agente2"]["escenarios"]["confirmados"]["estimacion"]["total_con_iva_eur"], 0)

    def test_ac019_candidate_boxes_available_while_vision_is_running(self):
        """#34 UI v4 AC-019: vista previa sin veredictos, rutas ni otra inferencia."""
        self.pipeline.detections = [
            {"damage_class": "dent", "score": .9, "bbox": {"x": 1, "y": 2, "width": 3, "height": 4}},
            {"damage_class": "glass shatter", "score": .001, "bbox": {"x": 2, "y": 1, "width": 4, "height": 3}},
        ]
        started, release = threading.Event(), threading.Event()
        original = self.pipeline.analyze
        def blocked(*args):
            started.set()
            release.wait(5)
            return original(*args)
        with patch.object(self.pipeline, "analyze", side_effect=blocked) as vision:
            case_id = self.flow.create(image_bytes(), "image/png", "preview")["ejecucion_id"]
            try:
                self.assertTrue(started.wait(2))
                state = self.flow.get(case_id)
                self.assertEqual(state["estado"], "analizando")
                self.assertIsNone(state["analisis"])
                preview = state.get("detecciones")
                self.assertIsNotNone(preview)
                self.assertEqual((preview["image_width"], preview["image_height"]), (40, 30))
                self.assertEqual(preview["findings"], [{"finding_id": f"{case_id}-1", "category": "dent", "score": .9, "bbox_xywh": [1, 2, 3, 4]}])
                self.assertNotIn(self.temp.name, json.dumps(preview))
                for _ in range(3):
                    self.flow.get(case_id)
                self.assertEqual(vision.call_count, 1)
                self.assertEqual(self.pipeline.calls, ["detector"])
            finally:
                release.set()
                self.flow.cases[case_id].future.result(5)
        self.assertEqual(self.flow.get(case_id)["estado"], "esperando_datos")

    def test_ac001_invalid_before_any_provider(self):
        for data, mime in ((b"", "image/png"), (b"text", "image/png"), (image_bytes(), "text/plain")):
            with self.assertRaises(FlowError):
                self.flow.create(data, mime, "invalid")
        self.assertEqual(self.pipeline.calls, [])
        with self.assertRaises(FlowError) as error:
            normalize_image(b"x" * (10 * 1024 * 1024 + 1), "image/png")
        self.assertEqual(error.exception.status, 413)

    def test_ac005_006_real_nonzero_costs_and_no_host_paths(self):
        self.pipeline.detections = [{"damage_class": "dent", "score": .9, "bbox": {"x": 1, "y": 2, "width": 3, "height": 4}}]
        case_id = self.create()
        analysis = self.flow.get(case_id)["analisis"]
        self.assertNotIn("crop_image_path", analysis["findings"][0])
        self.flow.generate(case_id, self.body(), "nonzero")
        self.flow.cases[case_id].future.result(5)
        result = self.flow.get(case_id)
        self.assertEqual(result["estado"], "completada", result)
        costs = result["resultado"]["agente2"]
        self.assertGreater(costs["escenarios"]["confirmados"]["estimacion"]["total_con_iva_eur"], 0)
        self.assertEqual(self.pipeline.verify(result["resultado"]["markdown"], costs), [])
        self.assertNotIn(self.temp.name, json.dumps(result))

    def test_ac002_preserves_detection_and_rejects_geometry(self):
        item = {"damage_class": "dent", "score": 0.6234, "bbox": {"x": 1, "y": 2, "width": 3, "height": 4}}
        result = adapt_detection({"vehicle_damage_assessment": [item, item]}, "case", Path("image"), (40, 30))
        self.assertEqual([p["instance_index"] for p in result["predictions"]], [1, 2])
        self.assertEqual(result["predictions"][0]["bbox_xywh"], [1, 2, 3, 4])
        self.assertEqual(result["predictions"][0]["score"], 0.6234)
        item["bbox"]["width"] = 999
        with self.assertRaises(FlowError):
            adapt_detection({"vehicle_damage_assessment": [item]}, "case", Path("image"), (40, 30))

    def test_ac004_rejected_context_keeps_analysis_and_key_reusable(self):
        case_id = self.create()
        with self.assertRaises(FlowError) as error:
            self.flow.generate(case_id, self.body(km=-1), "correctable")
        self.assertEqual(error.exception.status, 422)
        self.assertEqual(self.flow.get(case_id)["estado"], "esperando_datos")
        self.flow.generate(case_id, self.body(), "correctable")
        self.flow.cases[case_id].future.result(5)
        self.assertEqual(self.pipeline.calls.count("vision"), 1)

    def test_ac004_wrong_json_types_are_validation_errors(self):
        case_id = self.create()
        for field in ("vehiculo_id", "region", "tipo_taller", "acabado", "tipo_pieza", "rol", "poliza_id"):
            with self.subTest(field=field), self.assertRaises(FlowError) as error:
                self.flow.generate(case_id, self.body(**{field: []}), "invalid-types")
            self.assertEqual(error.exception.status, 422)
        self.assertEqual(self.pipeline.calls, ["detector", "vision"])

    def test_ac003_008_unknown_fallback_and_third_party(self):
        self.pipeline.category = "desconocido"
        case_id = self.create()
        body = self.body(vehiculo_id="V14", rol="tercero_perjudicado")
        body.pop("seleccion_vehiculo")
        self.flow.generate(case_id, body, "tercero")
        self.flow.cases[case_id].future.result(5)
        result = self.flow.get(case_id)
        self.assertEqual(result["estado"], "completada", result)
        context = result["resultado"]["agente2"]["contexto"]
        self.assertEqual(context["vehiculo_origen"], "minimo_por_defecto")
        self.assertNotIn("poliza_id", context)
        self.assertIn("Vehículo no identificado en la imagen", result["resultado"]["markdown"])

    def test_ac009_inconsistent_numbers_block_publication(self):
        self.pipeline.bad_numbers = True
        case_id = self.create()
        self.flow.generate(case_id, self.body(), "bad")
        self.flow.cases[case_id].future.result(5)
        result = self.flow.get(case_id)
        self.assertEqual(result["estado"], "error")
        self.assertEqual(result["error"]["codigo"], "CIFRAS_INCONSISTENTES")
        self.assertIsNone(result["resultado"])
        with self.assertRaises(FlowError):
            self.flow.download(case_id)

    def test_ac010_duplicate_requests_conflict_and_capacity(self):
        case_id = self.create()
        self.assertEqual(self.flow.create(image_bytes(), "image/png", "imagen")["ejecucion_id"], case_id)
        with self.assertRaises(FlowError) as conflict:
            self.flow.create(image_bytes() + b"changed", "image/png", "imagen")
        self.assertEqual(conflict.exception.status, 409)
        self.flow.generate(case_id, self.body(), "report")
        self.flow.generate(case_id, self.body(), "report")
        self.flow.cases[case_id].future.result(5)
        self.assertEqual(self.pipeline.calls.count("costes"), 1)
        self.create("second")
        with self.assertRaises(FlowError) as capacity:
            self.create("third")
        self.assertEqual(capacity.exception.public["codigo"], "CAPACIDAD_AGOTADA")
        self.assertEqual(self.pipeline.calls.count("detector"), 2)

    def test_ac012_polling_does_not_renew_ttl_and_discards_files(self):
        case_id = self.create()
        folder = self.flow.cases[case_id].folder
        self.now += 3599
        self.flow.get(case_id)
        self.now += 1
        with self.assertRaises(FlowError) as missing:
            self.flow.get(case_id)
        self.assertEqual(missing.exception.status, 404)
        self.assertFalse(folder.exists())
        self.assertEqual(self.flow.keys, {})

    def test_ac010_012_active_case_cannot_be_deleted_or_expired(self):
        self.pipeline.gate = threading.Event()
        case_id = self.flow.create(image_bytes(), "image/png", "busy")["ejecucion_id"]
        self.now += 3600
        self.assertEqual(self.flow.get(case_id)["estado"], "analizando")
        with self.assertRaises(FlowError) as busy:
            self.flow.delete(case_id)
        self.assertEqual(busy.exception.status, 409)
        self.pipeline.gate.set()

    def test_ac001_011_http_multipart_and_json_contract(self):
        client = TestClient(create_app(self.flow), raise_server_exceptions=False)
        response = client.post("/peritajes", files={"file": ("image.png", image_bytes(), "image/png")}, headers={"Idempotency-Key": "http"})
        self.assertEqual(response.status_code, 202, response.text)
        case_id = response.json()["ejecucion_id"]
        self.flow.cases[case_id].future.result(5)
        response = client.post(f"/peritajes/{case_id}/informe", json=self.body(km=-1), headers={"Idempotency-Key": "http-report"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(client.get(f"/peritajes/{case_id}").json()["estado"], "esperando_datos")
        response = client.post(f"/peritajes/{case_id}/informe", json=self.body(), headers={"Idempotency-Key": "http-report"})
        self.assertEqual(response.status_code, 202)
        self.flow.cases[case_id].future.result(5)
        state = client.get(f"/peritajes/{case_id}").json()
        self.assertEqual(state["estado"], "completada", state)
        self.assertEqual(client.get(f"/peritajes/{case_id}/informe.md").content, state["resultado"]["markdown"].encode())
        self.assertEqual(client.delete(f"/peritajes/{case_id}").status_code, 204)
        self.assertEqual(client.get(f"/peritajes/{case_id}").status_code, 404)


if __name__ == "__main__":
    unittest.main()
