---
name: implement-issue
description: Implementar autónomamente una Issue de PIIA2 con DoR acreditada, usando TDD/eval-first y entregando una Implementation PR en En revisión. Reanudar la misma ejecución; no aprobar, fusionar, cerrar ni marcar Hechas.
---

# Implementar una Issue de PIIA2

Entrada: `implement-issue 14` (entero positivo decimal, `#` opcional). Si falta,
pedir la Issue; rechazar cero, negativos, texto extra, URLs y otros repos. Leer
[AGENTS.md](../../../AGENTS.md), [workflow](../../../docs/workflow.md) y
[template de PR](../../../.github/pull_request_template.md).

Aplicar [gh-verifying-context](../gh-verifying-context/SKILL.md),
[gh-issue-management](../gh-issue-management/SKILL.md) y
[gh-project-management](../gh-project-management/SKILL.md); no duplicar sus
comandos, permisos, paginación ni comprobaciones. Cada escritura usa contexto y
lectura actuales, cambio mínimo, relectura y verificación. La invocación autoriza
rama, código/tests dentro del alcance, verificaciones, commits/push/PR, referencias
y transiciones rutinarias hasta En revisión; no pedir permiso por paso. Respetar
permisos del runtime y límites del usuario. No crear Issues, dar por aceptadas
decisiones que requieren humano, eliminar registros, aprobar/mergear, habilitar
auto-merge, cerrar ni marcar Hechas.
Permitir únicamente coordinación local del implementador con reviewer y QA
independientes según §3b; no crear Captain, crews, workers por Issues, worktrees
a escala ni infraestructura de orquestación.

## 1. Recuperar el acuerdo y comprobar entrada

Leer Issue y comentarios completos, pertenencia y Status del Project configurado.
Exigir Issue abierta, real y no archivada. Localizar el plan **vigente** y su
versión/evidencia DoR en las referencias; distinguir antecedentes sustituidos de
acuerdos actuales. Si hay candidatos contradictorios, no elegir solo por fecha.

Comprobar la DoR del workflow con evidencia: alcance/AC estables, restricciones
y comportamiento preservado, ADR decision resuelta, verificaciones por AC,
orientación/dependencias y ausencia de decisiones o impedimentos bloqueantes.
Fijar permalink y contenido evaluado (o archivo/commit) en el registro de ejecución.
Una columna Ready o checklist marcada no sustituye esta comprobación.

- Plan compacto en Issue/comentario: no exigir Spec Revisada, ADR ni Planning PR
  si no aplican; comprobar riesgo y ADR decision (justificación si NO_ADR_REQUIRED).
  Respetar adaptaciones humanas explícitas de planes anteriores sin fingir aprobación.
- REUSE_ADR: leer ADR Aceptado desde main actualizado y comprobar cobertura.
  NEW_ADR u otro disparador de revisión previa: comprobar Spec/planes/decisión
  revisados, aceptación humana de la versión pertinente y Planning PR aprobada
  sobre el head final e integrada por humano; leer documentos y ADR aplicable
  desde main actualizado.
- Mini-spec aún en rama publicada: recuperar el archivo/commit exactos y conservar
  trazabilidad; incluir ese archivo en la Implementation PR para integrarlo en main.

| Estado | Acción |
|---|---|
| Ready | Nueva ejecución solo con DoR completa; buscar ejecución anterior antes de crear. |
| En curso | Reanudar únicamente si plan, registro, rama y trabajo corresponden inequívocamente a esta Issue; volver a comprobar DoR/acuerdo. |
| En revisión | Reutilizar PR abierta y registro. Sin feedback autorizado ni trabajo pendiente: informar/no-op. Con feedback dentro del alcance: verificar, corregir y actualizar la misma PR. |
| Bloqueadas | Leer impedimento; continuar solo trabajo independiente autorizado. Para volver a En curso, registrar resolución y acreditar plan/rama y destino con el gestor. |
| Por hacer / Especificando / Hechas | No implementar ni reparar el estado por suposición; indicar qué requisito o fase falta. |

Si falta planificación, indicar el gap y remitir a
[plan-issue](../plan-issue/SKILL.md), sin inventar acuerdos ni iniciar producto.

## 2. Rama y registro de ejecución

