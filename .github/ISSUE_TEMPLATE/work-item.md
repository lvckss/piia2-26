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

<!-- Condiciones observables; concretarlas aquí o en el plan enlazado con IDs estables AC-001, etc.
     Cada AC expresa precondición/entrada, acción, resultado y éxito verificable. -->

## Planificación

<!-- Completar progresivamente; no comenzar producto sin DoR acreditada.
     Issue/mini-spec basta si el riesgo lo permite. No llenar secciones artificiales;
     no aplica requiere motivo. Referenciar versiones, no depender del chat. -->

- Plan vigente y versión (aquí/comentario con permalink o Spec + commit):
- Riesgo (impacto, reversibilidad, seguridad, incertidumbre) y justificación:
- Revisión humana previa necesaria: sí/no y motivo:
- Restricciones, contratos/invariantes y comportamiento preservado:
- Failure modes/NFRs relevantes y protección prevista:
- ADR decision (`NEW_ADR`, `REUSE_ADR` o `NO_ADR_REQUIRED`) y justificación:
- ADR y cobertura cuando aplique, o No requerido:
- Test/Eval Plan (por AC: caso, frontera, estrategia TDD/eval, datos, pasos y evidencia):
- Implementation Plan (orientación, dependencias y verificaciones; puede ser breve):
- Planning PR (solo si corresponde revisión previa):
- Clarify/analyze, decisiones humanas necesarias y pendientes:
- DoD específica adicional (si aplica):

## Ready (comprobación manual)

- [ ] Issue abierta, autorizada y en el Project configurado.
- [ ] Plan accesible y versión fijada, riesgo/camino justificados, AC verificables con IDs estables.
- [ ] Restricciones, preservación y failure modes/NFRs relevantes protegidos.
- [ ] ADR decision resuelta: NEW_ADR con ADR Aceptado en main; REUSE_ADR con ADR Aceptado en main y cobertura acreditada; NO_ADR_REQUIRED justificado.
- [ ] Test/Eval Plan cubre todos los AC y regresiones; estrategia y evidencia previstas.
- [ ] Implementation Plan proporcional suficiente para ejecutar/reanudar y cubre todos los AC.
- [ ] Si requiere revisión previa: Spec Revisada, planes y ADR decision aceptados; Planning PR aprobada e integrada por humano, comprobados desde main. Si no, indicar no aplica y motivo.
- [ ] Clarify/analyze sin gaps bloqueantes; decisiones humanas necesarias referenciadas; sin impedimentos ni bloqueo vigente.

## Implementación y cierre

- PR de entrega (distinta de Planning PR cuando esta sea necesaria):
- Evidencia de TDD/eval según plan y verificación de AC:

## Definition of Done

- [ ] Todos los Acceptance Criteria incluidos en el alcance están implementados.
- [ ] Cada Acceptance Criterion tiene tests o evidencia verificable trazable mediante `ruta de Spec o URL del plan en Issue + AC ID`.
- [ ] Todos los tests y verificaciones requeridos se han ejecutado y están en verde.
- [ ] No existen regresiones conocidas introducidas por el cambio.
- [ ] La verificación final está documentada en la PR de entrega.
- [ ] La PR de entrega ha sido revisada y aprobada.
- [ ] La PR de entrega ha sido integrada en `main`.
- [ ] No quedan bloqueos ni pendientes pertenecientes al alcance definido de esta Issue.
- [ ] La documentación afectada por el cambio está actualizada.

<!-- Marcar cada punto con referencia a su evidencia en la PR, los tests o los
     documentos correspondientes. Cumplir también la DoD específica del plan
     vigente antes de cerrar la Issue o pasarla a Hechas.
     Para trabajo exclusivamente documental, Ready/TDD/implementación funcional
     pueden ser “no aplica” con motivo; usar la PR documental para verificación,
     revisión, aprobación e integración. Los checks documentales siguen siendo
     obligatorios. -->
