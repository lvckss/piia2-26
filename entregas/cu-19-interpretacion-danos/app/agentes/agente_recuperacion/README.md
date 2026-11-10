# Agente 2 — Costes, cobertura y normativa (RAG)

Dos piezas en esta carpeta, con dos responsables y un único punto de contacto.

| Pieza | Responsable | Guía |
|---|---|---|
| **Costes y cobertura**: convierte los hallazgos del Agente 1 en dos presupuestos con la tool de la empresa (`piia2_paquete_datos/scripts/estimar_coste.py`) y calcula pérdida total, cobertura e indemnización. Fichero: `costes_y_cobertura.py`. | Víctor | [`agente2-costes-cobertura-guia.md`](../../../specs/agente2-costes-cobertura-guia.md) |
| **Normativa (RAG)**: PostgreSQL/pgvector compartida con el explorador. Indexado y búsqueda de pólizas y legislación; evaluación de 25 preguntas pendiente. | Lucas | [Spec 32](../../../specs/32-rag-normativa.md) |

**Punto de contacto:** `buscar_normativa(pregunta, k=4, poliza_id="") -> [{"tema", "extracto", "fuente"}]`
(la escribe Lucas y rellena el campo `normativa` de la salida de Víctor).

Datos de entrada y salida de ejemplo: `../ejemplos_contrato/`.

Los documentos, fragmentos, vectores y generaciones se guardan en el esquema
`rag` de la misma PostgreSQL Docker del explorador. No se utiliza ChromaDB.
Ya están implementados el indexado y `buscar_normativa()`; `agente2()` y la
evaluación de calidad siguen pendientes. Antes de componer `agente2()` debe
revisarse e integrarse la v1.7 acordada para AC-007.

