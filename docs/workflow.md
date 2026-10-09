# Lifecycle de desarrollo

Las invariantes están en [AGENTS.md](../AGENTS.md). Issue, planificación,
ejecución y entrega son responsabilidades distintas; la planificación no exige
siempre un documento ni una PR independiente.

```text
Issue → investigación + planificación proporcional → DoR → Ready
      → TDD/eval-first → Implementation PR → verificación + revisión humana
      → merge humano + DoD → Hechas
```

[plan-issue](../.agents/skills/plan-issue/SKILL.md) cubre únicamente
Por hacer → Especificando → Ready.
[implement-issue](../.agents/skills/implement-issue/SKILL.md) cubre Ready → En curso
→ Implementation PR → En revisión, con comprobación del plan, TDD/eval-first y
verificación de AC. `finish-issue` es una fase futura para la entrega final.
Ninguna de las skills actuales aprueba, fusiona ni cierra automáticamente la tarea.

## Planificación proporcional

Investigar código, consumidores, contratos, tests, datos y decisiones existentes
antes de elegir cuánto planificar. Valorar impacto, reversibilidad, seguridad,
incertidumbre, dependencias y capacidad de verificar el resultado. El tamaño del
diff no determina el riesgo. Registrar en la Issue la justificación, la ubicación
del plan vigente y si requiere revisión humana previa, con su motivo.

Estas situaciones son orientativas, no etiquetas ni niveles nuevos del Project:

| Situación | Plan suficiente | Intervención previa |
|---|---|---|
| Pequeña y localizada, reversible, requisitos claros | Issue con alcance, AC, restricciones, ADR decision justificada y verificaciones por AC. La estrategia de ejecución puede ser unas líneas junto a la verificación. | No requiere aprobación del plan ni Planning PR por defecto. |
| Feature habitual dentro de arquitectura y contratos acordados | Issue o mini-spec con comportamiento, AC, riesgos, Test/Eval Plan y orientación de implementación/dependencias suficientemente explícitos. | Solo para decisiones reales pendientes o riesgos que lo requieran. Puede entregarse el documento junto a la implementación. |
| Crítica, arquitectónica o difícil de revertir | Spec versionada, Test/Eval Plan e Implementation Plan detallados según el riesgo; ADR si hay decisión relevante. Planning PR separada, sin código productivo. | Diseño revisado y aprobado por humano, integrado antes de implementar. |

Se exige el camino con revisión previa si hay una decisión arquitectónica nueva
o modificada (`NEW_ADR`), impacto crítico (por ejemplo seguridad, pérdida de datos,
compatibilidad de consumidores independientes), reversión costosa o incertidumbre sustantiva
que requiera revisión humana del diseño para acordar requisitos/contratos verificables. Una
instrucción explícita de revisión previa también lo exige. Investigar antes de
escalar: una duda técnica resoluble por inspección no exige por sí sola una PR.
No rebajar riesgo por conveniencia ni generar ADR/documentos por precaución.

Una pregunta real de producto o alcance puede resolverse mediante respuesta humana
referenciada en la Issue sin imponer una Planning PR si no concurren los riesgos
anteriores. Nunca interpretar silencio, tiempo transcurrido o aprobación del agente
como una decisión humana. Si se necesita revisión previa, usar el camino versionado.

Para tareas pequeñas, preferir la propia Issue si permite registrar el plan suficiente.
La mini-spec usa las secciones pertinentes del [template de Spec](templates/spec-template.md),
sin una plantilla o entidad nueva. Puede vivir en la Issue o en
`entregas/<caso>/specs/<issue>-<slug>.md`. Sin revisión previa, su estado sigue
Borrador hasta revisión humana: Ready se acredita por DoR y no por la etiqueta
Revisada. Su versión para Ready queda fijada en un comentario de planificación
con permalink y copia del texto evaluado (o archivo y commit); un archivo aún no integrado debe quedar
accesible en una rama publicada. No depender de archivos locales ni del chat.
La revisión final cubre también esa planificación en la Implementation PR.
Si la mini-spec es un archivo que forma parte de la implementación, debe incluirse
e integrarse en main mediante esa Implementation PR. Su disponibilidad en una
rama publicada permite acreditar Ready, pero no constituye entrega definitiva
ni permite Done mientras siga únicamente en una rama temporal no integrada.

