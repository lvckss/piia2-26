# Spec: <nombre de la funcionalidad>

<!-- Copiar a entregas/<caso>/specs/<issue>-<slug-kebab-case>.md.
     Sustituir placeholders y eliminar instrucciones antes de revisión.
     Para mini-spec, conservar solo secciones pertinentes y las garantías comunes
     del workflow; también puede residir en la Issue. No exigir documento aparte.
     Este template completo se usa para el camino con revisión previa. -->

- GitHub Issue: <URL>
- Estado: Borrador / Revisada (elegir uno)
- ADR decision: NEW_ADR | REUSE_ADR | NO_ADR_REQUIRED (elegir uno)
- ADR: <ruta y estado | No requerido>
- Justificación: <decisión relevante nueva; cobertura concreta del ADR aceptado reutilizado; o por qué no hay decisión relevante>
- Plan vigente / versión: <permalink o archivo + commit>
- Riesgo y revisión previa: <impacto, reversibilidad, incertidumbre; sí/no y motivo>
- Planning PR: <URL cuando corresponda; no aplica con motivo en otro caso>

<!-- No dejar la decisión ADR ambigua. NEW_ADR: Propuesto hasta aceptación humana.
     REUSE_ADR: ya Aceptado, cobertura acreditada; humano confirma si hay
     revisión previa. No reescribirlo.
     NO_ADR_REQUIRED: justificación revisada en PR de entrega o Planning PR; nunca ocultar una decisión
     relevante, aunque el cambio sea pequeño. Borrador no impide Ready si no
     se exige revisión previa y DoR está acreditada. Al pasar a Revisada registrar quién,
     permalink y versión de la aceptación humana del plan y de la decisión ADR. -->

## Qué construir

<Comportamiento esperado, entradas y salidas, y dónde encaja en el sistema.>

## Por qué

<Problema, usuarios afectados y resultado que se persigue.>

## Alcance

- Incluido: <comportamientos cubiertos por esta Spec>
- Fuera de alcance: <límites explícitos>

## Restricciones y supuestos

<Validaciones, casos límite, errores, dependencias, compatibilidad y rendimiento.
Para IA: datos/partición, protocolo, métricas y umbrales verificables.>

<!-- Clarify antes de cerrar la Spec: distinguir hechos, decisiones y supuestos;
     resolver con evidencia del repo antes de preguntar al usuario. No inventar
     métricas/thresholds. Una pregunta que impide AC verificables es bloqueante. -->

| Incertidumbre | Clasificación | Evidencia / supuesto / pregunta y efecto |
|---|---|---|
| <ambigüedad, decisión ausente o contradicción> | <resuelta con evidencia / supuesto explícito aceptable / pregunta no bloqueante / pregunta bloqueante> | <referencia o decisión pendiente> |

## Comportamiento que debe preservarse

<Contratos y comportamiento observable existentes, invariantes, compatibilidad,
formatos/esquemas y regresiones críticas. Enlazar su protección mediante AC y
verificaciones previstas; si no existe comportamiento previo relevante, indicarlo.>

## Failure modes y requisitos no funcionales

<Solo los relevantes y dentro del alcance: entradas inválidas/parciales, fallos
externos, timeout, resultado ausente, recuperación; latencia, memoria, determinismo,
compatibilidad, seguridad u observabilidad. Indicar condición objetiva, evidencia
de umbrales y AC/verificación que lo cubre. No inventar NFRs para llenar la sección;
si no aplican, justificar brevemente.>

## Acceptance Criteria

<!-- Un resultado observable por fila. Mantener los IDs estables; no renumerar
     ni reutilizar un ID retirado. Evitar criterios como “funciona bien”. -->

| ID | Dado / Cuando | Resultado esperado y condición de éxito |
|---|---|---|
| AC-001 | <entrada o precondición y acción> | <resultado observable, umbral o tolerancia> |
| AC-002 | <entrada inválida o caso límite y acción> | <error o comportamiento verificable> |

## Test Plan

<!-- Test/Eval Plan obligatorio dentro de esta Spec. Cubrir todos los AC y
     proteger comportamiento preservado/failure modes relevantes. Identificar
     seams observables y su contrato, evitando acoplar tests a internals.
     Determinista: Red → Green → Refactor.
     ML/probabilístico/heurístico cuando TDD unitario no represente el objetivo:
     Baseline → criterio/eval que demuestra el gap → cambio → reevaluación → comparación.
     Puede ser híbrido; justificar estrategia por comportamiento. No escribir
     tests/fixtures ahora ni fingir un rojo artificial para una métrica ML. -->

| Referencia (ruta de Spec o URL del plan + AC) | Seam / contrato | Estrategia y nivel | Caso / resultado esperado | Datos / entorno | Comando o pasos previstos | Evidencia prevista |
|---|---|---|---|---|---|---|
| <ruta de esta Spec>#AC-001 | <frontera observable> | <TDD / eval-first; unitario/integración/contrato/evaluación> | <caso y éxito objetivo> | <fixture o dataset, versión/split/baseline> | <pasos reproducibles> | <resultado/informe> |

## Implementation Plan

<!-- Orientación proporcional y ajustable por el implementador dentro de AC,
     contratos y decisiones. No requiere nueva revisión por ajustes internos.
     Vertical slices pequeñas con resultado observable y verificable; no código,
     pseudocódigo detallado ni prediseño de internals. Cubrir todos los AC.
     Si mezcla objetivos independientes o demasiadas slices para un plan coherente,
     recomendar dividir la Issue; no crear child Issues automáticamente. -->

| Slice | Objetivo observable | AC relacionados | Componentes / contratos probablemente afectados | Dependencias | Verificación prevista |
|---|---|---|---|---|---|
| <1 — resultado> | <comportamiento incremental> | <AC-001> | <fronteras conocidas> | <requisitos previos> | <fila del Test/Eval Plan> |

## Pendientes para Ready

<Preguntas y dependencias que bloquean implementación. Resolverlas en la
Issue o Planning PR según el camino; “ninguno” solo cuando se hayan resuelto.
Registrar también resultado
de analyze: consistencia Issue/alcance/AC/ADR decision/planes, protección del
comportamiento existente y failure modes; gaps, resolución y evidencia. No declarar
lista para revisión completa con contradicciones o gaps bloqueantes; puede ser draft.>

## Definition of Done

La DoD global está definida por el workflow y la checklist de la Issue enlazada.
Esta sección añade condiciones verificables de esta funcionalidad; nunca puede
relajar ni sustituir la DoD global. Todos los AC de esta Spec deben estar
verificados con evidencia trazable mediante `ruta de Spec o URL del plan en Issue + AC ID`.

<!-- Completar solo los requisitos específicos aplicables, con condición de éxito
     y evidencia prevista. Si no hay requisitos adicionales, indicarlo.
     Ejemplos: métricas mínimas y tolerancias; datasets, particiones y versiones
     concretos; artefactos u outputs generados y su ubicación; documentación
     específica actualizada. No duplicar la checklist global de la Issue. -->

| Condición específica de cierre | Evidencia requerida |
|---|---|
| <resultado verificable o umbral específico> | <comando, informe, artefacto o documento> |
