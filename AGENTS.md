# Invariantes del repositorio

Estas reglas se aplican a personas y agentes en todo el repositorio.

## Antes de implementar

- La entrada oficial para planificar trabajo funcional nuevo es
  [plan-issue](.agents/skills/plan-issue/SKILL.md), desde una Issue existente.
  Cubre Por hacer → Especificando → Ready con planificación proporcional al
  riesgo, impacto, reversibilidad e incertidumbre; termina en Ready, sin implementar.
- Ningún código productivo se implementa sin una GitHub Issue que describa el trabajo.
- Toda implementación funcional requiere planificación accesible y DoR acreditada:
  alcance, AC, restricciones, Test/Eval Plan e Implementation Plan proporcionales.
  Pueden residir en la Issue o mini-spec. No exigir Spec independiente ni Planning
  PR por defecto; justificar el camino y fijar la versión del plan en la Issue.
- Decisión arquitectónica nueva/modificada, impacto crítico, reversión costosa o
  incertidumbre sustantiva que requiera revisión humana del diseño para acordar
  requisitos/contratos exigen Spec versionada Revisada y Planning PR aprobada e integrada por humano
  antes de implementar. Respetar también revisión previa expresamente solicitada.
  Preguntas de producto/alcance resolubles en la Issue no imponen una Planning
  PR por sí solas si no persiste otro disparador de revisión previa.
- Resolver exactamente una `ADR decision`: `NEW_ADR`, `REUSE_ADR` o
  `NO_ADR_REQUIRED`, con justificación. Una decisión fundamental, duradera o
  costosa de revertir exige ADR `Aceptado` antes de implementar. Un ADR aceptado
  reutilizado requiere cobertura acreditada, no una aprobación nueva por defecto.
  Sin revisión previa, la justificación de no requerir ADR se revisa en la PR de entrega.
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
  los requisitos de planificación, AC, planes ni verificación.
- El plan describe comportamiento, alcance, restricciones y AC verificables:
  entradas, resultado observable y condición de éxito. Cada AC tiene ID estable
  (`AC-001`, etc.); referencia completa: ruta de Spec o URL de Issue/comentario
  de planificación, más ID. Conservar IDs y trazabilidad al mover documentos.
- Planificación, ejecución y entrega son responsabilidades lógicas separadas.
  Solo el camino con revisión previa requiere Planning PR distinta de la
  Implementation PR. Preferir la Issue para tareas pequeñas si es suficiente.
  Una mini-spec en archivo que forme parte de la implementación debe integrarse
  en `main` mediante la Implementation PR; una rama temporal no acredita entrega.
- Si falta alguno de esos requisitos o existe una decisión relevante pendiente,
  el agente debe indicar qué falta y continuar únicamente con la planificación.

## Desarrollo y verificación

- El comportamiento determinista utiliza TDD: escribir un test que falle por el
  comportamiento ausente (Red), implementar lo mínimo para que pase (Green)
  y refactorizar manteniendo los tests en verde (Refactor).
- Para objetivos ML/probabilísticos/heurísticos que TDD unitario no representa,
  utilizar eval-first: Baseline → criterio/eval que demuestra el gap → cambio
  → reevaluación → comparación. Una tarea puede combinar ambas estrategias;
  el plan las justifica, sin tests rojos artificiales ni umbrales sin evidencia.
- Los tests deben poder trazarse hasta los AC mediante la referencia del plan y sus
  identificadores, en el Test Plan y en el nombre, comentario o documentación del
  test. Cada AC debe tener una verificación prevista y evidencia al terminar.
- Los agentes no pueden declarar trabajo terminado sin evidencia de verificación:
  comandos o pasos ejecutados, resultados y relación con los AC. Un check no
  ejecutado se registra como pendiente, con el motivo; nunca se presenta como éxito.
- Un agente no puede declarar una tarea terminada, cerrar su Issue ni marcarla
  como Done / Hechas mientras su Definition of Done no esté completamente
  satisfecha: tanto la DoD global del workflow/Issue como los requisitos
  específicos del plan. El plan puede ampliarla, nunca relajarla.
