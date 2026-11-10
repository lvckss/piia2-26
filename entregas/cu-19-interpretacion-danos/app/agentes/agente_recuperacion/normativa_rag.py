"""Persistent indexing and retrieval: spec 32, AC-001 to AC-005/012/013."""

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import time

import psycopg

from corpus_normativa import PROTOCOL


@dataclass(frozen=True)
class Model:
    name: str
    dimensions: int
    usd_per_million: float


MODELS = {
    "small": Model("text-embedding-3-small", 1536, 0.02),
    "large": Model("text-embedding-3-large", 3072, 0.13),
}


@dataclass(frozen=True)
class EmbeddingBatch:
    vectors: list[list[float]]
    input_tokens: int
    request_id: str = ""


class RagError(Exception):
    def __init__(self, code, message, *, stage="indexado", retryable=False):
        super().__init__(message)
        self.code, self.stage, self.retryable = code, stage, retryable


class NormativaRetriever:
    def __init__(self, connection, embedder, model=MODELS["small"]):
        self.connection, self.embedder, self.model = connection, embedder, model

    def search(self, pregunta, k=4, poliza_id=""):
        validate_query(pregunta, k, poliza_id)
        from embeddings_openai import count_tokens

        if count_tokens(pregunta) > 8192:
            raise RagError("ENTRADA_INVALIDA", "La pregunta supera el límite de 8192 tokens", stage="entrada")
        if self.model not in MODELS.values():
            raise RagError("INDICE_INCOMPATIBLE", "Modelo o dimensiones no compatibles", stage="busqueda")
        generation, expected_documents, expected_fragments = self._generation()
        # FKs and these counts reject an incomplete generation before paying.
        counts = self._execute("""SELECT count(*), count(DISTINCT f.document_id)
            FROM rag.generation_fragments gf
            JOIN rag.fragments f ON f.id=gf.fragment_id AND f.input_hash=gf.input_hash
            JOIN rag.documents d ON d.id=f.document_id
            JOIN rag.embeddings e ON e.model=gf.model AND e.dimensions=gf.dimensions AND e.input_hash=gf.input_hash
            WHERE gf.generation_id=%s AND gf.model=%s AND gf.dimensions=%s""",
            (generation, self.model.name, self.model.dimensions)).fetchone()
        if counts[:2] != (expected_fragments, expected_documents):
            raise RagError("INDICE_NO_PREPARADO", "La generación del índice está incompleta", stage="busqueda")
        policies = {row[0] for row in self._execute("""SELECT DISTINCT d.policy_id
            FROM rag.generation_fragments gf JOIN rag.fragments f ON f.id=gf.fragment_id
            JOIN rag.documents d ON d.id=f.document_id WHERE gf.generation_id=%s AND d.kind='poliza'""",
            (generation,)).fetchall()}
        if poliza_id and poliza_id not in policies:
            raise RagError("ENTRADA_INVALIDA", "La póliza indicada no pertenece al corpus activo", stage="entrada")
        parameters = (generation, poliza_id)
        candidates = self._execute("""SELECT count(*) FROM rag.generation_fragments gf
            JOIN rag.fragments f ON f.id=gf.fragment_id JOIN rag.documents d ON d.id=f.document_id
            WHERE gf.generation_id=%s AND (d.kind='legal' OR d.policy_id=%s)""", parameters).fetchone()[0]
        if not candidates:
            return []
        # Pin the generation before the external call; an index published meanwhile
        # must not change the model, corpus or eligible policies for this query.
        batch = self.embedder.embed([pregunta], self.model)
        if (not isinstance(batch, EmbeddingBatch) or not isinstance(batch.vectors, list)
                or len(batch.vectors) != 1 or not _valid_vector(batch.vectors[0], self.model.dimensions)):
            raise RagError("EMBEDDINGS_RESPUESTA_INVALIDA", "El vector de consulta es inválido o incompatible", stage="embeddings")
        # Materialize only IDs/distances first, so PostgreSQL never decompresses
        # and compares every full legal document before applying LIMIT.
        rows = self._execute("""WITH nearest AS MATERIALIZED (
                SELECT f.id,e.embedding <=> %s::vector AS distance
                FROM rag.generation_fragments gf
                JOIN rag.fragments f ON f.id=gf.fragment_id
                JOIN rag.documents d ON d.id=f.document_id
                JOIN rag.embeddings e ON e.model=gf.model AND e.dimensions=gf.dimensions AND e.input_hash=gf.input_hash
                WHERE gf.generation_id=%s AND (d.kind='legal' OR d.policy_id=%s)
                ORDER BY distance,f.id COLLATE "C" LIMIT %s
            ) SELECT f.body,f.source,
                f.body=substring(d.body FROM f.char_start+1 FOR f.char_end-f.char_start) AS literal
            FROM nearest n JOIN rag.fragments f ON f.id=n.id JOIN rag.documents d ON d.id=f.document_id
            ORDER BY n.distance,n.id COLLATE "C"
            """,
            (json.dumps(batch.vectors[0]), *parameters, min(k, candidates))).fetchall()
        if any(not literal or not body.strip() or not source.strip() for body, source, literal in rows):
            raise RagError("INDICE_INCOMPATIBLE", "Un pasaje recuperado no coincide con su documento", stage="busqueda")
        return [{"tema": pregunta, "extracto": body, "fuente": source} for body, source, _ in rows]

    def _execute(self, query, parameters=()):
        try:
            return self.connection.execute(query, parameters)
        except (psycopg.OperationalError, psycopg.InterfaceError) as error:
            raise RagError("BD_NO_DISPONIBLE", "No se ha podido consultar la base de datos",
                           stage="base_datos", retryable=True) from error
        except (psycopg.errors.UndefinedTable, psycopg.errors.InvalidSchemaName) as error:
            raise RagError("INDICE_NO_PREPARADO", "El índice no está preparado; ejecuta el indexado explícitamente",
                           stage="busqueda") from error
        except (psycopg.errors.UndefinedColumn, psycopg.errors.UndefinedFunction) as error:
            raise RagError("INDICE_INCOMPATIBLE", "El esquema del índice no es compatible con este buscador",
                           stage="busqueda") from error

    def _generation(self):
        row = self._execute("""SELECT a.generation_id,a.dimensions,g.model,g.dimensions,g.protocol,
            g.status,g.corpus_hash,g.document_count,g.fragment_count
            FROM rag.active_generations a JOIN rag.generations g ON g.id=a.generation_id
            WHERE a.model=%s""", (self.model.name,)).fetchone()
        if row is None:
            raise RagError("INDICE_NO_PREPARADO", "No hay generación activa para el modelo solicitado", stage="busqueda")
        generation, active_dims, model, dimensions, protocol, status, corpus_hash, documents, fragments = row
        identity = f"{corpus_hash}\0{protocol}\0{model}\0{dimensions}"
        if (active_dims != self.model.dimensions or model != self.model.name
                or dimensions != self.model.dimensions or protocol != PROTOCOL
                or generation != hashlib.sha256(identity.encode()).hexdigest()):
            raise RagError("INDICE_INCOMPATIBLE", "El manifiesto no coincide con el modelo o protocolo esperado", stage="busqueda")
        if status != "ready":
            raise RagError("INDICE_NO_PREPARADO", "La generación activa no está completa", stage="busqueda")
        return generation, documents, fragments


