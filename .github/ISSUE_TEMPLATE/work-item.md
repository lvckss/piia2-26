---
name: Trabajo planificado
about: Definir un cambio y sus referencias de planificación y verificación
title: ''
labels: ''
assignees: ''
---

## Problema y objetivo

<!-- Qué ocurre, a quién afecta y qué resultado se busca. -->

## Alcance

- Incluido:
- Fuera de alcance:

## Resultado esperado

<!-- Condiciones observables; concretarlas con IDs de AC en la Spec. -->

## Planificación

<!-- Completar progresivamente. No comenzar código productivo con referencias pendientes. -->

- Spec:
- ADR decision (`NEW_ADR`, `REUSE_ADR` o `NO_ADR_REQUIRED`):
- ADR(s) y estado cuando aplique, o No requerido con justificación en Spec:
- Test/Eval Plan (sección de Spec):
- Implementation Plan (sección de Spec):
- Planning PR:

## Ready (comprobación manual)

- [ ] Spec revisada en `main` con AC verificables e identificadores estables.
- [ ] ADR decision resuelta y revisada, con referencia de revisión según el caso:
  `NEW_ADR`: ADR `Aceptado`;
  `REUSE_ADR`: ADR existente `Aceptado` y cobertura confirmada;
  `NO_ADR_REQUIRED`: justificación revisada y aceptada.
- [ ] Test/Eval Plan con casos, datos y verificación prevista para todos los AC.
- [ ] Implementation Plan con slices verificables que cubren todos los AC.
- [ ] Planning PR revisada e integrada, sin código productivo.
- [ ] Dependencias y preguntas que bloquean la implementación resueltas.

## Implementación y cierre

- Implementation PR (distinta de la Planning PR):
- Evidencia de TDD/eval según Spec y verificación de AC:

## Definition of Done

- [ ] Todos los Acceptance Criteria incluidos en el alcance están implementados.
- [ ] Cada Acceptance Criterion tiene tests o evidencia verificable trazable mediante `Spec path + AC ID`.
- [ ] Todos los tests y verificaciones requeridos se han ejecutado y están en verde.
- [ ] No existen regresiones conocidas introducidas por el cambio.
- [ ] La verificación final está documentada en la Implementation PR.
- [ ] La Implementation PR ha sido revisada y aprobada.
- [ ] La Implementation PR ha sido integrada en `main`.
- [ ] No quedan bloqueos ni pendientes pertenecientes al alcance definido de esta Issue.
- [ ] La documentación afectada por el cambio está actualizada.

<!-- Marcar cada punto con referencia a su evidencia en la PR, los tests o los
     documentos correspondientes. Cumplir también la DoD específica de las Specs
     enlazadas antes de cerrar la Issue o pasarla a Hechas.
     Para trabajo exclusivamente documental, Ready/TDD/implementación funcional
     pueden ser “no aplica” con motivo; usar la PR documental para verificación,
     revisión, aprobación e integración. Los checks documentales siguen siendo
     obligatorios. -->
