"""Replay de #54 AC-024 con vectores guardados: sin API y PostgreSQL en solo lectura.

Plan: https://github.com/lvckss/piia2-26/issues/54#issuecomment-7140196344
Los archivos vectores-small/large.json y resultados.json proceden del baseline
autorizado; no se versionan los vectores ni los textos del paquete de la empresa.
"""

import argparse
import csv
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

CASE = Path(__file__).resolve().parents[1]
AGENTS = CASE / "app/agentes"
sys.path[:0] = [str(AGENTS / "agente_recuperacion"), str(AGENTS / "informes_reales"),
               str(AGENTS / "agente_redactor")]

from configuracion_rag import load_environment
from normativa_rag import EmbeddingBatch, MODELS, NormativaRetriever
import agente2 as composition
from generar_informes_reales import preparar_casos, leer_siniestros, SALIDAS_REALES
from informe import comprobar_cifras, generar_informe
import psycopg


class SavedVectors:
    def __init__(self, cache):
        self.vectors = dict(zip(cache["texts"], cache["vectors"], strict=True))

    def embed(self, texts, model):
        # Una consulta ausente falla: nunca consulta a un proveedor como fallback.
        return EmbeddingBatch([self.vectors[text] for text in texts], 0)


def replay(evidence, output):
    load_environment()
    baseline = json.loads((evidence / "resultados.json").read_text())
    cases = preparar_casos([json.loads(p.read_text()) for p in sorted(SALIDAS_REALES.glob("*.json"))],
                          leer_siniestros())
    report = {"plan": "https://github.com/lvckss/piia2-26/issues/54#issuecomment-7140196344",
              "new_api_calls": 0, "models": {}}
    output.mkdir(parents=True, exist_ok=True)
    for name, model in MODELS.items():
        cache = json.loads((evidence / f"vectores-{name}.json").read_text())
        assert cache["model"] == model.name
        saved = SavedVectors(cache)
        with psycopg.connect(os.environ["DATABASE_URL"], options="-c default_transaction_read_only=on",
                             connect_timeout=5) as connection:
            assert connection.execute("SHOW transaction_read_only").fetchone()[0] == "on"
            search = NormativaRetriever(connection, saved, model)
            generation = search._generation()[0]
            assert generation == baseline["models"][name]["generation"][0], "Cambió la generación del baseline"

            def query(topic, k=4, poliza_id=""):
                return search.search(topic, k, poliza_id)

            result = {"generation": generation, "benchmark": [], "cases": []}
            for row in baseline["models"][name]["benchmark"]:
                pair = []
                for enabled in ("0", "1"):
                    with patch.dict(os.environ, {"RAG_POLICY_TOPIC_FILTER": enabled}):
                        pair.append(query(row["pregunta"], poliza_id=row["poliza_id"]))
                assert pair[0] == row["results"], "El baseline no se reproduce"
                assert pair[0] == pair[1], "Regresión en los pasajes de una pregunta del benchmark"
                result["benchmark"].append({"id": row["id"], "pregunta": row["pregunta"],
                    "hit_at_4_before": row["hit_at_4"], "hit_at_4_after": any(
                        r["fuente"].split("#")[0] == row["fuente"] for r in pair[1]),
                    "identical_passages": True, "sources": [r["fuente"] for r in pair[1]]})

            for case in cases:
                pair = []
                for enabled in ("0", "1"):
                    with patch.dict(os.environ, {"RAG_POLICY_TOPIC_FILTER": enabled}), \
                            patch.object(composition, "buscar_normativa", side_effect=query):
                        pair.append(composition.agente2(case["salida_agente1"], case["contexto"],
                            modelo="sin-llm", autorizado=False, cache_dir=output / "cache-vacia"))
                before, after = pair
                for field in before.keys() - {"normativa", "diagnostico_rag", "justificaciones"}:
                    assert before[field] == after[field], f"Cambió un campo determinista: {field}"
                for agent2 in pair:
                    md = generar_informe(case["salida_agente1"], agent2, hoy="2026-11-27")
                    assert comprobar_cifras(md, agent2) == []
                    assert not any(j["estado"] == "generada" for j in agent2["justificaciones"])
                if case["image_id"] in (82, 1281):
                    assert after["normativa"]
                    assert all(r["fuente"].startswith("docs/polizas_sinteticas/P-TERC-BASICO.md#")
                               for r in after["normativa"])
                    assert not any("incendio" in r["extracto"].lower() or "homologación" in r["extracto"].lower()
                                   for r in after["normativa"])
                    assert any("3.4 **No están cubiertos" in r["extracto"] for r in after["normativa"])
                result["cases"].append({"image_id": case["image_id"], "deterministic_fields_identical": True,
                    "foreign_amounts": 0, "sources_before": [r["fuente"] for r in before["normativa"]],
                    "sources_after": [r["fuente"] for r in after["normativa"]]})
            report["models"][name] = result
            print(json.dumps({"model": name, "benchmark_identical": len(result["benchmark"]),
                              "cases_preserving_calculations": len(result["cases"])}), flush=True)
    (output / "comparacion.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    with (output / "benchmark.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["model", "question_id", "hit_before", "hit_after", "identical_passages"],
                                lineterminator="\n")
        writer.writeheader()
        for model, result in report["models"].items():
            for row in result["benchmark"]:
                writer.writerow({"model": model, "question_id": row["id"], "hit_before": row["hit_at_4_before"],
                                 "hit_after": row["hit_at_4_after"], "identical_passages": row["identical_passages"]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--destino", required=True, type=Path)
    args = parser.parse_args()
    replay(args.baseline, args.destino)
