# Invariantes del repositorio

Estas reglas se aplican a personas y agentes en todo el repositorio.

## Antes de implementar

- Ningún código productivo se implementa sin una GitHub Issue que describa el trabajo.
- Toda implementación debe estar cubierta por una Spec y por un ADR con estado
  `Aceptado`. Ambos documentos deben existir antes de comenzar la implementación.
- La Spec debe describir el comportamiento, alcance, restricciones y Acceptance
  Criteria (AC) verificables: entradas, resultado observable y condición de éxito.
- Cada AC debe tener un identificador estable dentro de su Spec (`AC-001`, etc.).
  La referencia completa incluye la ruta de la Spec y el identificador.
- Las fases de planificación e implementación son PRs distintas. La Planning PR
  revisa Spec, ADR y Test Plan, sin código productivo. Solo se comienza a
  implementar después de integrar esa PR y confirmar que el trabajo está Ready.
- Si falta la Issue, la Spec, el ADR aceptado o la planificación revisada,
  el agente debe indicar qué falta y continuar únicamente con la planificación.

## Desarrollo y verificación

- Todo desarrollo funcional utiliza TDD: escribir un test que falle por el
  comportamiento ausente (Red), implementar lo mínimo para que pase (Green)
  y refactorizar manteniendo los tests en verde (Refactor).
- Los tests deben poder trazarse hasta los AC mediante la ruta de la Spec y sus
  identificadores, en el Test Plan y en el nombre, comentario o documentación del
  test. Cada AC debe tener una verificación prevista y evidencia al terminar.
- Los agentes no pueden declarar trabajo terminado sin evidencia de verificación:
  comandos o pasos ejecutados, resultados y relación con los AC. Un check no
  ejecutado se registra como pendiente, con el motivo; nunca se presenta como éxito.
- Si cambia el alcance o una decisión aceptada, actualizar y revisar la
  planificación en una PR separada antes de implementar el nuevo comportamiento.

## Git y revisión

- `main` nunca recibe commits directos; todo entra mediante Pull Request desde
  una feature branch. Los agentes no fusionan ni aprueban sus propias PRs.
- La Implementation PR enlaza Issue, Spec, ADR aceptado, Test Plan y Planning PR,
  y aporta evidencia de TDD y de la verificación final.
- No subir secretos, credenciales ni datos privados. Respetar los cambios
  existentes y no incluir trabajo ajeno al alcance de la PR.

## Foundation y documentos existentes

Esta fase establece reglas y templates; su aplicación es manual. No incorpora
GitHub Projects, skills externas, GitHub Actions, automatización TDD, scripts de
trazabilidad ni branch protection.

Las specs actuales permanecen en `entregas/<caso>/specs/`. No se presupone que
las decisiones descritas en ellas sean ADRs aceptados: antes de una nueva
implementación, completar sus referencias y AC, y registrar o enlazar un ADR
aceptado. No se exige migrar retroactivamente el código existente en esta foundation.

Los cambios exclusivamente documentales, como esta foundation, no son desarrollo
funcional: se verifican mediante revisión de contenido, enlaces y diff. Esta
distinción no permite introducir código productivo sin los requisitos anteriores.

Consultar el [lifecycle](docs/workflow.md), el [template de Spec](docs/templates/spec-template.md)
y el [registro de ADRs](docs/adr/README.md).
