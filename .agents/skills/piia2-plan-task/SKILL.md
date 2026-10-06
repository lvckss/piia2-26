---
name: piia2-plan-task
description: Planificar trabajo funcional nuevo de PIIA2 desde una Issue existente, con investigación, Spec, ADR y Test Plan, hasta una Planning PR. Mantener Especificando; no implementar, escribir tests ni promover a Ready.
---

# Planificar una tarea de PIIA2

Entrada oficial para comenzar trabajo funcional nuevo: `piia2-plan-task #12`
o `piia2-plan-task 12`. Orquestar las skills existentes; no reimplementar sus
comandos, permisos, paginación ni verificaciones.

## Fuentes y alcance

Leer desde la raíz del repo [AGENTS.md](../../../AGENTS.md),
[lifecycle](../../../docs/workflow.md), [template de Spec](../../../docs/templates/spec-template.md),
[template de ADR](../../../docs/adr/template.md), [registro de ADRs](../../../docs/adr/README.md),
[template de Issue](../../../.github/ISSUE_TEMPLATE/work-item.md),
[template de PR](../../../.github/pull_request_template.md) y
[configuración del Project](../../../.github/project-config.json). Prevalecen
estas reglas sobre las referencias externas.

La invocación para una Issue concreta solicita el recorrido de planificación,
incluidas incorporación al Project y transiciones iniciales descritas abajo.
Respetar cualquier límite adicional del usuario. Crear recursos nuevos de prueba
requiere permiso; esta skill no crea la Issue de entrada.

## 1. Validar entrada y contexto antes de escribir

Aceptar solo un número entero positivo en decimal, con `#` opcional. Rechazar
cero, negativos, texto adicional, URLs y referencias a otro repositorio; no
reinterpretarlas como un número local. Si falta la entrada, pedir la Issue.

1. Ejecutar [gh-verifying-context](../gh-verifying-context/SKILL.md).
2. Leer la Issue mediante [gh-issue-management](../gh-issue-management/SKILL.md):
   número, URL, título, body, estado, labels, assignees y referencias existentes.
   Confirmar que es Issue de `lvckss/piia2-26`, no PR, y que está abierta.
3. Leer pertenencia y Status con [gh-project-management](../gh-project-management/SKILL.md),
   incluyendo items archivados. Rechazar `Hechas`, identidad ambigua o contexto
   inválido sin ninguna escritura. No reparar permisos/configuración ni reabrir.

## 2. Estado operacional

| Situación | Acción mediante gh-project-management |
|---|---|
| No pertenece | Añadir una vez y verificar pertenencia; después leer Status. |
| Sin Status | Asignar explícitamente Por hacer dentro de esta operación y verificar. |
| Por hacer | Solicitar Especificando para esta Issue y verificar la transición. |
| Especificando | Continuar; no emitir mutación de Status. |
| Ready / En curso / En revisión | Detenerse: ya pasó la fase de planificación. No regenerar ni retroceder. |
| Bloqueadas | Leer registro de bloqueo. Continuar solo si no impide planificación y el usuario lo solicita expresamente. |
| Hechas | Rechazar sin cambios. |

Si el bloqueo sigue vigente, solo investigar o preparar borradores bajo esa
petición, conservando Bloqueadas. Para completar el flujo en Especificando,
exigir resolución registrada y petición explícita de volver a Especificando,
según gh-project-management. No asumir que permiso para investigar equivale a
desbloquear. Si el bloqueo impide especificar, pedir la decisión que falta.

Antes de cada escritura GitHub, verificar contexto, leer estado actual,
determinar cambio mínimo, ejecutar, releer, comparar e informar mediante la
skill responsable. Un fallo detiene esa operación; no repetir mutaciones a ciegas.

## 3. Reanudar antes de crear artefactos

Buscar primero referencias en Issue y comentarios, Specs relacionadas,
[ADRs](../../../docs/adr/), ramas `plan/<issue>-*` y PRs (abiertas, cerradas e
integradas) del repositorio que referencien la Issue. Leer los artefactos en la
rama/head de la PR existente, no solo lo presente en main. Una búsqueda por título
no prueba identidad; comparar número/URL, alcance y enlaces de planificación.

Si hay una Spec válida, un ADR pertinente y una Planning PR abierta, continuar
ese mismo plan: revisar gaps y añadir solo lo necesario, conservando IDs de AC.
Si ya está completo, informar URLs y pendientes humanos sin nuevos commits,
comentarios duplicados, ADRs ni PRs. No invocar entrega sin cambios que publicar.
Si la PR está integrada pero Status sigue Especificando, informar desajuste y
requisitos de DoR pendientes; no abrir otro plan ni promover a Ready.
Ante PR cerrada sin merge, varios candidatos, rama con cambios ajenos o artefactos
incompatibles, detenerse y pedir una decisión concreta. No sobreescribir ni borrar.

## 4. Explorar el sistema en solo lectura