Buscar primero referencias en Issue/comentarios, ramas `impl/<issue>-*` locales y
remotas y PRs de esta Issue (abiertas/cerradas/integradas). Comparar repo, número,
alcance, plan y head; el nombre de rama no prueba identidad. Varios candidatos,
PR cerrada/integrada, checkout con trabajo ajeno o ejecución concurrente ambigua:
detener esa operación sin sobrescribir ni crear otra ejecución a ciegas.

Revisar status, staging, historial y operaciones Git pendientes. No descartar
cambios, reescribir historial ni mezclar trabajo ajeno. Para ejecución nueva,
con árbol limpio y sin commits locales de main pendientes de publicar:

```sh
git switch main
git pull --ff-only origin main
git switch -c impl/<issue>-<slug>
```

Crear solo si no existe una ejecución correspondiente. Una reanudación utiliza
su rama y cambios conocidos; no repite pull/creación ni sustituye trabajo local.
No implementar sobre main ni una rama de planificación. Si falla Git, investigar
sin reset, force-push o reparaciones destructivas.

Registrar una vez en la Issue: plan/versión y evidencia DoR, rama, SHA base,
AC/verificaciones y progreso/evidencia disponibles para reanudar. Actualizar este
registro al completar hitos o antes de interrumpir, solo si cambia, conservando
evidencia anterior y sin duplicar comentarios. Releer y comprobar el registro; después Ready → En curso mediante gh-project-management.
No empezar código si ese movimiento falla. Si se interrumpe entre rama, registro
y transición, reconciliar lo observado al reanudar, completando solo lo pendiente.
La autorización no reserva la Issue: si otro actor cambió plan/estado, detener y
resolver la concurrencia antes de escribir.

## 3. Ejecutar y verificar con autonomía

Inspeccionar código, tests y entorno del alcance. Implementar AC preservando
contratos, decisiones e invariantes; elegir organización, algoritmos, orden y
herramientas. El Implementation Plan orienta, no prescribe detalles internos.
Registrar ajustes relevantes, sin pedir nueva revisión por detalles técnicos internos.
Para alcance exclusivamente documental, aplicar la excepción del workflow:
verificar contenido, enlaces y diff; no escribir tests artificiales ni producto.

Determinista: escribir primero un test que falle por el comportamiento ausente,
registrar Red, implementar lo mínimo para Green y refactorizar en verde.
Regresiones ya satisfechas no requieren rojo artificial. ML/probabilístico:
baseline → eval que demuestra gap → cambio → reevaluación → comparación, con
protocolo/datos/versiones y criterios acordados; combinar estrategias si procede.
No inventar métricas, umbrales ni evidencia. En reanudación conservar la evidencia
previa; no reconstruir un Red ficticio. Si falta, registrar el gap y recuperarlo
de forma reproducible sobre la base pertinente sin descartar trabajo actual.

Cada AC se vincula a test/eval y resultado mediante URL del plan o ruta de Spec
+ ID, también en nombre/comentario/documentación del test. Ejecutar los checks
previstos y las regresiones pertinentes. Investigar fallos, distinguir defecto
del cambio, fallo previo o entorno, y corregir dentro del alcance autónomamente.
Un error de import/dependencia no demuestra Red del AC. Registrar comandos,
entorno/commit, resultados y pendientes; no declarar éxito de checks omitidos.
Si no puede avanzar sin información/permiso externo, registrar impedimento y
siguiente acción; usar Bloqueadas con las condiciones del gestor, sin bucle de
reintentos ni mutaciones a ciegas.

Decisión real de producto, cambio de alcance/AC/contrato/decisión aceptada o riesgo
que exige diseño previo: detener la parte afectada, conservar trabajo y registrar
motivo, nueva incertidumbre y siguiente decisión necesaria. Pedir criterio humano
y aplicar replanificación a Especificando o bloqueo acreditado según workflow.
No modificar unilateralmente el plan ni usar esta invocación como autorización
de ampliar alcance; reanudar solo con nueva versión/DoR acreditadas.

## 3b. Revisión independiente proporcional

Antes de presentar la PR, elegir y registrar profundidad por riesgo, impacto,
complejidad e incertidumbre. Reviewer examina corrección, contratos, arquitectura
y regresiones; QA busca defectos nuevos fuera de AC/tests mediante exploración
reproducible. Ambos pueden ser breves para tareas localizadas. Solo documentación
trivial admite QA no aplicable con justificación explícita; nunca simularlo.

