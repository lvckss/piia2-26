# Invariantes del repositorio

Estas reglas se aplican a personas y agentes en todo el repositorio.

## Antes de implementar

- La entrada oficial para planificar trabajo funcional nuevo es
  [piia2-plan-task](.agents/skills/piia2-plan-task/SKILL.md), desde una Issue existente.
  Cubre Por hacer → Especificando → Ready: registra aceptación humana explícita
  en la misma Planning PR y promueve a Ready solo después del merge humano,
  con Spec Revisada, ADR decision resuelta y revisada, y DoR completa
  verificados desde main.
  La invocación autoriza las operaciones no destructivas de planificación sobre
  esa Issue, incluidas referencias y promoción acreditada; no aprobar/mergear,
  cerrar, borrar contenido ni implementar. Su responsabilidad termina en Ready.
- Ningún código productivo se implementa sin una GitHub Issue que describa el trabajo.
- Toda implementación funcional requiere Issue, Spec `Revisada`, Test/Eval Plan,
  Implementation Plan y Planning PR revisada e integrada antes de comenzar.
- Durante planificación se resuelve explícitamente exactamente una `ADR decision`:
  `NEW_ADR`, `REUSE_ADR` o `NO_ADR_REQUIRED`, con justificación revisada por un humano.
  Toda decisión técnica/arquitectónica suficientemente fundamental, duradera o
  costosa de revertir debe estar cubierta por un ADR `Aceptado` antes de implementar.
- Para ADR, un contrato público relevante es una frontera estable consumida
  externamente o entre agentes/componentes que pueden evolucionar independientemente:
  API externa, contrato entre agentes, schema compartido, protocolo, formato
  persistente o interfaz estable usada fuera del componente. Un cambio pequeño
  en esas fronteras puede requerir ADR. Una función Python sin prefijo `_` o importada
  entre módulos del mismo componente no es tal frontera por ese mero hecho.
- Validaciones, excepciones/precondiciones, bugfixes, mejoras y algoritmos internos
  pueden ser `NO_ADR_REQUIRED` aunque cambie comportamiento observable local,
  si no introducen una decisión estructural. Una API interna con consecuencias
  estructurales, consumidores independientes o coste de reversión importante sí
  puede requerir ADR. Ante ambigüedad, investigar y usar clarify; no crear ADR
  por precaución ni ocultar una decisión arquitectónica real. Esto no reduce
  los requisitos de Spec, AC, planes ni verificación.
- La Spec debe describir el comportamiento, alcance, restricciones y Acceptance
  Criteria (AC) verificables: entradas, resultado observable y condición de éxito.
- Cada AC debe tener un identificador estable dentro de su Spec (`AC-001`, etc.).
  La referencia completa incluye la ruta de la Spec y el identificador.
- Las fases de planificación e implementación son PRs distintas. La Planning PR
  revisa Spec, decisión ADR, Test/Eval Plan e Implementation Plan, sin código
  productivo. Solo se comienza a implementar después de integrar esa PR y
  confirmar que el trabajo está Ready.
- Si falta alguno de esos requisitos o existe una decisión relevante pendiente,
  el agente debe indicar qué falta y continuar únicamente con la planificación.

## Desarrollo y verificación

- El comportamiento determinista utiliza TDD: escribir un test que falle por el
  comportamiento ausente (Red), implementar lo mínimo para que pase (Green)
  y refactorizar manteniendo los tests en verde (Refactor).
- Para objetivos ML/probabilísticos/heurísticos que TDD unitario no representa,
  utilizar eval-first: Baseline → criterio/eval que demuestra el gap → cambio
  → reevaluación → comparación. Una tarea puede combinar ambas estrategias;
  la Spec las justifica, sin tests rojos artificiales ni umbrales sin evidencia.
- Los tests deben poder trazarse hasta los AC mediante la ruta de la Spec y sus
  identificadores, en el Test Plan y en el nombre, comentario o documentación del
  test. Cada AC debe tener una verificación prevista y evidencia al terminar.
- Los agentes no pueden declarar trabajo terminado sin evidencia de verificación:
  comandos o pasos ejecutados, resultados y relación con los AC. Un check no
  ejecutado se registra como pendiente, con el motivo; nunca se presenta como éxito.
- Un agente no puede declarar una tarea terminada, cerrar su Issue ni marcarla
  como Done / Hechas mientras su Definition of Done no esté completamente
  satisfecha: tanto la DoD global del workflow/Issue como los requisitos
  específicos de las Specs. Las Specs pueden ampliarla, nunca relajarla.
- Checks requeridos no ejecutados, fallos conocidos introducidos por el cambio
  o trabajo pendiente dentro del alcance impiden marcar la tarea como Done.
- Si cambia el alcance o una decisión aceptada, actualizar y revisar la
  planificación en una PR separada antes de implementar el nuevo comportamiento.

## Git y revisión

- GitHub Issue es la unidad de trabajo; el GitHub Project v2 configurado en
  `.github/project-config.json` es la fuente de verdad del estado operacional.
  No sustituye a la Spec, el ADR ni la evidencia de verificación.
- Antes de operar sobre Issues o Projects, verificar el contexto con
  `.agents/skills/gh-verifying-context/SKILL.md`. Toda escritura requiere alcance
  autorizado, lectura previa, cambio mínimo, relectura y comprobación del resultado.
  No escribir con contexto ambiguo, permisos insuficientes o estados ausentes.
- Los cambios de estado deben ser explícitos y respetar DoR y DoD. Mover a
  `Bloqueadas` exige registrar en la Issue motivo, impedimento y siguiente acción;
  salir del bloqueo exige documentar su resolución y el estado operativo de destino.
- `main` nunca recibe commits directos; todo entra mediante Pull Request desde
  una feature branch. Los agentes no fusionan ni aprueban sus propias PRs.
- La Implementation PR enlaza Issue, Spec, Test/Eval Plan y Planning PR, además
  del ADR aceptado cuando aplique. En otro caso indica
  `ADR: No requerido — justificado en Spec`. Aporta evidencia de la estrategia
  TDD/eval prevista y de la verificación final.
- No subir secretos, credenciales ni datos privados. Respetar los cambios
  existentes y no incluir trabajo ajeno al alcance de la PR.

## Documentos existentes y cambios documentales

Las specs actuales permanecen en `entregas/<caso>/specs/`. No se presupone que
las decisiones descritas en ellas sean ADRs aceptados: antes de una nueva
implementación, completar sus referencias, AC y planes, y resolver/revisar la
decisión ADR según estas reglas. Referencias antiguas a un ADR obligatorio se
aplican únicamente cuando la decisión lo requiere; no inventar un ADR ni marcar
como aceptado un documento inexistente. Registrar el caso no aplicable y su
justificación en la Spec y en las referencias de planificación de la Issue.

Los cambios exclusivamente documentales no son desarrollo
funcional: se verifican mediante revisión de contenido, enlaces y diff. Esta
distinción no permite introducir código productivo sin los requisitos anteriores.
Para su DoD, la PR documental cumple los requisitos de evidencia, revisión,
aprobación e integración; los requisitos funcionales no aplicables se justifican.

Consultar el [lifecycle](docs/workflow.md), el [template de Spec](docs/templates/spec-template.md)
y el [registro de ADRs](docs/adr/README.md).
