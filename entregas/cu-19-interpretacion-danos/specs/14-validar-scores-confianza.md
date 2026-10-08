# Spec: Validar scores de confianza antes de clasificar hallazgos

- GitHub Issue: https://github.com/lvckss/piia2-26/issues/14
- Estado: Borrador
- ADR decision: NO_ADR_REQUIRED
- ADR: No requerido — justificado en Spec.
- Justificación: validación y excepción locales dentro del Agente 1, sin cambiar arquitectura, consumidores independientes, fronteras estables, schemas compartidos, protocolos, persistencia ni una decisión duradera/costosa de revertir. El carácter importable de las funciones y la elección de `ValueError` no requieren ADR por sí solos según la política vigente en main; la evidencia se detalla abajo.
- Planning PR: https://github.com/lvckss/piia2-26/pull/16
- Revisión humana de Spec, planes y ADR decision: pendiente en la Planning PR; sin aceptación acreditada.

## Qué construir

Validar el `score` numérico antes de clasificarlo en `confianza.py`: debe ser
finito y estar en el intervalo cerrado `[0, 1]`. Un valor negativo, mayor que
uno, `NaN`, infinito positivo o infinito negativo debe provocar `ValueError`,
sin devolver `confirmed` ni `needs_review`.

Se propone que el mensaje identifique el «score de confianza» como «inválido»
y explique que «debe ser finito» y estar en «[0, 1]». Esos fragmentos forman
el contrato verificable; no se fija el resto de la redacción ni la representación
del valor recibido. No se recorta, normaliza, sustituye ni convierte el score.

El contrato interno se aplica a `classify_confidence(category_name, score)` y
`decidir_tier(category_name, score, vision_verdict, pieza_id, regla_coste_aplicable)`.
Para scores válidos se preserva exactamente la clasificación actual y la regla
de consenso de score, visión y posibilidad de presupuestar.

## Por qué

Actualmente un score inválido puede producir un tier aparentemente legítimo:
la comparación puede confirmar valores superiores a uno o infinito positivo,
y asignar revisión a negativos, `NaN` o infinito negativo. Un dato inválido
no constituye evidencia de confianza baja o alta. La Issue pide distinguirlo
mediante un fallo explícito antes de usarlo en la clasificación.

### Contexto observado en el repositorio

Inspección de `origin/main` en el snapshot
`0717664d7e83622662b78c9b021564c8ad9a3ef5`, sin ejecutar producto ni tests:

- [confianza.py](../app/agentes/agente_multimodal/confianza.py): `classify_confidence`
  compara `score >= threshold` sin validar finitud/rango. Los umbrales son
  `0.7` para `dent`, `scratch`, `crack`; `0.6` para `lamp broken`,
  `glass shatter`, `tire flat`; y `0.8` para categorías desconocidas.
  `decidir_tier` llama primero a `classify_confidence`, después comprueba visión,
  pieza y regla de coste.
- [hallazgos.py](../app/agentes/agente_multimodal/hallazgos.py):
  `construir_hallazgos` clasifica las candidatas y copia el score recibido al
  finding, con `score_tier` y `confidence_tier` iniciales iguales.
- [seleccion.py](../app/agentes/agente_multimodal/seleccion.py): el filtro se
  ejecuta antes de clasificar; `filtrar=False` permite comprobar la frontera
  de construcción sin descartar candidatos. Esta tarea no valida toda la
  entrada cruda antes del filtro.
- [vision.py](../app/agentes/agente_multimodal/vision.py):
  `enriquecer_con_vision` utiliza `decidir_tier`. No captura su error y consulta
  visión antes de recalcular el tier: no se promete evitar toda llamada de
  visión para hallazgos manipulados externamente.
- [agente-confianza-hallazgos.md](agente-confianza-hallazgos.md) describe el
  consenso existente y advierte que los umbrales siguen pendientes de calibrar.
  Es contexto histórico, no un ADR aceptado ni evidencia de tests ejecutados.
- Los scripts existentes `probar_vision_stub.py`, `probar_seleccion_stub.py`
  y `probar_agente1_stub.py` cubren consenso, filtro y contrato JSON con datos
  válidos. No se ha localizado una prueba específica de finitud/rango.

### ADR decision: evidencia y política aplicada

