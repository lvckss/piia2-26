# Recuperación con fuentes y filtros · 10 de noviembre de 2026

Referencias: [Issue #32](https://github.com/lvckss/piia2-26/issues/32),
[spec v1.6](../../specs/32-rag-normativa.md),
[DoR](https://github.com/lvckss/piia2-26/issues/32#issuecomment-6609611397),
[ADR 0006 Aceptado](../adr/0006-rag-postgresql-estado-recuperacion.md) y
[PR #72](https://github.com/lvckss/piia2-26/pull/72).

Este incremento completa la slice 2 del buscador sobre el
[índice existente](32-indexado.md). No implementa `agente2()` ni evalúa las
25 preguntas. La Issue sigue En curso y la PR en borrador. Se conserva la
v1.7 exigida antes de la slice 3; no se da por revisada ni integrada.

## Comportamiento y trazabilidad

| Referencia de la spec 32 | Verificación observada |
|---|---|
| AC-002, parte de consulta | Índice ausente/incompleto e incompatibilidad de modelo, dimensiones o protocolo producen errores explícitos, sin gastar. Una consulta conserva la generación fijada aunque se publique otra mientras espera al proveedor. |
| AC-003 | Firma de tres argumentos; hasta k resultados con exactamente tema/extracto/fuente. Distancia coseno exacta, desempate por ID estable; extractos cotejados con el documento y fuentes relativas localizables. Un pasaje alterado se rechaza. |
| AC-004 | Las cuatro pólizas y el ID vacío respetan el filtro antes de LIMIT. Entrada vacía, k inválido, póliza desconocida y pregunta demasiado larga fallan antes de llamar al proveedor. |
| AC-005 | Sin candidatos válidos devuelve []; índice no preparado/incompatible, caída de BD y errores de proveedor permanecen diferenciados. Autenticación/acceso, cuota, límite temporal, timeout y respuesta inválida tienen pruebas; las excepciones inesperadas se propagan. |
| AC-012, parte de consulta | CLI sin --execute es un plan offline. La ejecución requiere presupuesto explícito. La función exige configuración de autorización y límite por invocación; importar no conecta. Proveedor simulado y cero gasto en las verificaciones de este incremento. |
| AC-013, parte del componente | Comandos Just y equivalentes PowerShell documentados; usa la misma PostgreSQL y generaciones persistentes. No acredita el Compose completo de #34 ni ejecución nativa en Windows. |

No se añade otro ADR: la implementación aplica la decisión NEW_ADR ya resuelta
en el ADR 0006. No cambia contratos entre agentes, modelos, corpus, protocolo,
filtros, k inicial ni criterios de calidad.

## TDD y regresiones

Antes de implementar se volvieron a ejecutar las pruebas que habían quedado
escritas en la sesión interrumpida: **15 tests, 40 fallos de comportamiento**,
sin errores de importación. El buscador vacío no recuperaba, filtraba ni
distinguía fallos; tampoco existía la CLI. Después pasaron esos 15 tests.

Las pruebas adicionales detectaron antes de corregirlos: preguntas demasiado
largas que llegaban al proveedor, respuestas sin campos que producían
AttributeError y contraseña vacía que producía IndexError en db-init.
Los tests de autorización y autenticación ya satisfechos se conservan como
regresiones; no se fabrica un Red para ellos. Tras refactorizar el SQL y añadir
la regresión de literalidad ante corrupción, la suite final está en verde.

Desde la carpeta del caso, comandos ejecutados:

```bash
just rag-test
.venv-rag/bin/python app/agentes/agente_recuperacion/probar_rag.py --postgres
RUN_POSTGRES_INTEGRATION=1 python3 -m unittest discover -s scripts/tests -v
just --fmt --check
just rag-query-plan 'Responsabilidad civil del asegurador' '' small
```

- Suite de indexado: **18 pruebas OK**.
- Suite final de búsqueda: **21 pruebas OK**, incluidas las integraciones;
  se repitió después del último cambio SQL. El primer `just rag-test` pasó
  cuando la suite de búsqueda tenía 20 pruebas; después se añadió la de corrupción.
- Scripts: **25 pruebas OK**, incluidas descarga, contraseña vacía e init/up
  con PostgreSQL Docker aislada. Sin omisiones en esas ejecuciones.
- Sintaxis Python, formato Just, destinos locales Markdown y diff comprobados.

Las pruebas crean y retiran exclusivamente sus proyectos/volúmenes Docker,
con corpus sintético y OpenAI simulado. No reciben la URL de la base real.

## Integración con el índice real, sin gasto

Se ejecutaron diez consultas técnicas en una conexión PostgreSQL de **solo
lectura**: las cuatro pólizas más el ID vacío, para small y large. Se utilizó
un vector ya guardado mediante un proveedor simulado, sin generar embeddings
nuevos ni enviar preguntas al proveedor. En todos los casos se recuperaron
cuatro pasajes literales del corpus activo y permitidos por el filtro.

Ambas generaciones siguen enlazando 2.032 fragmentos. El registro del indexado
conserva **124 peticiones**; el explorador conserva **4.000 imágenes, 8.740
instancias y 6 etiquetas**. La sesión de solo lectura no modifica esos datos.

El primer SQL comprobaba demasiados textos antes de limitar. Se separó la
selección de IDs/distancias en una CTE materializada y el cotejo literal de los
resultados seleccionados. En la comprobación final con vectores guardados,
la primera consulta tardó 1,61 s, incluida la carga inicial del tokenizador;
las nueve siguientes, entre 0,104 y 0,162 s. Son tiempos de esta comprobación
local, **sin latencia de OpenAI**, no el benchmark de AC-010 ni una garantía.

Entorno: Linux, Python 3.12, PostgreSQL 18.6, pgvector 0.8.7 y dependencias
fijadas en requirements-rag.txt. Los comandos PowerShell se revisaron, pero
no se ejecutaron en Windows. Sigue pendiente la verificación en otro equipo.

## Revisión y pendientes

Se actualiza docs/postgresql-local.md y se aclaran las recetas POSIX y los
equivalentes PowerShell solicitados por Lucía en la revisión del head 602d8b2.
También se corrige el error de contraseña vacía señalado allí.

El protocolo v1 conserva los fragmentos cortos de tablas legales: se medirá
primero la referencia inicial, sin filtrarlos silenciosamente. Si se modifica
el troceado o la recuperación, se versionará el experimento y se compararán
ambos modelos. Todavía no hay puntuación de calidad ni modelo ganador.

Pendientes de #32: v1.7 previa a la composición, `agente2()` y diagnóstico,
evaluador y referencia directa, small/large con las 25 preguntas y juicio humano,
integración de consumidores y entorno completo. La rama no se ha actualizado
con main; sigue pendiente la sincronización/verificación antes de presentarla
como lista para revisión completa, como pidió Lucía. No se aprueba, fusiona,
cierra ni marca Hechas con esta evidencia parcial.