### Garantías comunes

En cualquier ubicación, el plan contiene:

- Problema, comportamiento esperado, alcance y fuera de alcance, autorización
  para trabajar y restricciones relevantes.
- AC observables con IDs estables (`AC-001`, etc.): entrada/precondición, acción,
  resultado y condición objetiva de éxito. No renumerar ni reutilizar IDs retirados.
- Contratos, invariantes, compatibilidad y comportamiento que deben preservarse;
  failure modes y NFRs relevantes y cómo verificar su protección.
- `ADR decision`: exactamente NEW_ADR, REUSE_ADR o NO_ADR_REQUIRED, con justificación.
- Test/Eval Plan: cada AC asociado a una frontera observable, caso, resultado,
  datos/entorno, comando o pasos reproducibles y evidencia prevista. TDD para lo
  determinista; eval-first para objetivos ML/probabilísticos/heurísticos que TDD
  unitario no representa; estrategia híbrida cuando proceda.
- Implementation Plan proporcional: objetivo, AC cubiertos, dependencias,
  contratos y verificaciones; para una tarea pequeña puede ser una sola secuencia.
  Orienta y permite reanudar, sin prescribir internals ni todos los pasos.
- Riesgos, supuestos explícitos, decisiones pendientes y DoD específica si aplica.

**Clarify** distingue hechos, supuestos y preguntas bloqueantes/no bloqueantes.
Resolver con evidencia antes de preguntar; no inventar métricas ni umbrales.
**Analyze** contrasta Issue/plan, alcance, AC, preservación, ADR y verificaciones:
ningún AC sin verificación, requisito omitido, regresión sin protección o decisión
arquitectónica oculta. Registrar resultado y pendientes. Un plan compacto no
permite omitir estas comprobaciones; permite registrarlas brevemente.

La referencia de un AC es `ruta de Spec + AC ID` o `URL de Issue/comentario de
planificación + AC ID`. Tests (nombre, comentario o documentación), Test/Eval
Plan y PR usan esa misma referencia. Si se mueve el plan, conservar IDs y un
mapeo explícito de referencias; no romper la trazabilidad de tests existentes.

### ADRs selectivos

| ADR decision | Condición |
|---|---|
| NEW_ADR | Decisión fundamental, duradera o costosa de revertir: arquitectura, frontera estable, persistencia/schema compartido, integración/protocolo, seguridad estructural, deployment, concurrencia, dependencia estructural o estrategia ML/evaluación duradera. Crear Propuesto; humano acepta en Planning PR y se registra Aceptado antes de implementar. |
| REUSE_ADR | ADR Aceptado en main cubre realmente decisión y alcance. Enlazar y justificar cobertura; el agente puede verificarla sin aprobación previa nueva si no cambia la decisión ni existe otro disparador de riesgo. Si hay revisión previa, el humano confirma cobertura. |
| NO_ADR_REQUIRED | Sin decisión estructural relevante: validación, bugfix/mejora local, algoritmo interno, refactor que preserva fronteras, tests o documentación. Justificación breve; revisión en la PR de entrega salvo que se requiera revisión previa. |

Un contrato público relevante es una frontera estable consumida externamente o
entre agentes/componentes que evolucionan independientemente: API externa,
contrato entre agentes, schema compartido, protocolo o formato persistente.
Una función Python sin `_` o importada dentro del mismo componente no lo es por
ese mero hecho. Una API interna con consecuencias estructurales o coste de reversión
importante sí puede requerir ADR. Investigar consumidores y cobertura antes de
resolver la decisión. Ni crear ADR artificial ni ocultar arquitectura.

### Autonomía y cambios durante ejecución

El implementador puede ajustar orden, algoritmos, organización interna y estrategia
de tests mientras respete AC, restricciones, contratos y decisiones aceptadas.
Registrar ajustes relevantes y su evidencia en la PR; no pedir revisión previa
por cada detalle técnico ni por reordenar el Implementation Plan.

