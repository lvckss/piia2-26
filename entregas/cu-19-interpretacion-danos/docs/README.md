# Documentación de CU-19

La documentación del equipo se entrega dentro de la carpeta del caso:

- [Workflow de planificación, desarrollo y revisión](workflow.md).
- [Registro de decisiones arquitectónicas](adr/README.md), con los ADRs aceptados y su evidencia.
- [Template de ADR](adr/template.md) y [template de Spec](templates/spec-template.md).
- [Specs del proyecto](../specs/) y [documentación de la aplicación](../app/docs/README.md).

## Ubicaciones vigentes y referencias históricas

Lucas solicitó el 2026-11-02 que la documentación añadida por el equipo forme
parte de `entregas/cu-19-interpretacion-danos/`, porque la raíz corresponde al
repositorio de la asignatura. El [registro de esta reorganización](https://github.com/lvckss/piia2-26/issues/64#issuecomment-6576805544)
conserva sus antecedentes y el alcance documental.

| Ubicación anterior, desde la raíz del repo | Ubicación vigente, desde la raíz del repo |
|---|---|
| `docs/workflow.md` | `entregas/cu-19-interpretacion-danos/docs/workflow.md` |
| `docs/adr/` | `entregas/cu-19-interpretacion-danos/docs/adr/` |
| `docs/templates/` | `entregas/cu-19-interpretacion-danos/docs/templates/` |

Este es el único registro documental vigente del caso. Se trasladan los diez
documentos existentes y se añade este índice. Los nuevos ADRs se crean en
`docs/adr/` dentro del caso, con sus números y referencias de planificación.

Las decisiones, estados de aceptación, autores, revisiones e IDs de AC existentes
se conservan. Los enlaces fijados a commits históricos mantienen las rutas de
esos commits: acreditan lo revisado entonces. Las menciones a la ubicación
anterior en planes históricos, en particular la #37, se interpretan con este
mapa; la solicitud de Lucas actualiza la ubicación del registro, no las
decisiones técnicas ni sus requisitos de revisión. Los compromisos de entrega
de la #49 se mantienen y no se presentan como completados por el traslado.

Las rutas `docs/polizas_sinteticas/` y `docs/legal/` pertenecen al paquete de
datos de Plexus. Sus referencias y las fuentes de los informes se conservan;
no describen esta carpeta de documentación del equipo.

`AGENTS.md` y las skills siguen siendo puntos de entrada del repositorio y
enlazan estos documentos. El workflow enlaza una versión fijada de esas
herramientas y de las plantillas de GitHub en el fork del equipo, para que
sus referencias sigan disponibles al entregar solo la carpeta del caso.
Las reglas y sus requisitos no cambian por la reubicación.
