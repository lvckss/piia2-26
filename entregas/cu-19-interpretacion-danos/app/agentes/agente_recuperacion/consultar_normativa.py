"""Plan a query offline or execute it explicitly (spec 32, AC-003/004/005/012/013)."""

import argparse
import json
import math
import sys
import time

from configuracion_rag import load_environment
from embeddings_openai import OpenAIEmbeddings, SpendingBudget, count_tokens
from normativa_rag import MODELS, RagError, query_database, validate_query


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pregunta")
    parser.add_argument("--poliza-id", default="")
    parser.add_argument("--k", type=int, default=4)
    parser.add_argument("--model", choices=list(MODELS), default="small")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--max-cost-usd", type=float)
    args = parser.parse_args(argv)
    if args.execute and (args.max_cost_usd is None or not math.isfinite(args.max_cost_usd) or args.max_cost_usd < 0):
        parser.error("La ejecución requiere un presupuesto explícito: --max-cost-usd")
    budget = SpendingBudget(args.max_cost_usd or 0)
    try:
        validate_query(args.pregunta, args.k, args.poliza_id)
        model = MODELS[args.model]
        tokens = count_tokens(args.pregunta)
        if tokens > 8192:
            raise RagError("ENTRADA_INVALIDA", "La pregunta supera el límite de 8192 tokens", stage="entrada")
        report = {"mode": "execute" if args.execute else "plan", "model": model.name,
                  "dimensions": model.dimensions, "poliza_id": args.poliza_id, "k": args.k,
                  "estimated_input_tokens": tokens,
                  "estimated_query_cost_usd": tokens * model.usd_per_million / 1_000_000,
                  "prices_as_of": "2026-11-03"}
        if args.execute:
            load_environment()
            started = time.monotonic()
            report["resultados"] = query_database(args.pregunta, args.k, args.poliza_id, model, OpenAIEmbeddings(budget))
            report.update(seconds=time.monotonic()-started, authorized_budget_usd=budget.limit_usd,
                          reserved_cost_usd=budget.reserved_usd, reported_tokens_cost_usd=budget.reported_usd)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (RagError, PermissionError) as error:
        print(json.dumps({"codigo": getattr(error, "code", "EJECUCION_NO_AUTORIZADA"),
                          "etapa": getattr(error, "stage", "configuracion"), "mensaje": str(error),
                          "reintentable": getattr(error, "retryable", False),
                          "reserved_cost_usd": budget.reserved_usd,
                          "reported_tokens_cost_usd": budget.reported_usd}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
