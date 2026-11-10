"""Spec specs/32-rag-normativa.md, AC-002/003/004/005/012/013.

Deterministic retrieval tests: synthetic corpus, simulated embeddings, disposable DB.
"""

from dataclasses import replace
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch
import unittest

import psycopg

import normativa_rag as rag
from corpus_normativa import load_corpus
from embeddings_openai import OpenAIEmbeddings, SpendingBudget
import probar_indexado as index_tests
from probar_indexado import FakeEmbedder, run_postgres_tests


class SearchEmbedder(FakeEmbedder):
    def __init__(self, vector=None, error=None, callback=None):
        super().__init__()
        self.vector, self.error, self.callback = vector, error, callback

    def embed(self, texts, model):
        self.calls.append((tuple(texts), model))
        if self.callback:
            self.callback()
        if self.error:
            raise self.error
        return rag.EmbeddingBatch([self.vector if self.vector is not None else
                                  [1.0] + [0.0] * (model.dimensions - 1)], 1)


class PublicSearchTests(unittest.TestCase):
    def test_ac003_public_signature_and_delegation(self):
        self.assertTrue(callable(getattr(rag, "buscar_normativa", None)), "Falta buscar_normativa")
        self.assertEqual(str(inspect.signature(rag.buscar_normativa)), "(pregunta, k=4, poliza_id='')")
        with patch.object(rag, "_configured_search", return_value=[{"tema": "tema"}]) as configured:
            self.assertEqual(rag.buscar_normativa("tema", 2, "P-A"), [{"tema": "tema"}])
            configured.assert_called_once_with("tema", 2, "P-A")

    def test_ac004_invalid_inputs_fail_before_configuration_or_provider(self):
        self.assertTrue(callable(getattr(rag, "buscar_normativa", None)), "Falta buscar_normativa")
        cases = [("", 4, ""), ("  \n", 4, ""), (None, 4, ""), (1, 4, ""),
                 ("x", True, ""), ("x", 0, ""), ("x", -1, ""), ("x", 1.5, ""),
                 ("x", "4", ""), ("x", 4, None), ("x", 4, []), ("x", 4, "  ")]
        with patch.object(rag, "_configured_search") as configured:
            for args in cases:
                with self.subTest(args=args):
                    with self.assertRaises(rag.RagError) as caught:
                        rag.buscar_normativa(*args)
                    self.assertEqual((caught.exception.code, caught.exception.stage, caught.exception.retryable),
                                     ("ENTRADA_INVALIDA", "entrada", False))
            configured.assert_not_called()

    def test_ac012_query_command_is_offline_by_default(self):
        command = Path(__file__).with_name("consultar_normativa.py")
        self.assertTrue(command.exists(), "Falta el comando de consulta explícita")
        env = os.environ.copy()
        env["OPENAI_API_KEY"] = ""
        env["DATABASE_URL"] = "postgresql://invalid@127.0.0.1:1/unavailable"
        result = subprocess.run([sys.executable, str(command), "Cobertura", "--poliza-id", "P-A"],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["mode"], "plan")
        self.assertEqual(report["poliza_id"], "P-A")
        self.assertIn("estimated_query_cost_usd", report)
        self.assertNotIn("resultados", report)

    def test_ac012_query_execution_requires_explicit_budget(self):
        command = Path(__file__).with_name("consultar_normativa.py")
        self.assertTrue(command.exists(), "Falta el comando de consulta explícita")
        result = subprocess.run([sys.executable, str(command), "Cobertura", "--execute"],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("presupuesto", result.stderr)

    def test_ac012_function_requires_authorization_before_database_or_api(self):
        with patch("configuracion_rag.load_environment"), patch.object(rag.psycopg, "connect") as connect:
            for values in ({}, {"RAG_QUERY_EXECUTE": "1"},
                           {"RAG_QUERY_EXECUTE": "1", "RAG_QUERY_MAX_COST_USD": "nan"},
                           {"RAG_QUERY_EXECUTE": "1", "RAG_QUERY_MAX_COST_USD": "-1"}):
                with self.subTest(values=values), patch.dict(os.environ, values, clear=True):
                    with self.assertRaises(PermissionError):
                        rag.buscar_normativa("Pregunta")
            connect.assert_not_called()

    def test_ac005_unreachable_database_does_not_expose_connection_credentials(self):
        command = Path(__file__).with_name("consultar_normativa.py")
        env = {**os.environ, "DATABASE_URL": "postgresql://user:private_test_marker@127.0.0.1:1/unavailable", "OPENAI_API_KEY": ""}
        result = subprocess.run([sys.executable, str(command), "Pregunta", "--execute", "--max-cost-usd", "0"],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        error = json.loads(result.stderr)
        self.assertEqual((error["codigo"], error["etapa"], error["reintentable"]), ("BD_NO_DISPONIBLE", "base_datos", True))
        self.assertNotIn("private_test_marker", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


class ProviderErrorsTests(unittest.TestCase):
    def test_ac005_authentication_and_access_denied_are_typed(self):
        import httpx2
        import openai
        request = httpx2.Request("POST", "https://api.openai.com/v1/embeddings")
        for cls, status in ((openai.AuthenticationError, 401), (openai.PermissionDeniedError, 403)):
            error = cls("rechazado", response=httpx2.Response(status, request=request), body={})
            with self.subTest(status=status):
                with self.assertRaises(rag.RagError) as caught:
                    OpenAIEmbeddings(SpendingBudget(1), index_tests.FakeOpenAI(error=error)).embed(["x"], rag.MODELS["small"])
                self.assertEqual((caught.exception.code, caught.exception.stage, caught.exception.retryable),
                                 ("EMBEDDINGS_AUTENTICACION", "embeddings", False))

    def test_ac005_malformed_provider_fields_are_typed(self):
        for data in ([object()], [SimpleNamespace(index=0)], [SimpleNamespace(index=None, embedding=[]) ]):
            sdk = index_tests.FakeOpenAI()
            sdk.create = lambda **kwargs: SimpleNamespace(model=rag.MODELS["small"].name, data=data,
                                                         usage=SimpleNamespace(prompt_tokens=1))
            with self.subTest(data=data):
                with self.assertRaises(rag.RagError) as caught:
                    OpenAIEmbeddings(SpendingBudget(1), sdk).embed(["x"], rag.MODELS["small"])
                self.assertEqual(caught.exception.code, "EMBEDDINGS_RESPUESTA_INVALIDA")


@unittest.skipUnless(os.environ.get("RAG_TEST_DATABASE_URL"), "requires disposable RAG_TEST_DATABASE_URL")
class SearchTests(unittest.TestCase):
    # Reuse setup helpers, not the index tests themselves.
    setUp = index_tests.IndexTests.setUp

    def prepare_search(self, *, legal=True, model=None):
        for name in ("B", "C", "D"):
            (self.root / f"docs/polizas_sinteticas/P-{name}.md").write_text(
                f"# Producto {name}\n## 1. Cobertura\nCobertura propia {name}.\n")
        if not legal:
            (self.root / "docs/legal/ley.txt").unlink()
        self.corpus = load_corpus(self.root)
        model = model or rag.MODELS["small"]
        self.generation = self.store.index(self.corpus, model, FakeEmbedder(), execute=True)["generation"]
        return model

    def search(self, provider=None, model=None):
        self.assertTrue(hasattr(rag, "NormativaRetriever"), "Falta recuperación sobre el índice persistente")
        return rag.NormativaRetriever(self.connection, provider or SearchEmbedder(), model or rag.MODELS["small"])

    def assert_error(self, code, call, stage=None, retryable=False):
        with self.assertRaises(rag.RagError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(caught.exception.retryable, retryable)
        if stage:
            self.assertEqual(caught.exception.stage, stage)

    def test_ac003_literal_contract_cosine_order_tie_break_and_limit(self):
        model = self.prepare_search()
        fs = sorted(self.corpus.fragments, key=lambda f: f.id)
        # One winner aligned with the query and all other candidates orthogonal.
        winner = next(f for f in fs if f.document.kind == "legal")
        for f in fs:
            v = ([1.0, 0.0] if f == winner else [0.0, 1.0]) + [0.0] * (model.dimensions - 2)
            self.connection.execute("UPDATE rag.embeddings SET embedding=%s::vector WHERE input_hash=%s",
                                    (json.dumps(v), f.input_hash))
        search = self.search()
        result = search.search("Una pregunta", 100, "P-A")
        allowed = [f for f in fs if f.document.kind == "legal" or f.document.policy_id == "P-A"]
        expected = [winner] + [f for f in allowed if f != winner]
        self.assertEqual(result, [{"tema": "Una pregunta", "extracto": f.text, "fuente": f.source} for f in expected])
        self.assertEqual(search.search("Una pregunta", 2, "P-A"), result[:2])
        self.assertEqual(search.search("Una pregunta", 100, "P-A"), result)

    def test_ac004_all_four_policies_and_empty_filter_before_limit(self):
        self.prepare_search()
        search = self.search()
        by_source = {f.source: f for f in self.corpus.fragments}
        for policy in ("P-A", "P-B", "P-C", "P-D", ""):
            with self.subTest(policy=policy):
                result = search.search("Pregunta", 100, policy)
                expected = [f for f in self.corpus.fragments if f.document.kind == "legal" or
                            (policy and f.document.policy_id == policy)]
                self.assertEqual(len(result), len(expected))
                self.assertTrue(all(by_source[r["fuente"]] in expected for r in result))
                self.assertTrue(all(set(r) == {"tema", "extracto", "fuente"} for r in result))

    def test_ac004_unknown_policy_never_calls_provider(self):
        self.prepare_search()
        provider = SearchEmbedder()
        self.assert_error("ENTRADA_INVALIDA", lambda: self.search(provider).search("x", 4, "P-inexistente"), "entrada")
        self.assertEqual(provider.calls, [])

    def test_ac003_corrupted_passages_are_rejected_instead_of_cited(self):
        self.prepare_search()
        self.connection.execute("UPDATE rag.fragments SET body='Texto alterado' WHERE id=(SELECT min(id) FROM rag.fragments)")
        self.assert_error("INDICE_INCOMPATIBLE", lambda: self.search().search("x", 100, "P-A"))

    def test_ac004_query_exceeding_provider_limit_fails_before_paying(self):
        self.prepare_search()
        provider = SearchEmbedder()
        self.assert_error("ENTRADA_INVALIDA", lambda: self.search(provider).search("dato " * 9000), "entrada")
        self.assertEqual(provider.calls, [])

    def test_ac005_valid_search_without_candidates_returns_empty_without_provider(self):
        self.prepare_search(legal=False)
        provider = SearchEmbedder()
        self.assertEqual(self.search(provider).search("x"), [])
        self.assertEqual(provider.calls, [])

    def test_ac002_absent_schema_is_not_created_or_treated_as_empty(self):
        self.connection.execute("DROP SCHEMA rag CASCADE")
        provider = SearchEmbedder()
        self.assert_error("INDICE_NO_PREPARADO", lambda: self.search(provider).search("x"))
        self.assertEqual(provider.calls, [])
        self.assertIsNone(self.connection.execute("SELECT to_regnamespace('rag')").fetchone()[0])

    def test_ac002_missing_incomplete_or_incompatible_generation_never_pays(self):
        provider = SearchEmbedder()
        self.assert_error("INDICE_NO_PREPARADO", lambda: self.search(provider).search("x"))
        self.prepare_search()
        self.connection.execute("UPDATE rag.generations SET fragment_count=fragment_count+1")
        self.assert_error("INDICE_NO_PREPARADO", lambda: self.search(provider).search("x"))
        self.connection.execute("UPDATE rag.generations SET fragment_count=fragment_count-1,status='building'")
        self.assert_error("INDICE_NO_PREPARADO", lambda: self.search(provider).search("x"))
        self.connection.execute("UPDATE rag.generations SET status='ready',protocol='unsupported'")
        self.assert_error("INDICE_INCOMPATIBLE", lambda: self.search(provider).search("x"))
        self.assertEqual(provider.calls, [])

    def test_ac002_models_are_selected_separately(self):
        self.prepare_search()
        self.store.index(self.corpus, rag.MODELS["large"], FakeEmbedder(), execute=True)
        for model in rag.MODELS.values():
            provider = SearchEmbedder()
            self.assertTrue(self.search(provider, model).search("x"))
            self.assertEqual(provider.calls[0][1], model)
        self.assert_error("INDICE_INCOMPATIBLE", lambda: self.search(model=replace(rag.MODELS["small"], dimensions=3)).search("x"))

    def test_ac002_generation_is_pinned_if_index_changes_during_embedding(self):
        self.prepare_search()
        old_sources = {f.source for f in self.corpus.fragments if f.document.kind == "legal"}
        for path in (self.root / "docs/legal").glob("*.txt"):
            path.unlink()
        (self.root / "docs/legal/nueva.txt").write_text("Artículo 1.\nLegislación nueva.")
        changed = load_corpus(self.root)
        provider = SearchEmbedder(callback=lambda: self.store.index(changed, rag.MODELS["small"], FakeEmbedder(), execute=True))
        result = self.search(provider).search("x", 100)
        self.assertEqual({r["fuente"] for r in result}, old_sources)
        self.assertTrue(all(r["fuente"].startswith("docs/legal/nueva.txt#") for r in self.search().search("x", 100)))

    def test_ac005_each_typed_provider_error_is_preserved(self):
        self.prepare_search()
        for code, retry in [("EMBEDDINGS_AUTENTICACION", False), ("EMBEDDINGS_CUOTA", False),
                            ("EMBEDDINGS_LIMITE_TEMPORAL", True), ("EMBEDDINGS_TIMEOUT", True),
                            ("EMBEDDINGS_RESPUESTA_INVALIDA", False)]:
            error = rag.RagError(code, "Error simulado", stage="embeddings", retryable=retry)
            with self.subTest(code=code):
                with self.assertRaises(rag.RagError) as caught:
                    self.search(SearchEmbedder(error=error)).search("x")
                self.assertIs(caught.exception, error)
        with self.assertRaisesRegex(RuntimeError, "programación"):
            self.search(SearchEmbedder(error=RuntimeError("programación"))).search("x")

    def test_ac005_malformed_vectors_never_reach_cosine_query(self):
        self.prepare_search()
        for vector in ([], [1.0], [0.0] * 1536, [float("nan")] * 1536,
                       [float("inf")] * 1536, ["1"] * 1536, [True] * 1536):
            with self.subTest(kind=str(vector[:1])):
                self.assert_error("EMBEDDINGS_RESPUESTA_INVALIDA", lambda: self.search(SearchEmbedder(vector=vector)).search("x"), "embeddings")

    def test_ac005_database_unavailable_is_typed_and_not_empty(self):
        provider = SearchEmbedder()
        self.connection.close()
        self.assert_error("BD_NO_DISPONIBLE", lambda: self.search(provider).search("x"), "base_datos", True)
        self.assertEqual(provider.calls, [])


if __name__ == "__main__":
    if "--postgres" in sys.argv:
        raise SystemExit(run_postgres_tests(test_file=Path(__file__).resolve()))
    unittest.main()
