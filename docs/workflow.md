# Lifecycle de desarrollo

El proceso combina documentos versionados con GitHub Issues y Projects v2.
Las decisiones de transición y las comprobaciones de DoR/DoD siguen siendo
manuales y explícitas. Las invariantes están en [AGENTS.md](../AGENTS.md).

```text
GitHub Issue → Spec → ADR → Test Plan → Planning PR → Ready
             → TDD → Implementation PR → CI / traceability / review → Done
```

| Fase | Resultado y condición para avanzar |
|---|---|
| GitHub Issue | Problema y alcance registrados con el template de Issue. Es requisito antes de cualquier código productivo. |
| Spec | Comportamiento y AC verificables con IDs estables, enlazados a la Issue. Usar el template en `docs/templates/` y guardar en `entregas/<caso>/specs/`. |
| ADR | Decisión propuesta en `docs/adr/`, enlazada a la Issue y a las Specs que cubre. |
| Test Plan | Casos, datos, entorno y comandos previstos para cada AC; puede ser una sección de la Spec o un documento versionado enlazado. |
| Planning PR | PR de documentación que revisa Spec, ADR y Test Plan. El revisor acepta explícitamente el ADR; registrar esa aceptación e integrar la PR antes de implementar. |
| Ready | Issue enlazada, Spec revisada, ADR aceptado, Test Plan que cubre todos los AC, Planning PR integrada y sin pendientes que bloqueen implementación. Registrar la comprobación de DoR en la Issue y solicitar explícitamente el cambio a Ready en el Project. |
| TDD | En una nueva feature branch desde `main` con la planificación integrada, ejecutar Red → Green → Refactor por comportamiento y registrar evidencia. |
| Implementation PR | PR distinta que enlaza Issue, Spec, ADR, Test Plan y Planning PR, con tests trazables y evidencia de verificación. |
| CI / traceability / review | Revisar resultados de verificación, cobertura de AC y diff. La CI queda para una fase posterior; en esta foundation se aportan comandos y resultados manuales. |
| Done | DoD global y requisitos específicos de las Specs completamente satisfechos, con evidencia. Solo entonces cerrar la Issue y pasarla a Hechas. |

La Planning PR debe referenciar la Issue sin cerrarla (`Refs #N`). La
Implementation PR puede usar `Closes #N` si todos los puntos de la DoD se cumplen
al integrarla; si quedan pendientes, usar `Refs #N` y cerrar manualmente solo
cuando se cumpla la DoD. La Issue permanece abierta durante la implementación.
Ready y Done son condiciones del proceso, reflejadas en `Ready` y `Hechas`
en el Project mediante operaciones explícitas, sin sincronización automática.

## Seguimiento operacional con GitHub Projects v2

