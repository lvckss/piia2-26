## Tipo y resultado

- Tipo: Planning / Implementation / Documentación (elegir uno).
- Problema y comportamiento o documentación resultante:
- Alcance y límites:

## Referencias

- GitHub Issue:
- Plan vigente y versión (Issue/comentario o Spec):
- Riesgo y revisión previa (sí/no y motivo):
- ADR decision y justificación en el plan:
- ADR(s) y estado (si no aplica: ADR: No requerido — justificado en el plan):
- Test/Eval Plan (Issue/mini-spec/Spec):
- Implementation Plan (Issue/mini-spec/Spec):
- Planning PR (si corresponde; en otro caso no aplica y motivo):

<!-- Planning: usar “Refs #N”; no cerrar la Issue antes de implementar.
     Implementation con implement-issue: usar “Refs #N”; el cierre queda para
     la entrega final con DoD completa, sin cierre automático de esta skill.
     Documentación: indicar “no aplica” y motivo donde corresponda. -->

## Checklist de Planning

<!-- Completar si es Planning; en los otros tipos indicar “no aplica”. -->

- [ ] Contiene Spec y planes; ADR cuando aplique; no introduce código productivo.
- [ ] AC verificables con IDs estables; Test/Eval Plan e Implementation Plan cubren todos los AC.
- [ ] Comportamiento preservado y failure modes/NFRs relevantes tratados; clarify/analyze sin gaps bloqueantes.
- [ ] Spec revisada por humano; aceptación, autor y versión registrados.
- [ ] ADR decision revisada: NEW_ADR aceptado; REUSE_ADR con cobertura confirmada; NO_ADR_REQUIRED con justificación aceptada.
- [ ] Pendientes que bloquean Ready resueltos.

## Checklist de Implementation

<!-- Completar si es Implementation; en los otros tipos indicar “no aplica”. -->

- [ ] Issue existente y DoR del camino elegido acreditada antes de implementar.
- [ ] Plan accesible/versionado y ADR decision resuelta; si hay revisión previa, Spec Revisada y Planning PR distinta aprobada/integrada; ADR aceptado y cobertura acreditada cuando aplique.
- [ ] Estrategia TDD/eval-first/híbrida realizada según plan, con evidencia.
- [ ] Tests trazables mediante ruta de Spec o URL del plan en Issue e ID de AC.
- [ ] Todos los AC tienen evidencia de verificación final.
- [ ] Ajustes técnicos dentro del acuerdo documentados; cambios de alcance/AC/decisiones reevaluados y aceptados según workflow.
- [ ] Planificación pertinente incluida en la revisión humana de esta PR.

## Evidencia de verificación

<!-- Incluir comandos/pasos, entorno, resultados y logs relevantes.
     Implementation: evidencia Red (fallo esperado), Green y Refactor para TDD;
     baseline, gap, reevaluación y comparación para eval-first, según plan.
     Documentación: revisión de contenido, enlaces y diff.
     No presentar checks no ejecutados como éxitos. -->

| AC (ruta de Spec o URL del plan + ID) o check documental | Test / comando / pasos | Resultado y evidencia |
|---|---|---|
| <referencia> | <verificación reproducible> | <resultado observado> |

## Pendientes y riesgos

<!-- Checks no ejecutados y motivo, limitaciones y riesgos concretos. -->
