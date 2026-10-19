# Spec: Registrar como ADRs las decisiones estructurales previas del sistema

- GitHub Issue: https://github.com/lvckss/piia2-26/issues/37
- Estado: Borrador
- ADR decision: NEW_ADR
- ADR: [docs/adr/0002-contrato-json-entre-agentes.md](../../../docs/adr/0002-contrato-json-entre-agentes.md), [docs/adr/0003-proveedor-openai-clave-empresa.md](../../../docs/adr/0003-proveedor-openai-clave-empresa.md), [docs/adr/0004-herramienta-costes-datos-empresa.md](../../../docs/adr/0004-herramienta-costes-datos-empresa.md) y [docs/adr/0005-filtro-previo-detecciones-por-clase.md](../../../docs/adr/0005-filtro-previo-detecciones-por-clase.md) — los cuatro Propuestos.
- Justificación: el objeto de la Issue es registrar como ADR cuatro decisiones estructurales vigentes sin ADR (un contrato entre agentes, un proveedor externo, una dependencia estructural de datos y herramienta de terceros, y una estrategia de selección con coste). Son decisiones fundamentales y costosas de revertir, de las que dependen #28, #30 y #31; ningún ADR aceptado las cubre (`docs/adr/` solo tiene README y template en `main`). Cada ADR registra una decisión ya tomada; no se introduce ni se cambia ninguna.
- Plan vigente / versión: este archivo, en la rama `plan/37-adrs-decisiones-previas`; el commit exacto se registra en un comentario de la Issue.
- Riesgo y revisión previa: **sí** (disparador: NEW_ADR). Impacto medio-alto: los ADRs fijan decisiones que condicionan las Issues #28, #30 y #31, y el equipo decidió el 2026-10-19 que los ADRs se integran en `main` antes de implementar. Reversibilidad alta (documentos). Incertidumbre baja: las cuatro decisiones están escritas y medidas en el repo.
- Planning PR: pendiente de abrir; se enlaza aquí y en los ADRs al abrirla. La aprueba una persona distinta del autor (revisor acordado en el reparto: Lucas).

## Qué construir

Cuatro ADRs en `docs/adr/`, con el [template](../../../docs/adr/template.md) del repo, que registran decisiones estructurales ya vigentes:

| ADR | Decisión | Dónde está hoy |
|---|---|---|
| 0002 | Contrato JSON por imagen entre los agentes: todos los hallazgos con su nivel de confianza (Agente 1 → 2 y 3) y dos escenarios de coste con cobertura y normativa (Agente 2 → 3). | `specs/piia2-arquitectura-multiagente.md`, `ejemplos_contrato/`, `probar_agente1_stub.py` |
| 0003 | API de OpenAI con la clave de la empresa; clave en `OPENAI_API_KEY` y modelo en `OPENAI_MODEL`. | Arquitectura (decisiones), `agente1.py`, `vision.py`, `app/agentes/README.md` |
| 0004 | Costes con la herramienta y los datos de la empresa (`estimar_coste`, `valor_venal`, `polizas.csv`), sin precios propios. | Arquitectura v2, `agente2-costes-cobertura-guia.md`, paquete de la empresa |
| 0005 | Filtro previo por clase de las detecciones que van al modelo de visión. | `specs/agente-confianza-hallazgos.md`, `seleccion.py` |

Cada ADR recoge contexto y motivación, la decisión, las alternativas consideradas con su motivo de descarte, las consecuencias (incluidas las implicaciones para tests y AC) y referencias con rutas, fragmentos de código o comandos. Cubre así los mínimos de un ADR de la Entrega 2 (`evaluacion/entrega-2.md`: decisión, motivación, alternativas y referencias).

En esta Issue, el producto **son** los ADRs: se redactan en la Planning PR, una persona los acepta en esa misma PR (Propuesto → Aceptado, con quién, referencia y versión) y la integración en `main` los deja disponibles para #28, #30 y #31. No hay código.

## Por qué

El sistema se apoya en decisiones tomadas antes del workflow actual que no tienen ADR. `docs/adr/README.md` pide registrarlas antes de implementar cambios que dependan de ellas, y el equipo decidió el 2026-10-19 que los ADRs se integran en `main` antes de implementar: las Issues #30 y #31 no pueden pasar a Ready hasta que existan los ADRs del contrato (#30 y #31) y de la herramienta de costes (#30). Además, la Entrega 2 pide al menos dos ADRs.