El [Project PIIA2 — Seguimiento](https://github.com/users/lvckss/projects/1),
propiedad de `lvckss`, está vinculado a `lvckss/piia2-26`. Su vista `Seguimiento`
es un Board agrupado por `Status`. La configuración compartida está en
[project-config.json](../.github/project-config.json): owner y número identifican
el Project; los IDs de campos, opciones e items se descubren en cada operación.

| Recurso | Responsabilidad |
|---|---|
| GitHub Issue | Unidad de trabajo: alcance, referencias, bloqueos y evidencia de cierre. |
| GitHub Project | Fuente de verdad del estado operacional. |
| Spec | Comportamiento requerido y AC verificables. |
| ADR | Decisión técnica aceptada. |
| Test Plan | Estrategia de verificación de cada AC. |
| Planning PR | Aprobación de la planificación antes de implementar. |
| Implementation PR | Implementación y evidencia de verificación. |

El Project no sustituye a las Specs ni a los ADRs. Una Issue abierta/cerrada no
determina por sí sola su estado operacional, ni una columna prueba DoR o DoD.

| Status | Significado |
|---|---|
| Por hacer | Trabajo identificado, todavía no planificado. |
| Especificando | Elaboración o revisión de Spec, ADR y Test Plan. |
| Ready | DoR cumplida y planificación integrada; permite implementar. |
| En curso | Implementación activa. |
| En revisión | Implementation PR abierta. |
| Bloqueadas | Impedimento explícito documentado que impide continuar. |
| Hechas | DoD completamente cumplida y cambio integrado. |

Transiciones normales, siempre solicitadas explícitamente:

```text
Por hacer → Especificando → Ready → En curso → En revisión → Hechas
estado activo → Bloqueadas → estado operativo apropiado
```

Un estado activo es cualquiera salvo `Bloqueadas` y `Hechas`. Antes de bloquear,
registrar en la Issue motivo, dependencia o impedimento y siguiente acción
prevista. Sin los tres datos la skill se niega a escribir. Al desbloquear,
documentar la resolución y solicitar el destino apropiado; no volver a una
columna por suposición. Otras transiciones requieren una petición y justificación
explícitas. `Ready` y `Hechas` mantienen sus requisitos de DoR y DoD.

Las skills operacionales son:

- [gh-verifying-context](../.agents/skills/gh-verifying-context/SKILL.md): solo lectura;
  comprueba repo, configuración, CLI, autenticación, Issues, Project y estados.
- [gh-issue-management](../.agents/skills/gh-issue-management/SKILL.md): consulta Issues;
  creación explícitamente solicitada, actualizaciones mínimas y comentarios autorizados.
- [gh-project-management](../.agents/skills/gh-project-management/SKILL.md): consulta
  campos, pertenencia y estado; añade Issues y cambia Status bajo petición explícita.

Cada escritura sigue: verificar contexto → leer → determinar cambio mínimo →
escribir → releer → verificar exactamente el resultado → informar. No hay
cierres de Issues, borrados, archivados ni cambios de estructura desde estas skills.
Los workflows automáticos del Project deben estar desactivados para que añadir
o mover una Issue no provoque cambios ajenos a la solicitud.

Se adaptan conceptualmente la configuración compartida, la verificación previa
y la separación de gestores de [yu-iskw/github-project-skills](https://github.com/yu-iskw/github-project-skills).
No se instala su plugin ni se reutilizan triage, cierres, transferencias, borrados,
subagentes o sincronización autónoma. Se usan CLI/API oficiales, sin scraping.

## Definition of Ready y Definition of Done

La **Definition of Ready (DoR)** permite comenzar implementación: confirma que
la Issue, la Spec revisada, el ADR aceptado y el Test Plan están disponibles,
la Planning PR está integrada y no hay bloqueos de planificación. No acredita
que el comportamiento esté implementado ni verificado.

La **Definition of Done (DoD)** permite considerar terminada y cerrar la tarea,
y pasarla a `Hechas`. La checklist global está en el
[template de Issue](../.github/ISSUE_TEMPLATE/work-item.md#definition-of-done)
y se completa en cada Issue con referencias a evidencia verificable. Incluye
AC implementados y verificados, tests y checks requeridos en verde, ausencia
de regresiones conocidas, verificación final documentada, PR revisada,
aprobada e integrada en `main`, documentación actualizada y ausencia de
bloqueos o pendientes dentro del alcance.

La DoD de cada Spec puede añadir condiciones específicas (métricas, versiones
de datos, artefactos o documentación), pero nunca relajar la DoD global.
Ambas deben cumplirse. Checks requeridos no ejecutados, fallos conocidos
introducidos por el cambio o trabajo pendiente dentro del alcance impiden Done,
aunque la PR ya esté integrada. Registrar la evidencia de cierre en la Issue
y la verificación final en la Implementation PR.

Para la trazabilidad manual, usar siempre la ruta de la Spec junto al ID del
AC. El Test Plan relaciona AC y casos; los tests incluyen esa referencia; la
Implementation PR relaciona tests y evidencia. Para TDD, registrar el comando
y el fallo esperado en Red, el resultado en Green y la comprobación posterior
a Refactor. Indicar cualquier verificación pendiente con su motivo.

Los cambios exclusivamente documentales usan una PR documental y evidencia
de revisión de contenido, enlaces y diff. No requieren un ciclo TDD funcional
ni una Implementation PR adicional. Las specs y ejemplos existentes se
conservan; para nuevas implementaciones se completan según estas reglas.
Su DoD mantiene la verificación, revisión, aprobación, integración y ausencia
de pendientes: usar la PR documental como referencia y justificar los requisitos
funcionales no aplicables, sin omitir los checks documentales requeridos.

Nota histórica de la foundation: se establecieron reglas y templates sin exigir
la migración retroactiva del código existente. Esta capa operacional incorpora
Projects v2 y tres skills específicas del repositorio, sin enforcement automático.
La comprobación de DoD sigue siendo manual; su validación automática queda pendiente.
Las futuras `piia2-plan-task`, `piia2-implement-task` y `piia2-ship-task` decidirán
cuándo solicitar las transiciones. Esta fase no las implementa ni genera Specs,
ADRs, tests o TDD; tampoco incorpora `traceability-check`, Actions/CI adicional,
`babysit-pr`, branch protection ni automatismos de eventos Issue/PR a Status.

Templates: [Spec](templates/spec-template.md), [ADR](adr/template.md),
[GitHub Issue](../.github/ISSUE_TEMPLATE/work-item.md) y
[Pull Request](../.github/pull_request_template.md).
