"""TDD for specs/32-rag-normativa.md AC-006/007/008 and spec 97 AC-006."""

from __future__ import annotations

import copy
import importlib
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# La composición simula todas las consultas. Permitir ejecutar estas pruebas
# unitarias mínimas sin instalar el driver, que solo hace falta para PostgreSQL.
try:
    import psycopg  # noqa: F401
except ModuleNotFoundError:
    psycopg_falso = types.ModuleType("psycopg")
    psycopg_falso.OperationalError = type("OperationalError", (Exception,), {})
    psycopg_falso.InterfaceError = type("InterfaceError", (Exception,), {})
    psycopg_falso.errors = types.SimpleNamespace(**{
        name: type(name, (Exception,), {})
        for name in ("UndefinedTable", "InvalidSchemaName", "UndefinedColumn", "UndefinedFunction")
    })
    sys.modules["psycopg"] = psycopg_falso


def _hallazgo(fid: str, pieza: str) -> dict:
    return {
        "finding_id": fid,
        "category": "damage",
        "clase_tool": "dent",
        "confidence_tier": "confirmed",
        "vision_verdict": "confirmado",
        "pieza_id": pieza,
        "severidad": "grave",
        "regla_coste_aplicable": True,
    }


def _escenario(ids: list[str], motivo: str, *, perdida_total: bool = False) -> dict:
    return {
        "hallazgos_incluidos": ids,
        "estimacion": {"total_con_iva_eur": 300.0},
        "cobertura": {
            "cubierto": not motivo.startswith("Póliza sin cobertura"),
            "motivo": motivo,
            "franquicia_eur": 100.0,
            "perdida_total": perdida_total,
            "indemnizacion_estimada_eur": 200.0 if not motivo.startswith("Póliza sin cobertura") else 0.0,
        },
    }


def _base(contexto: dict, confirmados: dict, con_pendientes: dict) -> dict:
    return {
        "image_id": 7,
        "contexto": copy.deepcopy(contexto),
        "valor_venal_eur": 10_000.0,
        "umbral_perdida_total": 0.75,
        "escenarios": {"confirmados": confirmados, "con_pendientes": con_pendientes},
        "hallazgos_fuera_del_coste": [],
        "normativa": [],
    }


class ClienteFalso:
    def __init__(self):
        self.mensajes = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, *, model, messages, **kwargs):
        self.mensajes.append({"model": model, "messages": messages, "kwargs": kwargs})
        entrada = json.loads(messages[-1]["content"])
        extracto = entrada["pasajes"][0]
        cuerpo = json.dumps({"texto": "La fuente describe las condiciones del tema.", "citas": [extracto]}, ensure_ascii=False)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=cuerpo))],
            usage=None,
        )