## Alcance

- Incluido: los cuatro ADRs anteriores en estado Propuesto; su revisión y aceptación humana en la Planning PR; las referencias cruzadas con el ADR 0001 (#28) y con los planes de #30 y #31.
- Fuera de alcance: decisiones nuevas o cambios de las vigentes; el ADR 0001 de la #28 (tiene su propia Planning PR, #29); decisiones aún abiertas o asumidas sin confirmar en la arquitectura (framework Google ADK, #33; que el veredicto de visión no descarte nada; `vehiculo_id` como dato de entrada, que cambia la #28); copiar o enlazar los ADRs en `entregas/cu-19-interpretacion-danos/decisions/` para la Entrega 2, que corresponde a la #49; cambiar `docs/adr/README.md`, `AGENTS.md` o el workflow; código.

## Restricciones y supuestos

- Cada ADR distingue lo medido (con su comando o fuente) de lo supuesto, y no inventa alternativas: solo las que constan en el repo (primera versión de la arquitectura en `d890c20`, la propia spec de arquitectura, `agente-confianza-hallazgos.md`, el ADR 0001).
- Ningún ADR contiene claves ni valores secretos: solo nombres de variables de entorno.
- Los ADRs no modifican las specs existentes: las citan.
- Numeración: `0001` está ocupado por el ADR de la #28 (PR #29, sin integrar), así que estos usan `0002` a `0005`.

| Incertidumbre | Clasificación | Evidencia / supuesto / pregunta y efecto |
|---|---|---|
| ¿Dónde van los ADRs: `docs/adr/` (workflow) o `entregas/cu-19-interpretacion-danos/decisions/` (Entrega 2)? | Resuelta (decisión humana) | Víctor, en la sesión del 2026-10-19: registro canónico en `docs/adr/`, coherente con el workflow y con el ADR 0001; la copia o el enlace a `decisions/` para la Entrega 2 se hace en la #49. Hay que comunicarlo a quien lleve la #49 (Lucas); esta Issue no modifica la #49. |
| ¿Qué decisiones se registran? | Resuelta (decisión humana) | Víctor, en la sesión del 2026-10-19: las cuatro candidatas de la Issue. |
| El ADR del contrato (0002) lleva un número posterior al ADR 0001, que propone ampliar ese contrato. | Supuesto explícito aceptable, a confirmar en la revisión | El ADR 0001 ya prevé que, si hace falta un ADR del contrato completo, se renumere; aquí se evita renumerar: el 0002 registra el contrato base y cita el 0001 como ampliación propuesta. Si el revisor prefiere otra numeración, se cambia sin tocar el contenido. |
| La decisión del proveedor (0003) y la del paquete (0004) proceden de la reunión con la empresa; el único registro en el repo es la spec de arquitectura. | Supuesto explícito aceptable (límite declarado) | Los ADRs citan la arquitectura como fuente y lo declaran. |
| La cifra de MAPE 9,39 % (0004) procede de la revisión de la PR #40 y de `specs/30-costes-cobertura.md`, aún sin integrar. | Supuesto explícito aceptable | Se cita con su origen; si la #40 cambia la cifra, se actualiza el ADR antes de aceptarlo. |
| Fecha de la Entrega 2. | Pregunta no bloqueante | El repo dice lunes 16 de noviembre de 2026; no afecta a este plan. |

## Comportamiento que debe preservarse

- No hay código. Las decisiones que registran los ADRs deben coincidir con lo que hoy hace el repo y dicen las specs integradas: un ADR que contradiga el código o una spec integrada es un fallo (AC-003, AC-004).
- `docs/adr/README.md` y `docs/adr/template.md` no cambian.

## Failure modes y requisitos no funcionales

| Condición | Comportamiento esperado | Cobertura |
|---|---|---|
| Un ADR afirma algo que el código o los datos no hacen (cifra, campo, variable, valor). | Se detecta al contrastarlo con el repo; no se integra. | AC-003 |
| Un ADR contradice una spec integrada o el ADR 0001. | Se detecta en el cruce; no se integra. | AC-004 |
| Una alternativa inventada o sin motivo de descarte. | No se admite. | AC-002 |
| Un enlace roto (por ejemplo, a un archivo que solo existe en otra rama). | Se sustituye por la URL de la PR o se elimina. | AC-006 |
| Un secreto en un ADR. | No se admite. | AC-007 |
| Rendimiento u otros NFR. | No aplican: son documentos. | — |

## Acceptance Criteria

| ID | Dado / Cuando | Resultado esperado y condición de éxito |
|---|---|---|
| AC-001 | Los cuatro ADRs `docs/adr/0002-*.md` a `docs/adr/0005-*.md`. | Cada uno existe con nombre en kebab-case, sigue el template (metadatos: Estado, Fecha, GitHub Issue, Planes cubiertos, Planning PR, Aceptación, Sustituye; secciones: Contexto y motivación, Decisión, Alternativas consideradas, Consecuencias, Referencias y evidencia) y está en estado Propuesto en la Planning PR. |
| AC-002 | La tabla de alternativas de cada ADR. | Tiene la opción elegida y al menos otra con su motivo de descarte, y cada alternativa descartada tiene respaldo en el repo (archivo o commit citado). |
| AC-003 | Cada cifra, campo, variable, valor o ruta que cita un ADR. | Coincide con el repo en `main`: campos del hallazgo = `CAMPOS_FINDING` y `agente1_salida.json`; claves de la salida del Agente 2 = `agente2_salida.json`; `OPENAI_API_KEY`, `OPENAI_MODEL` y `crear_cliente_openai` = `agente1.py`; firma de `estimar_coste` = paquete de la empresa; `FILTRO_PREVIO` = `seleccion.py`; 18.507 → 3.712 y recall 97 / 94 / 100 % = `agente-confianza-hallazgos.md`. Lo que no está en `main` se cita con su origen. |
| AC-004 | Los ADRs leídos junto con `piia2-arquitectura-multiagente.md`, `agente-confianza-hallazgos.md` y el ADR 0001. | Ninguna contradicción; el 0002 cita el 0001 como ampliación propuesta y deja claro que, si se acepta, prevalece en el punto del coche. |
| AC-005 | La Planning PR aprobada e integrada. | Al menos 2 de los 4 ADRs (y en todo caso el 0002 y el 0004, de los que dependen #30 y #31) están en `main` en estado Aceptado, con quién los aceptó, la referencia de la revisión y la versión aceptada. |
| AC-006 | Los enlaces relativos de los ADRs y de esta spec. | Todos resuelven a archivos existentes en `main` en el commit integrado. |
| AC-007 | El texto de los ADRs. | No contiene claves, tokens ni valores secretos (solo nombres de variables de entorno). |
| AC-008 | El diff de la Planning PR. | Solo añade esta spec y los cuatro ADRs; no modifica ningún otro archivo. |

## Test Plan

Estrategia: **documental** (contenido, contraste con el repo, enlaces y diff). Según `docs/workflow.md`, TDD no aplica a un cambio exclusivamente documental; los scripts de prueba citados se ejecutan como evidencia, sin modificarlos.

### Test seams

- **S1 — Los ADRs:** contrato del template y de la Entrega 2.
- **S2 — El código, los ejemplos y los datos citados:** `ejemplos_contrato/`, `agente1.py`, `vision.py`, `seleccion.py`, `confianza.py`, `probar_*.py` y el paquete de la empresa en local.
- **S3 — Las specs integradas y el ADR 0001.**

| Referencia (ruta de Spec + AC) | Seam / contrato | Estrategia y nivel | Caso / resultado esperado | Datos / entorno | Comando o pasos previstos | Evidencia prevista |
|---|---|---|---|---|---|---|
| `specs/37-adrs-decisiones-previas.md#AC-001` | S1 | Documental | Secciones y metadatos del template en los 4 | `docs/adr/template.md` | `grep -n "^## \|^- Estado" docs/adr/000[2-5]-*.md` | Salida en la PR |
| `specs/37-adrs-decisiones-previas.md#AC-002` | S1, S3 | Documental | Cada alternativa con motivo y fuente | Arquitectura v1 (`d890c20`) y v2, `agente-confianza-hallazgos.md`, ADR 0001 | Lectura de cada tabla contra su fuente citada | Tabla de contraste en la PR |
| `specs/37-adrs-decisiones-previas.md#AC-003` | S1, S2 | Documental con ejecución de evidencia | Cifras, campos y valores = repo | `main`; paquete de la empresa en local | `python probar_agente1_stub.py`, `python probar_seleccion_stub.py` (desde `agente_multimodal/`), `git grep` de las variables y de `FILTRO_PREVIO`, y `valor_venal("V05", 3, 42000) == 17491.54` con el paquete | Salida de los comandos en la PR |
| `specs/37-adrs-decisiones-previas.md#AC-004` | S1, S3 | Documental | Sin contradicciones | Specs integradas y ADR 0001 (PR #29) | Lectura cruzada | Tabla de cruce en la PR |
| `specs/37-adrs-decisiones-previas.md#AC-005` | S1 | Revisión humana | ≥ 2 Aceptados (incluidos 0002 y 0004) con quién, referencia y versión | Revisión de la Planning PR | Leer la revisión y los metadatos de Aceptación desde `main` tras el merge | Registro en la Issue |
| `specs/37-adrs-decisiones-previas.md#AC-006` | S1 | Documental | Enlaces que resuelven | `main` | Script que resuelve los enlaces relativos con `git cat-file -e` | Salida en la PR |
| `specs/37-adrs-decisiones-previas.md#AC-007` | S1 | Documental | Sin secretos | — | `grep -n -iE "sk-[a-z0-9]{10,}\|api_key *= *['\"]" docs/adr/000[2-5]-*.md` sin resultados | Salida en la PR |
| `specs/37-adrs-decisiones-previas.md#AC-008` | S1 | Documental | Diff acotado | — | `git diff --stat origin/main...HEAD` | Salida en la PR |

## Implementation Plan

| Slice | Objetivo observable | AC relacionados | Componentes / contratos probablemente afectados | Dependencias | Verificación prevista |
|---|---|---|---|---|---|
| 1 — Redacción (en esta Planning PR) | Los cuatro ADRs Propuestos y verificados contra el repo. | AC-001 a AC-004, AC-006 a AC-008 | `docs/adr/0002` a `0005` (nuevos) | Ninguna | Filas AC-001 a AC-004 y AC-006 a AC-008 |
| 2 — Aceptación e integración (en esta Planning PR) | Revisión humana; metadatos de Aceptación completados por `plan-issue` con la evidencia; merge humano. | AC-005 | Metadatos de los ADRs y de esta spec | Slice 1; revisor | Fila AC-005 |
| 3 — Cierre | Comprobación de la DoD desde `main` y aviso a #30, #31 y #49 de que los ADRs están disponibles. | AC-005, AC-006 | Comentarios en esas Issues | Slice 2 | Registro en la Issue |

## Pendientes para Ready

- **Revisión previa (NEW_ADR):** Planning PR aprobada sobre el head final por una persona distinta del autor (revisor acordado: Lucas) e integrada por un humano; spec Revisada y ADRs Aceptados, con quién, el permalink y la versión registrados.
- **Confirmación en la revisión** de la numeración (0002 a 0005 con el 0001 de la #28 sin integrar) y de lo que queda fuera de alcance.

Resultado de analyze:

| Comprobación | Resultado |
|---|---|
| Cada requisito de la Issue tiene AC | Identificar decisiones vigentes y proponer un ADR por cada una → AC-001 a AC-004; revisión humana → AC-005; al menos dos ADRs aceptados → AC-005. La ubicación que pedía la Issue la resuelve la decisión humana (ver incertidumbres). |
| AC sin requisito en la Issue | AC-006 a AC-008 protegen enlaces, secretos y el alcance del diff; no amplían el trabajo. |
| Cada AC tiene verificación y slice | Sí (AC-001 a AC-008). |
| Comportamiento preservado | Coherencia con el código y las specs integradas (AC-003, AC-004); README y template sin cambios (AC-008). |
| ADR decision coherente | NEW_ADR: cuatro ADRs reales, sin decisiones ocultas ni inventadas. |
| Gaps | Ninguno bloqueante para la revisión. |

## Definition of Done

| Condición específica de cierre | Evidencia requerida |
|---|---|
| ADRs 0002 y 0004 Aceptados en `main` (los que necesitan #30 y #31), y al menos 2 en total. | Metadatos de Aceptación en `main` y enlace a la revisión. |
| #30, #31 y #49 avisadas de que los ADRs están en `main`. | Comentarios en esas Issues. |