def _valid_vector(vector, dimensions):
    return (isinstance(vector, list) and len(vector) == dimensions
            and all(type(x) in (float, int) and math.isfinite(x) and abs(x) <= 3.402823466e38 for x in vector)
            and any(abs(x) >= 1.175494351e-38 for x in vector))


def validate_query(pregunta, k=4, poliza_id=""):
    if (not isinstance(pregunta, str) or not pregunta.strip() or "\0" in pregunta
            or type(k) is not int or k <= 0 or not isinstance(poliza_id, str)
            or "\0" in poliza_id or (poliza_id and not poliza_id.strip())):
        raise RagError("ENTRADA_INVALIDA", "Indica una pregunta no vacía, k entero positivo y una póliza válida",
                       stage="entrada")


def _configured_search(pregunta, k, poliza_id):
    from configuracion_rag import load_environment
    from embeddings_openai import OpenAIEmbeddings, SpendingBudget

    load_environment()
    if os.environ.get("RAG_QUERY_EXECUTE") != "1":
        raise PermissionError("Consultar requiere RAG_QUERY_EXECUTE=1 y un presupuesto explícito")
    try:
        budget = float(os.environ["RAG_QUERY_MAX_COST_USD"])
    except (KeyError, ValueError):
        raise PermissionError("Falta un presupuesto válido en RAG_QUERY_MAX_COST_USD") from None
    if not math.isfinite(budget) or budget < 0:
        raise PermissionError("RAG_QUERY_MAX_COST_USD debe ser finito y no negativo")
    name = os.environ.get("RAG_MODEL", "small")
    if name not in MODELS:
        raise RagError("INDICE_INCOMPATIBLE", "RAG_MODEL debe ser small o large", stage="busqueda")
    return query_database(pregunta, k, poliza_id, MODELS[name], OpenAIEmbeddings(SpendingBudget(budget)))


