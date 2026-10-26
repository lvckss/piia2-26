"""Plan: https://github.com/lvckss/piia2-26/issues/33#issuecomment-6289598174.

AC-002 y AC-003: estos controles locales no acreditan la llamada real a OpenAI.
"""

import os
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from probar_adk_openai import cargar_clave, comprobar_evidencia, ejecutar


def evidencia_correcta():
    return {
        "completed": True,
        "ejecuciones_tool": 1,
        "llamadas": [{"id": "call-1", "name": "importe_prueba", "args": {}}],
        "respuestas": [{"id": "call-1", "name": "importe_prueba", "response": {"result": '{"total": 1233.55}'}}],
        "final": '{"total": 1233.55}',
    }


class ComprobacionLocal(unittest.TestCase):
    def test_ac002_evidencia_completa_e_importe_exacto(self):
        comprobar_evidencia(evidencia_correcta())

    def test_ac002_resultado_con_envoltorio_publico_adk(self):
        e = evidencia_correcta()
        e["final"] = '{"result": "{\\"total\\": 1233.55}"}'
        comprobar_evidencia(e)

    def test_ac003_envoltorio_adk_no_oculta_resultados_invalidos(self):
        for texto in ['{"result": "{\\"total\\": 0}"}',
                      '{"result": "{\\"total\\": 1233.55}", "extra": 0}',
                      '{"result": "{\\"total\\": 0}", "result": "{\\"total\\": 1233.55}"}',
                      '{"result": "{\\"total\\": 0, \\"total\\": 1233.55}"}']:
            with self.subTest(texto=texto):
                e = evidencia_correcta()
                e["final"] = texto
                with self.assertRaises(ValueError):
                    comprobar_evidencia(e)

    def test_ac003_no_acredita_importe_sin_ejecutar_tool(self):
        for campo in ["ejecuciones_tool", "llamadas", "respuestas"]:
            with self.subTest(campo=campo):
                e = evidencia_correcta()
                e[campo] = 0 if campo == "ejecuciones_tool" else []
                with self.assertRaises(ValueError):
                    comprobar_evidencia(e)

    def test_ac003_no_acredita_importe_incorrecto_o_respuesta_ambigua(self):
        for texto in ['{"total": 1233.56}', '{"total": 1233.5501}', '{"total": true}',
                      '{"total": NaN}', '{"total": Infinity}', '{"total": "1233.55"}',
                      '{"total": 1233.55, "total": 0}', 'importe 1233.55', '', None]:
            with self.subTest(texto=texto):
                e = evidencia_correcta()
                e["final"] = texto
                with self.assertRaises(ValueError):
                    comprobar_evidencia(e)

    def test_ac003_no_acredita_run_incompleto_aunque_tenga_respuesta(self):
        e = evidencia_correcta()
        e["completed"] = False
        with self.assertRaises(ValueError):
            comprobar_evidencia(e)

    def test_ac003_no_acredita_respuesta_de_otra_llamada(self):
        e = evidencia_correcta()
        e["respuestas"][0]["id"] = "otra-llamada"
        with self.assertRaises(ValueError):
            comprobar_evidencia(e)

    def test_ac003_no_acredita_otra_tool_o_multiples_ejecuciones(self):
        e = evidencia_correcta()
        e["llamadas"][0]["name"] = "otra_tool"
        with self.assertRaises(ValueError):
            comprobar_evidencia(e)
        e = evidencia_correcta()
        e["ejecuciones_tool"] = 2
        with self.assertRaises(ValueError):
            comprobar_evidencia(e)

    def test_ac003_no_acredita_resultado_tool_modificado(self):
        e = evidencia_correcta()
        e["respuestas"][0]["response"]["result"] = '{"total": 0}'
        with self.assertRaises(ValueError):
            comprobar_evidencia(e)

    def test_ac003_sin_configuracion_falla_antes_de_red(self):
        with patch.dict(os.environ, {}, clear=True), tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                cargar_clave(Path(d) / "inexistente.env")

    def test_ac003_carga_solo_clave_sin_ejecutar_el_env(self):
        with patch.dict(os.environ, {}, clear=True), tempfile.TemporaryDirectory() as d:
            p = Path(d) / ".env"
            p.write_text('OPENAI_API_KEY="clave-ficticia"\nOPENAI_BASE_URL=https://otro.example\n')
            self.assertEqual(cargar_clave(p), "clave-ficticia")
            self.assertNotIn("OPENAI_BASE_URL", os.environ)

    def test_ac003_clave_vacia_no_es_configuracion_valida(self):
        with patch.dict(os.environ, {}, clear=True), tempfile.TemporaryDirectory() as d:
            p = Path(d) / ".env"
            p.write_text('OPENAI_API_KEY=""\n')
            with self.assertRaises(ValueError):
                cargar_clave(p)

    def test_ac003_cli_sin_clave_no_accede_a_red(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, str(Path(__file__).with_name("probar_adk_openai.py")),
                                "--ejecutar", "--env-file", str(Path(d) / "inexistente.env")],
                               env={}, capture_output=True, text=True, timeout=5)
        self.assertEqual(r.returncode, 1)
        informe = json.loads(r.stdout)
        self.assertFalse(informe["success"])
        self.assertFalse(informe["evidencia"]["registro_tool"])
        self.assertEqual(informe["evidencia"]["usage"], [])

    def test_ac003_cli_sin_autorizacion_explicita_no_ejecuta(self):
        r = subprocess.run([sys.executable, str(Path(__file__).with_name("probar_adk_openai.py"))],
                           env={}, capture_output=True, text=True, timeout=5)
        self.assertEqual(r.returncode, 2)


