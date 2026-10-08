# Lifecycle de desarrollo

El proceso combina documentos versionados con GitHub Issues y Projects v2.
Las decisiones de transición y las comprobaciones de DoR/DoD siguen siendo
manuales y explícitas. Las invariantes están en [AGENTS.md](../AGENTS.md).

```text
GitHub Issue → Spec → ADR decision (ADR si aplica) → Test/Eval Plan
             → Planning PR → Ready → TDD/eval-first → Implementation PR
             → CI / traceability / review → Done
```

Orquestadores de alto nivel:

```text
Issue → piia2-plan-task → Ready → piia2-implement-task → En revisión
      → piia2-ship-task → Hechas
```

Solo `piia2-plan-task` existe actualmente; las otras dos skills son fases futuras.

| Fase | Resultado y condición para avanzar |
|---|---|
| GitHub Issue | Problema y alcance registrados con el template de Issue. Es requisito antes de cualquier código productivo. |
| Spec | Comportamiento y AC verificables con IDs estables, enlazados a la Issue. Usar el template en `docs/templates/` y guardar en `entregas/<caso>/specs/`. |
| ADR decision | NEW_ADR, REUSE_ADR o NO_ADR_REQUIRED, con justificación en Spec. Toda decisión relevante requiere un ADR aceptado antes de implementar. |
| Test/Eval Plan e Implementation Plan | Secciones obligatorias de la Spec: verificaciones por AC y estrategia TDD/eval; vertical slices pequeñas con objetivo observable, AC, contratos, dependencias y verificación. |
| Planning PR | Revisión humana de Spec, planes y ADR decision; acepta ADR nuevo, confirma cobertura del reutilizado o justifica no requerirlo. Registrar la aceptación y hacer merge humano antes de implementar. |
| Ready | DoR completa desde main: Spec Revisada, ADR decision resuelta y revisada, ambos planes cubren todos los AC y Planning PR revisada e integrada, sin bloqueos. Registrar evidencia y verificar promoción explícita por piia2-plan-task. |
| TDD/eval-first | En una nueva feature branch desde `main` con planificación integrada, ejecutar la estrategia determinista, ML o híbrida definida en Spec y registrar evidencia. |
| Implementation PR | PR distinta que enlaza Issue, Spec, Test/Eval Plan, Planning PR y ADR cuando aplique; en otro caso, `ADR: No requerido — justificado en Spec`. Tests/evals trazables y evidencia de verificación. |
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
| ADR | Decisión técnica/arquitectónica relevante aceptada; no es obligatorio crear uno por tarea. |
| Test/Eval Plan | Estrategia de verificación de cada AC. |
| Implementation Plan | Secuencia de vertical slices verificables dentro de la Spec. |
| Planning PR | Aprobación de la planificación antes de implementar. |
| Implementation PR | Implementación y evidencia de verificación. |

El Project no sustituye a las Specs ni a los ADRs. Una Issue abierta/cerrada no
determina por sí sola su estado operacional, ni una columna prueba DoR o DoD.

| Status | Significado |
|---|---|
| Por hacer | Trabajo identificado, todavía no planificado. |
| Especificando | Elaboración o revisión de Spec, decisión ADR y planes. |
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

La entrada oficial de planificación es
[piia2-plan-task](../.agents/skills/piia2-plan-task/SKILL.md), invocada con una
Issue existente (`#12` o `12`). Reutiliza las skills operacionales y de entrega:

```text
Por hacer → Especificando → investigación + clarify → Spec Borrador
          → ADR decision (NEW_ADR: Propuesto; REUSE_ADR; NO_ADR_REQUIRED)
          → Test/Eval Plan + Implementation Plan → analyze → Planning PR
          → revisión humana → Spec Revisada + ADR decision revisada
          → merge humano → DoR desde main → Ready
```

Explora código/documentación antes de redactar y ejecuta **clarify** conceptualmente:
requisitos/términos ambiguos, decisiones ausentes, supuestos como hechos, umbrales
sin evidencia, edge cases y contradicciones con comportamiento existente. Clasifica
cada incertidumbre como resuelta con evidencia, supuesto explícito aceptable,
pregunta no bloqueante o bloqueante. Primero inspecciona el repo; pregunta solo
por criterio humano necesario. No completa el plan si no puede definir AC verificables.

