---
name: piia2-plan-task
description: "Orquestar la planificación de PIIA2 desde una Issue existente: Por hacer, Especificando, Spec, decisión ADR y planes, Planning PR y Ready tras revisión humana, merge humano y DoR completa. No implementar ni escribir tests."
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

Una invocación explícita para una Issue concreta autoriza las operaciones no
destructivas de este ciclo: incorporación al Project, Por hacer si falta Status,
Por hacer → Especificando, creación/actualización de Spec/planes y ADR si aplica,
rama y Planning PR, referencias/comentarios mínimos en la Issue sin borrar
contenido, y Especificando → Ready después del merge si toda la DoR se acredita.
No pedir confirmación individual por esos pasos; respetar límites adicionales
del usuario. Esta autorización no incluye cerrar, Hechas, borrar/sustituir el
body, aprobar/mergear PRs, aceptar sin evidencia humana, estructura/workflows del
Project, producto ni tests ejecutables. No crear la Issue de entrada ni recursos
de prueba persistentes sin permiso.

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
| Especificando | Localizar el mismo plan y continuar según su PR: abierta (review) o mergeada (DoR). |
| Ready | Informar que la planificación ya finalizó; no-op, sin nuevos artefactos ni rama de implementación. |
| En curso / En revisión | Detenerse: ya empezó implementación. No regenerar ni retroceder. |
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

Si hay una Spec válida, una decisión ADR explícita y una Planning PR abierta, continuar
ese mismo plan: revisar gaps y añadir solo lo necesario, conservando IDs de AC.
Si ya está completo, continuar con la comprobación de revisión humana (§8) o
DoR post-merge (§9), sin recrear artefactos. Si aún falta review, informar URLs
y pendientes sin nuevos commits ni comentarios duplicados. No invocar entrega
sin cambios que publicar. Una PR integrada con Status Especificando se procesa
en §9 desde main, sin abrir otro plan.
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

### Clarify antes de cerrar la Spec

Contrastar requisitos ambiguos, términos con varias interpretaciones, decisiones
del usuario ausentes, supuestos presentados como hechos, métricas/thresholds sin
evidencia, edge cases sin resolver y contradicciones entre Issue y comportamiento
existente. Clasificar cada incertidumbre y registrar su evidencia/efecto en la Spec:
resuelta mediante repo/documentación; supuesto explícito aceptable; pregunta no
bloqueante; pregunta bloqueante. Un supuesto no puede sustituir una decisión humana
necesaria ni una condición objetiva de éxito. Resolver por inspección antes de
preguntar; solicitar criterio humano solo cuando realmente falte. Si una pregunta
bloqueante impide AC verificables, la planificación no está completa. Repetir
clarify al recibir feedback que cambie requisitos; no ocultar incertidumbres.

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
Mantener sus secciones y referencias: Issue, estado Borrador, ADR decision,
ADR (ruta/estado o No requerido), justificación, Planning PR cuando exista,
qué construir/por qué, alcance y fuera de alcance, restricciones/supuestos,
comportamiento que debe preservarse, failure modes/NFRs, AC, Test/Eval Plan,
Implementation Plan, pendientes para Ready y DoD específica. No dejar campos
ADR vacíos ni enlazar documentos ficticios.
La DoD de Spec amplía la global, nunca la relaja; indicar si no hay requisitos extra.

AC-001, AC-002, etc. son contratos observables, no tareas técnicas. Cada AC
expresa entrada/precondición, acción, resultado y condición objetiva de éxito.
Mantener IDs estables, sin renumerar/reutilizar IDs retirados. Evitar “funciona
bien”, detalles privados y thresholds arbitrarios. Para ML, identificar métrica,
dataset/versión/split, baseline y tolerancia con evidencia o pendiente explícito.
No declarar preparado para revisión de implementación un AC aún indeterminado.

### Comportamiento preservado y failure modes/NFRs

