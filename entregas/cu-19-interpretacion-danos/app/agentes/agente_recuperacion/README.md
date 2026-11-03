# Agente 2 — Costes, cobertura y normativa (RAG)

Dos piezas en esta carpeta, con dos responsables y un único punto de contacto.

| Pieza | Responsable | Guía |
|---|---|---|
| **Costes y cobertura**: convierte los hallazgos del Agente 1 en dos presupuestos con la tool de la empresa (`piia2_paquete_datos/scripts/estimar_coste.py`) y calcula pérdida total, cobertura e indemnización. Fichero: `costes_y_cobertura.py`. | Víctor | [`agente2-costes-cobertura-guia.md`](../../../specs/agente2-costes-cobertura-guia.md) |
| **Normativa (RAG)**: PostgreSQL/pgvector compartida con el explorador. Indexado de pólizas y legislación; búsqueda y evaluación de 25 preguntas en los siguientes incrementos. | Lucas | [Spec 32](../../../specs/32-rag-normativa.md) |

**Punto de contacto:** `buscar_normativa(pregunta, k=4, poliza_id="") -> [{"tema", "extracto", "fuente"}]`
(la escribe Lucas y rellena el campo `normativa` de la salida de Víctor).

Datos de entrada y salida de ejemplo: `../ejemplos_contrato/`.

Los documentos, fragmentos, vectores y generaciones se guardan en el esquema
`rag` de la misma PostgreSQL Docker del explorador. No se utiliza ChromaDB.
Este incremento entrega el indexado; `buscar_normativa()`, `agente2()` y la
evaluación de calidad todavía no están implementados.

## Indexado reproducible

Desde la raíz del caso, con Docker disponible y el paquete de Plexus local:

```bash
just db-init       # primera preparación; después basta just db-up
just rag-setup     # Python 3.11+, entorno .venv-rag; sin llamadas de pago
just rag-plan      # once documentos, fragmentos, tokens y estimación de coste
just rag-index 5   # autoriza como máximo 5 USD totales para small y large
```

El indexador busca el paquete en `datos/` o `piia2_paquete_datos/` de la copia del
repositorio. Para otra ubicación, incluida una entrega del caso por separado:

```bash
PLEXUS_DATA_DIR=/ruta/al/paquete just rag-plan
PLEXUS_DATA_DIR=/ruta/al/paquete just rag-index 5
```

El presupuesto es un argumento explícito de **cada ejecución**; el ejemplo no
autoriza gasto automático en el arranque. Ambos modelos comparten ese límite.
También se puede indexar uno: `just rag-index 1 small` o `just rag-index 1 large`.
No seleccionan el mejor modelo: la comparación con las 25 preguntas sigue pendiente.

`rag-setup` descarga también el tokenizador público en `.cache-rag/`, ignorada
por Git, para que el plan y las pruebas no necesiten descargarlo después.
Esa preparación no genera embeddings ni envía documentos al proveedor.

La conexión procede de `DATABASE_URL` (por defecto se carga `app/.env`, apuntando
a Docker) y la clave de `OPENAI_API_KEY` (se carga `.env` del caso cuando se va a
ejecutar). El modo plan no conecta a PostgreSQL ni necesita clave. Se indexan solo
`docs/polizas_sinteticas/*.md` y `docs/legal/*.txt`; el CSV de evaluación y sus
respuestas no se incluyen en documentos, consultas ni filtros.

El protocolo inicial separa pólizas por `##`, legislación por artículo (número
o palabras), preámbulos y documentos sin artículos. Los bloques legales usan
ventanas de 1.500 caracteres y 200 de solape. Conserva el pasaje literal y su
procedencia; añade título/sección únicamente al texto de entrada de embeddings.
Las referencias incluyen sección/ventana y líneas del documento original.

Cada generación identifica corpus SHA-256, protocolo, modelo y dimensiones:
small 1.536, large 3.072. Los vectores se separan por modelo y dimensiones;
una FK vincula los fragmentos al modelo correcto. No hay índices aproximados.
El cacheado se hace por entrada de embeddings y se guarda después de cada lote.
Repetir un índice completo del mismo corpus y modelo mantiene los IDs y no llama al proveedor;
`just rag-index 0` permite comprobarlo sin autorizar gasto adicional.

Solo se activa una generación completa, por modelo. Una caída conserva la
activa anterior y los embeddings de los lotes ya guardados; repetir reutiliza
esos lotes. Un corpus nuevo enlaza únicamente sus documentos, sin incluir un
archivo retirado; las generaciones anteriores permanecen para trazabilidad.
El indexado simultáneo del mismo modelo se rechaza explícitamente.

El informe JSON distingue tokens de entrada estimados, uso que devuelve el
proveedor y coste calculado con las tarifas consultadas el 2026-11-03; ese coste
no sustituye la factura de la cuenta. Se conserva el límite antes de cada
petición y se desactivan los reintentos automáticos del SDK. Fuentes de tarifa:
[small](https://developers.openai.com/api/docs/models/text-embedding-3-small),
[large](https://developers.openai.com/api/docs/models/text-embedding-3-large).

## Pruebas del indexado

```bash
just rag-test
```

Ejecuta las pruebas deterministas y de PostgreSQL en un proyecto/volumen Docker
desechable y un puerto libre, con documentos sintéticos y OpenAI simulado; no
usa la base real ni realiza llamadas de pago. Incluye literalidad, artículos,
repetición, separación de modelos, caché, fallo de lote, retirada de documentos,
respuestas incompatibles, cuota frente a límite temporal y autorización de gasto.
La referencia es `specs/32-rag-normativa.md` + cada ID AC en el nombre del test.

Para solo las pruebas sin base, se puede ejecutar `probar_indexado.py` sin
`--postgres`: omite las siete de integración, que no se presentan como superadas.
La calidad 23/25 y las pruebas de composición no se acreditan con estas pruebas.

Si cambia el troceado o el prefijo de embeddings, se debe versionar el protocolo
y conservar la comparación con la baseline. Una generación completa no se
reutiliza si sus IDs o entradas ya no coinciden con el manifiesto declarado.

## Costes y cobertura: uso y pruebas

Spec: [`specs/30-costes-cobertura.md`](../../../specs/30-costes-cobertura.md).
Necesita el paquete de la empresa extraído en la raíz del repo
(`piia2_paquete_datos/`, fuera de git); no usa red ni API Key.

```python
from costes_y_cobertura import estimar_siniestro

salida = estimar_siniestro(salida_agente1, contexto)  # JSON del contrato Agente 2 -> Agente 3
```

- `vehiculo_id` es obligatorio en el contexto; debe estar resuelto antes del cálculo de costes.
- `poliza_id` es obligatorio solo con `rol == "propio"`; con `tercero_perjudicado` se ignora.
- Un contexto no válido lanza `ValueError` con el nombre del campo.
- `normativa` sale vacía: la rellena el RAG (#32).

Desde esta carpeta:

```bash
python probar_costes.py    # pruebas de AC-001 a AC-008 y AC-010
python evaluar_costes.py   # evaluación de AC-011 con los siniestros sintéticos (val + test)
```
