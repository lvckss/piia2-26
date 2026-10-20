# Spec: RAG de normativa y composición del Agente 2

- GitHub Issue: https://github.com/lvckss/piia2-26/issues/32
- Estado: Borrador
- ADR decision: NEW_ADR
- ADR: [0006 — RAG con PostgreSQL y estado de recuperación](https://github.com/lvckss/piia2-26/blob/main/docs/adr/0006-rag-postgresql-estado-recuperacion.md) — Propuesto; accesible en la rama de esta Planning PR hasta su integración.
- Justificación: fija la persistencia vectorial, la separación de índices por modelo y una ampliación del contrato Agente 2 → Agente 3/orquestación para distinguir fuentes ausentes y fallos técnicos. Los ADRs previos de la #37 siguen Propuestos; no acreditan REUSE_ADR.
- Plan vigente / versión: v1, este archivo en `plan/32-rag-normativa`; el comentario de planificación de la Issue fijará el commit publicado.
- Riesgo y revisión previa: sí, por NEW_ADR y por la revisión de planes en PR acordada para la entrega. Impacto: fuentes de conclusiones económicas; consumidores independientes: #31 y #34. Reversión de la tecnología posible regenerando el índice; incertidumbre de calidad pendiente de evaluación.
- Planning PR: pendiente de publicación del borrador.

## Qué construir

Un RAG en Python que indexa las cuatro pólizas sintéticas y los siete textos
legales de Plexus en PostgreSQL con pgvector, recupera fragmentos literales con
su fuente y los incorpora a los cálculos de la #30 mediante `agente2()`.

La interfaz de recuperación se conserva:

`buscar_normativa(pregunta, k=4, poliza_id="") -> list[dict]`

Cada elemento tiene exactamente `tema`, `extracto` y `fuente`, cadenas no vacías.
`extracto` procede literalmente del documento; `fuente` identifica el fichero
relativo al paquete y la sección. `tema` es la pregunta de esa consulta.

`agente2(salida_agente1, contexto)` llama a `estimar_siniestro`, obtiene las
fuentes relevantes para ese caso y devuelve el resultado con `normativa` y
el diagnóstico de recuperación propuesto más abajo. La #34 consume esa función.

### Estado actual y evidencia

- Main examinado: `5bdabe2ef6d9aa63ca3ea68f20a57fc85f79f449`.
- `app/agentes/agente_recuperacion/` solo contiene un README; la guía
  `agente2-rag-normativa-guia.md` contiene una propuesta ChromaDB, sin implementación.
- El backend ya utiliza PostgreSQL (`app/server/bd/bd.ts`), sin evidencia de pgvector habilitado.
- Las specs de costes (#40, `476f0f7`) e informe (#41, `3d18937`) están en PRs abiertas;
  la primera asigna `agente2()` a #32. La aclaración de Lucía está en
  https://github.com/lvckss/piia2-26/issues/32#issuecomment-6236068132.
- La guía filtra por póliza cuando recibe un ID, pero con ID vacío consulta todo
  el corpus aunque su texto pide solo legislación para terceros. Este plan resuelve esa contradicción.
- El paquete se ha leído desde `datos/`, fuera de los archivos versionados.
  Sus 35 archivos extraídos coinciden con los del ZIP. Los 13 CSV están cargados
  también en `piia2.db`; esta SQLite no contiene un índice vectorial.

## Por qué

El informe necesita poder señalar los documentos que respaldan las reglas
aplicadas por costes y cobertura. La recuperación de un fragmento y la calidad
del presupuesto son verificaciones distintas: una cita no acredita por sí sola
la corrección de todas las conclusiones ni produce una probabilidad de fiabilidad.

Las fuentes pueden faltar o fallar técnicamente. El sistema debe conservar esa
diferencia para que el informe explique sus límites y las siguientes acciones.

## Alcance

- Incluido: indexado reproducible e idempotente; PostgreSQL y pgvector; embeddings
  de OpenAI small y large; recuperación filtrada con citas; evaluación de ambos;
  `agente2()`; consultas según el caso; diagnóstico distinguible por tema y error;
  entorno del componente preparado para el Compose raíz.
- Fuera de alcance: modificar cálculos o CSV de costes (#30), detección/visión,
  generar respuestas o conclusiones con otro LLM, modificar los documentos de
  Plexus, incorporar el CSV de preguntas al corpus, automatizar decisiones de
  cobertura a partir del texto, renderizar el informe (#31), orquestar todos los
  agentes o completar el despliegue del proyecto (#34), comparar modelos de chat.

### Primera entrega y evolución requerida

**Opción A, esta entrega:** recuperar citas que respalden los cálculos de
cobertura, franquicia, límites e indemnización.

**Opción B, evolución requerida:** recuperar además exclusiones, plazos y otras
condiciones, y mostrar qué circunstancias del siniestro necesitan revisión.
Deberá planificarse e implementarse después, con datos necesarios, reglas de
aviso y AC propios. Está pendiente de entrega futura y no forma parte de la
DoD de #32. Indexar los documentos completos permite consultar esos contenidos
en las 25 preguntas sin introducir ahora avisos automáticos sobre ellos.

## Restricciones y supuestos

### Datos y persistencia

- Entrada documental: `docs/polizas_sinteticas/*.md` y `docs/legal/*.txt` del paquete.
  Son cuatro pólizas, siete textos legales y 32 secciones de póliza. La legislación
  se trata como el snapshot recibido; no se afirma vigencia ni se descarga al arrancar.
- Paquete leído: ZIP SHA-256 `1a0ab7e4000f83716f94ebf6583f395748c9ae8d0cacbd16e8d8d20221613c83`.
- Preguntas: SHA-256 `4f9e629a317885f3c83559ca81b4d2ca476eb45aa0c6473b8a0adb4d97591369`;
  25 filas, 16 `poliza` y 9 `legal`. Todas sus fuentes existen.
- Corpus SHA-256 `f493d6494e41c24c43b127a37e1930d6e19e4fd0426520b190be7f129189cb5c`, calculado
  concatenando, en orden de ruta, ruta relativa UTF-8, byte nulo, contenido, byte nulo.
- La ruta del paquete será configurable; el montaje de Docker podrá usar la
  carpeta local `datos/` o una extracción `piia2_paquete_datos/`. Las fuentes
  devueltas conservan siempre rutas `docs/...`, sin rutas privadas del host.
- Troceado inicial: pólizas por encabezado `##`; legal por artículo con número
  o palabras, preámbulo separado y fallback para documentos sin artículos.
  Bloques legales largos en ventanas de hasta 1.500 caracteres y 200 de solape,
  siguiendo la guía. La sección y el ordinal distinguen las ventanas.
- Los títulos y el producto pueden acompañar al texto usado para generar el
  embedding, pero el extracto devuelto conserva el pasaje original.
- Cada generación identifica corpus, protocolo de troceado, modelo y dimensiones.
  small usa inicialmente 1.536 dimensiones y large 3.072; nunca se mezclan vectores
  de modelos distintos. Búsqueda exacta por coseno en la comparación inicial;
  los índices aproximados serán una optimización medible posterior.
- Una generación nueva solo sustituye a la activa al completarse y validarse.
  Reindexar las mismas entradas no duplica fragmentos ni repite embeddings ya
  guardados. Eliminar un archivo de un corpus nuevo retira sus fragmentos de esa
  generación, preservando la activa ante fallos.

### Búsqueda, composición y filtros

- Con `poliza_id` reconocido se consulta únicamente esa póliza y legislación.
  Con `poliza_id=""` se consulta únicamente legislación. No se infiere la póliza
  por similitud del texto cuando el contexto ya la identifica.
- Pregunta vacía, `k` no entero positivo o póliza desconocida producen error de
  entrada explícito. `k` limita los resultados; puede haber menos candidatos.
- La consulta no crea un índice vacío ni inicia un indexado automáticamente.
- La búsqueda inicial ordena por distancia y usa un identificador estable para
  desempatar. No se fija un umbral de relevancia sin calibración. Un top-k es un
  conjunto de candidatos, no una prueba automática de que la respuesta existe.
- Las consultas de `agente2()` se eligen por reglas deterministas a partir de
  los datos y resultados de costes. Se mantienen separadas por tema:
  daños propios por colisión → cobertura y franquicia de daños propios;
  daños de cristal → cobertura, franquicia y límite de lunas;
  pérdida total en algún escenario → criterio y regla de indemnización;
  tercero perjudicado → responsabilidad civil, únicamente legislación.
  Solo se incluye una consulta para cada tema distinto aplicable.
- Si ningún escenario tiene daños presupuestables, no se fuerza una consulta
  genérica: diagnóstico `no_aplica`. La lista vacía de ese caso no equivale a fallo.
- Con rol propio, la póliza viene del contexto validado por #30. Con tercero se
  omite la póliza aunque el contexto contenga un valor residual, igual que #30.
- Se conservan todos los resultados y cifras de `estimar_siniestro`; únicamente
  se sustituye `normativa` y se añade `diagnostico_rag`. Los errores de costes y
  de contrato se propagan; no se producen cifras alternativas ante ellos.

### Contrato propuesto de diagnóstico — a revisar con #31 y #34

El JSON del Agente 2 incorpora `diagnostico_rag`, objeto con:

- `estado`: `recuperadas`, `parcial`, `sin_resultados`, `error` o `no_aplica`.
- `consultas`: lista con `tema`, `estado`, `fuentes` e `incidencias` de cada consulta.
  En una consulta, el estado es `recuperadas`, `sin_resultados` o `error`.
  `fuentes` contiene las referencias de los fragmentos realmente devueltos.
- Cada incidencia contiene `codigo`, `etapa`, `mensaje` y `reintentable`.
  Los mensajes destinados al informe son comprensibles; los detalles técnicos
  y excepciones originales quedan en logs sin credenciales ni volcado de documentos.

Agregado: todas las consultas tienen fragmentos → `recuperadas`; algunas sí y
otras no o fallan → `parcial`; todas vacías con consultas correctas → `sin_resultados`;
ninguna tiene fragmentos y alguna falla → `error`; sin temas aplicables → `no_aplica`.
Una consulta fallida no elimina las citas de otras que terminaron correctamente.

`recuperadas` solo acredita recuperación, no validación semántica automática.
La evaluación manual comprueba pertinencia. En ejecución se presentan citas
por tema y la revisión necesaria, sin etiquetar conclusiones como verificadas
por el mero hecho de que PostgreSQL devuelva vecinos.

La #31 deberá mostrar las incidencias y el carácter preliminar en casos
`parcial`, `sin_resultados` o `error`, distinguiendo el tema afectado y el motivo.
Texto de referencia: «Informe preliminar: no se han recuperado fuentes
suficientes para respaldar las conclusiones indicadas sobre cobertura e
indemnización. Estas conclusiones requieren revisión».
Su representación es una dependencia de coordinación: este plan no modifica
silenciosamente el alcance ni los AC de la PR #41. La #34 debe transportar el
diagnóstico y distinguir esos fallos de un error que impide calcular costes.

### Entorno reproducible

Objetivo confirmado por Lucas: todo el proyecto arrancará desde un Compose
raíz. #32 entregará la parte de PostgreSQL/pgvector y el entorno Python de
los agentes con comandos de preparación, indexado, consulta y evaluación.
El montaje conjunto de frontend, backend, ML y recorrido completo se concretará
en la planificación de #34; no queda acreditado por probar solo el RAG.

PostgreSQL tendrá volumen persistente; los datos se montarán en solo lectura.
Versiones de PostgreSQL, pgvector y dependencias fijadas al implementar y
registradas en los resultados. Conexión y clave por entorno. El indexado y la
evaluación de pago serán comandos explícitos, separados del arranque normal.
El cliente RAG y el backend deben poder usar el mismo servicio PostgreSQL con
tablas propias del RAG, sin alterar las tablas existentes.

### Clarify

| Incertidumbre | Clasificación | Evidencia / decisión y efecto |
|---|---|---|
| Tecnología vectorial y ejecución | Resuelta por Lucas en esta sesión, 2026-10-20 | PostgreSQL + pgvector; Docker y Compose raíz como objetivo del proyecto. Sustituye la propuesta ChromaDB de la guía. |
| Dueño de `agente2()` | Resuelta por Lucas | Se incluye en #32; #34 la consume. Responde a la aclaración enlazada de Lucía. |
| Opción A o B | Resuelta por Lucas | A en esta entrega; B evolución requerida posterior. |
| Fallo o ausencia de fuentes | Resuelta en comportamiento de producto; contrato propuesto pendiente de revisión | Informe preliminar, causas distinguibles; sin confianza numérica inventada. #31 y #34 deben consumirlo. |
| Modelos y objetivo de calidad | Resuelta por Lucas | Comparar small y large. Objetivo del modelo seleccionado: al menos 24/25 correctas. Es requisito de producto, no resultado medido ni garantía del proveedor. |
| Compatibilidad del contrato aditivo | Bloqueante para Ready | Acordar `diagnostico_rag` y su representación con responsables de #31 y #34, y actualizar sus planes con trazabilidad. Por eso este plan se publica como borrador. |
| Calidad real y costes de ambos modelos | Pendiente de evaluación durante implementación | Sin baseline de este corpus. Medir siguiendo el protocolo antes de afirmar cumplimiento de AC-011. Un resultado insuficiente obliga a iterar o replanificar; no rebajar el objetivo. |
| Relevancia de candidatos en ejecución | Límite declarado | El top-k no garantiza soporte. No se introduce un clasificador de soporte ni un umbral de distancia sin evidencia; el informe conserva la necesidad de revisión. |
| Disponibilidad en la cuenta Plexus | Comprobación de entorno previa a implementación | Validar acceso a ambos modelos sin publicar la clave; una restricción requiere resolver el impedimento, no sustituir un modelo silenciosamente. |

## Comportamiento que debe preservarse

- Firma y tres campos por fragmento de `buscar_normativa`; documentos y rutas
  de fuente recibidos. → AC-003, AC-004.
- Cifras, hallazgos, escenarios y decisiones de cobertura de #30 sin cambios;
  ninguna llamada al RAG modifica las entradas. → AC-006, AC-007.
- Los consumidores con `normativa: []` siguen pudiendo leer el contrato base.
  Para los nuevos avisos se requiere adaptación explícita de #31 y #34. → AC-008.
- La función de costes y el generador determinista de informes no pasan a
  depender de OpenAI para funcionar por separado. → AC-006, AC-007.

## Failure modes y requisitos no funcionales

| Condición | Código / comportamiento | Cobertura |
|---|---|---|
| Consulta correcta sin candidatos | `SIN_RESULTADOS`; no es fallo técnico; `reintentable=false`. | AC-005, AC-008 |
| Entrada inválida, incluida póliza desconocida | `ENTRADA_INVALIDA`; excepción explícita, etapa `entrada`; no reintentable sin corregir datos. | AC-004, AC-005 |
| Índice ausente, incompleto o incompatible | `INDICE_NO_PREPARADO` o `INDICE_INCOMPATIBLE`; preparar o reconstruir, nunca devolverlo como falta de coincidencias. | AC-002, AC-005 |
| PostgreSQL inaccesible | `BD_NO_DISPONIBLE`, etapa `base_datos`; reintentable; el aviso informa de fallo de consulta. | AC-005, AC-008 |
| Credenciales del proveedor rechazadas | `EMBEDDINGS_AUTENTICACION`, etapa `embeddings`; no reintentable sin corregir configuración. | AC-005, AC-008 |
| Cuota agotada, límite temporal o timeout | `EMBEDDINGS_CUOTA` no reintentable sin resolver cuota; `EMBEDDINGS_LIMITE_TEMPORAL` y `EMBEDDINGS_TIMEOUT` reintentables. Conservar distinción cuando el proveedor la exponga. | AC-005, AC-008 |
| Respuesta de embeddings no válida | `EMBEDDINGS_RESPUESTA_INVALIDA`; error de proveedor, no usar vectores parciales ni incompatibles. | AC-002, AC-005 |
| Error inesperado de programación o contrato de costes inválido | Propagar; no ocultarlo como una incidencia recuperable ni producir un informe de éxito. | AC-007 |
| Algunas consultas fallan | Conservar resultados buenos y distinguir incidencias por tema. | AC-008 |
| Reinicio o reindexado | Persistencia, idempotencia y generación activa íntegra. | AC-001, AC-002, AC-013 |
| Latencia y coste | Medir ambos modelos sin inventar presupuestos de latencia ni afirmar rendimiento no observado. | AC-010, AC-011 |

## Acceptance Criteria

| ID | Dado / Cuando | Resultado esperado y condición de éxito |
|---|---|---|
| AC-001 | El corpus versionado y una PostgreSQL con pgvector preparada; se indexa y se repite con el mismo corpus, modelo y protocolo. | Hay fragmentos de los 11 documentos, con sección y procedencia; se conservan los artículos con número o palabras y los documentos sin artículos. La segunda ejecución mantiene IDs y recuento, sin duplicados ni nuevas llamadas de embeddings para entradas ya disponibles. |
| AC-002 | Una generación small activa; se crea large, se cambia el corpus o falla un lote durante el indexado. | Ambas generaciones quedan separadas por modelo/dimensiones/corpus; un fallo deja activa la generación anterior íntegra. Consultar con un modelo incompatible o sin generación válida produce el código correspondiente. |
| AC-003 | Pregunta válida y candidatos disponibles; se llama a la firma acordada. | Devuelve hasta k elementos, cada uno con exactamente `tema`, `extracto`, `fuente`; cada extracto coincide con un pasaje del documento citado y la sección se puede localizar. Solo se devuelven fuentes del corpus activo. |
| AC-004 | Consultas con cada póliza válida, con póliza vacía, con póliza desconocida, pregunta vacía o k inválido. | Póliza válida: todos los resultados son de esa póliza o legales. Vacía: todos legales. Entradas inválidas: `ENTRADA_INVALIDA` y ninguna consulta de pago. |
| AC-005 | Se simulan por separado ausencia de candidatos, índice ausente/incompatible, caída de PostgreSQL y cada error de embeddings de la tabla. | Ausencia válida devuelve []; fallos técnicos producen un error tipado con código, etapa, mensaje y reintentable acordes. Ningún error técnico se transforma en un resultado vacío válido. |
| AC-006 | Salida válida de la función de costes y respuestas de RAG guionizadas; se llama a `agente2()`. | Todos los campos originales son idénticos salvo `normativa`; se añaden citas y `diagnostico_rag`. Entradas sin mutaciones. Con la #30 integrada, la integración reproduce las cifras del ejemplo real. |
| AC-007 | Casos de colisión, cristal, pérdida total en un escenario, tercero y escenarios sin daños; también una excepción de costes y un error inesperado del RAG. | Se consultan solo los temas aplicables definidos en el plan; tercero usa únicamente legal; sin temas → `no_aplica`. Errores de costes o inesperados se propagan. No hay llamadas RAG cuando costes falla. |
| AC-008 | Todas las consultas devuelven citas, algunas vacías, todas vacías, algunas fallan, todas fallan y ningún tema aplica. | El diagnóstico sigue exactamente la agregación descrita, conserva las citas válidas y señala cada tema/código afectado. Una prueba de consumidor acordada con #31/#34 demuestra que se puede mostrar el aviso preliminar y distinguir ausencia de resultados de fallo técnico. |
| AC-009 | Las 25 preguntas del CSV local y su versión/hash; se ejecuta la evaluación. | Produce una fila por pregunta/modelo, IDs de fragmentos, fuentes, hit@4, juicio de suficiencia y motivo de fallo; resúmenes total y por tipo. Las respuestas esperadas y fuentes gold se usan solo al puntuar. |
| AC-010 | small y large disponibles; se comparan con el mismo corpus, troceado, preguntas, filtros y k=4. | Informe de ambos modelos con configuración, dimensiones, tokens, coste, latencia de consultas e indexado, aciertos y fallos. No se comparan configuraciones ocultamente diferentes ni se mezclan sus índices. |
| AC-011 | La comparación y la revisión de fragmentos están terminadas. | El modelo seleccionado resuelve correctamente al menos 24/25 preguntas, según fuente y suficiencia definidas en el protocolo. Se publica el resultado de ambos; el otro modelo puede quedar por debajo. Si ninguno cumple, no se acredita DoD ni se rebaja el criterio sin decisión humana y replanificación. |
| AC-012 | Un proceso de indexado o evaluación sin autorización explícita de gasto, y pruebas con cliente falso. | El arranque normal no genera embeddings ni ejecuta evaluación de pago; las pruebas deterministas se ejecutan sin clave ni red de OpenAI, usando PostgreSQL de prueba cuando corresponda. |
| AC-013 | Entorno limpio con Docker y el paquete local; se arranca la parte del RAG desde el Compose raíz, se indexa, consulta y reinician contenedores. | Los comandos documentados preparan el componente, la consulta funciona y los fragmentos persisten tras recrear los contenedores conservando el volumen. Documentos montados en lectura, configuración por entorno; datos, claves y volumen ausentes del diff. |

## Test Plan

### Test seams y estrategia

- **S1 — indexado y consulta de PostgreSQL/pgvector:** integración con una base
  desechable real y cliente de embeddings inyectado. Protege persistencia,
  filtros y cambio de generación, sin sustituir SQL por un mock.
- **S2 — `buscar_normativa(...)`:** frontera de recuperación ya acordada;
  observación de salida, citas, validaciones y errores.
- **S3 — `agente2(...)`:** composición pública consumida por #34; doble de
  `estimar_siniestro` hasta integrar #30, después verificación con herramienta real.
- **S4 — informe comparativo sobre las 25 preguntas:** modelo real y revisión
  humana de fragmentos. Eval-first para calidad; sin rojo artificial de métricas.
- **S5 — contrato Agente 2 → #31/#34 y entorno Compose:** esquema y pasos de
  integración pactados; no probar funciones privadas como fronteras.

TDD para lógica determinista: Red por comportamiento ausente con módulos
importables → Green → Refactor. Pruebas futuras en
`app/agentes/agente_recuperacion/probar_rag.py`; evaluación futura en
`evaluar_rag.py`. Cada caso llevará la ruta de esta Spec y su AC.
Durante esta planificación no se escriben ni ejecutan esos archivos.

| Referencia (ruta de Spec + AC) | Seam / contrato | Estrategia y nivel | Caso / resultado esperado | Datos / entorno | Comando o pasos previstos | Evidencia prevista |
|---|---|---|---|---|---|---|
| `specs/32-rag-normativa.md#AC-001` | S1 | TDD, integración | Corpus con artículos en letras/cifras, sin artículos y secciones; repetición sin duplicados ni gasto nuevo. | Textos sintéticos de prueba; después corpus local de Plexus. | `python probar_rag.py`; indexado explícito dos veces. | Red/Green/Refactor, recuentos y contador de llamadas. |
| `specs/32-rag-normativa.md#AC-002` | S1 + S2 | TDD, integración | Modelos y corpus separados; lote fallido conserva activa; incompatibilidad explícita. | PostgreSQL desechable; cliente falso con fallo en lote. | `python probar_rag.py` | Red/Green y comprobación de generación activa. |
| `specs/32-rag-normativa.md#AC-003` | S2 | TDD, contrato | Tres claves, literalidad y fuente localizable; hasta k. | Fragmentos de prueba y documento de origen. | `python probar_rag.py` | Red/Green; cotejo con origen. |
| `specs/32-rag-normativa.md#AC-004` | S1 + S2 | TDD, integración | Cada póliza y vacío respetan filtro; inválidos fallan antes de gastar. | Cuatro pólizas de prueba y fragmentos legales. | `python probar_rag.py` | Red/Green; ninguna fuente de otra póliza. |
| `specs/32-rag-normativa.md#AC-005` | S2 | TDD, fallos externos | Un caso por código; [] solo en consulta válida sin candidatos. | Cliente falso y conexión controlada de prueba. | `python probar_rag.py` | Red/Green; código/etapa/reintentable. |
| `specs/32-rag-normativa.md#AC-006` | S3 | TDD + integración final | Campos de costes preservados; solo citas y diagnóstico cambian. | Dobles inicialmente; ejemplos reales y #30 integrada al terminar. | `python probar_rag.py`; ejecutar integración con paquete presente. | Red/Green y comparación estructural de las cifras. |
| `specs/32-rag-normativa.md#AC-007` | S3 | TDD, integración | Temas por caso; tercero; no_aplica; propagación de fallos ajenos. | Contextos y salidas guionizados. | `python probar_rag.py` | Red/Green; consultas observadas. |
| `specs/32-rag-normativa.md#AC-008` | S3 + S5 | TDD, contrato | Seis combinaciones del diagnóstico; consumidor distingue avisos. | Salidas por tema y contrato revisado con #31/#34. | `python probar_rag.py`; prueba de consumidor acordada. | Red/Green y aceptación del contrato. |
| `specs/32-rag-normativa.md#AC-009` | S4 | TDD del evaluador sin red | Cuenta las 25 filas, puntúa aciertos y fallos conocidos sin filtrar gold al buscador. | CSV local; buscador falso con respuestas controladas. | `python probar_rag.py` | Red/Green del protocolo y resultados sintéticos. |
| `specs/32-rag-normativa.md#AC-010` | S4 | Eval-first | Comparación small/large con variables controladas y mediciones reales. | Corpus y CSV con hashes anteriores; cuenta Plexus. | Ejecutar indexados y `evaluar_rag.py` con permiso explícito de gasto. | Tabla por modelo, datos, tiempos, tokens y coste. |
| `specs/32-rag-normativa.md#AC-011` | S4 | Eval-first + revisión humana | Modelo seleccionado con al menos 24/25 correctas. | Las mismas 25 preguntas, protocolo siguiente. | Revisar pasajes, registrar juicios y seleccionar modelo. | Tabla 25×2 y justificación de selección. |
| `specs/32-rag-normativa.md#AC-012` | S1 + S2 + S4 | TDD y comprobación de arranque | Sin flag de ejecución no se llama OpenAI; cliente falso sin clave. | Entorno de prueba, contador/guardia de red. | `python probar_rag.py`; arranque sin clave. | Red/Green y cero llamadas externas. |
| `specs/32-rag-normativa.md#AC-013` | S5 | Integración y comprobación de diff | Preparar/indexar/consultar/recrear; datos conservados. | Docker Compose y paquete en montaje de lectura. | Seguir README en entorno limpio; revisar diff de entrega. | Versiones, comandos y resultados reproducibles. |

### Protocolo de evaluación

1. Congelar corpus, troceado, nombres de modelos, dimensiones, distancia coseno,
   filtros y k=4; registrar versiones y hashes. Baseline: primera configuración
   reproducible con small, aún sin resultado conocido; ejecutar luego large con
   la misma configuración. No declarar que un modelo mejora antes de medirlo.
2. Para preguntas de póliza, resolver el producto nombrado en la pregunta contra
   `polizas.csv`; registrar el ID usado. Para legales, usar póliza vacía. No usar
   la columna `fuente` ni `respuesta_esperada` para construir filtros o consultas.
   La evaluación mide búsqueda con contexto de póliza disponible, como el flujo real.
3. **hit@4:** el path anterior a `#` de algún resultado coincide exactamente con
   la fuente esperada. Reportarlo por sí solo, total y por tipo.
4. **Pregunta correcta:** además del hit, uno o varios pasajes de esa fuente
   entre los cuatro resultados contienen la información necesaria para respaldar
   la respuesta esperada, sin completarla con otro documento no recuperado.
   Una persona registra sí/no, el pasaje y motivo. Los resultados se presentan
   sin el nombre del modelo para reducir sesgo al juzgar suficiencia. Si el gold
   contradice el snapshot, documentar y resolver la discrepancia; no cambiarlo en silencio.
5. El objetivo 24/25 (96 %) fue aceptado expresamente por Lucas en la sesión de
   diseño del 2026-10-20 como interpretación de «casi todas». No procede de un
   benchmark de OpenAI ni de una medición ya ejecutada.
6. Publicar calidad de ambos, tiempo de indexado y de las 25 consultas (total,
   mediana y máximo), tokens y coste estimado con las tarifas publicadas y su
   fecha de consulta, diferenciando caché y pago. No confundir esa estimación
   con la factura real de la cuenta.
   Entre modelos que cumplen, preferir más preguntas correctas; empate → menor
   coste observado. Documentar latencia y cualquier excepción a la elección.
7. Si se ajusta el troceado o consulta, versionar el experimento y reevaluar ambos
   con las mismas condiciones, conservando baseline y fallos. Estas 25 preguntas
   son un benchmark conocido, no un test ciego ni evidencia de generalización.

## Implementation Plan

| Slice | Objetivo observable | AC relacionados | Componentes / contratos probablemente afectados | Dependencias | Verificación prevista |
|---|---|---|---|---|---|
| 1 — Corpus persistente reproducible | Índice completo, repetible y separado por modelo; conserva generación activa ante fallos. | AC-001, AC-002, AC-012, AC-013 | PostgreSQL/pgvector, indexado y parte RAG del Compose raíz. | ADR aceptado; paquete local; Docker. | Filas AC-001, AC-002, AC-012, AC-013. |
| 2 — Recuperación con citas y filtros | Búsqueda con la firma acordada, fuentes literales y errores distinguibles. | AC-003, AC-004, AC-005 | `normativa_rag.py`, contrato de errores RAG. | Slice 1. | Filas AC-003 a AC-005. |
| 3 — Agente 2 completo | Cálculos intactos, temas por caso y diagnóstico para consumidores. | AC-006, AC-007, AC-008 | `agente2()`, `diagnostico_rag`, ejemplos/documentación de contrato. | Slice 2; #30 para integración final; contrato acordado con #31/#34. | Filas AC-006 a AC-008. |
| 4 — Evaluación y comparación | Evaluador verificable; tabla de ambos modelos y selección con 24/25. | AC-009, AC-010, AC-011 | `evaluar_rag.py`, protocolo y resultados. | Slice 2; acceso a ambos modelos. | Filas AC-009 a AC-011. |
| 5 — Uso y entrega | Componente ejecutable desde Compose; documentación y evidencia final. | AC-012, AC-013 | README del RAG, guía actualizada y comandos del entorno. | Slices anteriores. | Arranque reproducible, checks y diff. |

## Pendientes para Ready

- Revisar este borrador con Lucas y responsables de #31/#34: aceptar o ajustar
  la ampliación de contrato, códigos y reparto de los avisos. Conservar IDs al
  cambiar el plan. No atribuir a PRs anteriores aceptación de este contrato nuevo.
- Revisión humana e integración de esta Planning PR, Spec Revisada y ADR 0006
  Aceptado sobre el head final. Las decisiones de diseño de esta sesión no
  sustituyen la revisión del documento completo.
- Integrar los ADRs aplicables de la #37, especialmente contratos, proveedor y
  herramienta de costes (0002, 0003, 0004 Propuestos en #51), respetando sus revisiones.
- Tener el contrato final de costes de #30 accesible; su código integrado se
  exige para completar la verificación de composición, sin impedir preparar
  y probar por separado la recuperación.
- Concretar el alcance de integración Compose y de presentación de avisos en
  los planes de #31/#34. Confirmar acceso a ambos modelos al preparar entorno.

### Resultado de analyze

| Comprobación | Resultado |
|---|---|
| Issue y decisiones de Lucas cubiertas | Corpus e índice → AC-001/002/013; firma/citas/filtro → AC-003/004; errores y preliminar → AC-005/008; composición → AC-006/007; 25 preguntas y modelos → AC-009/010/011; gasto explícito → AC-012. |
| Cada AC tiene verificación y slice | AC-001 a AC-013 con fila en Test Plan y al menos una slice. |
| Ampliaciones autorizadas | Lucas incluye `agente2()`, elige PostgreSQL y Compose, A ahora/B futura, diagnóstico preliminar, errores distintos y comparación small/large con objetivo 24/25. Registrar estas decisiones en la Issue con enlace a esta versión. |
| Preservación | Costes, entradas y firma protegidos; adición de diagnóstico requiere revisión de consumidores. |
| ADR decision | NEW_ADR por persistencia y frontera compartida; previos sin aceptar no se reutilizan como aceptados. |
| Gaps | Contrato y coordinación con consumidores pendientes: publicación como draft; no Ready ni código productivo. Calidad y rendimiento aún no medidos; son verificaciones futuras, no checks superados. |

## Definition of Done

La DoD global del workflow y la Issue sigue vigente. Esta Spec añade:

| Condición específica de cierre | Evidencia requerida |
|---|---|
| AC-001 a AC-013 verificados y regresiones pertinentes en verde. | Trazabilidad, comandos, Red/Green/Refactor y resultados finales en Implementation PR. |
| Ambos modelos evaluados; elegido con al menos 24/25 correctas. | Comparación completa, configuración, juicios humanos de suficiencia, coste y tiempos, baseline y cambios conservados. |
| Composición con el cálculo real de #30 integrada y sin cambio de cifras. | Ejecución con paquete presente y comparación con salida de costes. |
| Consumidores pueden distinguir ausencia, parcialidad y errores. | Contrato aceptado y comprobación de integración con #31/#34; no basta con que exista el campo en un productor aislado. |
| Parte RAG del Compose reproducible y persistente. | Pasos desde entorno limpio, consulta tras reinicio y versiones. El arranque de todo el proyecto se verificará en su integración global. |
| Documentación vigente y datos privados fuera de la PR. | Actualizar guía/README/contratos; diff sin paquete, SQLite, volumen, claves ni archivos ajenos. |

Referencias oficiales consultadas para el diseño: [pgvector](https://github.com/pgvector/pgvector),
[embeddings de OpenAI](https://developers.openai.com/api/docs/guides/embeddings),
[small](https://developers.openai.com/api/docs/models/text-embedding-3-small),
[large](https://developers.openai.com/api/docs/models/text-embedding-3-large),
[Docker Compose](https://docs.docker.com/compose/intro/compose-application-model/).