Registrar contratos existentes, comportamiento observable, invariantes,
compatibilidad, formatos/esquemas y regresiones brownfield importantes que deben
seguir funcionando. Si no existe comportamiento previo relevante, indicarlo.
Relacionar su protección con AC y verificaciones de regresión previstas, incluidos
tests existentes reutilizables; no asumir que satisfacer nuevos AC protege lo previo.

Seleccionar solo failure modes y NFRs relevantes para esta tarea: errores de
entrada/dependencias, datos parciales, timeout, modelo sin resultado, recuperación,
latencia/memoria/performance, determinismo, compatibilidad, seguridad u observabilidad.
Los verificables dentro del alcance deben reflejarse en AC o Test/Eval Plan,
con referencias trazables a los AC correspondientes. No inventar NFRs ni umbrales;
si no aplican, indicarlo con motivo. Una condición relevante aún indeterminada
pasa por clarify, no desaparece por dejar vacía la sección.

### Test seams y Test/Eval Plan

Antes de diseñar casos, añadir una sección Test seams: frontera observable,
contrato y justificación. Preferir seams públicos ya existentes y el nivel más
alto que verifique de forma fiable el comportamiento: endpoint, función pública,
esquema, interfaz de estrategia, pipeline, salida serializada o métricas.
Proponer una nueva frontera solo con necesidad justificada. No convertir funciones
privadas, mocks de internals ni pasos de implementación en contratos.

El Test Plan es obligatorio dentro de la Spec. Ampliar su tabla, conservando la
referencia completa `Spec path + AC ID`, datos/entorno y pasos reproducibles:

| AC (ruta de Spec + ID) | Seam/contrato | Estrategia y nivel | Caso/resultado esperado | Datos/fixture y versión | Comando/pasos previstos | Evidencia prevista |
|---|---|---|---|---|---|---|

Mapear cada AC a al menos una verificación. Considerar casos positivos, errores,
bordes, regresión, contratos/esquemas e integración; para ML, smoke/evaluación
cuantitativa cuando aplique. Identificar tests existentes reutilizables y cómo
se reproducirá la evaluación. Describir fixtures futuras sin crearlas.
Indicar estrategia por comportamiento: determinista, Red → Green → Refactor;
ML/probabilístico/heurístico cuando TDD unitario no representa el objetivo,
Baseline → criterio/eval que demuestra el gap → cambio → reevaluación → comparación.
Una tarea puede ser híbrida (contrato/pipeline con TDD, calidad del modelo con
eval-first). Especificar baseline, datos/split/versiones, protocolo y comparación
con evidencia, sin fingir un rojo unitario para métricas ML.
Todo es estrategia prevista: no escribir tests ejecutables ni presentar checks
futuros como ejecutados.

### Implementation Plan

Dentro de la Spec, ordenar vertical slices pequeñas y verificables. Para cada
slice, registrar objetivo observable, AC relacionados, componentes/contratos
probablemente afectados, dependencias y verificación prevista del Test/Eval Plan.
Cubrir todos los AC sin prediseñar internals, código ni pseudocódigo detallado.
Debe permitir empezar en otra sesión con el contexto existente. Si hay demasiadas
slices para un plan coherente o varios objetivos independientes, detenerse y
recomendar dividir la Issue antes de una mega-Spec. No crear child Issues sin
petición/autorización explícita.

### ADR decision condicional

Resolver exactamente un caso y registrar valor, ruta/estado o No requerido y
justificación en Spec/PR. Distinguir cambio observable local de decisión
arquitectónica/frontera estable/trade-off duradero. Investigar consumidores,
boundaries, consecuencias y coste de reversión antes de clasificar; ni el tamaño
del diff ni un cambio observable por sí solos deciden si hace falta ADR:

