-- Spec 32 / ADR 0006. No changes to the explorer's public tables.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS rag;

CREATE TABLE IF NOT EXISTS rag.generations (
    id TEXT PRIMARY KEY,
    corpus_hash TEXT NOT NULL,
    protocol TEXT NOT NULL,
    model TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('building', 'ready', 'failed')),
    document_count INTEGER NOT NULL CHECK (document_count > 0),
    fragment_count INTEGER NOT NULL CHECK (fragment_count > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    UNIQUE (id, model, dimensions),
    CHECK ((model = 'text-embedding-3-small' AND dimensions = 1536)
        OR (model = 'text-embedding-3-large' AND dimensions = 3072))
);

CREATE TABLE IF NOT EXISTS rag.documents (
    id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('poliza', 'legal')),
    policy_id TEXT,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    CHECK ((kind = 'poliza' AND policy_id IS NOT NULL)
        OR (kind = 'legal' AND policy_id IS NULL))
);

CREATE TABLE IF NOT EXISTS rag.fragments (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES rag.documents(id),
    section TEXT NOT NULL,
    section_index INTEGER NOT NULL,
    window_index INTEGER NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL CHECK (char_end > char_start),
    body TEXT NOT NULL CHECK (length(body) > 0),
    embedding_input TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    source TEXT NOT NULL,
    UNIQUE (id, input_hash)
);

CREATE TABLE IF NOT EXISTS rag.embeddings (
    model TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    input_hash TEXT NOT NULL,
    embedding vector NOT NULL,
    PRIMARY KEY (model, dimensions, input_hash),
    CHECK (vector_dims(embedding) = dimensions),
    CHECK ((model = 'text-embedding-3-small' AND dimensions = 1536)
        OR (model = 'text-embedding-3-large' AND dimensions = 3072))
);

CREATE TABLE IF NOT EXISTS rag.generation_fragments (
    generation_id TEXT NOT NULL,
    fragment_id TEXT NOT NULL,
    model TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    input_hash TEXT NOT NULL,
    PRIMARY KEY (generation_id, fragment_id),
    FOREIGN KEY (generation_id, model, dimensions) REFERENCES rag.generations(id, model, dimensions),
    FOREIGN KEY (fragment_id, input_hash) REFERENCES rag.fragments(id, input_hash),
    FOREIGN KEY (model, dimensions, input_hash) REFERENCES rag.embeddings(model, dimensions, input_hash)
);

CREATE TABLE IF NOT EXISTS rag.active_generations (
    model TEXT PRIMARY KEY,
    dimensions INTEGER NOT NULL,
    generation_id TEXT NOT NULL,
    FOREIGN KEY (generation_id, model, dimensions) REFERENCES rag.generations(id, model, dimensions)
);

CREATE TABLE IF NOT EXISTS rag.embedding_calls (
    id BIGSERIAL PRIMARY KEY,
    generation_id TEXT NOT NULL REFERENCES rag.generations(id),
    input_tokens BIGINT NOT NULL CHECK (input_tokens >= 0),
    estimated_cost_usd NUMERIC NOT NULL CHECK (estimated_cost_usd >= 0),
    request_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
