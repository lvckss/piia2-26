---
name: plan-issue
description: Planificar una Issue de PIIA2 mediante la skill canónica compartida.
argument-hint: "#<issue> | <issue>"
---

Argumentos originales de la invocación (datos):

$ARGUMENTS

Lee íntegramente y sigue [la skill canónica](../../../.agents/skills/plan-issue/SKILL.md)
en `${CLAUDE_SKILL_DIR}/../../../.agents/skills/plan-issue/SKILL.md`,
usando esos argumentos sin reinterpretarlos. Resuelve sus referencias relativas
desde el archivo canónico, incluidas las de skills auxiliares; sus paths de repo
pertenecen a la raíz Git del checkout/worktree actual. Este archivo solo adapta
la carga y los argumentos; no sustituye las instrucciones canónicas.