| ADR decision | Criterio y resultado |
|---|---|
| NEW_ADR | Introduce/cambia una decisión suficientemente fundamental, duradera o costosa de revertir: arquitectura; boundaries entre agentes/servicios/componentes independientes; contratos externos o fronteras estables; APIs externas; schemas/formatos persistentes o compartidos; datos/persistencia; integración/protocolo; deployment/serving; concurrencia; seguridad; dependencia externa estructural; estrategia ML/serving/evaluación duradera; trade-off importante difícil de revertir. Crear ADR Propuesto; requerir aceptación humana. |
| REUSE_ADR | Un ADR ya Aceptado cubre explícitamente decisión y alcance. Enlazarlo y justificar cobertura concreta, que debe confirmarse en review. No crear otro ni modificar el aceptado si la decisión no cambia. |
| NO_ADR_REQUIRED | No introduce/cambia una decisión estructural relevante: validaciones locales, error/excepción/precondición de API interna, comportamiento de funciones dentro del componente, bugfix/mejora localizada, algoritmo interno, refactor que preserva arquitectura/boundaries, tests o documentación. Justificación breve revisada por humano; no crear ADR artificial. Un cambio observable local puede encajar. |

Buscar decisiones existentes antes de elegir. Un ADR rechazado, sustituido o solo
parecido no permite REUSE_ADR. Si cambia una decisión aceptada, elegir NEW_ADR
con referencias a la anterior, conservando su historia.

Para ADR, contrato público relevante es una frontera estable consumida externamente
o entre componentes/agentes que pueden evolucionar independientemente: API externa,
contrato Agente 1 → Agente 2, schema JSON compartido, protocolo, formato persistente
o interfaz estable usada fuera del componente. Una función Python sin prefijo `_`
o importada por otro módulo del mismo componente no es tal frontera por ese hecho.
Elegir ValueError, cambiar su mensaje o una precondición interna no dispara NEW_ADR
por sí solo. Una API interna con consecuencias estructurales, consumidores
independientes o coste de reversión importante sí puede requerir ADR. Cambios
pequeños en fronteras estables también lo requieren: valorar relevancia/durabilidad,
no cantidad de líneas. Si sigue ambigua después de investigar, usar clarify,
sin crear ADR por precaución ni NO_ADR_REQUIRED para ocultar una decisión real.
Spec, AC, Test/Eval Plan, Implementation Plan y TDD/eval siguen siendo requisitos
para los cambios funcionales locales sin ADR.

Escenarios documentales de regresión (sin escribir producto ni tests):

| Situación | Decisión prevista |
|---|---|
| Función interna valida datos y ahora lanza ValueError, sin cambiar boundaries, schemas, protocolos ni establecer un trade-off estructural. | NO_ADR_REQUIRED, con justificación revisada; mantener Spec/AC y ambos planes. |
| Diff pequeño cambia schema JSON estable entre Agente 1 y Agente 2. | NEW_ADR si la decisión no está cubierta; REUSE_ADR solo si un ADR Aceptado cubre explícitamente ese cambio. Nunca NO_ADR_REQUIRED por tamaño. |

Solo para NEW_ADR, elegir el siguiente número de cuatro dígitos libre,
comprobando main y planes abiertos, y crear `docs/adr/<NNNN>-<slug>.md` desde el
template con estado Propuesto. Incluir contexto/motivación y drivers, propuesta,
alternativas reales, ventajas/inconvenientes, consecuencias/riesgos, implicaciones
para testing, evidencia e Issue/Spec. Distinguir supuestos de mediciones;
considerar status quo cuando proceda y justificar alternativas por drivers.
No inventar opciones; si solo hay una viable, explicar restricciones. Solo §8
registra Aceptado mediante evidencia humana explícita. Para NO_ADR_REQUIRED,
usar `ADR: No requerido — justificado en Spec` en referencias; no completar
checks antiguos de ADR aceptado como si existiera. Registrar no aplicable y
justificación sin sustituir el body de la Issue.

## 6. Preparación para revisión y límite de archivos

### Analyze antes de publicar para revisión completa