La Spec registra comportamiento que debe preservarse (contratos, compatibilidad,
esquemas e invariantes), failure modes y NFRs relevantes, con protección trazable
mediante AC/verificaciones. No inventa requisitos o umbrales. Mapea todos los AC a
seams observables, verificaciones y vertical slices del Implementation Plan, sin
código ni internals innecesarios. Si hay demasiadas slices o varios objetivos
independientes, recomienda dividir antes de una mega-Spec; no crea child Issues.

La estrategia por comportamiento es TDD para lo determinista: Red → Green →
Refactor. Para objetivos ML/probabilísticos/heurísticos que TDD unitario no representa:
Baseline → criterio/eval que demuestra el gap → cambio → reevaluación → comparación.
Puede ser híbrida. No inventa un test rojo artificial para métricas ML.

La decisión ADR queda explícita y justificada, eligiendo exactamente un caso.
El criterio es su relevancia estructural y durabilidad/coste de reversión, no
que cambie un comportamiento observable:

| ADR decision | Condición de planificación y aprobación |
|---|---|
| NEW_ADR | Decisión suficientemente fundamental, duradera o costosa de revertir: arquitectura, boundaries entre componentes independientes, contratos externos/fronteras estables, schemas/formatos compartidos o persistentes, datos/persistencia, integración/protocolo, deployment/serving, concurrencia, seguridad, dependencia externa estructural, estrategia ML/evaluación duradera o trade-off importante difícil de revertir. ADR nuevo Propuesto; el humano acepta la decisión y se registra Aceptado. |
| REUSE_ADR | ADR existente Aceptado cubre realmente decisión y alcance; ruta y explicación concreta. El humano confirma cobertura, sin reescribir la decisión ni crear duplicado. |
| NO_ADR_REQUIRED | Sin decisión estructural relevante: validación, excepción/precondición o comportamiento de función interna, bugfix/mejora localizada, algoritmo interno, refactor que preserva arquitectura/boundaries, tests o documentación. Puede cambiar comportamiento observable local. Justificación en Spec aceptada en review; no crear ADR artificial. |

Para ADR, **contrato público** significa frontera estable consumida externamente
o entre agentes/componentes que evolucionan independientemente: API externa,
Agente 1 → Agente 2, schema JSON compartido, protocolo, formato persistente o
interfaz estable usada fuera del componente. Ni carecer de prefijo `_` ni ser
importable entre módulos convierte una función interna en esa frontera.
Una API interna puede requerir ADR si adquiere consecuencias estructurales,
consumidores independientes o un coste de reversión importante. Un cambio pequeño
de schema entre agentes sigue requiriendo NEW_ADR o REUSE_ADR según cobertura.
Investigar consumidores, boundaries y coste/durabilidad antes de decidir; ante
ambigüedad restante usar clarify, sin ADR por precaución ni NO_ADR_REQUIRED para
ocultar arquitectura. Los cambios funcionales locales siguen requiriendo Spec,
AC, Test/Eval Plan, Implementation Plan y estrategia TDD/eval prevista.

Las referencias/checklists anteriores que exijan ADR incondicional se interpretan
según esta política y AGENTS.md: registrar no aplicable y justificación para
NO_ADR_REQUIRED, sin marcar un ADR inexistente como aceptado ni sustituir el body
de la Issue. Toda decisión relevante pendiente sigue bloqueando implementación.

Después de redactar, **analyze** contrasta Issue, alcance/fuera de alcance,
comportamiento preservado, failure modes/NFRs, AC, ADR decision/ADR y ambos planes.
Detecta requisitos omitidos, AC/slices fuera de alcance, AC sin verificación o
slice, verificación sin AC, regresiones/fallos sin protección, supuestos como
hechos, contradicciones y decisión ADR artificial/oculta o reutilización sin
cobertura. Corrige con evidencia inequívoca; si requiere criterio humano, registra
y pregunta. Con gaps bloqueantes no publica como lista para revisión completa;
puede abrir draft para discutir incertidumbres explícitas. Repite clarify/analyze
ante cambios sustantivos. Reanuda sin duplicar Specs, decisiones, ramas o PRs;
no escribe código productivo, tests ni fixtures.