Una invocación normal de plan-issue sobre Ready es no-op, sin escrituras.
Una solicitud explícita, vigente y autorizada de replanificación, con motivo concreto,
permite Ready → Especificando. Registrar solicitud, motivo y versión de partida;
reutilizar el plan y conservar versiones, IDs de AC y decisiones anteriores.
Reevaluar riesgo, necesidad de revisión previa y DoR para la nueva versión antes
de volver a Ready. La solicitud no autoriza por sí sola cambiar el alcance ni
eludir aprobaciones: decisiones humanas necesarias y revisiones aplicables se
acreditan para la versión pertinente, sin atribuir aceptación antigua a cambios nuevos.

Si cambia alcance, AC, contrato o decisión aceptada, detener la parte afectada,
registrar el cambio sin sobrescribir el acuerdo anterior y reevaluar riesgo/DoR.
Una decisión de producto/alcance requiere aceptación humana explícita de la nueva
versión. Si aparece un disparador de revisión previa, volver a Especificando
(o Bloqueadas si hay impedimento), abrir/reutilizar una Planning PR separada y
esperar revisión e integración antes de implementar ese comportamiento. En los
otros casos basta actualizar la planificación en Issue/mini-spec, resolver las
decisiones humanas necesarias y acreditar de nuevo Ready. No ampliar silenciosamente
una tarea ni aplicar cambios a tareas ajenas.

## Definition of Ready

Ready habilita implementación; no acredita que ya se verificó el resultado.
La columna por sí sola no prueba DoR. Registrar en la Issue evidencia para:

- Issue abierta, autorizada y perteneciente al Project configurado.
- Plan accesible y versión identificada; evaluación de riesgo y camino justificados.
- Alcance, AC verificables, restricciones y preservación acordes a la solicitud.
- Test/Eval Plan cubre todos los AC y regresiones relevantes, con datos/protocolo
  y estrategia justificadas; Implementation Plan suficiente para ejecutar/reanudar.
- ADR decision resuelta: NEW_ADR con ADR Aceptado en main; REUSE_ADR con ADR
  Aceptado en main y cobertura acreditada; NO_ADR_REQUIRED con justificación.
- Clarify/analyze sin gaps bloqueantes; decisiones humanas necesarias resueltas
  con referencia, sin impedimentos ni bloqueo operacional vigente.

Además, **si requiere revisión previa**: Spec Revisada, planes y ADR decision
aceptados por humano, autor/permalink/versión registrados; Planning PR aprobada
sobre el head final e integrada por humano. Comprobar documentos y ADR desde un
snapshot actualizado de main. Un merge solo no demuestra aceptación del diseño.
Sin revisión previa: no se exige Spec Revisada ni Planning PR; comprobar el plan
registrado y su cobertura, y consignar estos requisitos como no aplicables con
motivo. Para REUSE_ADR, leer igualmente el ADR desde main actualizado.

## Definition of Done

