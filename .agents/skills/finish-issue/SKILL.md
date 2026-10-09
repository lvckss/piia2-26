---
name: finish-issue
description: Verificar la entrega de una Issue de PIIA2 tras integración en main, acreditar DoD con evidencia existente y mover a Hechas de forma idempotente. No aprobar, mergear ni cerrar la GitHub Issue.
---

# Completar la entrega de una Issue

Entrada: `finish-issue 14`, entero positivo decimal con `#` opcional. Pedir el
número si falta; rechazar cero, negativos, texto extra, URLs y otros repos.
Leer [AGENTS.md](../../../AGENTS.md), [workflow y DoD](../../../docs/workflow.md)
y la DoD de la Issue/plan. No exigir Spec, ADR ni Planning PR si no aplican.

Aplicar [gh-verifying-context](../gh-verifying-context/SKILL.md),
[gh-issue-management](../gh-issue-management/SKILL.md) y
[gh-project-management](../gh-project-management/SKILL.md), sin duplicar sus
mecanismos. La invocación autoriza lecturas, comprobaciones acotadas, registro de
entrega y transiciones justificadas con relectura/verificación, sin permiso por
paso; respetar runtime y límites del usuario. No crear Issues, implementar o
cambiar el plan, aprobar/mergear PRs, habilitar auto-merge ni cerrar/reabrir la
GitHub Issue. Conservar su estado OPEN/CLOSED; no confundirlo con Status Hechas.

## 1. Identificar la entrega y su versión

Leer Issue, comentarios completos y Project/Status. Rechazar identidad ambigua,
item archivado o contexto inválido antes de escribir. Recuperar plan vigente,
versión/AC y registro de implementación; respetar adaptaciones humanas explícitas
y antecedentes históricos. Buscar la PR de entrega referenciada (Implementation,
o documental para alcance exclusivamente documental); comparar repo, Issue,
alcance, plan y head. No elegir por título/fecha ni confundir una Planning PR con
la entrega. Leer reviews, comentarios y checks de la PR completos, paginando.
Resolver contradicciones antes de continuar, sin nuevos artefactos.

Exigir PR MERGED hacia main, head final, merge commit y autor humano de integración.
Actualizar el snapshot remoto de main mediante fetch del origin verificado,
fijar su SHA y comprobar que contiene la integración; leer archivos desde ese
snapshot sin cambiar de rama ni tocar trabajo local. Acreditar que el contenido
integrado corresponde al plan/versionado y al contenido verificado, también con
squash/rebase: no exigir que el head original sea ancestro de main. Revisar cambios
posteriores relevantes/reversiones; un merge antiguo no prueba el resultado actual.

## 2. Acreditar DoD reutilizando evidencia

Contrastar DoD global y específica con las fuentes, no solo checklists/Status:

- Todos los AC del plan vigente cubiertos y trazados a tests/evals/resultados;
  contratos/preservación y documentación afectada verificados.
- Checks requeridos ejecutados y en verde, con comandos/pasos, entorno/datos,
  resultados y versión del contenido; evidencia TDD/eval-first pertinente.
  Para alcance documental, revisión de contenido/enlaces/diff y no aplicables
  justificados según workflow. No rebajar requisitos de tareas ya planificadas.
- Mini-spec en archivo que forme parte de la entrega integrada en main;
  Planning PR/Spec Revisada y ADR Aceptado/cobertura acreditados cuando aplican.
- Revisión y aprobación humanas de código/documentación y planificación pertinente
  sobre la versión final, según la evidencia de entrega admitida en el workflow.
  Aceptar review válida o aceptación humana explícita en PR/Issue/sesión vigente,
  con autor/origen, alcance y versión identificados; no exigir APPROVED formal
  si existe evidencia alternativa suficiente. Si proviene de la sesión, registrar
  fielmente decisión/origen y versión al resumir, sin autoaprobar ni atribuirla al agente.
  Resolver observaciones/revocaciones contradictorias; merge, silencio, reacciones,
  bots o autoaprobación del agente no acreditan revisión/aceptación ausentes.