Las recetas `just` usan un shell POSIX y las rutas de entorno virtual de Linux,
macOS o WSL. Para Windows nativo se ofrecen [comandos de PowerShell](#windows-nativo-powershell);
no se afirma que las recetas POSIX funcionen en PowerShell.

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

## Búsqueda con fuentes y filtro por póliza

```bash
just rag-query-plan '¿Qué cubre esta póliza?' POLIZA_ID small
just rag-query 0.01 '¿Qué cubre esta póliza?' POLIZA_ID small
just rag-query 0.01 'Responsabilidad civil del asegurador' '' large
```

Sustituye `POLIZA_ID` por el nombre del fichero de póliza sin `.md`, respetando
mayúsculas. El primer comando solo estima tokens/coste, sin conectar a la base
ni comprobar que exista esa póliza. Los dos siguientes ejecutan una consulta
con un máximo explícito de 0,01 USD **por comando**, no un presupuesto global.
Para fijar otro k se puede usar `consultar_normativa.py --k N` directamente.
La estimación usa las tarifas registradas el 2026-11-03; no es una factura.

La recuperación usa la generación activa del modelo seleccionado, búsqueda
exacta por coseno, filtro SQL antes del límite y el ID del fragmento para
desempatar. Con póliza se consulta esa póliza y legislación; con ID vacío,
únicamente legislación. Un ID desconocido falla antes de llamar a OpenAI.
No hay inferencia de póliza por similitud, umbral de relevancia ni índices
HNSW/IVFFlat: la columna `vector` conserva 1.536/3.072 dimensiones separadas
por modelo. Esta configuración sigue la referencia inicial aceptada.

Cada resultado tiene exactamente `tema`, `extracto` y `fuente`: pregunta de
consulta, pasaje literal y ruta relativa con sección/ventana y líneas.
La consulta fija una generación antes de pedir el embedding y la conserva
aunque se publique otra mientras espera. No crea tablas ni indexa al consultar.

La función de integración conserva su firma:

```python
from normativa_rag import buscar_normativa

fragmentos = buscar_normativa("Responsabilidad civil del asegurador", k=4)
```

Para ejecutarla se configuran `DATABASE_URL`, `OPENAI_API_KEY`,
`RAG_QUERY_EXECUTE=1`, `RAG_QUERY_MAX_COST_USD` y opcionalmente `RAG_MODEL=small`
o `large` (small por defecto provisional). El límite es **por invocación**;
no controla todo el gasto de una aplicación. Un consumidor con varias
consultas puede reutilizar `NormativaRetriever` con un único cliente
`OpenAIEmbeddings(SpendingBudget(limite_total))` para compartir presupuesto.
Importar el módulo no conecta ni llama al proveedor. Las variables exportadas
tienen prioridad sobre `.env` del caso y `app/.env`; solo se cargan al ejecutar.

`RagError` expone `code`, `stage`, `retryable` y un mensaje sin credenciales.
Distingue entrada inválida, índice no preparado/incompatible, BD no disponible,
autenticación, cuota, límite temporal, timeout y respuesta inválida.
`[]` indica únicamente una consulta válida sin candidatos permitidos; no oculta
fallos técnicos. La falta de autorización o presupuesto lanza `PermissionError`.
Los errores inesperados se propagan. No hay reintentos automáticos.

**Límite de calidad:** top-k devuelve candidatos, no acredita que respalden una
conclusión. Se conserva el protocolo v1, incluidos los fragmentos cortos de
tablas legales señalados en revisión. No se filtran silenciosamente antes de
medir la referencia inicial. Cualquier mejora requiere versionar el experimento
y comparar ambos modelos; sigue pendiente el objetivo de 23/25.

## Pruebas del indexado y la búsqueda

```bash
just rag-test
```

Ejecuta las suites de indexado y búsqueda, cada una con proyecto/volumen Docker
desechable y un puerto libre, con documentos sintéticos y OpenAI simulado; no
usa la base real ni realiza llamadas de pago. Incluye literalidad, artículos,
repetición, separación de modelos, caché, fallo de lote, retirada de documentos,
respuestas incompatibles, cuota frente a límite temporal y autorización de gasto.
También comprueba las cuatro pólizas, vacío/desconocida, orden por coseno,
desempate, fuentes literales, índice incompleto, cambio concurrente de generación,
caída de BD y consultas demasiado largas sin gasto.
La referencia es `specs/32-rag-normativa.md` + cada ID AC en el nombre del test.

Para solo las pruebas sin base, se puede ejecutar `probar_indexado.py` sin
`--postgres`: omite las siete de integración, que no se presentan como superadas.
La calidad 23/25 y las pruebas de composición no se acreditan con estas pruebas.

Para ejecutar solo la suite de búsqueda con base desechable:

```bash
.venv-rag/bin/python app/agentes/agente_recuperacion/probar_rag.py --postgres
```

Sin `--postgres` ni `RAG_TEST_DATABASE_URL`, `probar_rag.py` omite las pruebas
de integración; los skips no acreditan PostgreSQL. No se debe exportar la URL
de la base real como `RAG_TEST_DATABASE_URL`.

Si cambia el troceado o el prefijo de embeddings, se debe versionar el protocolo
y conservar la comparación con la baseline. Una generación completa no se
reutiliza si sus IDs o entradas ya no coinciden con el manifiesto declarado.

## Windows nativo (PowerShell)

Desde la carpeta del caso, con Python 3.11+ y Docker Desktop configurado para
contenedores Linux, estos son los equivalentes sin Just:

```powershell
py -3 scripts/init_postgres.py
docker compose --env-file .env.postgres up -d --wait postgres
py -3 -m venv .venv-rag
$ragPython = ".\.venv-rag\Scripts\python.exe"
$ragDir = "app/agentes/agente_recuperacion"
& $ragPython -m pip install -r "$ragDir/requirements-rag.txt"
$env:TIKTOKEN_CACHE_DIR = "$PWD/.cache-rag/tiktoken"
& $ragPython -c 'import tiktoken; tiktoken.get_encoding("cl100k_base")'
& $ragPython "$ragDir/indexar_normativa.py" --model both
& $ragPython "$ragDir/consultar_normativa.py" 'Responsabilidad civil del asegurador'
& $ragPython "$ragDir/probar_indexado.py" --postgres
& $ragPython "$ragDir/probar_rag.py" --postgres
```

El indexado o la consulta de pago se solicitan añadiendo
`--execute --max-cost-usd 0.01` al comando correspondiente, ajustando el máximo
antes de ejecutarlo. Para el paquete fuera de las rutas por defecto:
`$env:PLEXUS_DATA_DIR = 'C:/ruta/al/paquete'`. Para detener la base:
`docker compose --env-file .env.postgres stop postgres`.
Los ejemplos nativos se han revisado, pero no ejecutado en Windows en esta
entrega; la verificación de este incremento se ha realizado en Linux.

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