- Checks requeridos no ejecutados, fallos conocidos introducidos por el cambio
  o trabajo pendiente dentro del alcance impiden marcar la tarea como Done.
- Una invocación normal de plan-issue en Ready es no-op, sin escrituras.
  Solo una solicitud explícita, vigente y autorizada de replanificación con motivo concreto
  permite volver a Especificando, reutilizando el plan y conservando versiones,
  IDs de AC y decisiones anteriores. Reevaluar riesgo/DoR y revisión previa;
  no eludir aprobaciones ni cambiar alcance sin autorización humana.
- Si cambia el alcance o una decisión aceptada, actualizar y revisar la
  planificación y reevaluar riesgo/DoR antes de implementar la parte afectada.
  Exigir decisión humana para cambios de producto/alcance y Planning PR separada
  si corresponde revisión previa según el workflow. Ajustes técnicos internos
  que preservan AC, contratos y decisiones quedan a criterio del implementador;
  el Implementation Plan orienta, no prescribe todos los detalles.

## Git y revisión

- GitHub Issue es la unidad de trabajo; el GitHub Project v2 configurado en
  `.github/project-config.json` es la fuente de verdad del estado operacional.
  No sustituye al plan, el ADR ni la evidencia de verificación.
- Antes de operar sobre Issues o Projects, verificar el contexto con
  `.agents/skills/gh-verifying-context/SKILL.md`. Toda escritura requiere alcance
  autorizado, lectura previa, cambio mínimo, relectura y comprobación del resultado.
  No escribir con contexto ambiguo, permisos insuficientes o estados ausentes.
- La autorización inicial sobre una Issue incluye operaciones rutinarias no
  destructivas dentro del alcance: referencias/evidencia, incorporación al Project
  y transiciones justificadas con condiciones verificadas, sin permiso por paso.
  Permite coordinación técnica entre agentes mediante capacidades disponibles;
  no autoriza comunicación ajena al trabajo ni sustituye permisos del runtime.
  Crear Issues sigue requiriendo petición explícita. No cerrar, borrar, aprobar,
  mergear ni cambiar estructura/workflows por esta autorización.
- Los cambios de estado deben ser explícitos y respetar DoR y DoD. Mover a
  `Bloqueadas` exige registrar en la Issue motivo, impedimento y siguiente acción;
  salir del bloqueo exige documentar su resolución y acreditar el destino apropiado.
- `main` nunca recibe commits directos; todo entra mediante Pull Request desde
  una feature branch. Los agentes no fusionan ni aprueban sus propias PRs.
- La Implementation PR enlaza Issue, versión del plan y Test/Eval Plan, además
  de Planning PR y ADR aceptado cuando apliquen; justificar no aplicables.
  Aporta evidencia de TDD/eval y verificación final. La revisión y aprobación
  humana de la PR cubren también la planificación pertinente antes del merge.
- No subir secretos, credenciales ni datos privados. Respetar los cambios
  existentes y no incluir trabajo ajeno al alcance de la PR.

## Documentos existentes y cambios documentales

Las specs actuales permanecen en `entregas/<caso>/specs/`. No asumir ADRs
aceptados por referencias antiguas. Las tareas ya planificadas conservan su alcance,
decisiones, referencias y gates de revisión; no rebajarlos retroactivamente.
Una adaptación requiere decisión humana explícita y trazabilidad de versiones
según el workflow. Nuevas tareas usan planificación proporcional.

Los cambios exclusivamente documentales no son desarrollo
funcional: se verifican mediante revisión de contenido, enlaces y diff. Esta
distinción no permite introducir código productivo sin los requisitos anteriores.
Para su DoD, la PR documental cumple los requisitos de evidencia, revisión,
aprobación e integración; los requisitos funcionales no aplicables se justifican.

Consultar el [lifecycle](docs/workflow.md), el [template de Spec](docs/templates/spec-template.md)
y el [registro de ADRs](docs/adr/README.md).