class RecorridoNativoSinRed(unittest.IsolatedAsyncioTestCase):
    """AC-001/002/003: ADK y LiteLLM reales, HTTP simulado; no acredita al proveedor."""

    async def recorrido(self, *, status=200, repetir_tool=False):
        import httpx

        self.peticiones = []

        async def responder(client, request, **kwargs):
            self.peticiones.append((str(request.url), json.loads(request.content)))
            if status != 200:
                return httpx.Response(status, json={"error": {"message": "Control local",
                                      "type": "rate_limit_error"}}, request=request)
            n = len(self.peticiones)
            salida = ([{"type": "function_call", "id": f"fc_{n}", "call_id": f"call-{n}",
                        "name": "importe_prueba", "arguments": "{}", "status": "completed"}]
                      if n == 1 or repetir_tool else
                      [{"type": "message", "id": "msg_1", "role": "assistant", "status": "completed",
                        "content": [{"type": "output_text", "text": '{"total":1233.55}', "annotations": []}]}])
            return httpx.Response(200, json={"id": f"resp_local_{n}", "object": "response",
                                  "created_at": 0, "status": "completed", "model": "gpt-6.1-sol",
                                  "output": salida, "usage": {"input_tokens": 10,
                                  "output_tokens": 5, "total_tokens": 15}}, request=request)

        self.evidencia = {"completed": False, "registro_tool": False, "ejecuciones_tool": 0,
                          "llamadas": [], "respuestas": [], "final": None, "usage": []}
        with patch("httpx.AsyncClient.send", autospec=True, side_effect=responder):
            await asyncio.wait_for(ejecutar("clave-ficticia-no-real", self.evidencia), timeout=20)

    async def test_ac001_ac002_bridge_responses_tool_y_limites_efectivos(self):
        await self.recorrido()
        comprobar_evidencia(self.evidencia)
        self.assertEqual(len(self.peticiones), 2)
        for url, body in self.peticiones:
            self.assertEqual(url, "https://api.openai.com/v1/responses")
            self.assertEqual(body["model"], "gpt-6.1-sol")
            self.assertEqual(body["reasoning"]["effort"], "high")
            self.assertEqual(body["max_output_tokens"], 4096)
            self.assertEqual(len(body["tools"]), 1)

    async def test_ac003_429_no_se_reintenta_ni_es_exito(self):
        with self.assertRaises(ValueError):
            await self.recorrido(status=429)
        self.assertEqual(len(self.peticiones), 1)
        self.assertFalse(self.evidencia["completed"])
        self.assertEqual(self.evidencia["ejecuciones_tool"], 0)

    async def test_ac003_no_hay_tercera_llamada_aunque_modelo_pida_mas(self):
        with self.assertRaises(ValueError):
            await self.recorrido(repetir_tool=True)
        self.assertEqual(len(self.peticiones), 2)
        self.assertFalse(self.evidencia["completed"])


if __name__ == "__main__":
    unittest.main()
