## Tipo y resultado

- Tipo: Planning / Implementation / Documentación (elegir uno).
- Problema y comportamiento o documentación resultante:
- Alcance y límites:

## Referencias

- GitHub Issue:
- Spec(s):
- ADR decision y justificación en Spec:
- ADR(s) y estado (si no aplica: ADR: No requerido — justificado en Spec):
- Test/Eval Plan (sección de la Spec):
- Implementation Plan (sección de la Spec):
- Planning PR (para Implementation):

<!-- Planning: usar “Refs #N”; no cerrar la Issue antes de implementar.
     Implementation: usar “Closes #N” cuando se cubra todo su alcance.
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

- [ ] Issue existente y Planning PR distinta e integrada antes de implementar.
- [ ] Spec revisada y ADR decision resuelta; ADR aceptado y cobertura confirmada cuando aplique.
- [ ] Estrategia TDD/eval-first/híbrida realizada según Spec, con evidencia.
- [ ] Tests trazables mediante ruta de Spec e ID de AC.
- [ ] Todos los AC tienen evidencia de verificación final.

## Evidencia de verificación

<!-- Incluir comandos/pasos, entorno, resultados y logs relevantes.
     Implementation: evidencia Red (fallo esperado), Green y Refactor para TDD;
     baseline, gap, reevaluación y comparación para eval-first, según Spec.
     Documentación: revisión de contenido, enlaces y diff.
     No presentar checks no ejecutados como éxitos. -->

| AC (ruta de Spec + ID) o check documental | Test / comando / pasos | Resultado y evidencia |
|---|---|---|
| <referencia> | <verificación reproducible> | <resultado observado> |

## Pendientes y riesgos

<!-- Checks no ejecutados y motivo, limitaciones y riesgos concretos. -->
