# Agente 2 — Costes, cobertura y normativa (RAG)

Responsable: Víctor.

Guía paso a paso (léela entera antes de empezar):
[`../../../specs/agente2-recuperacion-guia-victor.md`](../../../specs/agente2-recuperacion-guia-victor.md).

Tres piezas:

1. **Costes**: convierte los hallazgos del Agente 1 en dos presupuestos con la
   herramienta de costes de la empresa (`piia2_paquete_datos/scripts/estimar_coste.py`).
2. **Cobertura**: pérdida total, cobertura de la póliza e indemnización.
3. **Normativa (RAG)**: base vectorial (ChromaDB) sobre pólizas y legislación,
   evaluada con las 25 preguntas de la empresa.

Datos de entrada y salida de ejemplo: `../ejemplos_contrato/`.

La base vectorial se genera en `chroma_db/` (en `.gitignore`).