Comprobar consistencia bidireccional Issue ↔ Spec ↔ alcance/fuera de alcance ↔
comportamiento preservado ↔ failure modes/NFRs ↔ AC ↔ ADR decision/ADR si aplica
↔ Test/Eval Plan ↔ Implementation Plan. Registrar resultado, gaps y resolución
en pendientes para Ready. Detectar al menos:

- Requisito de Issue ausente, AC o slice fuera de alcance.
- AC sin verificación, verificación sin AC o AC sin slice.
- Comportamiento preservado importante sin protección o failure mode relevante sin cobertura.
- ADR contradictorio con Spec; NEW_ADR sin decisión real; NO_ADR_REQUIRED que oculta
  decisión relevante; REUSE_ADR sin cobertura real.
- Supuesto presentado como hecho, contradicciones entre secciones o Issue demasiado grande.

Corregir solo lo inequívoco según evidencia del repo; si necesita criterio humano,
marcar pendiente y preguntar. Revisar dependencias, alcance y claridad de AC/seams,
estrategia TDD/eval y planes. Repetir analyze tras feedback o cambios sustantivos.
No presentar Planning PR lista para revisión completa con contradicciones o gaps
bloqueantes conocidos. Puede publicarse draft para discutir incertidumbres explícitas.

Preparado para revisión no significa Ready para implementación. Quedan review
humana de Spec y ADR decision (aceptación del ADR nuevo, cobertura del reutilizado
o justificación de no requerirlo), merge humano y DoR íntegra. No marcar estos
checks como cumplidos antes de que lo sean.

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
Incluir Issue, Spec, ADR decision/justificación y ADR/estado cuando aplique,
Test/Eval Plan, Implementation Plan, problema, alcance/fuera de alcance,
comportamiento preservado, failure modes/NFRs, decisiones/alternativas,
AC, seams, resultados de clarify/analyze, riesgos y pendientes de DoR.

Pedir revisión humana explícita de claridad/fidelidad de requisitos, alcance y
fuera de alcance, comportamiento preservado, failure modes/NFRs, AC verificables,
seams, estrategia TDD/eval y cobertura de Test/Eval Plan e Implementation Plan,
riesgos, preguntas y consistencia global. Para NEW_ADR, revisar decisión y
alternativas y aceptar el ADR; REUSE_ADR, confirmar su cobertura; NO_ADR_REQUIRED,
aceptar justificación y confirmar que no oculta una decisión relevante.
No pedir validación de internals de código inexistente.
No aprobar, fusionar ni habilitar auto-merge.

Al conocer URL de PR, completar el campo Planning PR en Spec y ADR nuevo y
publicar la actualización en la misma rama/PR; nunca crear otra PR para esos
enlaces. Si la entrega no pudo crear la PR, informar compare URL y dejar ese
campo pendiente. No fingir que se abrió ni marcar el flujo como completado.

La invocación autoriza registrar referencias a Spec, ADR decision/ADR si aplica,
secciones Test/Eval Plan e Implementation Plan y
Planning PR en la Issue. Usar gh-issue-management para añadir referencias o un
comentario mínimo conservando el original; releer y verificar. Actualizar por
adiciones, nunca sustituir el body. Si ya existen y son vigentes, no duplicarlas;
si el usuario limitó esta escritura, respetarlo e informar lo pendiente.

## 8. Reejecución con Planning PR abierta: revisión humana

La Planning PR es el único mecanismo de aprobación del plan. Leer estado,
head SHA, reviews/comentarios, autores, fechas, commit revisado, revisiones
vigentes y solicitudes de cambios en GitHub. Releer los documentos del head
actual. Buscar evidencia humana explícita que cubra el plan completo: Spec/AC,
comportamiento preservado, failure modes/NFRs, Test/Eval Plan/seams/estrategia,
Implementation Plan y especialmente ADR decision según los tres casos (§5),
no solo formato o un fragmento.