Usar `rg` / `rg --files` y leer el código, Specs, ADRs, tests, interfaces públicas,
modelos/esquemas, configuración, dependencias y restricciones relacionados.
Contrastar documentos con comportamiento real; no tratar guías antiguas o
código de referencia como un ADR aceptado ni como funcionalidad ya verificada.
Priorizar comportamientos y decisiones existentes frente a nuevas abstracciones.

Registrar en la Spec un resumen con evidencia (paths/símbolos relevantes):
comportamiento actual, cambio requerido, componentes afectados, contratos
públicos, incertidumbres, riesgos y comportamiento observable desde tests.
Esto debe permitir continuar en otra sesión sin reconstruir la conversación.
No ejecutar prototipos, migraciones ni comandos que cambien producto o datos.

Si faltan requisitos, identificar la decisión exacta y formular una pregunta
concreta al usuario; avanzar solo en partes independientes. No redactar una
Spec que finja certeza. Diferenciar hechos observados, decisiones propuestas y
supuestos explícitos; registrar todas las preguntas relevantes en pendientes.
Un umbral ML sin evidencia queda pendiente de experimento, sin inventar un valor.

## 5. Rama y documentos de planificación

Para un plan nuevo, partir de `main` actualizado mediante lectura/fetch de origin,
sin rebase, merge ni reescritura de historial; crear `plan/<issue>-<slug>` desde
esa referencia antes de editar. No continuar sobre trabajo ajeno ni sobre main.
Si local main tiene commits no publicados, detenerse. Para reanudar, usar la
rama del plan únicamente si el árbol/checkout es seguro; puede usarse un worktree
limpio. No cambiar de rama ni mezclar commits para facilitar la entrega.

### Spec y AC

Crear una única Spec por Issue en
`entregas/cu-19-interpretacion-danos/specs/<issue>-<slug-kebab-case>.md`,
basada en el template del repo. Para otro caso, confirmar su ubicación.
Mantener sus secciones y referencias: Issue, estado Borrador, ADR asociado,
Planning PR cuando exista, qué construir/por qué, alcance y fuera de alcance,
restricciones/supuestos, AC, Test Plan, pendientes para Ready y DoD específica.
La DoD de Spec amplía la global, nunca la relaja; indicar si no hay requisitos extra.

AC-001, AC-002, etc. son contratos observables, no tareas técnicas. Cada AC
expresa entrada/precondición, acción, resultado y condición objetiva de éxito.
Mantener IDs estables, sin renumerar/reutilizar IDs retirados. Evitar “funciona
bien”, detalles privados y thresholds arbitrarios. Para ML, identificar métrica,
dataset/versión/split, baseline y tolerancia con evidencia o pendiente explícito.
No declarar preparado para revisión de implementación un AC aún indeterminado.

### Test seams y Test Plan

Antes de diseñar casos, añadir una sección Test seams: frontera observable,
contrato y justificación. Preferir seams públicos ya existentes y el nivel más
alto que verifique de forma fiable el comportamiento: endpoint, función pública,
esquema, interfaz de estrategia, pipeline, salida serializada o métricas.
Proponer una nueva frontera solo con necesidad justificada. No convertir funciones
privadas, mocks de internals ni pasos de implementación en contratos.

El Test Plan es obligatorio dentro de la Spec. Ampliar su tabla, conservando la
referencia completa `Spec path + AC ID`, datos/entorno y pasos reproducibles:

| AC (ruta de Spec + ID) | Seam/contrato | Nivel | Caso/resultado esperado | Datos/fixture y versión | Comando/pasos previstos | Evidencia prevista |
|---|---|---|---|---|---|---|

Mapear cada AC a al menos una verificación. Considerar casos positivos, errores,
bordes, regresión, contratos/esquemas e integración; para ML, smoke/evaluación
cuantitativa cuando aplique. Identificar tests existentes reutilizables y cómo
se reproducirá la evaluación. Describir fixtures futuras sin crearlas.
Todo es estrategia prevista: no escribir tests ejecutables ni presentar checks
futuros como ejecutados. La futura implementación escribirá los tests con TDD.

### ADR

Buscar primero ADRs que cubran explícitamente decisión y alcance. Reutilizar uno
solo con justificación concreta en Spec/PR; un ADR rechazado o sustituido no
habilita implementación. No duplicar decisiones equivalentes. Si se reutiliza
un ADR Aceptado, conservar su estado y su evidencia de aceptación; no reescribirlo.

Si hace falta uno nuevo, elegir el siguiente número de cuatro dígitos libre,
comprobando main y planes abiertos para evitar colisiones, y crear
`docs/adr/<NNNN>-<slug>.md` desde el template con estado Propuesto.
Incluir contexto/motivación y decision drivers, propuesta, alternativas reales,
ventajas/inconvenientes, consecuencias/riesgos, implicaciones para testing,
evidencia/referencias e Issue/Spec cubiertas. Distinguir supuestos de mediciones.
Considerar status quo cuando proceda; justificar las alternativas por drivers.
No inventar opciones de relleno; si solo queda una viable, explicar restricciones.
Nunca marcar un ADR nuevo Aceptado ni atribuir aprobación humana inexistente.

