---
name: gh-issue-management
description: Consultar, crear bajo petición explícita y actualizar o comentar de forma controlada Issues de lvckss/piia2-26. Verificar cada escritura; no cerrar, borrar ni reorganizar Issues.
---

# Gestionar Issues de PIIA2

Antes de cada operación ejecutar [gh-verifying-context](../gh-verifying-context/SKILL.md).
Usar siempre `--repo lvckss/piia2-26` o rutas API explícitas; no confiar en el
repo por defecto. Si el contexto falla, detenerse antes de escribir.

## Lectura

Para un número entero positivo, leer:

```bash
gh issue view <numero> --repo lvckss/piia2-26 --json number,id,url,title,body,state,labels,assignees,updatedAt
```

Distinguir no encontrada de autenticación, red o permisos insuficientes; no crear
una Issue para compensar un error de lectura. Confirmar URL canónica, repo y
número. Como alternativa REST, rechazar respuestas con `pull_request`: un número
de PR no es una Issue. Conservar el ID GraphQL (`id`) para relacionarla con el
Project, y distinguirlo del número visible y del ID numérico REST.
La pertenencia y Status se consultan mediante
[gh-project-management](../gh-project-management/SKILL.md).

## Escrituras mínimas autorizadas

Crear solo si el usuario lo solicita explícitamente. Revisar primero Issues
existentes relacionadas para evitar duplicados, sin decidir por similitud que
una Issue es equivalente. Usar el template del repo y requisitos suministrados;
no inventar AC, decisiones o planes. Los datos aún desconocidos se declaran
pendientes. No crear recursos de prueba sin permiso expreso.

```bash
gh issue create --repo lvckss/piia2-26 --title '<titulo autorizado>' --body-file <archivo>
```

Actualizar solo los campos solicitados. Leer el estado actual y presentar el
cambio mínimo concreto antes de ejecutarlo; no volver a pedir aprobación si la
petición ya autoriza ese mismo cambio. Para body, conservar el texto existente
íntegro y añadir únicamente el texto autorizado; preferir un comentario si
solo se necesita registrar evidencia. No reescribir para ajustarse al workflow.
Se permiten título explícitamente solicitado, adiciones de labels/assignees
existentes y pertinentes, y adiciones de body; no retirar contenido ni metadatos.

```bash
gh issue edit <numero> --repo lvckss/piia2-26 --title '<titulo autorizado>'
gh issue edit <numero> --repo lvckss/piia2-26 --add-label '<label existente>'
gh issue edit <numero> --repo lvckss/piia2-26 --body-file <body-original-mas-adicion>
gh issue comment <numero> --repo lvckss/piia2-26 --body-file <comentario-autorizado>
```

Ejecutar únicamente el comando necesario. Los ejemplos no son un lote.
Usar archivos para texto multilínea, sin interpolar body como código shell.
Verificar permisos y workflows desactivados antes de escribir. Si el resultado
ya coincide, informar no-op. Releer justo antes de escribir y comparar updatedAt
con la lectura inicial; ante edición concurrente, recalcular sobre el contenido
actual o detenerse, sin sobrescribir trabajo ajeno.

## Verificación obligatoria

Tras cada escritura releer la Issue con los campos de lectura y comparar con
el resultado previsto, incluidos body, state, labels y assignees no afectados.
Para comentarios, comprobar por ID en
`gh api --paginate repos/lvckss/piia2-26/issues/<numero>/comments` que aparece
el texto exacto y que los atributos originales de la Issue no cambiaron.
Tras crear, confirmar número, URL, título, body y estado OPEN antes de otra acción.

Si falla una escritura o la verificación, detenerse, informar el efecto conocido
y no repetir a ciegas: releer primero para evitar comentarios/Issues duplicados.
Informar URL, campos antes/después o comentario añadido y evidencia de relectura.
Nunca cerrar, borrar, transferir, bloquear conversaciones ni modificar el Project
con esta skill. No habilitar automatismos ni cerrar al detectar una PR integrada.