Leer [el soporte operativo](references/independent-review.md) al ejecutar esta
fase. Usar procesos reales con historial y snapshots separados del mismo candidato
identificable; no entregar conversación del autor ni conclusiones del otro rol.
Verificar permisos efectivos: reviewer solo lectura; QA escribe en su copia y
no puede modificar el checkout original por rutas absolutas, relativas o symlink.
Solo el implementador escribe su rama. Aislamiento fallido bloquea entrega.

Recibir informes automáticamente, agrupar duplicados, reproducir y contrastar
hallazgos. Corregir defectos fundamentados por lotes; rechazar falsos positivos
con evidencia sin alterar el contrato para satisfacer una sugerencia. Registrar
candidata/IDs, decisión, repro y resultado en el registro existente, preservando
la evidencia previa. No reinvestigar descartes sin evidencia nueva.

Tras cambios, verificar tests/evals y delegar revalidación independiente del nuevo
candidato: delta, correcciones y efectos colaterales, ampliando por riesgo. No
repetir todo el análisis por defecto. Dos lotes de corrección y un retry técnico
por rol son el presupuesto inicial orientativo; agotarlo informa/escala, conserva
pendientes y no rebaja garantías. Revisiones incompletas no acreditan aprobación.

Registrar por agente/intento tokens input/output/cached disponibles del runtime,
duración, retries y hallazgos útiles aceptados; desconocido sigue desconocido.
Reportar el mecanismo realmente probado: Codex y Claude pueden diferir; mantener
canon único y marcar mecanismos no verificados sin fallback inseguro.

Un CLI con exit 0 no basta: comprobar turno, informe, candidata, checks realmente
ejecutados, exploración QA y hallazgos resueltos. Fallos, timeout, permisos,
verificaciones incompletas o defectos relevantes pendientes impiden presentar
entrega verificada. Esta fase complementa AC/DoD y la revisión humana de la PR.

## 4. Implementation PR y En revisión

Contrastar todos los AC, preservación y DoD técnica con evidencia del estado final.
Revisar diff, trazabilidad, documentación afectada y secretos. Checks requeridos
fallidos/no ejecutados, regresiones conocidas o AC pendientes impiden presentar
la implementación como lista; mantener En curso o bloqueo real. Si hace falta
feedback sobre trabajo incompleto, puede existir PR draft con pendientes visibles,
pero no acredita entrega para revisión completa ni justifica promover por sí sola.

Con verificación y revisión independiente completas, preparar el template con tipo Implementation:
Issue (`Refs #N`, sin keywords de cierre), plan/versión, Test/Eval Plan, AC →
tests/evals → resultados, evidencia TDD/eval, decisiones/ajustes y riesgos. Añadir
candidata revisada, roles/profundidad, hallazgos y decisiones, revalidación, coste
real y límites del runtime; checks no ejecutados siguen pendientes.
Enlazar Planning PR/ADR solo cuando apliquen; justificar los no aplicables.
Incluir mini-spec en archivo pendiente de integración cuando forme parte del plan.

Aplicar [semantic-commits-and-push](../semantic-commits-and-push/SKILL.md) a los
cambios comprendidos de esta rama. Preparar contenido antes: esa skill no edita
archivos. Invocarla desde la rama dedicada/reanudada, nunca una rama ajena;
si ya hay PR, omitir creación y actualizar la misma.
No publicar archivos ajenos ni repetir commits/PR si no hay cambios.

Tras push, releer head/base/repo, diff y estado de PR; verificar que el código
publicado es el verificado. Si publicación falla, informar efecto parcial y
reanudar sin duplicar. Añadir/verificar referencia a PR y evidencia en la Issue
solo si falta; luego En curso → En revisión y releer Status e Issue abierta.
Con PR previa en En revisión, verificar su actualización sin repetir movimiento.
Si falla registro o transición después de abrir PR, informar y completar solo
ese paso en la siguiente ejecución.

Salida: PR/rama/head, plan vigente, AC y comprobaciones con resultados/pendientes,
estado verificado y revisión/aprobación/merge humanos pendientes. Terminar en
En revisión, sin declarar tarea Done: la entrega final pertenece a
[finish-issue](../finish-issue/SKILL.md). No aprobar, fusionar, cerrar ni marcar Hechas.