La invocación autoriza las operaciones no destructivas de este recorrido sobre
esa Issue, incluidas referencias y comentarios mínimos sin sustituir su body,
y promoción acreditada a Ready. No se pide confirmación por cada paso.

Abrir la Planning PR significa presentar el plan a revisión. Mientras siga abierta,
la Issue permanece abierta en `Especificando`, aunque los documentos ya estén
revisados/aceptados. Si faltan decisiones que
impiden definir contratos verificables, el plan sigue como borrador y su eventual
PR es draft, con los pendientes visibles. Una tarea bloqueada solo se investiga
con petición expresa y si su impedimento lo permite; no se desbloquea por suposición.
La misma skill, al reejecutarse, localiza esa PR y busca evidencia humana explícita
de aceptación del plan: claridad y alcance, comportamiento preservado,
failure modes/NFRs, AC/seams, estrategia TDD/eval, ambos planes, riesgos,
preguntas, ADR decision y consistencia global. No pide revisar internals inexistentes.
Solo con evidencia suficiente registra quién, referencia y versión revisada,
y actualiza Spec a Revisada y, en NEW_ADR, ADR a Aceptado en la misma rama/PR.
Para REUSE_ADR registra cobertura confirmada; NO_ADR_REQUIRED, justificación
aceptada. No infiere aceptación por silencio ni merge.
Después de cada push comprueba la aprobación real: si GitHub la invalida, debe
renovarse. El humano comprueba y aprueba el head final y hace el merge.

Tras el merge, una reejecución verifica los documentos del snapshot actualizado
de main, aceptación humana y aprobación final, Issue abierta y en el Project,
cobertura de todos los AC en ambos planes, ADR decision según su caso,
clarify/analyze sin gaps bloqueantes, y ausencia de preguntas, dependencias
o bloqueos que impidan implementar. Solo con DoR completa mueve Especificando
→ Ready, relee y verifica el resultado y registra evidencia mínima en la Issue.
La Issue sigue abierta y aquí termina piia2-plan-task, sin rama de implementación.
Si el merge dejó NEW_ADR Propuesto, ADR decision incompleta, Spec Borrador u otra
carencia, conserva Especificando e informa: hace falta corrección documental revisada, sin arreglos
silenciosos para pasar DoR ni duplicar planificación.

La **Definition of Ready (DoR)** permite comenzar implementación. Requiere:

- Issue abierta y perteneciente al Project; Planning PR correcta revisada por
  humano, con aprobación final válida antes del merge humano.
- Spec Revisada en main, aceptación humana referenciada y AC verificables.
- Test/Eval Plan e Implementation Plan en Spec cubren todos los AC; seams,
  estrategia, datos y verificación previstos; slices dentro del alcance.
- Comportamiento preservado y failure modes/NFRs relevantes tratados/protegidos.
- Sin ambigüedades bloqueantes, analyze sin gaps bloqueantes, sin dependencias
  que impidan implementar ni bloqueo operacional vigente.
- ADR decision resuelta y revisada: NEW_ADR con ADR Aceptado en main;
  REUSE_ADR con ADR existente Aceptado en main y cobertura confirmada en review;
  NO_ADR_REQUIRED con justificación en Spec revisada y aceptada en Planning PR.

Los documentos se comprueban desde un snapshot actualizado de main, incluyendo
correcciones revisadas si las hubo. DoR no acredita implementación ni verificación
final; la columna Ready por sí sola tampoco acredita estos requisitos.

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
a Refactor. Para eval-first, registrar baseline, evaluación del gap, datos/versiones,
reevaluación y comparación reproducible según Spec. Indicar cualquier verificación
pendiente con su motivo.

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
`piia2-plan-task` cubre Por hacer → Especificando → Ready, con aceptación
explícita en Planning PR, merge humano y comprobación completa de DoR desde main.
Las futuras `piia2-implement-task` y `piia2-ship-task` cubrirán implementación
con TDD/eval-first según Spec y entrega. No se implementan todavía tests, TDD, `traceability-check`, Actions/CI adicional,
`babysit-pr`, branch protection ni automatismos de eventos Issue/PR a Status.

Templates: [Spec](templates/spec-template.md), [ADR](adr/template.md),
[GitHub Issue](../.github/ISSUE_TEMPLATE/work-item.md) y
[Pull Request](../.github/pull_request_template.md).
