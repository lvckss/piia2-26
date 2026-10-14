# Spec: Agente 2 — costes y cobertura a partir de los hallazgos

- GitHub Issue: https://github.com/lvckss/piia2-26/issues/30
- Estado: Borrador
- ADR decision: NO_ADR_REQUIRED
- ADR: No requerido — justificado en Spec.
- Justificación: esta Issue implementa, sin cambiarlo, el contrato Agente 2 → Agente 3 ya acordado en `specs/piia2-arquitectura-multiagente.md` y fijado por `ejemplos_contrato/agente2_salida.json`. No introduce una decisión estructural nueva: usa la herramienta de costes de la empresa (decisión previa) y replica reglas de cobertura deterministas ya descritas. Registrar como ADR las decisiones previas (contrato entre agentes, herramienta de la empresa) es el alcance de la Issue #37, no de esta. El único cambio de contrato que toca esta Issue (`vehiculo_id` opcional y `vehiculo_origen`) lo decide el ADR 0001 de la Issue #28; aquí solo se consume (AC-009). **A confirmar en la revisión:** que esta justificación no oculta una decisión relevante.
- Plan vigente / versión: este archivo, en la rama `plan/30-costes-cobertura`; el commit exacto se registra en un comentario de la Issue.
- Riesgo y revisión previa: **sí, por solicitud expresa**. Por riesgo no haría falta (sin NEW_ADR, reversible, contrato preservado), pero el equipo acordó en el reparto de la Entrega 1 que esta mini-spec la revise Lucas antes de implementar. Según AGENTS.md («respetar también revisión previa expresamente solicitada») y el workflow, eso activa el camino con revisión previa: Spec Revisada y Planning PR aprobada e integrada por un humano antes de implementar. Consumidores: Agente 3 (#31) y la función `agente2()` de la integración (#32/#34). Impacto medio (las cifras llegan al informe), reversibilidad alta (función nueva, sin datos persistentes), incertidumbre baja (código de referencia probado en la guía).
- Planning PR: https://github.com/lvckss/piia2-26/pull/40 (revisa Lucas). Al aprobarla, la spec pasa a Revisada y se registran quién la acepta, el permalink y la versión.

## Qué construir

Una función determinista del Agente 2, `estimar_siniestro(salida_agente1, contexto)`, en
`entregas/cu-19-interpretacion-danos/app/agentes/agente_recuperacion/costes_y_cobertura.py`, que:

- **Recibe** la salida del Agente 1 (`image_id`, `findings[]`) y el contexto del siniestro
  (coche, taller, póliza, rol, edad, km).
- **Reparte los hallazgos** en tres grupos:
  - *confirmados* (`confidence_tier == "confirmed"`): entran en los dos escenarios;
  - *pendientes* (`needs_review` con pieza, severidad y regla de coste): solo en el
    escenario «con pendientes»;
  - *fuera del coste*, con motivo `rechazado_por_vision`, `sin_pieza_o_severidad` o
    `sin_regla_de_coste`.
- **Presupuesta dos escenarios** (`confirmados` y `con_pendientes`) llamando a la herramienta de la
  empresa `estimar_coste(vehiculo_id, danos, region, tipo_taller, acabado, tipo_pieza)`.
- **Calcula por escenario** la pérdida total, la cobertura y la indemnización estimada con
  `valor_venal` y `polizas.csv`, replicando las reglas con las que la empresa generó sus
  siniestros (`piia2_paquete_datos/scripts/generate_claims.py`).
- **Devuelve** un diccionario con la forma de `ejemplos_contrato/agente2_salida.json`, con
  `normativa: []` (la rellena el RAG de la Issue #32).

Encaja entre el Agente 1 (`agente_multimodal/agente1.py`) y el Agente 3 (#31). El código de
referencia de `specs/agente2-costes-cobertura-guia.md` es el punto de partida.

### Estado actual (exploración en solo lectura, `origin/main` en `5bdabe2`)

| Qué | Evidencia |
|---|---|
| No existe código productivo del Agente 2: la carpeta solo tiene un README. | `app/agentes/agente_recuperacion/README.md` |
| El contrato de entrada y salida está fijado por ejemplos: 5 hallazgos (confirmado, rechazado, pendiente por score, pendiente con visión incierta, confirmado grave) y la salida esperada calculada con la herramienta real. | `app/agentes/ejemplos_contrato/{agente1_salida,contexto_siniestro,agente2_salida}.json` y su README |
| Cifras de referencia del ejemplo: valor venal 17.491,54 €; `confirmados` 1.019,46 € sin IVA / 933,55 € de indemnización; `con_pendientes` 1.488,23 € / 1.500,76 €; `160-2` fuera por `rechazado_por_vision`. | `agente2_salida.json` |
| La guía trae el código de referencia (`clasificar_hallazgos`, `calcular_cobertura`, `estimar_siniestro`) y la prueba mínima `probar_costes.py`. | `specs/agente2-costes-cobertura-guia.md` |
| Las reglas de cobertura (pérdida total, tercero, lunas, daños propios, sin cobertura) están descritas en la guía, pieza B. | Ídem |
| El contrato Agente 2 → Agente 3 y los motivos de `hallazgos_fuera_del_coste` están en la arquitectura. | `specs/piia2-arquitectura-multiagente.md`, «Agente 2 → Agente 3» |
| La Issue #28 (PR #29, ADR 0001 Propuesto) propone `vehiculo_id` opcional en el contexto y `vehiculo_origen` en la salida. | `plan/28-categoria-vehiculo:specs/28-categoria-vehiculo.md#AC-009` |
| La herramienta y los datos de la empresa no están en git; cada miembro extrae `piia2_paquete_datos/` en la raíz del repo. | `.gitignore`, arquitectura |

## Por qué

El Agente 1 ya entrega hallazgos con pieza, severidad y veredicto, pero nada los convierte en un
presupuesto ni dice si la póliza los cubre. Sin esta pieza no hay cifras para el informe (#31) y la
cadena foto → informe no se puede cerrar. Las cifras deben salir de código determinista (la
herramienta de la empresa y reglas fijas), nunca de un modelo de lenguaje, para que el informe se
pueda verificar.

## Alcance

- Incluido: reparto de hallazgos en tres grupos con motivo; dos escenarios de coste con
  `estimar_coste`; valor venal, umbral y pérdida total; cobertura e indemnización estimada para
  rol propio y tercero perjudicado; salida con la forma del contrato; validación explícita de la
  entrada del siniestro; uso del coche estimado por visión cuando el contexto no trae `vehiculo_id`
  (condicionado a la #28); evaluación con los siniestros sintéticos de la empresa.
- Fuera de alcance: el RAG de normativa y la función `agente2()` que lo junta (#32); el informe
  (#31); la orquestación y ADK (#33, #34); modificar la herramienta o los datos de la empresa;
  precios reales; aprobar o rechazar reparaciones o indemnizaciones; cambiar el Agente 1.

## Restricciones y supuestos

- Sin LLM ni red: la función solo usa la librería estándar y la herramienta de la empresa. Funciona
  sin `OPENAI_API_KEY`.
- No se suben a git el paquete de la empresa, ni CarDD, ni claves.
- El paquete se localiza en `<raíz del repo>/piia2_paquete_datos/`. Si falta, el módulo falla con un
  mensaje que dice dónde extraerlo (no con un error opaco).
- La indemnización es **orientativa**: los datos de pólizas y precios son sintéticos (relacionado
  con la #35, alcance del README del caso).
- Contexto obligatorio: `vehiculo_id` (opcional solo si se acepta la #28, AC-009), `region`,
  `tipo_taller`, `acabado`, `tipo_pieza`, `rol`, `edad_anios` y `km`. `poliza_id` es obligatorio y
  debe existir en `polizas.csv` solo si `rol == "propio"`; con `tercero_perjudicado` se ignora
  (puede venir vacío, AC-003).

| Incertidumbre | Clasificación | Evidencia / supuesto / pregunta y efecto |
|---|---|---|
| ¿Requiere ADR el contrato de salida del Agente 2, que consume el Agente 3? | Pregunta no bloqueante, a confirmar en la revisión | Se elige NO_ADR_REQUIRED porque el contrato ya está acordado y no cambia; su registro como ADR corresponde a la #37. Si el revisor lo pide, se crea el ADR en la #37 y esta Issue lo reutiliza (REUSE_ADR) sin cambiar los AC. |
| ¿Se aprueba la #28 (`vehiculo_id` opcional y `vehiculo_origen`)? | Pregunta no bloqueante para AC-001 a AC-008 y AC-010 y AC-011; bloqueante solo para AC-009 | Si el ADR 0001 se acepta, AC-009 se implementa tal cual. Si se rechaza, AC-009 se retira (sin renumerar) y `vehiculo_id` sigue siendo obligatorio (AC-010). La #28 (slice 4) añade `contexto.vehiculo_origen` a `ejemplos_contrato/agente2_salida.json`: AC-001 compara siempre con el ejemplo vigente en `main` cuando se ejecuta, así que, si la #28 se integra antes que esta Issue, AC-001 incluye ese campo. |
| Un hallazgo `confirmed` siempre trae pieza, severidad y `regla_coste_aplicable == true`. | Resuelta con evidencia | `decidir_tier` (`agente_multimodal/confianza.py`) solo devuelve `confirmed` si `pieza_id` existe y la regla es `true`, y `vision.py` solo calcula la regla si hay pieza y severidad. El Agente 2 confía en esa invariante y no vuelve a comprobar los confirmados. |
| ¿Qué pólizas concretas usan AC-004, AC-005 y AC-006 y qué importes esperados salen? | Supuesto a comprobar con `polizas.csv` antes de Ready | El paquete de la empresa no está extraído en la máquina donde se revisó el plan. Hay que comprobar que `P-TERC-BASICO` existe y no cubre colisión, el criterio de pérdida total y la franquicia de `P-TR-FR300` (para fijar la indemnización de AC-005) y qué póliza cubre lunas (AC-006), y anotar los importes esperados en los AC. |
| ¿`estimar_coste` acepta una lista de daños vacía? | Supuesto a comprobar al implementar | La guía la llama con la lista vacía cuando no hay confirmados. Si la herramienta falla con `[]`, el escenario vacío se construye sin llamarla. En cualquier caso, el escenario vacío conserva la misma forma que uno con daños (AC-007), porque el Agente 3 lo consume sin comprobar claves (`specs/31-informe-peritaje.md#AC-007`). |
| Umbral de la evaluación de costes (AC-011). | Resuelta con evidencia (parcial) | El ≈ 9 % de MAPE es de la herramienta de la empresa con los daños reales, no de este código (que solo le pasa los daños): se reproduce como suelo, no como objetivo a mejorar. Lo que sí mide este código es la concordancia de `perdida_total` y `cobertura_aplica` con el CSV; se espera 100 % porque replica la lógica del generador. Si no, se documenta cada discrepancia. |
| Valores exactos del caso de pérdida total (V14). | Resuelta con evidencia (guía) | La guía da 935,85 € (`con_pendientes`) frente a un umbral de 870 € (75 % de 1.160 €) y 560,80 € (`confirmados`). Se usan como referencia en AC-005. |
| La #30 está asignada a Víctor y a Lucas. | Pregunta de equipo, no bloqueante | El reparto de la Entrega 1 la asigna a Víctor; queda abierto si Lucas se desasigna. |

## Comportamiento que debe preservarse

- No existe código previo del Agente 2: no hay regresiones de código que proteger.
- Sí hay un **contrato** previo: la forma de `agente2_salida.json` (claves de nivel superior, de cada
  escenario y de `cobertura`) y los tres motivos de `hallazgos_fuera_del_coste`. Lo protege AC-001.
- El Agente 1 y sus ejemplos no se modifican.

## Failure modes y requisitos no funcionales

| Condición | Comportamiento esperado | Cobertura |
|---|---|---|
| Hallazgo sin regla de coste (`regla_coste_aplicable` distinto de `true`). | Fuera del coste con `sin_regla_de_coste`; nunca entra en un presupuesto con 0 €. | AC-002 |
| Ningún hallazgo presupuestable. | Escenarios con la misma forma que uno con daños (importes 0, listas vacías), cobertura «Sin daños presupuestables», sin excepción. | AC-007 |
| `poliza_id`, `vehiculo_id` o `rol` inválidos, o falta un campo obligatorio del contexto. | Excepción explícita que nombra el campo; no se devuelve una salida parcial. | AC-010 |
| Paquete de la empresa ausente. | Error al importar que indica la ruta esperada. | AC-010 |
| Determinismo. | Misma entrada → misma salida, sin red ni clave. | AC-008 |
| Rendimiento. | No aplica: cálculo local de milisegundos; sin requisito. | — |

## Acceptance Criteria

| ID | Dado / Cuando | Resultado esperado y condición de éxito |
|---|---|---|
| AC-001 | Los ejemplos del contrato (`agente1_salida.json`, `contexto_siniestro.json`) y se llama a `estimar_siniestro`. | La salida es **igual** a `agente2_salida.json` (versión vigente en `main`) ignorando `normativa`, y `normativa == []`. Importes de referencia: 1.019,46 € / 933,55 € (`confirmados`) y 1.488,23 € / 1.500,76 € (`con_pendientes`). |
| AC-002 | Hallazgos con cada combinación: `confirmed`; `needs_review` con pieza, severidad y regla; `rechazado`; sin pieza o sin severidad; con `regla_coste_aplicable` `false` o `null`. | Los confirmados están en los dos escenarios; los pendientes, solo en `con_pendientes`; el resto, en `hallazgos_fuera_del_coste` con su motivo exacto. Cada `finding_id` aparece en un único grupo y ninguno se pierde. |
| AC-003 | El contexto del ejemplo con `rol = "tercero_perjudicado"` y `poliza_id` vacío. | `umbral_perdida_total == 1.0`; en cada escenario con daños `cubierto == true`, `franquicia_eur == 0`, motivo de RC obligatoria e indemnización igual al total con IVA (o al valor venal si hay pérdida total). |
| AC-004 | El contexto del ejemplo con una póliza que no cubre daños propios por colisión (`P-TERC-BASICO`) y daños que no son solo cristales. | `cubierto == false` e `indemnizacion_estimada_eur == 0` en los dos escenarios. |
| AC-005 | Los hallazgos del ejemplo con `vehiculo_id = "V14"`, `edad_anios = 16`, `km = 300000`. | `perdida_total == true` solo en `con_pendientes` (≈ 935,85 € sin IVA frente a un umbral de ≈ 870 €) y `false` en `confirmados` (≈ 560,80 €); la indemnización de `con_pendientes` sigue la regla de pérdida total de la póliza (valor venal, +10 % si el criterio es `valor_venal_mas_10pct`, menos franquicia). |
| AC-006 | Solo daños sobre piezas de zona `cristal` con una póliza que cubre lunas. | Motivo «Cobertura de lunas», franquicia de lunas de la póliza e indemnización = `min(total con IVA, límite anual de lunas) − franquicia de lunas`. |
| AC-007 | Una salida del Agente 1 sin hallazgos presupuestables (todos rechazados, o `findings` vacío). | No se lanza excepción. Cada escenario vacío conserva **la misma forma** que uno con daños: `hallazgos_incluidos == []`; `estimacion` con las mismas claves que en `agente2_salida.json` (`desglose` con sus 6 categorías a 0, `subtotal_sin_iva_eur`, `iva_eur` y `total_con_iva_eur` a 0, `lineas == []`, `arrastres_posibles == []`); y `cobertura` con sus 5 claves: `cubierto == false`, motivo «Sin daños presupuestables», `franquicia_eur == 0`, `perdida_total == false`, indemnización 0. |
| AC-008 | Se ejecuta dos veces con la misma entrada, sin `OPENAI_API_KEY` y sin red. | Las dos salidas son idénticas y la ejecución no necesita clave ni red. |
| AC-009 | (Condicionado a la aceptación del ADR 0001, #28.) Un contexto con `vehiculo_id` («con»), otro sin él ante una salida del Agente 1 con `vehiculo` («sin») y otro sin él ante una salida sin `vehiculo` («ninguno»). | «Con»: se presupuesta con ese coche y `contexto.vehiculo_origen == "dato_de_entrada"`. «Sin»: se usa `vehiculo.vehiculo_id_referencia` (y queda en `contexto.vehiculo_id`) y `contexto.vehiculo_origen == "estimado_por_vision"`. «Ninguno»: error explícito. Misma referencia que `specs/28-categoria-vehiculo.md#AC-009`. |
| AC-010 | Un contexto con `poliza_id` inexistente (con `rol == "propio"`), `vehiculo_id` inexistente, `rol` fuera de `propio`/`tercero_perjudicado` o un campo obligatorio ausente; o el paquete de la empresa no está en su ruta. | Se lanza una excepción cuyo mensaje nombra el campo o la ruta problemática; no se devuelve salida. |
| AC-011 | Los siniestros de `siniestros_sinteticos.csv` con `split` `val` o `test`. | Se documentan, con un script reproducible: el MAPE de `estimar_coste` con `danos_json` frente a `coste_facturado_sin_iva_eur` (referencia ≈ 9 %), y la concordancia de `cobertura.perdida_total` frente a `perdida_total` y de `cobertura.cubierto` frente a `cobertura_aplica` del CSV, construyendo el contexto con las columnas de cada siniestro (se espera 100 %; si no, cada discrepancia queda explicada). |

## Test Plan

### Test seams

- **S1 — `estimar_siniestro(salida_agente1, contexto)`:** función pública nueva y única frontera
  del componente; es lo que consumen el Agente 3 y `agente2()`. Cubre AC-001 a AC-010.
- **S2 — Herramienta de la empresa (`estimar_coste`, `valor_venal`) y CSV:** dependencia real, no se
  simula: las cifras de referencia están calculadas con ella.
- **S3 — `siniestros_sinteticos.csv`:** datos de evaluación de la empresa (AC-011).
- No se prueban funciones internas (`clasificar_hallazgos`, `calcular_cobertura`) como contrato.

Siguiendo el estilo del repo (`probar_*.py` ejecutables con `python`), las pruebas van en
`app/agentes/agente_recuperacion/probar_costes.py` y la evaluación en `evaluar_costes.py`. Cada
comprobación lleva en su nombre o comentario `30-costes-cobertura.md#AC-0XX`.

| Referencia (ruta de Spec + AC) | Seam / contrato | Estrategia y nivel | Caso / resultado esperado | Datos / entorno | Comando o pasos previstos | Evidencia prevista |
|---|---|---|---|---|---|---|
| `specs/30-costes-cobertura.md#AC-001` | S1 + S2 | TDD (Red → Green); contrato | Salida == `agente2_salida.json` salvo `normativa` | `ejemplos_contrato/`; paquete de la empresa | `python probar_costes.py` | Red (módulo ausente) y Green |
| `specs/30-costes-cobertura.md#AC-002` | S1 | TDD; unitario sobre la frontera | Cada combinación en su grupo con su motivo; sin duplicados ni pérdidas | Hallazgos construidos a partir de `agente1_salida.json` | `python probar_costes.py` | Red y Green |
| `specs/30-costes-cobertura.md#AC-003` | S1 + S2 | TDD | Tercero: umbral 1,0, franquicia 0, RC, total con IVA | Contexto del ejemplo modificado | `python probar_costes.py` | Red y Green |
| `specs/30-costes-cobertura.md#AC-004` | S1 + S2 | TDD | Póliza sin colisión: no cubierto, 0 € | `poliza_id = "P-TERC-BASICO"` | `python probar_costes.py` | Red y Green |
| `specs/30-costes-cobertura.md#AC-005` | S1 + S2 | TDD | Pérdida total solo en `con_pendientes` con V14 | V14, 16 años, 300.000 km | `python probar_costes.py` | Red y Green |
| `specs/30-costes-cobertura.md#AC-006` | S1 + S2 | TDD | Cobertura de lunas con límite y franquicia | Hallazgo único sobre `PARABRISAS`; póliza que cubre lunas según `polizas.csv` | `python probar_costes.py` | Red y Green |
| `specs/30-costes-cobertura.md#AC-007` | S1 + S2 | TDD | Sin daños presupuestables: mismas claves que un escenario con daños (comparadas con `agente2_salida.json`), importes 0, listas vacías, sin excepción | `findings` vacío y todo rechazado | `python probar_costes.py` | Red y Green |
| `specs/30-costes-cobertura.md#AC-008` | S1 | TDD | Dos ejecuciones idénticas sin clave ni red | Variable `OPENAI_API_KEY` eliminada del entorno del proceso y `socket.socket` sustituido durante la prueba por una función que lanza excepción | `python probar_costes.py` | Green (comprobación de igualdad, sin intento de conexión) |
| `specs/30-costes-cobertura.md#AC-009` | S1 + S2 | TDD (si se acepta el ADR 0001) | «Con», «sin», «ninguno» | Ejemplos con y sin `vehiculo` según la #28 | `python probar_costes.py` | Red y Green, o AC retirado con referencia a la decisión |
| `specs/30-costes-cobertura.md#AC-010` | S1 | TDD | Excepción que nombra campo o ruta | Contextos inválidos; para el paquete ausente, copia del módulo en un directorio temporal con un `.git` vacío y sin `piia2_paquete_datos/`, importada en un subproceso | `python probar_costes.py` | Red y Green |
| `specs/30-costes-cobertura.md#AC-011` | S2 + S3 | Eval (medición reproducible, sin rojo artificial) | MAPE ≈ 9 % y concordancia de banderas | `siniestros_sinteticos.csv`, `split` val + test, versión del paquete local | `python evaluar_costes.py` | Tabla con n, MAPE y concordancias en la PR de implementación |

## Implementation Plan

| Slice | Objetivo observable | AC relacionados | Componentes / contratos probablemente afectados | Dependencias | Verificación prevista |
|---|---|---|---|---|---|
| 1 — Ejemplo del contrato | `estimar_siniestro` reproduce `agente2_salida.json` con el reparto de hallazgos. | AC-001, AC-002, AC-007 | `agente_recuperacion/costes_y_cobertura.py` (nuevo); contrato Agente 2 → 3 | Paquete de la empresa extraído en local | Filas AC-001, AC-002, AC-007 |
| 2 — Reglas de cobertura | Tercero, póliza sin cobertura, pérdida total y lunas correctos. | AC-003, AC-004, AC-005, AC-006 | Ídem | Slice 1 | Filas AC-003 a AC-006 |
| 3 — Robustez de la entrada | Errores explícitos y ejecución determinista sin red. | AC-008, AC-010 | Ídem | Slice 1 | Filas AC-008, AC-010 |
| 4 — Coche estimado por visión | `vehiculo_id` opcional y `vehiculo_origen`. | AC-009 | Ídem; contrato de la #28 | ADR 0001 aceptado y la #28 integrada | Fila AC-009 |
| 5 — Evaluación | MAPE y concordancias documentados. | AC-011 | `agente_recuperacion/evaluar_costes.py` (nuevo) | Slice 2 | Fila AC-011 |

Al terminar, el README de `agente_recuperacion/` indica cómo ejecutar las pruebas y la evaluación.

## Pendientes para Ready

- **Decisión de la #28 (bloquea solo AC-009 y la slice 4):** aceptación o rechazo del ADR 0001 en la PR #29. Las slices 1, 2, 3 y 5 no dependen de ella.
- **Revisión previa (solicitud del equipo):** Planning PR #40 aprobada por Lucas e integrada por un humano; spec en estado Revisada, con quién la acepta, el permalink y la versión registrados en la Issue.
- **Confirmación en la revisión** de la ADR decision (NO_ADR_REQUIRED) y de su relación con la #37.
- **Importes esperados de AC-004 a AC-006** fijados a partir de `polizas.csv` (ver Restricciones y supuestos).
- **Prerrequisito de implementación (no de planificación):** extraer `piia2_paquete_datos/` en la raíz del repo.

Resultado de analyze:

| Comprobación | Resultado |
|---|---|
| Cada requisito de la Issue tiene AC | Dos presupuestos → AC-001, AC-002; fuera del coste con motivo → AC-002; valor venal, pérdida total, cobertura e indemnización → AC-001, AC-003 a AC-006; forma del contrato → AC-001; cifras solo de código → AC-008; error medido → AC-011; dependencia de la #28 → AC-009. |
| AC sin requisito en la Issue | AC-007 y AC-010 cubren failure modes; no amplían el alcance funcional. |
| Cada AC tiene verificación y slice | Sí (AC-001 a AC-011). |
| Comportamiento preservado | El contrato, protegido por AC-001. |
| ADR decision coherente | NO_ADR_REQUIRED justificado; se señala para confirmación. |
| Gaps | Importes concretos de AC-004 a AC-006 pendientes de `polizas.csv`; AC-009 depende de la #28. El resto no tiene gaps bloqueantes. |

## Definition of Done

| Condición específica de cierre | Evidencia requerida |
|---|---|
| `probar_costes.py` ejecutado **con el paquete de la empresa presente** y en verde. | Salida del comando en la PR de implementación. |
| Evaluación de AC-011 documentada. | Tabla con n, MAPE y concordancias, y comando para reproducirla. |
| AC-009 implementado o retirado con referencia a la decisión de la #28. | Enlace a la PR #29 y su resultado. |
| README de `agente_recuperacion/` actualizado. | Diff de la PR. |
