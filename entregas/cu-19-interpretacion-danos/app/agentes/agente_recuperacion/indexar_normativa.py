"""Prepare a corpus or explicitly index it (spec 32, AC-001/002/012/013)."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import importlib.metadata
import json
import math
import os
from pathlib import Path
import shlex
import sys

import psycopg

from corpus_normativa import load_corpus
from embeddings_openai import OpenAIEmbeddings, SpendingBudget, count_tokens
from normativa_rag import IndexStore, MODELS, RagError

CASE = Path(__file__).resolve().parents[3]


def load_environment():
    for path in (CASE / ".env", CASE / "app/.env"):
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip().removeprefix("export ")
            if not line or line.startswith("#") or "=" not in line:
                continue
            key,value = line.split("=",1)
            values = shlex.split(value,comments=True)
            os.environ.setdefault(key.strip()," ".join(values))


def resolve_package(value):
    if value:
        return Path(value)
    if os.environ.get("PLEXUS_DATA_DIR"):
        return Path(os.environ["PLEXUS_DATA_DIR"])
    # Convenient repository defaults; explicit paths also work for a standalone case.
    for name in ("datos","piia2_paquete_datos"):
        path = CASE.parents[1] / name
        if (path / "docs/legal").is_dir():
            return path
    raise ValueError("Indica el paquete con --package o PLEXUS_DATA_DIR")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package")
    parser.add_argument("--model",choices=["small","large","both"],default="both")
    parser.add_argument("--execute",action="store_true")
    parser.add_argument("--max-cost-usd",type=float)
    parser.add_argument("--batch-size",type=int,default=32)
    parser.add_argument("--report",type=Path)
    args = parser.parse_args(argv)
    if args.execute and (args.max_cost_usd is None or not math.isfinite(args.max_cost_usd) or args.max_cost_usd<0):
        parser.error("La ejecución requiere un presupuesto explícito: --max-cost-usd")
    budget = SpendingBudget(args.max_cost_usd or 0)
    try:
        corpus = load_corpus(resolve_package(args.package))
        inputs = {f.input_hash:f.embedding_input for f in corpus.fragments}
        token_counts = [count_tokens(text) for text in inputs.values()]
        if max(token_counts)>8192:
            raise ValueError("Un fragmento excede 8192 tokens; revisa el protocolo antes de llamar a OpenAI")
        models = list(MODELS.values()) if args.model=="both" else [MODELS[args.model]]
        report = {"mode":"execute" if args.execute else "plan", "recorded_at":datetime.now(timezone.utc).isoformat(),
                  "corpus_hash":corpus.hash,"protocol":corpus.protocol,"documents":len(corpus.documents),
                  "fragments":len(corpus.fragments),"unique_embedding_inputs":len(inputs),
                  "fragments_by_type":dict(Counter(f.document.kind for f in corpus.fragments)),
                  "input_tokens_without_cache_per_model":sum(token_counts),"max_fragment_tokens":max(token_counts),
                  "estimated_full_cost_usd":{m.name:sum(token_counts)*m.usd_per_million/1_000_000 for m in models},
                  "prices_as_of":"2026-11-03", "price_sources":[
                      "https://developers.openai.com/api/docs/models/text-embedding-3-small",
                      "https://developers.openai.com/api/docs/models/text-embedding-3-large"],
                  "versions":{p:importlib.metadata.version(p) for p in ("openai","psycopg","tiktoken")}}
        if args.execute:
            load_environment()
            dsn = os.environ.get("DATABASE_URL")
            if not dsn:
                raise ValueError("Falta DATABASE_URL para la PostgreSQL Docker")
            client = OpenAIEmbeddings(budget)
            with psycopg.connect(dsn,autocommit=True) as connection:
                store = IndexStore(connection)
                report["results"] = []
                for model in models:
                    report["results"].append(store.index(corpus,model,client,execute=True,batch_size=args.batch_size,
                        progress=lambda value:print(json.dumps(value),file=sys.stderr,flush=True)))
                report["postgres_version"] = connection.execute("SHOW server_version").fetchone()[0]
                report["pgvector_version"] = connection.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()[0]
            report["authorized_budget_usd"] = budget.limit_usd
            report["reserved_cost_usd"] = budget.reserved_usd
            report["reported_tokens_cost_usd"] = budget.reported_usd
        serialized = json.dumps(report,indent=2,ensure_ascii=False)+"\n"
        if args.report:
            args.report.write_text(serialized)
        print(serialized,end="")
        return 0
    except (RagError,PermissionError,ValueError) as error:
        print(json.dumps({"error":str(error),"code":getattr(error,"code",type(error).__name__),
                          "reserved_cost_usd":budget.reserved_usd,"reported_tokens_cost_usd":budget.reported_usd},
                         ensure_ascii=False),file=sys.stderr)
        return 1
    except psycopg.Error as error:
        # Fatal, never treated as an empty search or success; do not echo SQL data.
        print(json.dumps({"error":"Fallo de PostgreSQL","type":type(error).__name__}),file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
