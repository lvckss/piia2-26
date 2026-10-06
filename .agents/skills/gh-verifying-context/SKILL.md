---
name: gh-verifying-context
description: Verificar en solo lectura el repositorio PIIA2, autenticación, Issues y el Project v2 configurado antes de consultar o modificar sus recursos. Detenerse ante cualquier discrepancia sin corregirla.
---

# Verificar contexto de PIIA2

Esta skill es read-only. Leer `.github/project-config.json` desde la raíz Git;
no crear configuración, cambiar autenticación, habilitar Issues ni modificar
Issues, Projects o sus workflows. Ejecutarla antes de cada operación de los
otros gestores; una comprobación antigua no autoriza una escritura nueva.

## Comprobaciones

1. Localizar raíz con `git rev-parse --show-toplevel`. Comprobar que existe
   la configuración, es JSON válido y contiene repository owner/name, project
   owner/owner_type/number, status_field y statuses. Repository debe ser
   exactamente `lvckss/piia2-26`, campo `Status` y estados exactamente:
   `Por hacer`, `Especificando`, `Ready`, `En curso`, `En revisión`,
   `Bloqueadas`, `Hechas`, sin duplicados. No aceptar una config que cambie el repo.
2. `command -v gh` y `gh auth status` deben funcionar. No imprimir tokens.
   Leer `git remote get-url origin` y `git remote get-url --push origin`;
   normalizar únicamente SSH/HTTPS de github.com, sufijo `.git` y barra final.
   Ambos deben identificar `lvckss/piia2-26`. Comprobar también
   `gh repo view --json nameWithOwner` sin `--repo`: si el contexto implícito
   apunta a otro repo (por ejemplo, upstream o GH_REPO), detenerse.
3. `gh api repos/lvckss/piia2-26` debe devolver ese `full_name` y
   `has_issues: true`. No exigir que el usuario autenticado sea el owner:
   colaboradores con permisos también son válidos.
4. Leer `gh project view <number> --owner <project-owner> --format json`.
   Comparar owner y number con config y exigir `closed: false`.
   Descubrir el ID del Project; nunca usar un ID guardado de otra sesión.
   `owner_type` debe coincidir con User/Organization devuelto por GitHub.
   Confirmar mediante GraphQL su asociación al repo, `viewerCanUpdate` y
   los workflows. Elegir raíz `user` u `organization` según owner_type:

   ```graphql
   query($owner:String!, $number:Int!) {
     user(login:$owner) {
       projectV2(number:$number) {
         id number owner { ... on User { login } ... on Organization { login } }
         closed viewerCanUpdate
         repositories(first:100) { nodes { nameWithOwner } pageInfo { hasNextPage endCursor } }
         workflows(first:100) { nodes { name enabled } pageInfo { hasNextPage endCursor } }
       }
     }
   }
   ```

   Usar `gh api graphql -f query='<consulta>' -f owner='<owner>' -F number=<n>`.
   Para Organization reemplazar solo `user` por `organization`. Paginar cada
   conexión si hasNextPage; no considerar una respuesta truncada prueba de ausencia.
   Errores GraphQL, null, repo no asociado o identidad contradictoria son fallo.
5. Leer `gh project field-list <number> --owner <owner> --format json --limit 100`.
   Comparar longitud de fields con totalCount; si está truncado, paginar fields
   por GraphQL hasta el final. Debe existir un único campo `Status`, tipo
   `ProjectV2SingleSelectField`, con exactamente los siete nombres de config,
   sin opciones extra ni repetidas. Resolver ID de campo y opción por nombre.

## Resultado y límites

Informar repo, Project (owner/number/URL), campo y estados encontrados, cuenta
activa y capacidad de escritura. No inventar un resultado ante falta de red.
Si falla una comprobación, detener la operación e indicar esperado, observado
(o error exacto) y qué debe resolver el usuario. No intentar arreglarlo.

Lecturas son posibles con permiso read:project. Para cualquier escritura exigir
permisos de la operación: `permissions.push` o `triage` en el repo para editar
metadatos ajenos y `viewerCanUpdate: true` en el Project para añadir/mover items;
crear/comentar requiere capacidad de participación en Issues. El scope OAuth
`project` permite escribir Projects; un fine-grained token debe tener su permiso
correspondiente. No refrescar permisos desde esta skill.

Devolver también workflows activos. Los gestores deben rechazar escrituras
si alguno está habilitado: podrían cerrar Issues o cambiar estados indirectamente.
Un resultado read-only correcto no implica autorización para mutaciones.
