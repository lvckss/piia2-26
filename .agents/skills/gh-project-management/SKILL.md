---
name: gh-project-management
description: Consultar campos, pertenencia y Status de Issues en el Project v2 configurado para PIIA2; añadir Issues y ejecutar cambios de estado explícitos con verificación posterior, sin automatismos ni borrados.
---

# Gestionar el Project v2 de PIIA2

Ejecutar [gh-verifying-context](../gh-verifying-context/SKILL.md) antes de cada
operación. Leer owner/number de `.github/project-config.json`; localizar Project,
campo Status y opciones dinámicamente. No crear Projects/campos/opciones ni
cambiar su estructura desde esta skill. Para escribir exigir permiso project,
viewerCanUpdate y ningún workflow automático habilitado.

## Localizar Issue, item y estado (solo lectura)

Leer la Issue con [gh-issue-management](../gh-issue-management/SKILL.md).
Debe ser una Issue real de `lvckss/piia2-26`, no PR ni borrador.
Los IDs de Issue, Project, campo, opción e item son distintos; no intercambiarlos.

Enumerar todos los items, incluidos archivados, hasta agotar la conexión:

```graphql
query($project:ID!, $endCursor:String) {
  node(id:$project) {
    ... on ProjectV2 {
      id
      items(first:100, after:$endCursor, archivedStates:[ARCHIVED, NOT_ARCHIVED]) {
        nodes {
          id isArchived
          content { ... on Issue { id number url repository { nameWithOwner } } }
          fieldValueByName(name:"Status") {
            ... on ProjectV2ItemFieldSingleSelectValue { optionId name field { ... on ProjectV2SingleSelectField { id name } } }
          }
        }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}
```

Ejecutar `gh api graphql --paginate -f query='<consulta>' -f project='<ID descubierto>'`;
inspeccionar todas las páginas y errores. Comparar content.id con el ID de la
Issue, y confirmar URL y repo. Cero coincidencias tras paginación completa significa
no incluida; una permite leer Status (null significa sin asignar); varias son
ambiguas y bloquean escrituras. Un item archivado requiere intervención explícita:
no desarchivar ni añadir un duplicado. No inferir ausencia de un listado parcial.

## Añadir una Issue

Solo con autorización sobre la Issue (petición inicial o invocación de su ciclo),
después de comprobar que no pertenece al Project:

```bash
gh project item-add <numero-project> --owner <owner> --url <url-canonica-issue> --format json
```

Si ya pertenece, no-op. Reenumerar tras añadir y verificar una sola coincidencia,
identidad del item y Status actual, sin cambiar campos ni Issue. Añadir no decide
un estado: si queda sin Status, informarlo; asignar `Por hacer` también exige
destino elegido explícitamente y verificación independiente; la autorización
inicial sobre la Issue basta para esta operación rutinaria.

## Cambiar Status

Requerir número de Issue, destino exacto de config y autorización sobre esa tarea.
La petición inicial de trabajar sobre la Issue o la invocación de una skill de
su ciclo autoriza operaciones rutinarias no destructivas dentro del alcance,
incluidos añadir/asignar estado, bloqueo y desbloqueo acreditados; no pedir
confirmación por paso. Registrar destino y justificación concretos. Una consulta
read-only no autoriza escritura; respetar límites adicionales del usuario.
[plan-issue](../plan-issue/SKILL.md), [implement-issue](../implement-issue/SKILL.md),
[finish-issue](../finish-issue/SKILL.md) o el agente autorizado aplicando el workflow acreditan
las condiciones y el momento;
esta skill no decide por commits, PRs o eventos ni implementa validadores de DoR/DoD.
Exigir referencias del plan y su versión que acrediten DoR del camino elegido
para `Ready` y DoD para `Hechas`;
si faltan, negarse a mover. No cerrar la Issue al mover a `Hechas`.

Transiciones normales:
`Por hacer → Especificando → Ready → En curso → En revisión → Hechas`.
Cualquier estado salvo `Bloqueadas`/`Hechas` puede pasar a `Bloqueadas`.
Ready / En curso / En revisión → Especificando permite replanificación registrada
si cambia el acuerdo o aparece riesgo que exige revisión previa; detener ejecución
afectada y reevaluar DoR. Otras transiciones requieren petición y justificación
explícitas, sin saltarse DoR/DoD. Para un item nuevo sin Status, permitir un
destino explícito justificado.
Si origen y destino coinciden, no-op; no emitir una mutación innecesaria.

### Bloqueo y desbloqueo

Antes de cualquier escritura hacia `Bloqueadas`, exigir los tres valores concretos:

- motivo del bloqueo;
- dependencia o impedimento;
- siguiente acción prevista.

No bastan textos vacíos, placeholders o “bloqueado”. Si falta alguno, negarse
sin publicar comentario ni cambiar estado. Con los tres datos y autorización,
registrarlos mediante comentario en la Issue usando gh-issue-management (o
referenciar un registro existente que contenga los tres), releer y verificar ese
registro, y solo entonces mover. Informar su URL junto con el cambio de Status.
Si el movimiento falla, conservar el registro y comunicar el estado observado.
Para salir de `Bloqueadas`, requerir evidencia de resolución registrada en la
Issue y destino operativo elegido y justificado, apropiado al trabajo realmente completado.
No probar el bloqueo de una tarea real solo para demostrar la skill.

### Mutación y comprobación

Releer item y campos inmediatamente antes de escribir. Si cambiaron el origen,
la pertenencia o las opciones respecto a lo revisado, detenerse y reevaluar;
no sobrescribir silenciosamente un movimiento concurrente. Capturar los otros
valores del item (`fieldValues`, paginados) y los atributos de la Issue para
comprobar que la escritura afecta únicamente Status.

```bash
gh project item-edit --id <item-id> --project-id <project-id> --field-id <status-field-id> --single-select-option-id <destino-option-id>
```

Resolver todos los IDs en lecturas actuales y comprobar su relación con el
Project configurado. Releer el item vía GraphQL después del comando; comparar
optionId y nombre exacto con destino, pertenencia e identidad con origen y los
otros valores/atributos con la lectura previa. La salida del comando de escritura
no sustituye a esta relectura. Si falla o hay discrepancia, detenerse y no repetir
ni revertir a ciegas. Informar Issue/Project, Status anterior y final, evidencia
y cualquier efecto parcial. GitHub no ofrece una escritura condicional por
Status: ante concurrencia detectada después de escribir, informar el conflicto.

Nunca borrar/archivar Projects o items, campos, opciones, Issues o contenido;
no cerrar Issues, cambiar workflows ni usar scraping. No reparar un contexto
inválido ni añadir recursos de prueba sin autorización expresa.