Una review APPROVED de un revisor humano sobre la versión pertinente del plan,
sin restricciones de alcance, puede acreditar aceptación del diff completo.
Un comentario debe expresar aceptación del contenido y decisión, identificar
inequívocamente su versión y tener permalink. No bastan tiempo transcurrido,
silencio, PR abierta/mergeada, apariencia correcta, una reacción o merge por sí
solo. No tratar bots o autoaprobación del agente como evidencia humana; ante
autoría, alcance o versión ambiguos, informar lo que falta y mantener los estados.
Reviews DISMISSED, PENDING o CHANGES_REQUESTED no son aprobación vigente;
revisar el estado real de GitHub, no solo el historial de APPROVED.

Si aún no hay aceptación suficiente del contenido, informar pendientes y
conservar Especificando, Spec Borrador y ADR Propuesto si NEW_ADR. Una aceptación humana
ya acreditada no se borra ni se revierte por invalidación de aprobación final
tras un commit solo de metadatos: conservar Aceptado/Revisada y su evidencia,
sin repetir el commit, y señalar la nueva aprobación final pendiente.
Si el usuario/revisor solicita feedback concreto,
actualizar solo el mismo plan, conservando IDs y sin atribuir nueva aprobación.

Con aceptación humana suficiente del contenido actual, registrar en la misma PR:

- ADR nuevo: Propuesto → Aceptado, con nombre/login del humano y URL de
  review/comentario, versión revisada y fecha en Aceptación. No alterar una
  decisión aceptada reutilizada de main; verificar su evidencia y cobertura.
- ADR decision: registrar en la Spec quién, referencia y versión que acepta
  NEW_ADR, confirma cobertura de REUSE_ADR o acepta justificación de NO_ADR_REQUIRED.
- Spec: Borrador → Revisada únicamente si la revisión cubre su contenido y planes,
  registrando también humano, referencia y versión revisada junto a sus metadatos.

La actualización registra una decisión humana; no es aprobación del agente.
Delegar solo commit/push sobre la misma rama/PR. Informar que el humano debe
comprobar el diff final y aprobarlo antes del merge. Releer reviews/head después
de cada push: una aprobación invalidada por nuevos commits no sigue vigente.
La aceptación del contenido anterior puede documentar el origen del cambio de
metadatos, pero no sustituye la aprobación final del head actualizado. Si cambian
AC, alcance, comportamiento preservado, failure modes, planes o decisión, la
aceptación anterior no cubre automáticamente esa versión: exigir nueva evidencia y explicitar el pendiente antes de Ready.

Mientras la PR esté abierta, Issue abierta y Status Especificando, aunque ADR
decision esté revisada y Spec Revisada. No repetir commits/comentarios si los metadatos ya
coinciden con la evidencia. Nunca aprobar ni mergear: el merge es humano.

## 9. Reejecución tras merge humano: DoR desde main

Confirmar identidad de la Planning PR, base main, Issue/artefactos cubiertos,
estado MERGED, merge commit y autor humano del merge. Exigir evidencia humana
explícita del plan y aprobación final vigente en GitHub antes del merge:
comprobar reviews y su commit contra el head final integrado, sin aprobación
invalidada ni solicitudes de cambios sin resolver. El merge no prueba aceptación.
Si los datos son insuficientes, no inferir: informar y detener la promoción.

Actualizar la referencia origin/main mediante fetch de origin verificado y
fijar su SHA. Leer Spec, planes y ADR cuando aplique desde ese snapshot de main (por ejemplo,
git show <main-sha>:<ruta>); no confiar en checkout local main atrasado, rama
antigua ni archivos no integrados. Si el plan está en corrección documental
revisada posterior, comprobar también la aceptación y merge de esa corrección.

Acreditar cada punto de DoR con ruta/AC/referencia GitHub y evidencia concreta:

- Issue sigue abierta, pertenece al Project correcto y Status es Especificando.
- Planning PR correcta mergeada por humano, con aceptación explícita y
  aprobación final del contenido integrado; referencias coherentes Issue/Spec/planes/ADR decision/PR.