- Sin regresiones, bloqueos, checks requeridos ni trabajo del alcance pendientes:
  leer feedback, checks y registros actuales y comprobar resoluciones conocidas.

Reutilizar CI, logs y evidencia concreta ya registrada en PR/Issue si cubre el
contenido integrado y sigue siendo válida. No pedir adjuntos/formato nuevos ni
repetir toda la suite por rutina. Si el merge o cambios relevantes invalidan una
prueba, falta un check requerido o la evidencia no permite relacionarlo con la
versión entregada, explicar el gap y ejecutar solo la comprobación necesaria
sobre el snapshot pertinente, sin alterar checkout ajeno ni reparar producto.
Checks opcionales omitidos con motivo no bloquean; requeridos omitidos/fallidos sí.
Nunca presentar comandos previstos o no ejecutados como resultados reales.

Si la DoD no se acredita, no marcar Hechas ni declarar Done. Investigar lo
resoluble dentro del alcance; si depende de una decisión/evidencia humana,
solicitar únicamente esa información concreta, reutilizando lo ya acreditado.
Mantener el estado apropiado; un bloqueo real usa motivo/impedimento/siguiente
acción y registro del gestor. Correcciones funcionales/nuevo alcance se remiten
a ejecución/replanificación autorizada; no se implementan en esta skill.

## 3. Registrar y finalizar sin duplicados

Buscar primero un resumen existente que acredite la misma entrega: plan/versión,
PR/head/merge, AC/verificaciones y aceptación humana. Comparar contenido/evidencia,
no exigir un encabezado o marcador nuevo. Si ya basta, reutilizarlo; si hay un gap,
añadir solo la información faltante conservando registros anteriores. Un nuevo
SHA de main sin cambios relevantes no exige otro resumen.

| Status | Acción con DoD acreditada |
|---|---|
| En revisión | Registrar/verificar resumen si falta; después mover a Hechas y releer. |
| Hechas | Revalidar evidencia vigente; no escribir si registro/resultado ya coinciden. Si solo falta registro, completar ese gap sin repetir transición. Si DoD no se sostiene, informar inconsistencia sin revertir estados a ciegas. |
| En curso | Solo con PR integrada y registro inequívoco de la misma ejecución: reconciliar En revisión atrasado mediante el gestor, verificando el paso; continuar entrega. |
| Bloqueadas | Acreditar y registrar resolución del impedimento antes de salir; justificar destino apropiado con DoD completa según gestor. |
| Otros / sin item o Status | Indicar discrepancia; no inferir fases completadas ni reparar estado por el merge. |

Resumen mínimo en la Issue mediante gh-issue-management: enlace y versión del
plan, PR/head/merge y main comprobado, conclusión por AC/DoD con enlaces a evidencia,
aceptación humana y omisiones opcionales con motivo. No copiar logs completos
ni repetir la planificación. Registrar antes de Hechas y verificar el texto.
Releer contexto/plan/PR/item antes de la transición; si cambió el acuerdo,
contenido o estado, reevaluar sin sobrescribir decisiones concurrentes.

Mover únicamente mediante gh-project-management con destino y justificación
explícitos y referencia que acredite DoD completa. Verificar Status, pertenencia,
identidad y que los demás campos/estado de la Issue se conservan. Si una escritura
falla o queda un efecto parcial, informar lo observado y releer antes de reintentar:
resumen existente + movimiento fallido implica completar solo el movimiento;
Hechas ya confirmado implica no repetirlo. No borrar ni revertir a ciegas.

Salida: Issue y PR, plan/versionado, main/head/merge comprobados, evidencia de DoD,
Status observado y gaps si existen. Solo declarar entrega completada tras registro
y Hechas verificados. La GitHub Issue conserva su estado; no aprobar ni mergear.