## 6. Preparación para revisión y límite de archivos

Revisar Issue abierta, Spec completa, alcance/límites, AC verificables, seams,
ADR que cubre el cambio, Test Plan con todos los AC, dependencias y preguntas.
Registrar qué está acreditado y qué falta; preguntar por decisiones bloqueantes.
Si quedan incertidumbres que impiden completar los contratos, conservar borrador
y, si se publica para debatirlas, usar Planning PR draft indicando que aún no
está preparada para revisión completa ni Ready. No inventar para cerrar gaps.

Preparado para revisión no significa Ready para implementación. Incluso con
el plan completo, quedan revisión humana, aceptación del ADR propuesto,
integración de Planning PR y DoR íntegra. No marcar estos checks como cumplidos.

Revisar el diff completo antes de publicar y aplicar una lista permitida de
paths concretos: Spec de esta Issue, ADR necesario y documentación estrictamente
relacionada, justificada. La Planning PR debe contener cero código productivo:
prohibidos `app/**` (también bajo entregas), Python productivo, frontend/backend,
ML, tests ejecutables, fixtures, runtime config, dependencias o scripts de
implementación. Si aparecen, detener la entrega sin borrar cambios ajenos.
Documentar cualquier necesidad de código y dejarla para la siguiente fase.

## 7. Planning PR y referencias de Issue

Con cambios comprendidos y diff permitido, delegar commits/push/PR a
[semantic-commits-and-push](../semantic-commits-and-push/SKILL.md) desde la rama
plan. Respetar su prohibición de editar archivos: redactar antes de entregarlos.
La rama dedicada y la reanudación autorizadas por esta orquestación prevalecen
sobre quedarse en una rama previa ajena. No publicar todas las modificaciones
si incluyen trabajo no relacionado; resolver la ambigüedad primero.
Si ya existe la Planning PR del plan, reutilizarla y delegar solo commit/push;
omitir el paso de creación de PR de la skill de entrega. La idempotencia de esta
orquestación prevalece sobre abrir una PR nueva en cada invocación.

Usar el template de PR con tipo Planning y título
`docs(#<issue>): planificar <problema>`, `Refs #<issue>` y nunca `Closes`/`Fixes`/
`Resolves`. Escribir claramente: “Esta PR no implementa código productivo.”
Incluir Issue, Spec, ADR/estado, Test Plan, problema, alcance/fuera de alcance,
decisiones/alternativas, AC, seams, riesgos y pendientes de DoR.

Pedir revisión humana explícita de: fidelidad de Spec al problema, alcance, AC
verificables, cobertura del Test Plan, seams, decisión de ADR, alternativas,
resolución de preguntas bloqueantes y aceptación de Propuesto a Aceptado.
Si se reutiliza ADR aceptado, pedir revisión de su cobertura sin nueva autoaceptación.
No aprobar, fusionar ni habilitar auto-merge.

Al conocer URL de PR, completar el campo Planning PR en Spec y ADR nuevo y
publicar la actualización en la misma rama/PR; nunca crear otra PR para esos
enlaces. Si la entrega no pudo crear la PR, informar compare URL y dejar ese
campo pendiente. No fingir que se abrió ni marcar el flujo como completado.

Registrar referencias a Spec, ADR, sección Test Plan y Planning PR en la Issue
solo si la autorización de la tarea incluye esa escritura. Usar gh-issue-management
para añadir referencias o un comentario mínimo conservando todo el original;
releer y verificar. Si ya existen, no duplicarlas. Si falta autorización, preparar
el texto y pedirla, manteniendo el resto de la planificación disponible.

## 8. Salida e idempotencia final

Releer Issue/Status y PR mediante las skills responsables. Informar URLs,
archivos, evidencia de revisión documental, supuestos, riesgos y pendientes.
Issue debe seguir abierta y en Especificando después de abrir la Planning PR;
si otro actor cambió estado/cerró la Issue, detenerse e informar el conflicto,
sin restaurar a ciegas ni sobrescribir una decisión humana.

Nunca promover a Ready, cerrar Issues, marcar DoD/Hechas, modificar estructura
Project/workflows ni implementar. Ready solo procede posteriormente con revisión
humana, ADR aceptado, Planning PR integrada y DoR completamente satisfecha.

Adaptación conceptual de [mattpocock/to-spec](https://github.com/mattpocock/skills/blob/main/skills/engineering/to-spec/SKILL.md):
explorar antes de especificar, preferir seams existentes y comportamiento externo,
y conservar contexto de testing. PIIA2 mantiene sus templates/paths, AC estables,
ADR separado y revisión humana; no adopta publicación del plan como body único,
etiquetas de ready, omisión de preguntas necesarias ni prototipos de código.