def query_database(pregunta, k, poliza_id, model, embedder):
    """Explicitly configured entry for CLI/integration; never prepares an index."""
    validate_query(pregunta, k, poliza_id)
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RagError("BD_NO_DISPONIBLE", "Falta configurar DATABASE_URL", stage="base_datos", retryable=True)
    try:
        with psycopg.connect(dsn, autocommit=True, connect_timeout=5) as connection:
            return NormativaRetriever(connection, embedder, model).search(pregunta, k, poliza_id)
    except (psycopg.OperationalError, psycopg.InterfaceError) as error:
        raise RagError("BD_NO_DISPONIBLE", "No se ha podido conectar con la base de datos",
                       stage="base_datos", retryable=True) from error


def buscar_normativa(pregunta, k=4, poliza_id=""):
    validate_query(pregunta, k, poliza_id)
    return _configured_search(pregunta, k, poliza_id)


class IndexStore:
    def __init__(self, connection):
        self.connection = connection

    def prepare(self):
        with self.connection.transaction():
            self.connection.execute("SELECT pg_advisory_xact_lock(hashtextextended('rag-schema-v1',0))")
            self.connection.execute(Path(__file__).with_name("schema_rag.sql").read_text())

    def index(self, corpus, model, embedder=None, *, execute=False, batch_size=32, progress=None):
        if not execute:
            raise PermissionError("Indexar requiere autorización explícita (--execute)")
        if model not in MODELS.values():
            raise RagError("INDICE_INCOMPATIBLE", "Modelo o dimensiones no compatibles")
        if not corpus.documents or not corpus.fragments or type(batch_size) is not int or not 1 <= batch_size <= 2048:
            raise ValueError("Corpus vacío o tamaño de lote no válido")
        if not self.connection.autocommit:
            raise ValueError("El indexador necesita una conexión autocommit para conservar los lotes completados")
        self.prepare()
        lock = "rag-index-" + model.name
        acquired = self.connection.execute("SELECT pg_try_advisory_lock(hashtextextended(%s,0))", (lock,)).fetchone()[0]
        if not acquired:
            raise RagError("INDICE_NO_PREPARADO", "Ya hay un indexado de este modelo en curso", retryable=True)
        identity = f"{corpus.hash}\0{corpus.protocol}\0{model.name}\0{model.dimensions}"
        generation = hashlib.sha256(identity.encode()).hexdigest()
        started = time.monotonic()
        unique = {f.input_hash: f.embedding_input for f in corpus.fragments}
        result = {"generation": generation, "model": model.name, "dimensions": model.dimensions,
                  "corpus_hash": corpus.hash, "protocol": corpus.protocol,
                  "documents": len(corpus.documents), "fragments": len(corpus.fragments),
                  "unique_inputs": len(unique), "new_embeddings": 0, "api_calls": 0,
                  "input_tokens": 0, "estimated_cost_usd": 0.0}
        try:
            previous = self.connection.execute("SELECT status FROM rag.generations WHERE id=%s", (generation,)).fetchone()
            if previous and previous[0] == "ready":
                recorded = self.connection.execute("""SELECT fragment_id,input_hash FROM rag.generation_fragments
                    WHERE generation_id=%s ORDER BY fragment_id""", (generation,)).fetchall()
                expected = sorted((f.id,f.input_hash) for f in corpus.fragments)
                if recorded != expected:
                    raise RagError("INDICE_INCOMPATIBLE", "La generación completa tiene un manifiesto incoherente")
            else:
                with self.connection.transaction():
                    self.connection.execute("""INSERT INTO rag.generations
                        (id,corpus_hash,protocol,model,dimensions,status,document_count,fragment_count)
                        VALUES (%s,%s,%s,%s,%s,'building',%s,%s)
                        ON CONFLICT (id) DO UPDATE SET status='building', completed_at=NULL""",
                        (generation,corpus.hash,corpus.protocol,model.name,model.dimensions,len(corpus.documents),len(corpus.fragments)))
                    with self.connection.cursor() as cursor:
                        cursor.executemany("""INSERT INTO rag.documents
                            (id,path,content_hash,kind,policy_id,title,body) VALUES (%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (id) DO NOTHING""",
                            [(d.id,d.path,d.content_hash,d.kind,d.policy_id,d.title,d.text) for d in corpus.documents])
                        cursor.executemany("""INSERT INTO rag.fragments
                            (id,document_id,section,section_index,window_index,char_start,char_end,body,embedding_input,input_hash,source)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING""",
                            [(f.id,f.document.id,f.section,f.section_index,f.window_index,f.start,f.end,
                              f.text,f.embedding_input,f.input_hash,f.source) for f in corpus.fragments])
                existing = {row[0] for row in self.connection.execute("""SELECT input_hash FROM rag.embeddings
                    WHERE model=%s AND dimensions=%s AND input_hash=ANY(%s)""",
                    (model.name,model.dimensions,list(unique))).fetchall()}
                missing = [(h,text) for h,text in unique.items() if h not in existing]
                if missing and embedder is None:
                    raise RagError("EMBEDDINGS_AUTENTICACION", "No se ha configurado el cliente de embeddings", stage="embeddings")
                for offset in range(0, len(missing), batch_size):
                    entries = missing[offset:offset+batch_size]
                    batch = embedder.embed([text for _,text in entries], model)
                    valid = len(batch.vectors) == len(entries) and type(batch.input_tokens) is int and batch.input_tokens >= 0
                    for vector in batch.vectors:
                        valid = valid and len(vector) == model.dimensions and all(
                            isinstance(x, (float,int)) and math.isfinite(x) for x in vector) and any(x != 0 for x in vector)
                    if not valid:
                        raise RagError("EMBEDDINGS_RESPUESTA_INVALIDA", "Vectores incompletos, dimensiones incompatibles o valores no válidos", stage="embeddings")
                    cost = batch.input_tokens * model.usd_per_million / 1_000_000
                    with self.connection.transaction():
                        with self.connection.cursor() as cursor:
                            cursor.executemany("""INSERT INTO rag.embeddings (model,dimensions,input_hash,embedding)
                                VALUES (%s,%s,%s,%s::vector) ON CONFLICT DO NOTHING""",
                                [(model.name,model.dimensions,h,json.dumps(v)) for (h,_),v in zip(entries,batch.vectors)])
                        self.connection.execute("""INSERT INTO rag.embedding_calls
                            (generation_id,input_tokens,estimated_cost_usd,request_id) VALUES (%s,%s,%s,%s)""",
                            (generation,batch.input_tokens,cost,batch.request_id))
                    result["new_embeddings"] += len(entries)
                    result["api_calls"] += 1
                    result["input_tokens"] += batch.input_tokens
                    result["estimated_cost_usd"] += cost
                    if progress:
                        progress({"model":model.name,"new_embeddings":result["new_embeddings"],
                                  "pending_inputs":len(missing)-offset-len(entries),
                                  "input_tokens":result["input_tokens"],
                                  "estimated_cost_usd":result["estimated_cost_usd"]})
                with self.connection.transaction():
                    with self.connection.cursor() as cursor:
                        cursor.executemany("""INSERT INTO rag.generation_fragments
                            (generation_id,fragment_id,model,dimensions,input_hash) VALUES (%s,%s,%s,%s,%s)
                            ON CONFLICT DO NOTHING""",
                            [(generation,f.id,model.name,model.dimensions,f.input_hash) for f in corpus.fragments])
            # This transaction publishes only a complete generation. Previously active
            # generations and all their links remain available if an earlier step fails.
            with self.connection.transaction():
                self.connection.execute("""UPDATE rag.generations SET status='ready',completed_at=coalesce(completed_at,now())
                    WHERE id=%s""", (generation,))
                self.connection.execute("""INSERT INTO rag.active_generations (model,dimensions,generation_id)
                    VALUES (%s,%s,%s) ON CONFLICT (model) DO UPDATE
                    SET dimensions=excluded.dimensions,generation_id=excluded.generation_id""",
                    (model.name,model.dimensions,generation))
            result["reused_inputs"] = len(unique) - result["new_embeddings"]
            result["seconds"] = time.monotonic() - started
            return result
        except Exception:
            self.connection.execute("UPDATE rag.generations SET status='failed' WHERE id=%s AND status!='ready'", (generation,))
            raise
        finally:
            self.connection.execute("SELECT pg_advisory_unlock(hashtextextended(%s,0))", (lock,))
