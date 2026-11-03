"""PostgreSQL index lifecycle: spec 32, AC-001/002/012/013."""

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import time


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
