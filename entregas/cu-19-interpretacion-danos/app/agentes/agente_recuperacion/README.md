# Agente 2 — Costes, cobertura y normativa (RAG)

Dos piezas en esta carpeta, con dos responsables y un único punto de contacto.

| Pieza | Responsable | Guía |
|---|---|---|
| **Costes y cobertura**: convierte los hallazgos del Agente 1 en dos presupuestos con la tool de la empresa (`piia2_paquete_datos/scripts/estimar_coste.py`) y calcula pérdida total, cobertura e indemnización. Fichero: `costes_y_cobertura.py`. | Víctor | [`agente2-costes-cobertura-guia.md`](../../../specs/agente2-costes-cobertura-guia.md) |
| **Normativa (RAG)**: base vectorial (ChromaDB) sobre pólizas y legislación, evaluada con las 25 preguntas de la empresa. Ficheros: `normativa_rag.py`, `evaluar_rag.py`. | Lucas | [`agente2-rag-normativa-guia.md`](../../../specs/agente2-rag-normativa-guia.md) |

**Punto de contacto:** `buscar_normativa(pregunta, k=4, poliza_id="") -> [{"tema", "extracto", "fuente"}]`
(la escribe Lucas y rellena el campo `normativa` de la salida de Víctor).

Datos de entrada y salida de ejemplo: `../ejemplos_contrato/`.

La base vectorial se genera en `chroma_db/` (en `.gitignore`).
