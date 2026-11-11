# Agente 2 — Costes, cobertura y normativa (RAG)

Dos piezas en esta carpeta, con dos responsables y un único punto de contacto.

| Pieza | Responsable | Guía |
|---|---|---|
| **Costes y cobertura**: convierte los hallazgos del Agente 1 en dos presupuestos con la tool de la empresa (`piia2_paquete_datos/scripts/estimar_coste.py`) y calcula pérdida total, cobertura e indemnización. Fichero: `costes_y_cobertura.py`. | Víctor | [`agente2-costes-cobertura-guia.md`](../../../docs/guias/agente2-costes-cobertura-guia.md) |
| **Normativa (RAG)**: PostgreSQL/pgvector compartida con el explorador. Indexado y búsqueda de pólizas y legislación; evaluación de 25 preguntas pendiente. | Lucas | [Spec 32](../../../specs/32-rag-normativa.md) |

**Punto de contacto:** `buscar_normativa(pregunta, k=4, poliza_id="") -> [{"tema", "extracto", "fuente"}]`
(la escribe Lucas y rellena el campo `normativa` de la salida de Víctor).

Datos de entrada y salida de ejemplo: `../ejemplos_contrato/`.

Los documentos, fragmentos, vectores y generaciones se guardan en el esquema
`rag` de la misma PostgreSQL Docker del explorador. No se utiliza ChromaDB.

## Costes y cobertura: uso y pruebas

Spec: [`specs/30-costes-cobertura.md`](../../../specs/30-costes-cobertura.md).
Necesita el paquete de la empresa extraído en la raíz del repo
(`piia2_paquete_datos/`, fuera de git); no usa red ni API Key.

```python
from costes_y_cobertura import estimar_siniestro

salida = estimar_siniestro(salida_agente1, contexto)  # JSON del contrato Agente 2 -> Agente 3
```

- `vehiculo_id` es obligatorio en el contexto (la #28, que lo hacía opcional, está aparcada).
- `poliza_id` es obligatorio solo con `rol == "propio"`; con `tercero_perjudicado` se ignora.
- Un contexto no válido lanza `ValueError` con el nombre del campo.
- `normativa` sale vacía: la rellena el RAG (#32).

Desde esta carpeta:

```bash
python probar_costes.py    # pruebas de AC-001 a AC-008 y AC-010
python evaluar_costes.py   # evaluación de AC-011 con los siniestros sintéticos (val + test)
```