La misma DoD aplica a todos los caminos. La checklist global del
[template de Issue](../.github/ISSUE_TEMPLATE/work-item.md#definition-of-done)
y los requisitos específicos del plan deben estar completamente satisfechos:

- Todos los AC implementados y verificados con evidencia trazable.
- Tests/evals y checks requeridos ejecutados y en verde, sin regresiones conocidas.
- Evidencia TDD: comando/fallo esperado Red, Green y verificación tras Refactor.
  Eval-first: baseline, eval que demuestra gap, datos/versiones/protocolo,
  reevaluación y comparación reproducible. No fingir rojos ni checks ejecutados.
- Implementation PR enlaza Issue, versión del plan, AC, Test/Eval Plan, ADR y
  Planning PR cuando aplique (o no aplicable con motivo). Incluye verificación final.
- PR y planificación pertinente revisadas y aprobadas por humano; head final
  integrado en main por humano. Los agentes no aprueban ni fusionan sus propias PRs.
- Mini-specs en archivo que formen parte de la implementación incluidas en la
  Implementation PR e integradas en main; no basta su presencia en una rama temporal.
- Documentación actualizada y ningún bloqueo, check pendiente ni trabajo dentro
  del alcance sin resolver. Evidencia de cierre registrada en la Issue.

Un plan puede ampliar la DoD, nunca relajarla. Una PR mergeada con checks requeridos
pendientes no permite Hechas. La Planning PR usa `Refs #N`; la Implementation PR
solo puede usar `Closes #N` si la DoD se cumple al integrar. `implement-issue` usa
siempre `Refs #N` y deja el cierre para la entrega final. Los gestores actuales
no cierran Issues; no inferir autorización de cierre de una transición de estado.

Los cambios exclusivamente documentales se verifican mediante contenido, enlaces
y diff, con justificación de TDD/ejecución funcional no aplicables. Usan una sola
PR documental; mantienen evidencia, revisión, aprobación humana e integración.

## Seguimiento operacional con GitHub Projects v2

El [Project PIIA2 — Seguimiento](https://github.com/users/lvckss/projects/1)
se identifica mediante [project-config.json](../.github/project-config.json).
No se añaden estados, campos ni automatismos. Issue es la unidad de trabajo y
Project la fuente de verdad operacional; no sustituyen el plan ni los ADRs.

| Status | Condición |
|---|---|
| Por hacer | Trabajo identificado. |
| Especificando | Investigación, planificación o revisión previa necesaria. |
| Ready | DoR acreditada para el camino elegido. |
| En curso | Ejecución activa dentro de la planificación vigente. |
| En revisión | PR de entrega abierta, evidencia y pendientes visibles. |
| Bloqueadas | Motivo, impedimento y siguiente acción registrados en la Issue. |
| Hechas | DoD completa y cambio integrado por humano. |

```text
Por hacer → Especificando → Ready → En curso → En revisión → Hechas
estado activo → Bloqueadas → estado operativo apropiado
Ready / En curso / En revisión → Especificando (replanificación justificada)
```

La autorización inicial para trabajar sobre una Issue incluye incorporación al
Project, asignación Por hacer si falta Status, referencias, evidencia, comentarios
y transiciones rutinarias no destructivas dentro del alcance. El agente elige
explícitamente destino y razón, comprueba sus condiciones y verifica el resultado;
no solicita un permiso nuevo por cada paso. Para desbloquear, registrar resolución
y acreditar el destino. Estados archivados/ambiguos, conflictos concurrentes o
transiciones excepcionales sin justificación detienen la escritura.

Esta autorización también permite coordinación técnica con otros agentes sobre
esa tarea mediante capacidades disponibles, respetando permisos del runtime y
restricciones de datos. No exige un humano como intermediario; no implica instalar
un framework, aprobar decisiones humanas ni comunicar con terceros ajenos al trabajo.

Las skills [gh-verifying-context](../.agents/skills/gh-verifying-context/SKILL.md),
[gh-issue-management](../.agents/skills/gh-issue-management/SKILL.md) y
[gh-project-management](../.agents/skills/gh-project-management/SKILL.md) mantienen:
verificar contexto → leer → cambio mínimo autorizado → escribir → releer →
comprobar resultado → informar. Descubrir IDs actuales, paginar y exigir permisos.
No borrar, archivar, cerrar ni modificar estructura/workflows; workflows automáticos
del Project desactivados. Autonomía no sustituye autorización ni DoR/DoD.

## Convivencia con planificación existente

No migrar ni rebajar retroactivamente Issues, Specs, ADRs o Planning PRs existentes.
Una tarea con Planning PR abierta conserva ese recorrido y sus compromisos; una
ya integrada conserva su plan revisado y sus referencias. Ready existente no se
revoca por este cambio. Si falta acreditar el antiguo gate, completar ese gate;
no usar la nueva vía para eludir revisión solicitada o cambios pendientes.
Una adaptación de un plan existente requiere decisión explícita del humano,
referencia a ambas versiones y evaluación de riesgo, sin alterar el alcance ni
aceptaciones anteriores. Nuevas tareas usan planificación proporcional.
Las specs antiguas permanecen en `entregas/<caso>/specs/`; no se presume que sus
referencias sean ADRs aceptados. Investigar antes de nueva implementación.

No se incorpora enforcement automático, CI adicional, protección de ramas ni
orquestación. Revisión de DoR/DoD y operaciones siguen explícitas, ejecutables por
agentes con evidencia y límites de autorización. Templates:
[Spec](templates/spec-template.md), [ADR](adr/template.md),
[Issue](../.github/ISSUE_TEMPLATE/work-item.md),
[PR](../.github/pull_request_template.md).
