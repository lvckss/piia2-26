"""Spec specs/32-rag-normativa.md, AC-001/002/003/012/013.

Synthetic documents only; importing/running deterministic tests never calls OpenAI.
"""

import hashlib
from dataclasses import replace
import os
from pathlib import Path
import subprocess
import secrets
import socket
import sys
import tempfile
from types import SimpleNamespace
import unittest
from urllib.parse import quote
import uuid

import psycopg

from normativa_rag import EmbeddingBatch, IndexStore, MODELS, RagError
from embeddings_openai import OpenAIEmbeddings, SpendingBudget

from corpus_normativa import Document, fragment_document, load_corpus


def document(text, kind="legal"):
    path = "docs/legal/ley.txt" if kind == "legal" else "docs/polizas_sinteticas/P-A.md"
    return Document(path, text, kind, "P-A" if kind == "poliza" else None,
                    hashlib.sha256(text.encode()).hexdigest(), "Documento de prueba")


def write_corpus(root):
    for name, text in [
        ("docs/polizas_sinteticas/P-A.md", "# Producto A\nIntro.\n## 1. Cobertura\nCobertura de prueba.\n## 2. Franquicia\nFranquicia de prueba."),
        ("docs/legal/ley.txt", "Preámbulo.\nArtículo primero.\nNorma de prueba.\nArtículo 2 bis.\nOtra norma."),
    ]:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    (root / "preguntas_evaluacion.csv").write_text("respuesta_esperada\nGOLD_NO_INDEXABLE\n")


