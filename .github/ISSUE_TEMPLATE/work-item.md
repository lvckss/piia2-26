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
- ADR(s) y estado:
- Test Plan (sección de Spec o documento versionado):
- Planning PR:

## Ready (comprobación manual)

- [ ] Spec revisada con AC verificables e identificadores estables.
- [ ] ADR aceptado que cubre la implementación, con referencia de revisión.
- [ ] Test Plan con casos, datos y verificación prevista para todos los AC.
- [ ] Planning PR integrada, sin código productivo.
- [ ] Dependencias y preguntas que bloquean la implementación resueltas.

## Implementación y cierre

- Implementation PR (distinta de la Planning PR):
- Evidencia de TDD y verificación de AC:

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
