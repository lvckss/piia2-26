# ADR 0006: RAG con PostgreSQL, comparación de embeddings y estado de recuperación

- Estado: Aceptado
- Fecha: 2026-10-20
- GitHub Issue: https://github.com/lvckss/piia2-26/issues/32
- Planes cubiertos (Issue/mini-spec/Spec): [32-rag-normativa.md](../../entregas/cu-19-interpretacion-danos/specs/32-rag-normativa.md), persistencia, contrato de citas y diagnóstico, composición y evaluación.
- Planning PR: https://github.com/lvckss/piia2-26/pull/56 — integrada en `main` (merge `9d2affb`).
- Aceptación: Lucía Luis Castaño (`lucia-luis-castano`), [revisión APPROVED del 2026-10-28](https://github.com/lvckss/piia2-26/pull/56#pullrequestreview-5681219827) sobre la versión `b0a27d7` (v1.6), que cubre este ADR y la spec 32; incluye la decisión de Lucas del 2026-10-27 sobre el mínimo de 23/25. La adaptación del consumidor #31 está recogida por la #58 integrada; el plan de #34 sigue en revisión (PR #60).
- Versión: propuesta alineada con la Spec v1.6; v1 conservada en `0197825`, v1.1 en `88bd84d` y v1.2 en `c77a17c`. Referencias previas del 2026-10-22, mínimo 23/25 y reparto explícito de Compose actualizados el 2026-10-27.
- Sustituye / sustituido por: no sustituye un ADR aceptado. Sustituye la propuesta ChromaDB de la guía de RAG. Amplía el contrato base del ADR 0002 Aceptado e integrado por #37/#51 (`4a279e9`); los ADRs 0003 y 0004 también están Aceptados. Referencias fijadas más abajo.

## Contexto y motivación

La guía propone ChromaDB local y embeddings de OpenAI. El usuario ha elegido
PostgreSQL con pgvector, un entorno Docker integrable en un Compose raíz para
todo el proyecto, y la comparación de `text-embedding-3-small` y
`text-embedding-3-large`. El backend ya usa PostgreSQL, mientras que el RAG aún
no tiene código productivo.

El corpus contiene cuatro pólizas sintéticas y siete documentos legales. El
paquete trae 25 preguntas con respuesta y documento esperados. El objetivo
aceptado por Lucas, actualizado el 2026-10-27, es resolver al menos 23/25 con
el modelo seleccionado: 23 «bien», 24 «genial» y 25 «GOD»; su
viabilidad no está medida. Cambiar modelo puede cambiar dimensiones y geometría,
por lo que compartir una generación de embeddings entre modelos es incorrecto.

Las pólizas son cortas (2.415–3.283 caracteres), con ocho secciones homogéneas y
parámetros de cálculo disponibles en CSV. Cuando se conocen la póliza y el
concepto, la cláusula puede recuperarse directamente. Por eso no se presupone
que los embeddings sean necesarios ni mejores para ese subconjunto.
La arquitectura recoge el requisito de base vectorial y el corpus incluye
legislación extensa y variada: se mantiene la recuperación semántica y se
evalúa su utilidad por tipo de documento.

Los textos legales se consultan en la parte normativa del Agente 2, después
de los cálculos y antes del informe; aportan contexto general, especialmente
en responsabilidad civil de terceros. Las condiciones concretas del producto
proceden de su póliza y los números de la herramienta de costes. Recuperar una
ley no valida jurídicamente el presupuesto ni obliga a citar todos los textos.

El contrato actual admite `normativa: []` y el informe muestra «Sin fuentes».
Ese único valor no distingue una búsqueda correcta sin resultados de un índice
ausente o una caída del proveedor. Lucas pide un informe preliminar cuando
falta respaldo, con tipos de error bien diferenciados. Esto modifica una
frontera consumida por otras personas y requiere revisión previa.

## Decisión propuesta

1. **Persistencia:** PostgreSQL con pgvector, tablas propias para documentos,
   fragmentos, embeddings y manifiesto de generación. Texto y procedencia se
   conservan junto a los vectores. El origen documental sigue siendo el paquete
   recibido; la SQLite de CSV no se migra como requisito del RAG.
2. **Entorno:** un Compose común en `entregas/cu-19-interpretacion-danos/compose.yaml`,
   cuyo archivo e integración global son responsabilidad de #34. #32 aporta
   PostgreSQL/pgvector, volumen persistente, preparación del schema RAG, comandos
   y dependencias Python del componente; #34 integra el entorno de los agentes
   con web/backend/ML. La parte de base de datos puede verificarse antes del
   conjunto. Paquete en lectura y configuración por entorno; indexado y
   evaluaciones de pago explícitos. No hay un segundo Compose ni otra PostgreSQL.
3. **Modelos separados:** comparar small (1.536 dimensiones por defecto) y large
   (3.072), conservando manifiestos y generaciones independientes, sin mezcla
   de vectores. Publicar generación solo al completarse; reindexado idempotente
   y recuperación del índice activo anterior ante fallo.
4. **Baseline de búsqueda:** distancia coseno exacta, mismo corpus, troceado,
   filtros y k=4 para ambos. A este volumen, se prioriza una comparación sin
   pérdida adicional de recall por un índice aproximado. No se afirma latencia
   suficiente antes de medir. pgvector limita los índices HNSW de `vector` a
   2.000 dimensiones; no se crea uno sin adaptar y medir la configuración de
   large. Reducir dimensiones o usar otro tipo exige registrar otro experimento.
5. **Filtros:** póliza reconocida → esa póliza y legal; ID vacío → solo legal;
   ID desconocido → error. Los CSV gold de evaluación nunca forman parte del
   corpus ni proporcionan filtros ocultos a la búsqueda.
6. **Composición:** `agente2()` pertenece a #32, conserva el cálculo de #30 y
   añade las fuentes. Las consultas dependen del caso, con cobertura/franquicia,
   cristales/límites, pérdida total e indemnización o RC según corresponda.
   Las advertencias automáticas sobre otras exclusiones y plazos son evolución
   requerida posterior, con planificación propia.
7. **Contrato aditivo:** mantener `normativa` y añadir `diagnostico_rag` con
   estado agregado, resultados por consulta e incidencias con código, etapa,
   mensaje y reintentable, según la Spec. Propagar entradas/contratos inválidos
   y errores inesperados; representar los fallos externos esperados sin perder
   citas de consultas correctas. #31 y #34 deben aceptar y consumir la adición.
8. **Semántica honesta:** fragmentos recuperados son candidatos a respaldar una
   conclusión; top-k no demuestra soporte. No se añade LLM generador ni un score
   de fiabilidad numérico. La suficiencia se revisa en la evaluación; en el
   informe se exponen fuentes, temas sin fuentes y causas de fallos.
9. **Selección:** ambos modelos con las mismas 25 preguntas; hit@4 y suficiencia
   humana por pregunta, total y por tipo; tiempos, tokens y coste. Elegido con
   al menos 23 correctas; entre quienes cumplan, más aciertos y, en empate, menor
   coste. Si ninguno cumple, iterar con trazabilidad o replanificar con humano.
10. **Referencia directa:** evaluar las 16 preguntas de póliza recuperando por
    producto y tema/sección, sin embeddings ni consulta al gold. Aplicar la misma
    rúbrica y comparar con small/large en ese subconjunto. Las nueve preguntas
    legales son no aplicables a esta referencia; no se fabrica un total de 25
    ni se presupone superioridad vectorial. La referencia es un control de la
    evaluación, no un cambio de la interfaz ni del buscador productivo.

## Alternativas consideradas

| Alternativa | Ventajas | Inconvenientes / motivo |
|---|---|---|
| PostgreSQL + pgvector, elegida | SQL, filtros y persistencia en la tecnología ya usada por el backend; encaja con el Compose solicitado. | Exige extensión, preparación de schema, volumen y disciplina de versiones/modelos. |
| ChromaDB local, propuesta previa | Arranque sencillo desde Python; ya esbozada en la guía. | Lucas elige consolidar persistencia con PostgreSQL; cambiar ahora tiene poco coste porque el RAG no está implementado. |
| Qdrant | Almacén especializado con filtros de metadatos y ejecución local. | Introduce otra tecnología de persistencia sin requisito identificado que la haga preferible en este corpus. |
| Recuperación directa por póliza y sección | Predecible para cuatro documentos homogéneos; sin embeddings ni gasto de API. | Se incluye como referencia de evaluación de pólizas (AC-014). No cubre por sí sola la recuperación semántica del conjunto ni el requisito vectorial recogido en la arquitectura. |
| Un único modelo sin comparación | Menos indexado y evaluación. | Omite la comparación small/large expresamente solicitada por Lucas. |
| Mantener solo `normativa: []` | No cambia la forma del contrato. | Pierde la causa: consulta sin resultados, índice no preparado y fallo técnico se confundirían. |
| Fallar todo el flujo ante cualquier ausencia de fuentes | Evita un informe sin citas. | Lucas acepta el diagnóstico preliminar con límites visibles; una ausencia de fuentes puede coexistir con datos y cálculos disponibles. |
| Tratar cualquier excepción como falta de fuentes | Permite continuar siempre. | Oculta errores de entrada, cálculos o programación; se limita la degradación a fallos de recuperación esperados y tipados. |

## Consecuencias

- Se introduce PostgreSQL/pgvector como dependencia de la recuperación; el resto
  del cálculo sigue pudiendo ejecutarse aisladamente sin API de OpenAI.
- Los índices son regenerables desde datos y manifiesto; la configuración de
  embeddings debe coincidir al indexar y consultar. Cambiar modelo no reutiliza
  los vectores anteriores como si fueran equivalentes.
- Dos modelos suponen dos indexados y evaluaciones. Se medirá el coste y se
  reutilizarán embeddings de entradas idénticas. No hay gasto realizado en planificación.
- El mínimo 23/25 y las valoraciones 24 «genial» / 25 «GOD» son un requisito
  humano actualizado por Lucas, sin baseline propio todavía. El
  benchmark es pequeño y conocido; no permite afirmar rendimiento general ni
  garantía normativa para cualquier siniestro.
- La referencia directa permite comprobar si los embeddings aportan algo sobre
  las pólizas y evita justificar la tecnología solo por su disponibilidad.
  Los resultados legales se publican separados y no se atribuye una mejora sin
  una referencia medida. El presupuesto sigue siendo determinista y no se
  interpreta una cita como validación jurídica automática de la indemnización.
- El plan de #31 ya recoge la adaptación del contrato en AC-014 y AC-015 de su
  v2 (#58 integrada), condicionada a aceptar e integrar esta propuesta. Falta
  recoger el transporte del diagnóstico en el plan de #34. La #56 y este ADR quedan
  aceptados (ver «Aceptación»).
- TDD en indexado, filtros, errores y composición; eval-first en calidad. Cada
  AC de la Spec tiene frontera y evidencia prevista; las pruebas no se escriben
  en la Planning PR.
- La futura opción B sigue pendiente: incluir los documentos completos ahora
  no implementa el análisis de exclusiones y plazos ni cierra ese trabajo futuro.

## Referencias y evidencia

- Referencias contrastadas con `main` `73f60750572f0731c9bb9203ebb0dc4c4eaaead5` el 2026-10-22:
  [ADR 0002 — contrato JSON](https://github.com/lvckss/piia2-26/blob/73f60750572f0731c9bb9203ebb0dc4c4eaaead5/docs/adr/0002-contrato-json-entre-agentes.md),
  [ADR 0003 — proveedor OpenAI](https://github.com/lvckss/piia2-26/blob/73f60750572f0731c9bb9203ebb0dc4c4eaaead5/docs/adr/0003-proveedor-openai-clave-empresa.md) y
  [ADR 0004 — herramienta de costes](https://github.com/lvckss/piia2-26/blob/73f60750572f0731c9bb9203ebb0dc4c4eaaead5/docs/adr/0004-herramienta-costes-datos-empresa.md),
  Aceptados e integrados por [#51](https://github.com/lvckss/piia2-26/pull/51) (`4a279e9`).
- Consumidor #31: spec v2 integrada por [#58](https://github.com/lvckss/piia2-26/pull/58)
  (`0deba77`, merge `73f6075`), con
  [confirmación de Víctor](https://github.com/lvckss/piia2-26/pull/56#issuecomment-6321492952)
  y [revisión de Lucas](https://github.com/lvckss/piia2-26/pull/58#pullrequestreview-5615735502)
  sobre AC-014 y AC-015. No acredita aceptación del conjunto de #56 ni de este ADR.
- Issue y aclaración de alcance: https://github.com/lvckss/piia2-26/issues/32#issuecomment-6236068132.
- Decisiones de Lucas: conversación de diseño de #32, 2026-10-20, que se registra
  mediante comentario de planificación con la versión de este borrador. Son
  decisiones de alcance, no aceptación anticipada del documento ni del ADR.
- Inspección del paquete: 35 archivos coincidentes con el ZIP, 11 documentos,
  32 secciones de póliza y 25 preguntas (16/9); hashes en la Spec. Sin ejecución
  de estimadores, llamadas de embeddings ni evaluación de calidad.
- [pgvector: exact search, dimensiones, filtros e imagen Docker](https://github.com/pgvector/pgvector).
- [OpenAI: embeddings y dimensiones](https://developers.openai.com/api/docs/guides/embeddings).
- [OpenAI small](https://developers.openai.com/api/docs/models/text-embedding-3-small),
  [OpenAI large](https://developers.openai.com/api/docs/models/text-embedding-3-large).
- [Docker Compose](https://docs.docker.com/compose/intro/compose-application-model/).
- Guía de partida: `entregas/cu-19-interpretacion-danos/specs/agente2-rag-normativa-guia.md`.