class Agente2Tests(unittest.TestCase):
    def _modulo(self):
        spec = importlib.util.find_spec("agente2")
        self.assertIsNotNone(spec, "AC-006: falta la composición pública agente2() de la slice 3")
        return importlib.import_module("agente2")

    def _llamar(self, base: dict, a1: dict, contexto: dict, buscar):
        agente2 = self._modulo()
        cliente = ClienteFalso()
        with tempfile.TemporaryDirectory() as cache:
            with patch.object(agente2, "estimar_siniestro", return_value=copy.deepcopy(base)) as coste:
                with patch.object(agente2, "buscar_normativa", side_effect=buscar) as rag:
                    resultado = agente2.agente2(
                        a1,
                        contexto,
                        cliente=cliente,
                        modelo="modelo-falso",
                        autorizado=True,
                        cache_dir=cache,
                    )
        return resultado, cliente, coste, rag

    def test_spec32_ac006_spec97_ac006_conserva_salida_y_no_justifica_tema_vacio(self):
        """AC-006: tres temas RAG, uno vacío; no altera cálculo/entradas y no llama al LLM sin pasajes."""
        contexto = {"rol": "propio", "poliza_id": "POLIZA-1"}
        hallazgos = [_hallazgo("F1", "PUERTA_DEL_I"), _hallazgo("F2", "PARABRISAS")]
        a1 = {"image_id": 7, "findings": hallazgos}
        base = _base(
            contexto,
            _escenario(["F1"], "Daños propios por colisión"),
            _escenario(["F1", "F2"], "Pérdida total", perdida_total=True),
        )
        entradas_antes = copy.deepcopy((a1, contexto))
        consultas = []

        def buscar(tema, *, k, poliza_id):
            consultas.append((tema, k, poliza_id))
            if "pérdida total" in tema.lower():
                return []
            return [{"tema": tema, "extracto": f"Cláusula literal: {tema}.", "fuente": "polizas/POLIZA-1.md#2"}]

        resultado, cliente, coste, rag = self._llamar(base, a1, contexto, buscar)
        self.assertEqual(coste.call_count, 1)
        self.assertEqual(rag.call_count, 3)
        self.assertEqual({poliza for _, _, poliza in consultas}, {"POLIZA-1"})
        self.assertEqual({k for _, k, _ in consultas}, {4})
        self.assertEqual(len(resultado["normativa"]), 2)
        self.assertEqual(len(cliente.mensajes), 2, "el tema sin pasajes no debe llamar al modelo")
        self.assertEqual([j["estado"] for j in resultado["justificaciones"]], ["generada", "generada"])
        self.assertEqual(resultado["diagnostico_rag"]["estado"], "parcial")
        for key, value in base.items():
            if key != "normativa":
                self.assertEqual(resultado[key], value, f"AC-006: cambió el campo original {key}")
        self.assertEqual((a1, contexto), entradas_antes, "AC-006: se mutaron entradas")

    def test_spec32_ac007_cristal_por_pieza_o_resultado_y_sin_cobertura(self):
        """AC-007: lunas por pieza o motivo; explicar la póliza incluso con cubierto=false e indemnización cero."""
        contexto = {"rol": "propio", "poliza_id": "POLIZA-SIN-LUNAS"}
        a1 = {"image_id": 7, "findings": [_hallazgo("F1", "PARABRISAS")]}
        no_danos = _escenario([], "Sin daños presupuestables")
        sin_cobertura = _escenario(["F1"], "Póliza sin cobertura de daños propios para este siniestro")
        base = _base(contexto, no_danos, sin_cobertura)
        consultas = []

        def buscar(tema, *, k, poliza_id):
            consultas.append((tema.lower(), poliza_id))
            return []

        resultado, cliente, _, _ = self._llamar(base, a1, contexto, buscar)
        temas = [tema for tema, _ in consultas]
        self.assertTrue(any("luna" in tema or "cristal" in tema for tema in temas), temas)
        self.assertTrue(any("sin cobertura" in tema or "cobertura de daños propios" in tema for tema in temas), temas)
        self.assertTrue(all(poliza == "POLIZA-SIN-LUNAS" for _, poliza in consultas))
        self.assertEqual(resultado["diagnostico_rag"]["estado"], "sin_resultados")
        self.assertNotEqual(resultado["diagnostico_rag"]["estado"], "no_aplica")
        self.assertEqual(cliente.mensajes, [])

    def test_spec32_ac007_cristal_por_resultado_aunque_la_pieza_no_sea_cristal(self):
        """AC-007: `Cobertura de lunas` activa la consulta aunque la pieza no sea de cristal."""
        contexto = {"rol": "propio", "poliza_id": "POLIZA-1"}
        a1 = {"image_id": 7, "findings": [_hallazgo("F1", "PUERTA_DEL_I")]}
        sin_danos = _escenario([], "Sin daños presupuestables")
        motivo_lunas = _escenario(["F1"], "Cobertura de lunas")
        base = _base(contexto, sin_danos, motivo_lunas)
        consultas = []

        resultado, _, _, _ = self._llamar(
            base, a1, contexto,
            lambda tema, *, k, poliza_id: consultas.append(tema) or [],
        )
        self.assertTrue(any("cristal" in tema.lower() for tema in consultas), consultas)
        self.assertEqual(len(consultas), len(resultado["diagnostico_rag"]["consultas"]))

    def test_spec32_ac007_union_deduplica_y_tercero_usa_solo_legislacion(self):
        """AC-007: ambos escenarios comparten colisión; tercero consulta legislación con póliza vacía."""
        contexto = {"rol": "tercero_perjudicado", "poliza_id": "RESIDUAL-IGNORADO"}
        a1 = {"image_id": 7, "findings": [_hallazgo("F1", "PUERTA_DEL_I")]}
        base = _base(
            contexto,
            _escenario(["F1"], "Daños a tercero: RC obligatoria (acción directa, LRCSCVM art. 7)"),
            _escenario(["F1"], "Daños a tercero: RC obligatoria (acción directa, LRCSCVM art. 7)"),
        )
        consultas = []

        def buscar(tema, *, k, poliza_id):
            consultas.append((tema.lower(), poliza_id))
            return [{"tema": tema, "extracto": "La ley establece la responsabilidad civil.", "fuente": "legal/ley.txt#art-7"}]

        resultado, _, _, _ = self._llamar(base, a1, contexto, buscar)
        self.assertEqual(len(consultas), 1, "la unión debe deduplicar temas compartidos")
        self.assertEqual(consultas[0][1], "", "tercero debe omitir el ID residual de póliza")
        self.assertIn("responsabilidad civil", consultas[0][0])
        self.assertEqual(resultado["diagnostico_rag"]["estado"], "recuperadas")

    def test_spec32_ac007_sin_danos_no_fuerza_consulta(self):
        """AC-007/008: dos escenarios sin hallazgos producen no_aplica y cero llamadas."""
        contexto = {"rol": "propio", "poliza_id": "POLIZA-1"}
        a1 = {"image_id": 7, "findings": []}
        base = _base(contexto, _escenario([], "Sin daños presupuestables"), _escenario([], "Sin daños presupuestables"))
        resultado, cliente, _, rag = self._llamar(base, a1, contexto, lambda *args, **kwargs: self.fail("no debe consultar RAG"))
        self.assertEqual(rag.call_count, 0)
        self.assertEqual(cliente.mensajes, [])
        self.assertEqual(resultado["diagnostico_rag"], {"estado": "no_aplica", "consultas": []})
        self.assertEqual(resultado["justificaciones"], [])

    def test_spec32_ac008_error_por_tema_agrega_error_sin_ocultar_incidentes(self):
        """AC-008: una RagError por consulta conserva código/etapa y agrega error si ninguna recupera."""
        from normativa_rag import RagError

        contexto = {"rol": "propio", "poliza_id": "POLIZA-1"}
        a1 = {"image_id": 7, "findings": [_hallazgo("F1", "PUERTA_DEL_I")]}
        base = _base(contexto, _escenario(["F1"], "Daños propios por colisión"), _escenario(["F1"], "Daños propios por colisión"))

        def buscar(tema, *, k, poliza_id):
            raise RagError("BD_NO_DISPONIBLE", "No se ha podido consultar", stage="base_datos", retryable=True)

        resultado, cliente, _, rag = self._llamar(base, a1, contexto, buscar)
        self.assertEqual(rag.call_count, 1, "tema compartido consultado una vez")
        self.assertEqual(resultado["diagnostico_rag"]["estado"], "error")
        consulta = resultado["diagnostico_rag"]["consultas"][0]
        self.assertEqual(consulta["estado"], "error")
        self.assertEqual(consulta["incidencias"][0], {
            "codigo": "BD_NO_DISPONIBLE",
            "etapa": "base_datos",
            "mensaje": "No se ha podido consultar",
            "reintentable": True,
        })
        self.assertEqual(cliente.mensajes, [])
        self.assertEqual(resultado["justificaciones"], [])

    def test_spec32_ac007_error_inesperado_de_costes_se_propaga_sin_buscar(self):
        """AC-007: no se oculta un error inesperado de costes ni se inicia el RAG."""
        agente2 = self._modulo()
        contexto = {"rol": "propio", "poliza_id": "POLIZA-1"}
        a1 = {"image_id": 7, "findings": []}
        with patch.object(agente2, "estimar_siniestro", side_effect=RuntimeError("coste inválido")):
            with patch.object(agente2, "buscar_normativa") as buscar:
                with self.assertRaisesRegex(RuntimeError, "coste inválido"):
                    agente2.agente2(a1, contexto, cliente=ClienteFalso(), modelo="m", autorizado=True)
        buscar.assert_not_called()

    def test_spec32_ac007_error_inesperado_de_rag_se_propaga(self):
        """AC-007: los fallos inesperados del RAG se propagan; solo RagError es recuperable."""
        agente2 = self._modulo()
        contexto = {"rol": "propio", "poliza_id": "POLIZA-1"}
        a1 = {"image_id": 7, "findings": [_hallazgo("F1", "PUERTA_DEL_I")]}
        base = _base(contexto, _escenario(["F1"], "Daños propios por colisión"),
                      _escenario([], "Sin daños presupuestables"))
        with patch.object(agente2, "estimar_siniestro", return_value=base):
            with patch.object(agente2, "buscar_normativa", side_effect=RuntimeError("fallo interno")):
                with self.assertRaisesRegex(RuntimeError, "fallo interno"):
                    agente2.agente2(a1, contexto, cliente=ClienteFalso(), modelo="m", autorizado=True)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Agente2Tests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