class CorpusTests(unittest.TestCase):
    def assert_literal(self, fragments):
        for f in fragments:
            self.assertEqual(f.text, f.document.text[f.start:f.end])
            self.assertTrue(f.text.strip())
            self.assertTrue(f.source.startswith(f.document.path + "#"))
            self.assertIn("L", f.source)
            self.assertIn(f.text, f.embedding_input)

    def test_ac001_policy_sections_and_preamble_keep_literal_text(self):
        text = "# Producto\nIntroducción.\n## 1. Cobertura\n  Texto literal.\n## 2. Exclusiones\nOtra regla.\n"
        fs = fragment_document(document(text, "poliza"))
        self.assertEqual(len(fs), 3)
        self.assertEqual([f.section for f in fs][1:], ["1. Cobertura", "2. Exclusiones"])
        self.assertEqual({f.document.policy_id for f in fs}, {"P-A"})
        self.assert_literal(fs)

    def test_ac001_legal_articles_in_words_numbers_and_repeated_headings(self):
        text = "Inicio.\nArtículo primero.\nUna norma.\nArtículo 2 bis.\nOtra norma.\nArtículo primero.\nRepetición."
        fs = fragment_document(document(text))
        self.assertEqual(len(fs), 4)
        self.assertEqual(fs[1].section, "Artículo primero.")
        self.assertEqual(fs[2].section, "Artículo 2 bis.")
        self.assertNotEqual(fs[1].source, fs[3].source)
        self.assert_literal(fs)

    def test_ac001_long_fallback_windows_cover_nonwhitespace_with_overlap(self):
        text = "Texto de norma áéí. " * 240
        fs = fragment_document(document(text))
        self.assertGreater(len(fs), 2)
        self.assertTrue(all(len(f.text) <= 1500 for f in fs))
        covered = set()
        for f in fs:
            covered.update(range(f.start, f.end))
        self.assertTrue(all(i in covered for i, c in enumerate(text) if not c.isspace()))
        self.assertTrue(all(a.end > b.start for a, b in zip(fs, fs[1:])))
        self.assert_literal(fs)

    def test_ac001_stable_hash_ids_and_no_evaluation_gold(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_corpus(root)
            first, second = load_corpus(root), load_corpus(root)
            self.assertEqual(len(first.documents), 2)
            self.assertGreater(len(first.fragments), 2)
            self.assertEqual(first, second)
            self.assertEqual(len(first.hash), 64)
            self.assertNotIn("GOLD_NO_INDEXABLE", "".join(f.embedding_input for f in first.fragments))
            self.assertEqual(len({f.id for f in first.fragments}), len(first.fragments))
            self.assert_literal(first.fragments)

    def test_ac002_removed_document_changes_manifest_and_new_fragment_set(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_corpus(root)
            first = load_corpus(root)
            (root / "docs/legal/ley.txt").unlink()
            second = load_corpus(root)
            self.assertNotEqual(first.hash, second.hash)
            self.assertEqual(len(second.documents), 1)
            self.assertTrue(all(f.document.kind == "poliza" for f in second.fragments))


class FakeEmbedder:
    def __init__(self, fail_after=None, bad_dimensions=False):
        self.calls = []
        self.fail_after = fail_after
        self.bad_dimensions = bad_dimensions

    def embed(self, texts, model):
        if self.fail_after is not None and len(self.calls) >= self.fail_after:
            raise RagError("EMBEDDINGS_TIMEOUT", "Timeout simulado", retryable=True)
        self.calls.append(tuple(texts))
        dimensions = model.dimensions - int(self.bad_dimensions)
        return EmbeddingBatch([[1.0] + [0.0] * (dimensions - 1) for _ in texts],
                              sum(len(t.split()) for t in texts), "fake-request")


class FakeOpenAI:
    def __init__(self, *, duplicate_index=False, error=None):
        self.calls, self.error, self.duplicate_index = [], error, duplicate_index
        self.embeddings = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        data = [SimpleNamespace(index=0 if self.duplicate_index else i,
                                embedding=[float(i+1)] + [0.0]*(kwargs["dimensions"]-1))
                for i in range(len(kwargs["input"]))]
        return SimpleNamespace(model=kwargs["model"], data=list(reversed(data)),
                               usage=SimpleNamespace(prompt_tokens=len(data)), _request_id="fake-sdk-request")


class OpenAIAdapterTests(unittest.TestCase):
    def test_ac012_total_budget_is_shared_by_models_and_checked_before_request(self):
        sdk = FakeOpenAI()
        client = OpenAIEmbeddings(SpendingBudget(0.0000001), sdk)
        client.embed(["x"], MODELS["small"])
        with self.assertRaises(PermissionError):
            client.embed(["x"], MODELS["large"])
        self.assertEqual(len(sdk.calls), 1)

    def test_ac002_response_order_and_duplicate_indices(self):
        client = OpenAIEmbeddings(SpendingBudget(5), FakeOpenAI())
        result = client.embed(["a", "b"], MODELS["small"])
        self.assertIsInstance(result, EmbeddingBatch)
        self.assertEqual([v[0] for v in result.vectors], [1.0,2.0])
        with self.assertRaises(RagError):
            OpenAIEmbeddings(SpendingBudget(5), FakeOpenAI(duplicate_index=True)).embed(["a","b"], MODELS["small"])

    def test_ac012_overlong_inputs_are_rejected_before_any_request(self):
        sdk = FakeOpenAI()
        with self.assertRaises(ValueError):
            OpenAIEmbeddings(SpendingBudget(5),sdk).embed(["dato "*9000],MODELS["small"])
        self.assertEqual(sdk.calls, [])

    def test_ac005_quota_rate_limit_and_timeout_are_distinct(self):
        import httpx2
        import openai
        request = httpx2.Request("POST", "https://api.openai.com/v1/embeddings")
        response = httpx2.Response(429,request=request)
        cases = [
            (openai.RateLimitError("quota",response=response,body={"code":"insufficient_quota"}),"EMBEDDINGS_CUOTA",False),
            (openai.RateLimitError("rate",response=response,body={"code":"rate_limit_exceeded"}),"EMBEDDINGS_LIMITE_TEMPORAL",True),
            (openai.APITimeoutError(request=request),"EMBEDDINGS_TIMEOUT",True),
        ]
        for error,code,retryable in cases:
            with self.subTest(code=code):
                with self.assertRaises(RagError) as caught:
                    OpenAIEmbeddings(SpendingBudget(5),FakeOpenAI(error=error)).embed(["x"],MODELS["small"])
                self.assertEqual(caught.exception.code,code)
                self.assertEqual(caught.exception.retryable,retryable)


class CommandTests(unittest.TestCase):
    def test_ac012_default_cli_is_offline_plan_without_key_or_database(self):
        with tempfile.TemporaryDirectory() as folder:
            write_corpus(Path(folder))
            env = os.environ.copy()
            env.pop("OPENAI_API_KEY",None)
            env["DATABASE_URL"] = "postgresql://invalid:invalid@127.0.0.1:1/unavailable"
            result = subprocess.run([sys.executable,str(Path(__file__).with_name("indexar_normativa.py")),
                "--package",folder,"--model","both"],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('"mode": "plan"',result.stdout)
            self.assertIn('"documents": 2',result.stdout)

    def test_ac012_execution_requires_an_explicit_budget(self):
        result = subprocess.run([sys.executable,str(Path(__file__).with_name("indexar_normativa.py")),
            "--execute"],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn("presupuesto",result.stderr)


@unittest.skipUnless(os.environ.get("RAG_TEST_DATABASE_URL"), "requires disposable RAG_TEST_DATABASE_URL")
class IndexTests(unittest.TestCase):
    def setUp(self):
        self.connection = psycopg.connect(os.environ["RAG_TEST_DATABASE_URL"], autocommit=True)
        self.addCleanup(self.connection.close)
        # Never run destructive setup against the actual application database.
        if not self.connection.execute("SELECT current_database()").fetchone()[0].startswith("cu19_test_rag"):
            self.fail("La conexión debe ser una base desechable cu19_test_rag*")
        self.connection.execute("DROP SCHEMA IF EXISTS rag CASCADE")
        self.store = IndexStore(self.connection)
        self.store.prepare()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        write_corpus(self.root)
        self.corpus = load_corpus(self.root)

    def count(self, table):
        return self.connection.execute("SELECT count(*) FROM rag." + table).fetchone()[0]

    def active(self, model=MODELS["small"]):
        return self.connection.execute("SELECT generation_id FROM rag.active_generations WHERE model=%s",
                                       (model.name,)).fetchone()[0]

    def test_ac013_schema_is_prepared_without_changing_explorer(self):
        self.assertIsNotNone(self.connection.execute("SELECT to_regclass('rag.generations')").fetchone()[0])
        self.assertIsNotNone(self.connection.execute("SELECT to_regclass('rag.embeddings')").fetchone()[0])

    def test_ac001_repeated_generation_keeps_ids_and_makes_no_paid_calls(self):
        provider = FakeEmbedder()
        first = self.store.index(self.corpus, MODELS["small"], provider, execute=True, batch_size=2)
        self.assertEqual(first["new_embeddings"], len({f.input_hash for f in self.corpus.fragments}))
        self.assertGreater(len(provider.calls), 0)
        ids = self.connection.execute("SELECT fragment_id FROM rag.generation_fragments ORDER BY fragment_id").fetchall()
        second = self.store.index(self.corpus, MODELS["small"], execute=True)
        self.assertEqual(second["generation"], first["generation"])
        self.assertEqual(second["api_calls"], 0)
        self.assertEqual(second["new_embeddings"], 0)
        self.assertEqual(self.connection.execute("SELECT fragment_id FROM rag.generation_fragments ORDER BY fragment_id").fetchall(), ids)

    def test_ac002_models_are_separate_and_wrong_dimensions_never_activate(self):
        small = self.store.index(self.corpus, MODELS["small"], FakeEmbedder(), execute=True)
        with self.assertRaises(RagError):
            self.store.index(self.corpus, MODELS["large"], FakeEmbedder(bad_dimensions=True), execute=True)
        self.assertEqual(self.active(), small["generation"])
        large = self.store.index(self.corpus, MODELS["large"], FakeEmbedder(), execute=True)
        self.assertNotEqual(small["generation"], large["generation"])
        self.assertEqual(self.active(MODELS["large"]), large["generation"])
        self.assertEqual(self.count("active_generations"), 2)

    def test_ac002_failed_batch_keeps_previous_active_and_reuses_saved_embeddings(self):
        initial = self.store.index(self.corpus, MODELS["small"], FakeEmbedder(), execute=True)
        extra = self.root / "docs/legal/segunda.txt"
        extra.write_text("Artículo 1.\nCambio primero.\nArtículo 2.\nCambio segundo.\nArtículo 3.\nCambio tercero.")
        changed = load_corpus(self.root)
        failing = FakeEmbedder(fail_after=1)
        with self.assertRaises(RagError):
            self.store.index(changed, MODELS["small"], failing, execute=True, batch_size=1)
        self.assertEqual(self.active(), initial["generation"])
        cached = self.count("embeddings")
        resumed = self.store.index(changed, MODELS["small"], FakeEmbedder(), execute=True)
        self.assertEqual(self.active(), resumed["generation"])
        self.assertEqual(resumed["new_embeddings"], self.count("embeddings") - cached)

    def test_ac002_removed_file_is_not_linked_from_the_new_generation(self):
        first = self.store.index(self.corpus, MODELS["small"], FakeEmbedder(), execute=True)
        (self.root / "docs/legal/ley.txt").unlink()
        next_corpus = load_corpus(self.root)
        second = self.store.index(next_corpus, MODELS["small"], execute=True)
        self.assertNotEqual(first["generation"], second["generation"])
        paths = self.connection.execute("""SELECT DISTINCT d.path FROM rag.generation_fragments g
            JOIN rag.fragments f ON f.id=g.fragment_id JOIN rag.documents d ON d.id=f.document_id
            WHERE g.generation_id=%s""", (second["generation"],)).fetchall()
        self.assertEqual(paths, [("docs/polizas_sinteticas/P-A.md",)])
        self.assertEqual(second["new_embeddings"], 0)

    def test_ac002_unchanged_version_cannot_hide_changed_embedding_inputs(self):
        first = self.store.index(self.corpus, MODELS["small"], FakeEmbedder(), execute=True)
        fragment = self.corpus.fragments[0]
        altered = replace(fragment,embedding_input=fragment.embedding_input+" Cambiado",
                          input_hash=hashlib.sha256((fragment.embedding_input+" Cambiado").encode()).hexdigest())
        incompatible = replace(self.corpus,fragments=(altered,*self.corpus.fragments[1:]))
        with self.assertRaises(RagError) as caught:
            self.store.index(incompatible,MODELS["small"],execute=True)
        self.assertEqual(caught.exception.code,"INDICE_INCOMPATIBLE")
        self.assertEqual(self.active(),first["generation"])

    def test_ac012_no_execution_authorization_means_no_provider_calls(self):
        provider = FakeEmbedder()
        with self.assertRaises(PermissionError):
            self.store.index(self.corpus, MODELS["small"], provider)
        self.assertEqual(provider.calls, [])
        self.assertEqual(self.count("generations"), 0)


def run_postgres_tests():
    """An explicit integration run owns and removes only its disposable project."""
    case = Path(__file__).resolve().parents[3]
    project = "cu19-rag-test-" + uuid.uuid4().hex[:10]
    with tempfile.TemporaryDirectory(prefix="cu19 rag tests ") as folder:
        config = Path(folder) / "postgres.env"
        password = secrets.token_urlsafe(32)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1",0))
            port = listener.getsockname()[1]
        config.write_text(f"POSTGRES_USER=postgres\nPOSTGRES_DB=cu19_test_rag_index\nPOSTGRES_PASSWORD={password}\nPOSTGRES_PORT={port}\n")
        config.chmod(0o600)
        compose = ["docker","compose","--env-file",str(config),"-f",str(case/"compose.yaml"),"-p",project]
        env = os.environ.copy()
        # Shell PostgreSQL overrides must not redirect an isolated test service.
        for key in ("POSTGRES_DB","POSTGRES_USER","POSTGRES_PASSWORD","POSTGRES_PORT"):
            env.pop(key,None)
        env["RAG_TEST_DATABASE_URL"] = f"postgresql://postgres:{quote(password,safe='')}@127.0.0.1:{port}/cu19_test_rag_index"
        try:
            subprocess.run([*compose,"up","-d","--wait","postgres"],env=env,check=True)
            return subprocess.run([sys.executable,str(Path(__file__).resolve()),"-v"],env=env).returncode
        finally:
            subprocess.run([*compose,"down","--volumes"],env=env,check=True)


if __name__ == "__main__":
    if "--postgres" in sys.argv:
        raise SystemExit(run_postgres_tests())
    unittest.main()
