# Primer indexado del RAG · 3 de noviembre de 2026

Referencias: [Issue #32](https://github.com/lvckss/piia2-26/issues/32),
[spec v1.6](../../specs/32-rag-normativa.md), [ADR 0006 Aceptado](../adr/0006-rag-postgresql-estado-recuperacion.md)
y [autorización del primer indexado](https://github.com/lvckss/piia2-26/issues/32#issuecomment-6610867828).

Este incremento verifica el indexado y su persistencia; **no mide aún la calidad
de recuperación ni acredita el objetivo de 23/25**. Continúan pendientes la
búsqueda, `agente2()` y la evaluación de ambos modelos.

## Corpus y protocolo congelados

- Cuatro pólizas sintéticas y siete textos legales del paquete original.
- SHA-256 del corpus: `f493d6494e41c24c43b127a37e1930d6e19e4fd0426520b190be7f129189cb5c`.
- Protocolo: `articles-policy-sections-char1500-overlap200-title-v1`.
- Pólizas por encabezado `##`; artículos legales con números o palabras,
  preámbulo separado y fallback cuando no hay artículos. Ventanas legales de
  hasta 1.500 caracteres y 200 de solape. Título/sección en la entrada de
  embeddings, sin alterar el pasaje literal conservado.
- **2.032 fragmentos:** 36 de póliza (32 secciones y cuatro preámbulos), 1.996 legales.
- **1.981 entradas distintas**; las 51 repeticiones reutilizan el mismo vector
  dentro de cada modelo, manteniendo todas las procedencias.
- 572.370 tokens distintos por modelo; máximo por entrada: 992 tokens.
- Las 25 preguntas y sus respuestas/fuentes gold están fuera del corpus.

## Ejecución real

Lucas autorizó hasta **5 USD** para este primer indexado con ambos modelos.
Las llamadas se ejecutaron explícitamente; el SDK tiene sus reintentos
automáticos desactivados. La base es PostgreSQL en Docker, compartida con el
explorador, con tablas propias en `rag`.

| Modelo | Dimensiones | Vectores nuevos | Peticiones | Tokens de entrada reportados | Tiempo | Coste calculado |
|---|---:|---:|---:|---:|---:|---:|
| text-embedding-3-small | 1.536 | 1.981 | 62 | 572.370 | 52,94 s | 0,0114474 USD |
| text-embedding-3-large | 3.072 | 1.981 | 62 | 572.370 | 80,24 s | 0,0744081 USD |
| **Total** | — | **3.962** | **124** | **1.144.740** | — | **0,0858555 USD** |

El coste se calcula con los tokens devueltos por OpenAI y las tarifas
consultadas el 2026-11-03: [small](https://developers.openai.com/api/docs/models/text-embedding-3-small)
y [large](https://developers.openai.com/api/docs/models/text-embedding-3-large).
Es una estimación de uso, no la factura de la cuenta.

Generaciones completas, activas por modelo:

- Small: `0268f36a2bdde33559fd9b64243e5e69b564c769df8f6543e0448634d5015e82`.
- Large: `702458e2ca49f00a4b4bca29f52dbb2123787a96e7a5d27973fb16409e862f54`.

Cada una enlaza los once documentos y los 2.032 fragmentos. No se ha elegido
todavía un modelo ganador ni se han creado índices aproximados.

## Verificación

| Comprobación | Resultado observado |
|---|---|
| Literalidad en PostgreSQL | Cero fragmentos cuyo texto difiera del intervalo del documento citado. |
| Repetición sin clave utilizable y presupuesto cero | Ambos modelos: cero vectores nuevos, cero peticiones, cero tokens y cero coste adicional. |
| Persistencia real | Recreado el contenedor conservando el volumen; ambas generaciones siguen completas y reutilizables con presupuesto cero. |
| Explorador | Se conservan 4.000 imágenes, 8.740 instancias y 6 etiquetas; SHA-256 de filas y posiciones de secuencias iguales al respaldo previo. |
| Modelos y caché | 1.981 vectores de 1.536 dimensiones y 1.981 de 3.072, con claves y FKs que separan modelo/dimensiones. |
| Fallos y reanudación | Pruebas con PostgreSQL real y proveedor simulado conservan la activa anterior y reutilizan lotes guardados. |

TDD observado: primero fallaron las pruebas del corpus vacío, esquema ausente,
indexado sin efectos, presupuesto sin control y CLI sin plan. Tras implementar,
pasaron; una prueba adicional detectó que no bastaba comparar el número de
fragmentos de una generación completa y se añadió comparación de IDs/entradas.

Comando reproducible de las pruebas deterministas e integración:

```bash
just rag-setup
just rag-test
```

Son **18 pruebas**, con documentos sintéticos, PostgreSQL Docker desechable,
puerto libre y OpenAI simulado; no utilizan el índice real ni gasto de API.
La retirada de archivos se verifica en una generación nueva conservando las
históricas. También se comprueban cuota, límite temporal y timeout diferenciados.

Entorno verificado: PostgreSQL 18.6, pgvector 0.8.7, Python 3.12,
OpenAI Python 3.42.1, psycopg 3.3.7 y tiktoken 0.14.0. El SQL y los comandos
operan dentro de la carpeta del caso; no se publican documentos, vectores,
credenciales, volúmenes ni respaldos privados.

La verificación corresponde a AC-001/002, literalidad de AC-003, parte de errores
de AC-005, gasto explícito de AC-012 y parte RAG de AC-013. Las verificaciones de
consulta, consumidores, montaje del entorno completo y calidad siguen pendientes.
