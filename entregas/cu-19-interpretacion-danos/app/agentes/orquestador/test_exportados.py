"""#34 complemento UI v2, AC-016/017/018.
https://github.com/lvckss/piia2-26/issues/34#issuecomment-7138654855
"""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from pipeline import ProductionPipeline
from servidor import create_app
from workflow import Workflow


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.exports, self.images = root / "exports", root / "images"
        self.exports.mkdir()
        original = self.images / "test/fullsize/000082.png"
        original.parent.mkdir(parents=True)
        Image.new("RGB", (40, 30), "white").save(original)
        self.data = original.read_bytes()
        self.document = {"image_id": 82, "image_file": "000082.png", "image_width": 40, "image_height": 30, "split": "test", "strategy_name": "baseline_prompt", "image_path": "/content/drive/private/image.png", "predictions": [
            {"instance_index": 4, "damage_class": "dent", "score": .73, "bbox_xywh": [1, 2, 3, 4], "is_true_positive": False},
            {"instance_index": 7, "damage_class": "scratch", "score": .46, "bbox_xywh": [2, 1, 4, 3], "is_true_positive": True},
        ]}
        (self.exports / "000082.json").write_text(json.dumps(self.document))
        (self.exports / "_manifest.json").write_text(json.dumps({"image_ids": [82]}))
        self.env = patch.dict("os.environ", {"PERITAJE_DETECTION_SOURCE": "export", "PERITAJE_EXPORT_DIR": str(self.exports), "PERITAJE_DATASET_DIR": str(self.images)})
        self.env.start()
        self.pipeline = ProductionPipeline()
        self.flow = Workflow(self.pipeline, root=root / "cases")
        self.client = TestClient(create_app(self.flow), raise_server_exceptions=False)
        self.inputs = []
        def analyze(path, _folder):
            document = json.loads(path.read_text())
            self.inputs.append(document)
            return {"image_id": document["image_id"], "findings": [], "vehiculo": {"categoria": "C", "vehiculo_id_referencia": "V02"}}
        self.vision = patch.object(self.pipeline, "analyze", side_effect=analyze).start()
        self.ml = patch.object(self.pipeline, "detect", side_effect=AssertionError("No debe ejecutarse ML")).start()

    def tearDown(self):
        self.flow.close()
        patch.stopall()
        self.temp.cleanup()

    def send(self, data=None, name="000082.png"):
        return self.client.post("/peritajes", files={"file": (name, data if data is not None else self.data, "image/png")}, headers={"Idempotency-Key": "document"})

    def test_ac016_reads_export_without_ml_and_preserves_predictions(self):
        response = self.send()
        self.assertEqual(response.status_code, 202, response.text)
        case_id = response.json()["ejecucion_id"]
        self.flow.cases[case_id].future.result(5)
        state = self.flow.get(case_id)
        self.assertEqual(state["estado"], "esperando_datos", state)
        self.ml.assert_not_called()
        self.assertEqual(state["analisis"]["image_id"], 82)
        self.assertNotEqual(case_id, "82")
        self.assertEqual([f["instance_index"] for f in self.inputs[0]["predictions"]], [4, 7])
        self.assertEqual([f["score"] for f in self.inputs[0]["predictions"]], [.73, .46])
        self.assertEqual(self.inputs[0]["predictions"][0]["bbox_xywh"], [1, 2, 3, 4])
        self.assertNotIn("is_true_positive", self.inputs[0]["predictions"][0])
        self.assertNotIn("/content/drive", json.dumps(self.inputs[0]))

    def test_ac016_wrong_photo_with_same_filename_rejected_before_vision(self):
        stream = io.BytesIO(); Image.new("RGB", (40, 30), "black").save(stream, "PNG")
        response = self.send(stream.getvalue())
        self.assertEqual(response.status_code, 422, response.text)
        self.vision.assert_not_called(); self.ml.assert_not_called()

    def test_ac016_missing_document_rejected_without_ml(self):
        response = self.send(name="000009.png")
        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn("documento", response.json()["error"]["mensaje"])
        self.vision.assert_not_called(); self.ml.assert_not_called()

    def test_ac017_catalogue_only_exposes_available_export_images(self):
        result = self.client.get("/catalogos").json()
        self.assertEqual(result["fuente_detecciones"], "documentos")
        self.assertEqual([i["file_name"] for i in result["imagenes_exportadas"]], ["000082.png"])
        self.assertNotIn(self.temp.name, json.dumps(result))
        self.assertNotIn("/content/drive", json.dumps(result))
        self.vision.assert_not_called(); self.ml.assert_not_called()

    def test_ac018_report_keeps_document_id_and_download_bytes(self):
        case_id = self.send().json()["ejecucion_id"]
        self.flow.cases[case_id].future.result(5)
        body = {"contexto": {"vehiculo_id": "V02", "edad_anios": 5, "km": 60000, "region": "Madrid", "tipo_taller": "multimarca", "tipo_pieza": "oem", "acabado": "solido", "rol": "propio", "poliza_id": "P-TERC-BASICO"}, "seleccion_vehiculo": {"tipo": "referencia_confirmada", "vehiculo_id": "V02"}}
        with patch("agente2.buscar_normativa", return_value=[]):
            response = self.client.post(f"/peritajes/{case_id}/informe", json=body, headers={"Idempotency-Key": "report"})
            self.assertEqual(response.status_code, 202, response.text)
            self.flow.cases[case_id].future.result(5)
        state = self.flow.get(case_id)
        self.assertEqual(state["estado"], "completada", state)
        self.assertEqual(state["resultado"]["agente2"]["image_id"], 82)
        self.assertIn("imagen 82", state["resultado"]["markdown"])
        self.assertEqual(self.flow.download(case_id), state["resultado"]["markdown"].encode())
        self.ml.assert_not_called()

    def test_ac016_invalid_geometry_stops_before_vision(self):
        self.pipeline.archive.records["000082.png"]["predictions"][0]["bbox_xywh"] = [0, 0, 999, 999]
        response = self.send()
        self.assertEqual(response.status_code, 502, response.text)
        self.assertEqual(response.json()["error"]["codigo"], "CONTRATO_INVALIDO")
        self.vision.assert_not_called(); self.ml.assert_not_called()


if __name__ == "__main__":
    unittest.main()