Reevaluación sobre `origin/main` en el snapshot
`c043af54f7cb97dbc5747974e861071864dfb18b`, aplicando
[AGENTS.md](https://github.com/lvckss/piia2-26/blob/c043af54f7cb97dbc5747974e861071864dfb18b/AGENTS.md),
[workflow](https://github.com/lvckss/piia2-26/blob/c043af54f7cb97dbc5747974e861071864dfb18b/docs/workflow.md)
y [piia2-plan-task](https://github.com/lvckss/piia2-26/blob/c043af54f7cb97dbc5747974e861071864dfb18b/.agents/skills/piia2-plan-task/SKILL.md)
de ese mismo snapshot, aunque la rama del plan aún tenga la política anterior.

- `git grep` sobre todos los Python de main encuentra consumidores productivos
  de `classify_confidence` en `hallazgos.py` y `decidir_tier`, y de
  `decidir_tier` en `vision.py`; el resto son pruebas/referencias dentro de
  `app/agentes/agente_multimodal`. No se han encontrado consumidores externos
  o componentes que evolucionen independientemente usando estas funciones.
- Esas importaciones son colaboraciones internas del Agente 1. La frontera
  estable Agente 1 → Agentes 2/3 es el JSON de findings; no cambia su schema,
  nombres/campos, significado de tiers válidos, protocolo ni formato persistente.
- Se modifica una precondición interna y su excepción para datos inválidos.
  No se introduce excepción propia, API externa, dependencia estructural,
  recuperación distribuida ni cambios de seguridad, deployment o estrategia ML.
- El ajuste y una eventual revisión del error quedan localizados en el mismo
  componente y sus tests; no exigen migrar datos, coordinar versiones de agentes
  o mantener un trade-off estructural. No se usa el tamaño del diff como razón.
- El código de `app/agentes/agente_multimodal` no cambió entre el snapshot
  inicial y este main; el análisis previo de comportamiento sigue siendo válido.

Por tanto, el caso activo es **NO_ADR_REQUIRED**, con justificación pendiente
de revisión humana en #16. [ADR 0001](../../../docs/adr/0001-rechazo-scores-confianza-invalidos.md)
se conserva como propuesta **Rechazada** por su clasificación innecesaria
bajo la política actual, sin atribuir aceptación/rechazo humano del comportamiento.
Es historial, no ADR aplicable ni dependencia para Ready. La propuesta de
`ValueError`, los siete AC, seams, Test Plan e Implementation Plan siguen
vigentes y requieren revisión; no se da el plan por aceptado.

## Alcance

- Incluido: rechazo de los cinco grupos de valores inválidos indicados por la
  Issue, contrato `ValueError`/mensaje, ambas funciones públicas de confianza,
  propagación natural a la construcción de hallazgos cuando la candidata llega
  a clasificación y regresión del comportamiento válido.
- Fuera de alcance: cambiar umbrales, filtro previo, visión, reglas de costes,
  arquitectura general, calibración o calidad ML; validación de tipos no
  numéricos, coerción de strings, política nueva para booleanos, nuevos campos
  JSON, captura/recuperación del error, excepciones propias y traducción HTTP.
  No se amplía la validación al input completo antes de `seleccion.py`.

## Restricciones y supuestos

- El dominio de esta tarea son scores numéricos del contrato existente
  `score: float`, incluidos los valores no finitos y los extremos numéricos
  `0` y `1`. Se conserva la aceptación de los extremos enteros `0` y `1`.
  No se especifica aquí una nueva política de validación de tipos.
- El fallo debe ocurrir antes de comparar el score con el umbral. En
  `decidir_tier` se rechaza aun si visión, pieza o regla impedirían confirmar.
- Se mantiene la comparación inclusiva `>=` para cada umbral y no se altera
  `ConfidenceTier`, firmas, nombres, categorías ni constantes actuales.
- No hacen falta API Key, datos privados, dataset CarDD o modelo real para
  verificar el nuevo contrato. Las regresiones de visión con cliente falso
  requieren Pillow ya disponible en el entorno del proyecto.
- Los umbrales actuales se preservan, sin dar por resuelta su calibración
  pendiente. Este cambio no tiene objetivo de precisión/recall y usa TDD.

| Incertidumbre | Clasificación | Evidencia / supuesto / pregunta y efecto |
|---|---|---|
| Tipo y contenido del fallo | Pregunta no bloqueante | Se propone `ValueError` y los fragmentos de Qué construir, con AC verificables; confirmar en la revisión del plan. Su elección local no implica una decisión arquitectónica ni aceptación ya obtenida. |
| ¿Se valida toda detección antes del filtro? | Resuelta con evidencia | La Issue excluye modificar `seleccion.py`; solo se garantiza rechazo de scores que llegan a confianza. |
| ¿Afecta a ambas funciones de confianza? | Resuelta con evidencia | Ambas son observables dentro del componente y `decidir_tier` delega ya en `classify_confidence`. AC-005 y AC-006 protegen estos seams; no son fronteras externas por ser importables. |
| ¿Requiere ADR con la política vigente? | Resuelta con evidencia | Política y búsqueda de consumidores del snapshot `c043af5`: validación/excepción interna sin consecuencias estructurales, NO_ADR_REQUIRED. La justificación aún debe aceptarse en #16; no se necesita reutilizar/aceptar un ADR. |
| Strings, `None`, booleanos u otros tipos | Supuesto explícito aceptable | No se redefine su tratamiento: la Issue pide finitud/rango de scores numéricos, no validación general de tipos. Confirmar el límite durante review. |
| Restricción histórica del body a crear solamente la Issue | Resuelta por petición actual | «planifica la issue #14» autoriza ahora el ciclo de planificación; se conserva íntegro el body original y se añadirán referencias en un comentario. |

## Comportamiento que debe preservarse

- `classify_confidence` devuelve `confirmed` exactamente cuando un score
  válido alcanza el umbral de su clase; usa `0.8` para una clase desconocida.
  Se aceptan `0`, `-0.0` y `1`. Protección: AC-001.
- `decidir_tier` exige score suficiente, `vision_verdict == "confirmado"`,
  `pieza_id is not None` y `regla_coste_aplicable is True`. Visión no rescata
  scores bajos. No endurecer la comprobación de pieza ni la de regla.
  Protección: AC-006 y `probar_vision_stub.py::probar_decidir_tier`.
- Para entradas válidas, construcción conserva campos, valores de score,
  orden e identificadores de findings y `resumen_filtro_previo`. Filtro,
  recorte, visión y costes mantienen su comportamiento. Protección: AC-007,
  `probar_seleccion_stub.py` y `probar_agente1_stub.py`.

## Failure modes y requisitos no funcionales

- Score finito fuera de rango: `ValueError`, sin tier ni corrección silenciosa
  (AC-002 y AC-004), también en el tier final (AC-005).
- `NaN` o infinito: mismo rechazo explícito (AC-003 y AC-004), sin usar el
  resultado de una comparación IEEE como decisión de confianza (AC-005).
- Detección candidata inválida: `construir_hallazgos` propaga el error y no
  devuelve un resultado normal con un tier inventado (AC-007). No se añade
  recuperación por hallazgo ni un resultado parcial como contrato.
- Compatibilidad y determinismo: mismos tiers y estructura para datos válidos
  y fallo reproducible para datos inválidos (AC-001, AC-006, AC-007).
- No se requieren dependencias nuevas ni llamadas externas para validar un
  score. No se fijan umbrales de latencia/memoria: no hay un requisito medido
  en la Issue y esta validación no altera serving ni cargas ML.

## Acceptance Criteria

| ID | Dado / Cuando | Resultado esperado y condición de éxito |
|---|---|---|
| AC-001 | Score finito en `[0, 1]`, categoría conocida o desconocida; al llamar a `classify_confidence`. | Devuelve exactamente el tier previo: `confirmed` si `score >=` el umbral actual, `needs_review` en otro caso. Incluye `0`, `-0.0`, `1` y valores inmediatamente debajo, iguales y encima del umbral; las constantes permanecen iguales. |
| AC-002 | Score finito negativo o superior a `1`; al llamar a `classify_confidence` con una clase conocida o desconocida. | Lanza `ValueError` antes de clasificar y no devuelve un tier, incluidos los valores representables adyacentes a `0` por debajo y a `1` por encima. |
| AC-003 | Score `NaN`, infinito positivo o infinito negativo; al llamar a `classify_confidence` con una clase conocida o desconocida. | Cada valor lanza `ValueError` antes de clasificar y no devuelve un tier. |
| AC-004 | Cualquier score inválido de AC-002/AC-003; al llamar a cualquiera de las dos funciones de confianza. | El texto de `ValueError` contiene «score de confianza», «inválido», «debe ser finito» y «[0, 1]», sin distinguir mayúsculas/minúsculas. No depende de inspeccionar un traceback para entender la restricción. |
| AC-005 | Score inválido y cualquier combinación de visión, pieza y regla; al llamar a `decidir_tier`. | Lanza `ValueError`, sin devolver tier, incluso con visión ausente/rechazada, pieza ausente o regla falsa/ausente; esos datos no ocultan el score inválido. |
| AC-006 | Score válido; al llamar a `decidir_tier` con combinaciones de score suficiente/insuficiente, visión, pieza y regla. | Conserva la regla actual de las tres condiciones; solo confirma si todas se cumplen. Incluye score exactamente en el umbral, categorías desconocidas y extremos `0`/`1`. |
| AC-007 | Detecciones válidas o candidata con score inválido; al llamar a `construir_hallazgos`. | Con datos válidos conserva findings y resumen previos, con y sin filtro. Con `filtrar=False`, cada grupo inválido propaga `ValueError` sin devolver hallazgos; con filtro activo, una única candidata `lamp broken` con score `1.1` también propaga el error. No se exige validar las detecciones descartadas por el filtro. |

## Test seams

| Frontera observable | Contrato y justificación |
|---|---|
| `confianza.classify_confidence` | Función pública determinista: tier o `ValueError`. Permite comprobar todas las clases y bordes sin modelo, mocks de internals ni nuevas interfaces. |
| `confianza.decidir_tier` | Función pública del tier final: mismo error y consenso existente. Detecta que un retorno temprano no oculta entradas inválidas. |
| `hallazgos.construir_hallazgos` | Salida de findings/resumen o propagación del fallo de una candidata. Es la integración pública más próxima; `filtrar=False` es un parámetro existente. |
| Scripts stub existentes | Contrato válido del filtro, visión y pipeline/JSON. Se reutilizan para regresión, sin llamadas reales ni redefinir su comportamiento. |

## Test Plan

Estrategia determinista **Red → Green → Refactor**. En implementación se crearán
pruebas con `unittest` de la biblioteca estándar, siguiendo la posibilidad de
ejecutar scripts directamente que ya usa el módulo. Nombre previsto:
`app/agentes/agente_multimodal/probar_confianza.py`; todavía no existe.
Cada test incluirá la ruta completa de esta Spec y el ID de AC en nombre,
comentario o documentación. Las fixtures futuras serán datos sintéticos en
memoria; no se crean en esta Planning PR.

Todos los comandos siguientes se ejecutarán **desde la raíz del repositorio**
en la fase de implementación. `python` debe apuntar al entorno del proyecto;
registrar versión e ID de commit en la evidencia. No se han ejecutado ahora.

| Referencia (ruta de Spec + AC) | Seam / contrato | Estrategia y nivel | Caso / resultado esperado | Datos / entorno | Comando o pasos previstos | Evidencia prevista |
|---|---|---|---|---|---|---|
| `entregas/cu-19-interpretacion-danos/specs/14-validar-scores-confianza.md#AC-001` | `classify_confidence`: tier válido y umbrales | TDD; unitario de regresión | Seis clases y una desconocida; `0`, `-0.0`, `1`, enteros extremos y `math.nextafter(t, -inf)`, `t`, `math.nextafter(t, inf)`. Oráculo: tabla de umbrales del snapshot y comparación inclusiva. | Matriz sintética v1, biblioteca estándar; valores de umbral explícitos independientes de la implementación. | `python entregas/cu-19-interpretacion-danos/app/agentes/agente_multimodal/probar_confianza.py`; verificar que las constantes coinciden con la tabla previa. | Casos y resultado verde antes/después; no se exige rojo artificial para comportamiento preservado. |
| `entregas/cu-19-interpretacion-danos/specs/14-validar-scores-confianza.md#AC-002` | `classify_confidence`: error fuera de rango | TDD; unitario | `-0.1`, `1.1`, `math.nextafter(0.0, -inf)` y `math.nextafter(1.0, inf)`; clases conocidas y desconocida; siempre `ValueError`. | Matriz sintética v1; sin tolerancia que permita valores fuera de rango. | Mismo script; ejecutar antes de cambiar confianza, después del cambio mínimo y tras refactor. | Red por tier devuelto en vez de error; Green y Refactor con todos los casos pasando. |
| `entregas/cu-19-interpretacion-danos/specs/14-validar-scores-confianza.md#AC-003` | `classify_confidence`: error no finito | TDD; unitario | `float('nan')`, `float('inf')`, `float('-inf')`; todas las clases y desconocida; siempre `ValueError`. | Matriz sintética v1; sin dataset/modelo. | Mismo script en Red, Green y Refactor. | Fallo esperado por ausencia de validación; posterior rechazo de los tres valores. |
| `entregas/cu-19-interpretacion-danos/specs/14-validar-scores-confianza.md#AC-004` | Excepción pública y mensaje de ambas funciones | TDD; contrato unitario | Todos los inválidos anteriores; comprobar tipo y los cuatro fragmentos sobre `str(error).lower()`, sin fijar texto completo. | Matriz sintética v1. | Mismo script en Red, Green y Refactor. | Registro de que ambas fronteras comunican finitud/rango; no un fallo accidental por import o dependencia. |
| `entregas/cu-19-interpretacion-danos/specs/14-validar-scores-confianza.md#AC-005` | `decidir_tier`: prioridad de validación | TDD; unitario | Inválidos anteriores cruzados con visión `confirmado`/`rechazado`/`incierto`/`None`, pieza presente/ausente y regla `True`/`False`/`None`; siempre `ValueError`. | Matriz sintética v1; categorías conocidas y desconocida; sin mocks privados. | Mismo script en Red, Green y Refactor. | Rechazo independiente del resto de argumentos; ninguna combinación devuelve tier. |
| `entregas/cu-19-interpretacion-danos/specs/14-validar-scores-confianza.md#AC-006` | `decidir_tier`: consenso válido | TDD; regresión unitaria e integración stub | Valores válidos/bordes de AC-001 y combinaciones de visión/pieza/regla. Reutilizar `probar_decidir_tier` y el cliente falso existente. | Matriz v1 y `MINI_CATALOGO` versionado en el snapshot; Python con Pillow para script stub. | Nuevo script y `python entregas/cu-19-interpretacion-danos/app/agentes/agente_multimodal/probar_vision_stub.py`. | Tiers esperados y exit code cero; registrar por separado la eventual omisión del catálogo real. |
| `entregas/cu-19-interpretacion-danos/specs/14-validar-scores-confianza.md#AC-007` | `construir_hallazgos` y JSON válido | TDD; integración y regresión stub | Detección mínima con cada inválido sin filtro; una `lamp broken` `1.1` con filtro. Para válidos, comparar diccionario completo previsto, score sin modificar y resumen con/sin filtro; conservar pipeline stub. | Fixture sintética v1 futura; ejemplos JSON y scripts ya versionados; Pillow para pipeline. | Nuevo script; `python entregas/cu-19-interpretacion-danos/app/agentes/agente_multimodal/probar_seleccion_stub.py`; `python entregas/cu-19-interpretacion-danos/app/agentes/agente_multimodal/probar_agente1_stub.py`. | Red por resultado normal con candidata inválida; Green/Refactor; JSON/resumen válidos y scripts sin regresión. Registrar explícitamente omisiones de datos opcionales. |

Las partes opcionales de los scripts existentes que usan catálogo empresarial o
export de 500 imágenes pueden omitirse si no están disponibles, indicando la
omisión; no equivalen a verificaciones realizadas. No son necesarias para el
contrato numérico nuevo ni para las regresiones sintéticas requeridas.
Si falla una regresión requerida por entorno o por un fallo previo, registrar
causa y resolver su verificación antes de Done; nunca presentarla como exitosa.
No hay eval-first: el comportamiento es determinista y no se recalibra ML.

## Implementation Plan

Solo se comienza después de Ready, con esta Planning PR integrada, Spec
Revisada y justificación de NO_ADR_REQUIRED revisada y aceptada. Los slices
son incrementos observables de un mismo contrato; no son rediseños independientes.

| Slice | Objetivo observable | AC relacionados | Componentes / contratos probablemente afectados | Dependencias | Verificación prevista |
|---|---|---|---|---|---|
| 1 — Clasificación rechaza datos inválidos | Las llamadas directas rechazan fuera de rango/no finitos con diagnóstico común, preservando todos los tiers válidos. | AC-001, AC-002, AC-003, AC-004 en `classify_confidence` | `confianza.py` y futuro `probar_confianza.py`; firmas y constantes preservadas. | DoR completa; Spec/planes y justificación de NO_ADR_REQUIRED aceptados en Planning PR integrada. | Matrices y ciclo TDD de las cuatro filas del Test Plan; las regresiones válidas deben seguir verdes. |
| 2 — Tier final conserva consenso y error | El tier final aplica el mismo rechazo sin que visión/pieza/regla lo oculten y mantiene la regla actual para scores válidos. | AC-004 en `decidir_tier`, AC-005, AC-006 | `decidir_tier`, delegación pública existente y tests; sin cambiar `vision.py` ni costes. | Slice 1. | Matrices del tier final y `probar_vision_stub.py`; añadir casos antes de cualquier ajuste necesario. La delegación puede satisfacerlos sin más código productivo. |
| 3 — Hallazgos verifican el contrato y documentan el fallo | Las candidatas inválidas propagan el error y el flujo válido conserva findings/resumen/JSON; documentar finitud, rango y excepción en las funciones/README del módulo. | AC-007; documentación de AC-001–AC-006 | Tests sobre `construir_hallazgos`; documentación de `confianza.py`/README del Agente 1; sin modificar filtro ni formato JSON. | Slices 1 y 2; entorno con Pillow para regresiones stub. | Red/Green de integración, scripts de selección y Agente 1, suite nueva completa tras Refactor; revisión documental y diff final. |

## Pendientes para Ready

- Revisar explícitamente Spec/AC, límites, comportamiento preservado, failure
  modes, seams, TDD, cobertura de ambos planes y propuesta de error en la
  misma Planning PR. Confirmar el límite sobre tipos no numéricos y filtro.
- Aceptar humanamente la justificación de NO_ADR_REQUIRED y confirmar que no
  oculta una decisión estructural; registrar humano, permalink y versión
  revisada del plan/ADR decision, y actualizar Spec a Revisada dentro de #16.
  Aceptar un ADR no aplica; ADR 0001 es historial descartado, no una dependencia.
- Revisión/aprobación final del head tras los metadatos y merge humano;
  comprobar DoR desde main y solo entonces promover a Ready.
- No hay preguntas de requisitos que impidan proponer AC verificables; la
  elección del error es una propuesta concreta pendiente de aceptación.

**Analyze documental:** los requisitos de la Issue se cubren en AC-001
(válidos), AC-002 (negativos/mayores que uno), AC-003 (no finitos), AC-004
(diagnóstico), AC-005/AC-006 (tier final) y AC-007 (integración/regresión).
Todos tienen seam, datos, verificación y slice. La decisión NO_ADR_REQUIRED
se apoya en consumidores internos, fronteras preservadas y reversión localizada,
según la política de main `c043af5`. Se elimina de los gates la aceptación
del ADR artificial anterior, conservando su historia; no cambian AC, Test Plan,
objetivos de slices, fallo propuesto, umbrales, arquitectura ML ni filtro.
Las regresiones protegen lo válido; el límite del filtro impide prometer validación global.
No se han detectado contradicciones ni gaps bloqueantes para presentar el
plan a revisión. La aceptación y el merge siguen pendientes, sin acreditarlos
por la existencia de este documento.

## Definition of Done

La DoD global está definida por el [workflow](../../../docs/workflow.md) y la
checklist de la Issue enlazada. Esta sección la amplía, nunca la sustituye ni
la relaja. Todos los AC deben tener evidencia mediante ruta de Spec + ID.

| Condición específica de cierre | Evidencia requerida |
|---|---|
| Rechazo de las cinco familias inválidas en ambas funciones, con diagnóstico acordado, y matrices válidas sin regresión. | Evidencia TDD y ejecución final del futuro script, trazable a AC-001–AC-006. |
| Propagación desde candidatas y conservación de findings/resumen/JSON válido. | Casos de AC-007 y regresiones sintéticas/stub requeridas ejecutadas; omisiones opcionales identificadas. |
| Umbrales y filtro previo intactos; ninguna calibración o llamada real necesaria para verificar esta tarea. | Diff de implementación revisado y comparación de constantes con el snapshot; comandos de verificación registrados. |
| Documentación pública de confianza describe finitud, rango y `ValueError`, distinguiendo la validación del filtro previo. | Docstrings/README revisados y enlazados desde la Implementation PR. |
