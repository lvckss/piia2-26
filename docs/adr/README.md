# Registro de decisiones (ADRs)

Las nuevas decisiones que cubren implementaciones se registran aquí. Copiar el
[template](template.md) a `NNNN-nombre-kebab-case.md`, con un número de cuatro
dígitos no utilizado (empezando por `0001`). Enlazar la Issue y las Specs cubiertas.
El template y este README no son decisiones aceptadas.

Estados:

- **Propuesto**: pendiente de revisión; no habilita implementación.
- **Aceptado**: decisión aprobada por un revisor en la Planning PR; registrar
  quién la aceptó y la referencia de revisión antes de integrar la planificación.
- **Rechazado**: propuesta descartada, conservada con el motivo.
- **Sustituido**: reemplazado por otro ADR aceptado, enlazando ambos documentos.

No reescribir silenciosamente una decisión aceptada: si cambia, proponer otro
ADR en una Planning PR y conservar el historial. Una implementación puede
reutilizar un ADR aceptado si cubre explícitamente su alcance y restricciones;
no basta con que exista cualquier ADR en el repositorio.

El ejemplo docente en `entregas/cu00-ejemplo/decisions/` se conserva en su
ubicación. Las decisiones de las specs antiguas deben revisarse y registrarse
como ADRs antes de implementar nuevos cambios que dependan de ellas.

Ver el [lifecycle](../workflow.md) para la revisión y el paso a Ready.