- Spec existe en main, estado Revisada y revisión humana referenciada que cubre
  el contenido actual, AC y ambos planes.
- ADR decision explícita, justificada, resuelta y revisada con humano/URL/versión:
  NEW_ADR, ADR Aceptado en main con aceptación referenciada;
  REUSE_ADR, ADR existente Aceptado en main y cobertura confirmada en review;
  NO_ADR_REQUIRED, justificación en Spec aceptada en Planning PR, sin decisión
  relevante oculta ni enlace ficticio. No exigir un ADR inexistente en este caso.
- Test/Eval Plan dentro de la Spec cubre todos los AC mediante ruta + ID,
  seam, estrategia, casos, datos/versiones, pasos y evidencia prevista; AC verificables.
- Implementation Plan contiene slices verificables que cubren todos los AC.
- Comportamiento preservado y failure modes/NFRs relevantes tratados/protegidos;
  clarify sin ambigüedades bloqueantes y analyze sin gaps/contradicciones bloqueantes.
- Alcance/fuera de alcance claros, dependencias identificadas y sin impedimentos
  para implementar; ninguna pregunta bloqueante ni bloqueo operacional vigente.

La ausencia de una anotación no demuestra resolución de un bloqueo: leer su
registro y evidencia de resolución si lo hubo. No marcar cumplido un check aún
pendiente. Antes de promover, releer contexto, Issue/Status, PR y SHA de main;
si cambió algo relevante, reevaluar el snapshot, sin escribir con datos obsoletos.

Si falla cualquier punto (por ejemplo NEW_ADR aún Propuesto, ADR decision
incompleta, Spec Borrador, aceptación ausente o AC sin cobertura en algún plan),
conservar Especificando, listar exactamente qué falta y terminar sin promoción. No arreglar silenciosamente documentos ya
integrados para pasar el gate: requieren corrección documental revisada e
integrada. No crear otra Spec/ADR/plan ni una PR correctiva automáticamente.

Solo con toda la DoR acreditada, pedir a gh-project-management la transición
Especificando → Ready, autorizada por esta invocación. Releer el Project y
verificar Status exactamente Ready y Issue aún abierta. Registrar con
gh-issue-management un comentario mínimo de evidencia (Planning PR/merge,
snapshot main, Spec/ADR decision/ADR si aplica/review y DoR), si no hay ya un registro equivalente,
y verificarlo. Si el comentario falla tras la transición, informar el efecto
parcial; reanudar el registro sin repetir movimiento ni revertir a ciegas.

## 10. Salida e idempotencia final

Releer Issue/Status y PR mediante las skills responsables. Informar URLs,
archivos, revisión/documentos, supuestos, riesgos y pendientes de aprobación/DoR.
Mientras la PR esté abierta, indicar Especificando y qué revisión/merge falta.
Tras promoción verificada, informar planificación finalizada en Ready; la Issue
permanece abierta y finaliza toda responsabilidad de planificación.

Una reejecución en Ready es no-op. Puede completar un registro post-promoción
fallido ya identificado, sin recrear artefactos ni repetir la transición. Nunca
crear la rama de implementación, empezar TDD, escribir producto/tests, cerrar
Issues, marcar DoD/Hechas o modificar estructura/workflows del Project.
Si otro actor cambió estado o cerró la Issue, informar conflicto sin restaurar
a ciegas. Solo la futura piia2-implement-task comienza implementación tras Ready.

Adaptación conceptual de [mattpocock/to-spec](https://github.com/mattpocock/skills/blob/main/skills/engineering/to-spec/SKILL.md):
explorar antes de especificar, preferir seams existentes y comportamiento externo,
y conservar contexto de testing. PIIA2 mantiene sus templates/paths, AC estables,
ADR separado cuando hay decisión relevante y revisión humana; no adopta publicación del plan como body único,
etiquetas de ready, omisión de preguntas necesarias ni prototipos de código.
