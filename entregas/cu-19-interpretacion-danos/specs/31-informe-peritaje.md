# Spec: Agente 3 — informe de peritaje en markdown con cifras verificadas

- GitHub Issue: https://github.com/lvckss/piia2-26/issues/31
- Estado: Revisada (v2) — por Lucas García (`lvckss`), [revisión APPROVED del 2026-10-22](https://github.com/lvckss/piia2-26/pull/58#pullrequestreview-5615735502) sobre la versión `0deba77`, integrada en `main` (merge `73f6075`), que cubre la spec v2 y sus planes. La v1 se aceptó en `17502ac` (PR #41).
- ADR decision: NO_ADR_REQUIRED — aceptada para la v2 por Lucas García en la misma [revisión](https://github.com/lvckss/piia2-26/pull/58#pullrequestreview-5615735502) («consume la ampliación que se propone en el ADR 0006 de la #32; no hace falta otro ADR aquí»); para la v1, por Lucas (versión `17502ac`) y por Lucía Luis Castaño (revisión de `f61a637`).
- ADR: No requerido — justificado en Spec.
- Justificación: el Agente 3 es el último eslabón de la cadena. Consume los contratos ya acordados (salida del Agente 1 y del Agente 2, fijados por `ejemplos_contrato/`) sin cambiarlos y produce un documento markdown para una persona, no un formato que consuma otro agente ni que se persista como schema compartido. Su única interfaz, `generar_informe(agente1, agente2)`, la invocará la orquestación (#34) como una función más. No introduce dependencias externas (solo la librería estándar y los CSV de la empresa ya usados por el Agente 2) ni un trade-off difícil de revertir. La ampliación del contrato con `diagnostico_rag` la decide el ADR 0006 de la Issue #32 (PR #56); aquí solo se consume (AC-014 y AC-015), como antes se hacía con el ADR 0001 de la #28 para AC-010, ya retirado. Si el ADR 0006 se acepta, esta Issue puede pasar a REUSE_ADR para esos AC sin cambiarlos. **A confirmar en la revisión de la v2.**
- Plan vigente / versión: **v2**, este archivo en la rama `plan/31-informe-peritaje-v2`; el commit exacto se registra en un comentario de la Issue. Versión de partida: v1 en `main` `633cf9b` (se conserva). [Solicitud de replanificación](https://github.com/lvckss/piia2-26/issues/31) de Víctor, 2026-10-21.
- Riesgo y revisión previa: **sí, por solicitud expresa**. Por riesgo no haría falta (sin NEW_ADR, reversible, sin consumidores que dependan del formato del texto), pero el equipo acordó en el reparto de la Entrega 1 que los planes de #30, #31, #32 y #34 vayan como archivo en una PR y que Lucas revise los de Víctor antes de implementar. Según AGENTS.md («respetar también revisión previa expresamente solicitada») eso activa el camino con revisión previa: Spec Revisada y Planning PR aprobada e integrada por un humano antes de implementar. Impacto medio (es lo que lee el usuario final; un importe falso sería grave), reversibilidad alta (función nueva, sin datos persistentes), incertidumbre baja (código de referencia probado en la guía).
- Planning PR: v2 https://github.com/lvckss/piia2-26/pull/58 (v1: https://github.com/lvckss/piia2-26/pull/41, integrada). La aprueba una persona distinta del autor (revisor acordado en el reparto: Lucas). Al aprobarla, la spec pasa a Revisada y se registran quién la acepta, el permalink y la versión.

### Cambios de la v2 respecto a la v1

- **AC-010 retirado sin renumerar** (su ID no se reutiliza): la #28 se aparcó por decisión humana de Lucía el 2026-10-20 ([registro](https://github.com/lvckss/piia2-26/issues/31#issuecomment-6297183738)); `vehiculo_id` es siempre un dato de entrada. Se quitan la cabecera del coche estimado, su fila del Test Plan y la slice 5.
- **AC-014 y AC-015 nuevos:** el informe consume `diagnostico_rag`, el campo que la #32 (PR #56, ADR 0006 Propuesto) propone añadir a la salida del Agente 2. Decisión de Víctor del 2026-10-21 (opción b de la decisión 3 del plan del equipo).
- Los demás AC no cambian.

## Qué construir

Una función determinista del Agente 3, `generar_informe(agente1, agente2, hoy=None) -> str`, en
`entregas/cu-19-interpretacion-danos/app/agentes/agente_redactor/informe.py`, que redacta un
**informe de peritaje en markdown** a partir de la salida del Agente 1 (hallazgos) y de la del
Agente 2 (costes, cobertura y normativa), y una función `comprobar_cifras(informe, agente2) -> list[float]`
que devuelve los importes en euros del informe que **no** están entre los **campos monetarios** de
la salida del Agente 2 (lista vacía = ninguna cifra inventada). Campos monetarios: los valores de
las claves terminadas en `_eur`, el `importe_eur` de cada línea y los valores de `desglose`. Otros
números del JSON (`image_id`, `km`, `edad_anios`, cantidades, probabilidades) no cuentan como
importes permitidos (AC-013).

El informe tiene estas secciones, con estos encabezados y en este orden:

1. **Cabecera** (`# Informe de peritaje — imagen <image_id>`): fecha, vehículo (marca y modelo
   del catálogo para el `vehiculo_id` del siniestro, que es siempre un dato de entrada), taller (tipo
   y región), póliza (producto) y el aviso legal fijado en AC-001. Si el diagnóstico del RAG indica
   que faltan fuentes (`parcial`, `sin_resultados` o `error`), también el **aviso de informe
   preliminar** (AC-014).
2. `## Resumen`: número de detecciones de PIIA-1 (`resumen_filtro_previo.detecciones_totales` del
   Agente 1, las que llegaron antes del filtro previo) frente al número de hallazgos analizados y de
   hallazgos de cada grupo, coste de los dos escenarios
   (sin IVA y con IVA), pérdida total en cada escenario e indemnización estimada en cada escenario.
3. `## Daños confirmados`: pieza, tipo de daño, severidad, reparación prevista y score.
4. `## Daños pendientes de revisión`: los mismos datos más **por qué** están pendientes, con la
   advertencia de que requieren verificación humana.
5. `## Detecciones no incluidas en el coste`: cada hallazgo de `hallazgos_fuera_del_coste` con su
   motivo explicado.
6. `## Desglose del coste`: tabla con dos columnas (solo confirmados / con pendientes) por
   concepto, subtotal sin IVA, IVA y total con IVA.
7. `## Posibles daños asociados (no incluidos en el coste)`: los `arrastres_posibles`.
8. `## Cobertura e indemnización`: cobertura, motivo, franquicia e indemnización de **cada**
   escenario.
9. `## Fuentes consultadas`: la `normativa` con su fuente, o «Sin fuentes»; y, si el diagnóstico
   del RAG lo indica, cada tema cuya consulta no recuperó fuentes, con el motivo (AC-014).

**Todas las cifras, tablas y listas se generan con código a partir de los JSON**; ningún importe
se calcula ni se escribe a mano. No se usa ningún modelo de lenguaje.

Encaja al final de la cadena: Agente 1 (`agente_multimodal/agente1.py`) → Agente 2 (#30, #32) →
**Agente 3** → informe para el usuario. La orquestación (#34) llamará a `generar_informe`. El
código de referencia de `specs/agente3-informe-guia.md` es el punto de partida.

### Estado actual (exploración en solo lectura, `origin/main` en `5bdabe2`)

| Qué | Evidencia |
|---|---|
| No existe código productivo del Agente 3: la carpeta solo tiene un README. | `app/agentes/agente_redactor/README.md` |
| La entrada está fijada por ejemplos: 5 hallazgos (`160-1` y `160-4` confirmados; `160-3` pendiente por score 0,68; `160-5` pendiente con visión incierta; `160-2` rechazado por la visión) y la salida del Agente 2 con dos escenarios, 6 `arrastres_posibles`, 2 extractos de `normativa` y el campo `estimacion.aviso`. | `app/agentes/ejemplos_contrato/{agente1_salida,agente2_salida,contexto_siniestro}.json` |
| Cifras del ejemplo: `confirmados` 1.019,46 € sin IVA / 1.233,55 € con IVA / 933,55 € de indemnización; `con_pendientes` 1.488,23 € / 1.800,76 € / 1.500,76 €; valor venal 17.491,54 €; franquicia 300,00 €. | `agente2_salida.json` |
| La guía trae un generador de referencia (`generar_informe`, `comprobar_cifras`, `importes_en_euros`) y una prueba mínima (`probar_informe.py`), además de 5 casos a probar (tercero, sin confirmados, todos rechazados, pérdida total, sin arrastres y sin normativa). | `specs/agente3-informe-guia.md`, pasos 2 y 3 |
| El generador de referencia solo muestra la cobertura del escenario `confirmados` en la sección de cobertura. | Ídem, sección «Cobertura e indemnización» del código |
| El contrato Agente 2 → Agente 3 y los tres motivos de `hallazgos_fuera_del_coste` están en la arquitectura; el Agente 2 se planifica en la #30 (PR #40) sin cambiar ese contrato. | `specs/piia2-arquitectura-multiagente.md`; `specs/30-costes-cobertura.md` (rama `plan/30-costes-cobertura`) |
| La Issue #28 (categoría del vehículo) está **aparcada** desde el 2026-10-20 por decisión de Lucía: el coche es siempre dato de entrada. | [registro en la #31](https://github.com/lvckss/piia2-26/issues/31#issuecomment-6297183738) |
| El plan del RAG (#32, PR #56 en borrador, ADR 0006 Propuesto) propone añadir `diagnostico_rag` a la salida del Agente 2: `estado` (`recuperadas`, `parcial`, `sin_resultados`, `error`, `no_aplica`) y `consultas` (cada una con `tema`, `estado`, `fuentes` e `incidencias` con `codigo`, `etapa`, `mensaje` y `reintentable`). Pide que la #31 muestre las incidencias y el carácter preliminar en `parcial`, `sin_resultados` o `error`, con el texto de referencia «Informe preliminar: no se han recuperado fuentes suficientes para respaldar las conclusiones indicadas sobre cobertura e indemnización. Estas conclusiones requieren revisión». | `plan/32-rag-normativa:specs/32-rag-normativa.md` («Contrato propuesto de diagnóstico») |
| El README del caso (PR #39) declara las cifras económicas y de cobertura «orientativas y no vinculantes». | `impl/35-readme-alcance:entregas/cu-19-interpretacion-danos/README.md` |
| Los nombres de piezas, vehículos y pólizas salen de los CSV de la empresa, que no están en git. | `.gitignore`; guía, paso 2 |

## Por qué

El informe de peritaje es el resultado final del sistema y lo que lee el usuario. Hoy no existe:
hay hallazgos y cifras, pero nada los presenta. Además, un informe con un importe inventado es
peor que no tener informe, porque se presenta con autoridad. Por eso el informe se genera con
código a partir de las salidas de los agentes anteriores, separa siempre lo confirmado de lo
pendiente y se comprueba automáticamente que cada importe en euros procede del Agente 2.

## Alcance

- Incluido: las 9 secciones descritas arriba; separación de confirmados, pendientes y no
  incluidos, con el motivo de cada pendiente y de cada no incluido; los dos escenarios de coste;
  pérdida total, cobertura e indemnización de cada escenario; normativa con su fuente o «Sin
  fuentes»; aviso legal; presentación del diagnóstico del RAG (`diagnostico_rag`, condicionado al
  contrato de la #32); comprobación automática de cifras; validación de la coherencia de las entradas; casos límite de la guía.
- Fuera de alcance: informe en PDF; calcular o corregir cifras (Agente 2, #30); el RAG (#32); la
  orquestación y ADK (#33, #34); un párrafo de resumen redactado por un modelo de lenguaje (paso 4
  opcional de la guía); comprobar que existen los ficheros de imagen enlazados; modificar los
  Agentes 1 y 2 o sus ejemplos; el coche estimado por visión (#28, aparcada; AC-010 retirado);
  calcular o validar el diagnóstico del RAG, que solo se presenta tal como llega.

## Restricciones y supuestos

- Sin LLM ni red: solo librería estándar y los CSV de la empresa. Funciona sin `OPENAI_API_KEY`.
- No se suben a git el paquete de la empresa, ni CarDD, ni claves.
- El paquete se localiza en `<raíz del repo>/piia2_paquete_datos/`. Si falta, el módulo falla con
  un mensaje que dice dónde extraerlo.
- Números en formato español en todo el informe: importes con separador de miles y dos decimales
  (`1.233,55 €`) y scores con coma decimal y dos decimales (`0,55`). La comprobación de cifras
  reconoce los importes seguidos de `€`, con o sin separador de miles. El patrón de
  `importes_en_euros` de la guía **no se copia tal cual**: con `1234,56 €` devuelve `[234.56]`
  (pierde el «1»), y AC-004 debe salir en rojo contra él.
- Forma del escenario vacío: el informe asume que cada escenario del Agente 2 trae siempre
  `estimacion` con `desglose` (las 6 categorías), `subtotal_sin_iva_eur`, `iva_eur`,
  `total_con_iva_eur`, `lineas` y `arrastres_posibles`, y `cobertura` con sus 5 claves, aunque no
  haya hallazgos (importes 0 y listas vacías). Esa forma la fija `specs/30-costes-cobertura.md#AC-007`.
- La fecha del informe es un parámetro (`hoy`); por defecto, la fecha del sistema. Las pruebas
  la fijan para que el resultado sea reproducible.
- `diagnostico_rag` es **opcional** en la entrada: la salida de `estimar_siniestro` (#30) no lo trae
  hasta que la #32 componga `agente2()`. Sin el campo, el informe se comporta como en la v1 (AC-015).
  Con el campo, del diagnóstico solo se muestran `tema` y `mensaje` de cada incidencia (textos
  pensados para el informe según la #56); `codigo`, `etapa` y `reintentable` no se muestran. El
  informe nunca califica una cita o una conclusión como «verificada»: `recuperadas` solo acredita
  que hubo recuperación (#56).

| Incertidumbre | Clasificación | Evidencia / supuesto / pregunta y efecto |
|---|---|---|
| ¿Entra en esta Issue el párrafo de resumen redactado por un LLM (paso 4 de la guía)? | Supuesto explícito aceptable, a confirmar en la revisión | Fuera de alcance: la Issue no lo pide, la guía lo marca como opcional y añadiría red, clave y una fuente de cifras no deterministas. Si se quiere, va en otra Issue reutilizando `comprobar_cifras`. |
| Plantilla del informe (secciones, encabezados, orden) y nivel de detalle. | Resuelta en este plan (la Issue lo delega al plan) | Se fijan las 9 secciones de «Qué construir», que son las 8 de la guía con la cabecera separada. Cambios de redacción que respeten los AC son ajuste interno; cambiar encabezados u orden exige actualizar AC-001 con replanificación. |
| ¿Entra en esta Issue mirar 3-4 informes de peritaje reales y justificar la plantilla con ellos? | Supuesto explícito aceptable, a confirmar en la revisión (decisión de alcance) | La guía lo incluye en su «Definición de terminado», pero la Issue no lo pide. Se propone dejarlo fuera de esta Issue: la plantilla queda fijada por este plan y por la guía. Si el revisor lo quiere dentro, se añade como condición de la DoD específica (documento con los informes consultados y la justificación), sin cambiar los AC. |
| Texto del aviso legal. | Resuelta en este plan, a confirmar en la revisión | Se fija en AC-001, combinando la guía («no sustituye a una valoración pericial») y el README del caso de la PR #39 («orientativas y no vinculantes»). |
| La sección de cobertura del generador de referencia solo muestra el escenario `confirmados`. | Resuelta con evidencia | La guía (paso 3) pide que el informe explique la diferencia entre escenarios cuando la pérdida total solo se da en uno; se muestran los dos (AC-008). |
| ¿Qué «póliza» muestra la cabecera de un tercero perjudicado (sin `poliza_id`)? | Supuesto explícito aceptable | «Terceros (RC obligatoria)», como el generador de referencia, y el rol se indica en la cabecera (AC-006). |
| La comprobación de cifras solo reconoce importes seguidos de `€`. | Supuesto explícito aceptable (límite declarado) | Todos los importes los escribe una única función de formato. Un importe con `€`, con o sin separador de miles, se reconoce entero (AC-004). Importes sin `€` no se comprueban; el informe no los usa. |
| ¿Qué números de la salida del Agente 2 acepta `comprobar_cifras` como importes permitidos? | Resuelta en la revisión de la PR #41 | En la versión `f61a637` se dejaba como límite conocido que aceptara cualquier número del JSON. Lucía ([comentario](https://github.com/lvckss/piia2-26/pull/41#discussion_r4303254003)) y Lucas (revisión del 2026-10-17) piden restringirlo: con el límite, importes inventados como `160,00 €`, `42.000,00 €` o `3,00 €` pasaban por coincidir con `image_id`, `km` o `edad_anios`. Se restringe a los campos monetarios (ver «Qué construir») y se añade AC-013. |
| ¿Se aprueba la #28 (aviso de origen del coche)? | Resuelta (decisión humana) | Aparcada por Lucía el 2026-10-20 ([registro](https://github.com/lvckss/piia2-26/issues/31#issuecomment-6297183738)); equivale a «rechazado»: AC-010 retirado sin renumerar, como preveía la v1. |
| ¿Se incorpora ya `diagnostico_rag` a esta spec (decisión 3 del plan del equipo)? | Resuelta (decisión humana) | Víctor, sesión del 2026-10-21: opción b, incorporarlo ya ([solicitud](https://github.com/lvckss/piia2-26/issues/31)). |
| ¿Se acepta el contrato de `diagnostico_rag` tal como lo propone la #56? | Bloqueante para Ready (solo para AC-014 y AC-015) | Propuesto en la #56 (borrador) y en el ADR 0006 (Propuesto). Si se acepta tal cual, AC-014 y AC-015 se implementan como están. Si cambia, se actualizan conservando sus IDs con una versión nueva del plan. Si se rechaza, se retiran sin renumerar y la v1 vuelve a bastar. |
| Nombre del vehículo y producto de la póliza del ejemplo. | Resuelta con evidencia | Comprobado por Lucía con los CSV de la empresa ([comentario](https://github.com/lvckss/piia2-26/pull/41#discussion_r4303254008)): `V05` = Volkswagen Golf y `P-TR-FR300` = «Todo Riesgo con franquicia 300 EUR». AC-001 fija esos literales. |
| ¿Deben estar integrados los ADRs de la #37 antes de implementar esta Issue? (`docs/adr/README.md` pide registrar las decisiones estructurales previas antes de implementar cambios que dependan de ellas.) | Resuelta (decisión humana); bloqueante para Ready | Decisión del equipo, comunicada por Víctor en la sesión del 2026-10-19: **los ADRs se integran en `main` antes de la implementación** (común a #28, #30 y #31, como pedía Lucas). Efecto en esta Issue: no pasa a Ready hasta que los ADRs de la #37 que registran las decisiones de las que depende (el contrato Agente 1 → Agente 2 → Agente 3) estén Aceptados e integrados en `main`; mientras, sigue en Especificando. La ADR decision de esta Issue sigue siendo NO_ADR_REQUIRED, porque no introduce ni cambia ninguna decisión; si la revisión considera que debe referenciar esos ADRs, pasa a REUSE_ADR sin cambiar los AC. |
| La #30 aún no está implementada. | Resuelta con evidencia | El Agente 3 solo depende del contrato (los ejemplos), no del código del Agente 2. |

## Comportamiento que debe preservarse

- No existe código previo del Agente 3: no hay regresiones de código que proteger.
- Los contratos de entrada (`agente1_salida.json`, `agente2_salida.json`) no se modifican; el
  informe los consume tal cual. Lo protegen AC-001 a AC-003, que usan los ejemplos sin editar.
- Una salida del Agente 2 **sin** `diagnostico_rag` produce el mismo informe que en la v1. Lo protege
  AC-015.

## Failure modes y requisitos no funcionales

| Condición | Comportamiento esperado | Cobertura |
|---|---|---|
| Un importe del informe no procede del Agente 2. | `comprobar_cifras` lo devuelve; las pruebas fallan. | AC-003, AC-004 |
| Un importe inventado coincide con un número no monetario del JSON del Agente 2 (`image_id`, `km`, `edad_anios`). | `comprobar_cifras` lo devuelve igualmente. | AC-013 |
| El RAG no recuperó fuentes para algún tema, o falló (`parcial`, `sin_resultados`, `error`). | Aviso de informe preliminar en la cabecera y tema afectado con su motivo en «Fuentes consultadas»; las citas recuperadas se siguen mostrando. | AC-014 |
| `diagnostico_rag` ausente. | Mismo informe que en la v1. | AC-015 |
| `diagnostico_rag` malformado. | Excepción explícita que nombra el campo; no se devuelve informe. | AC-015 |
| `normativa` vacía. | «Sin fuentes»; ninguna fuente inventada. | AC-005 |
| Ningún hallazgo confirmado, o todos rechazados. | Secciones vacías con «Ninguno», sin excepción ni tablas rotas. | AC-007 |
| Sin `arrastres_posibles`. | «Ninguno previsto». | AC-009 |
| Entradas incoherentes: un `finding_id` del Agente 2 que no existe en el Agente 1, un hallazgo del Agente 1 que no aparece en ningún grupo del Agente 2, `image_id` distintos, `vehiculo_id` o `pieza_id` fuera del catálogo. | Excepción explícita que nombra el identificador; no se devuelve informe. Ningún hallazgo desaparece del informe sin dejar rastro. | AC-011 |
| Escenario sin hallazgos. | Se presenta con importes 0 gracias a la forma fija del escenario vacío. | AC-007 |
| Paquete de la empresa ausente. | Error al importar que indica la ruta esperada. | AC-011 |
| Determinismo. | Mismas entradas y misma fecha → mismo informe, sin red ni clave. | AC-012 |
| Rendimiento. | No aplica: formateo local de milisegundos; sin requisito. | — |

## Acceptance Criteria

| ID | Dado / Cuando | Resultado esperado y condición de éxito |
|---|---|---|
| AC-001 | Los ejemplos del contrato (`agente1_salida.json`, `agente2_salida.json`) y se llama a `generar_informe(agente1, agente2, hoy="2026-10-14")`. | El markdown contiene los 9 encabezados de «Qué construir» en ese orden. La cabecera contiene la fecha `2026-10-14`, `Volkswagen Golf` (`V05` en `vehiculos.csv`), `multimarca`, `Madrid`, `Todo Riesgo con franquicia 300 EUR` (`P-TR-FR300` en `polizas.csv`) y, literalmente, el aviso: «Informe generado automáticamente con datos sintéticos de prototipo. Las cifras son orientativas y no vinculantes, y no sustituyen a una valoración pericial.» «Resumen» indica las `31` detecciones de PIIA-1 (`resumen_filtro_previo.detecciones_totales`) frente a los `5` hallazgos analizados. |
| AC-002 | La misma entrada de AC-001. | `160-1` y `160-4` aparecen solo en «Daños confirmados»; `160-3` y `160-5` solo en «Daños pendientes de revisión», cada uno con todos sus motivos (`160-3`: score de detección bajo, `0,68`; `160-5`: score de detección bajo, `0,55`, y la visión lo ve incierto), con los scores en formato español, y la sección incluye la advertencia de verificación humana; `160-2` solo en «Detecciones no incluidas en el coste», con el motivo de rechazo por la visión. Cada `finding_id` de la entrada aparece en una única de esas tres secciones. |
| AC-003 | La misma entrada de AC-001. | `comprobar_cifras(informe, agente2) == []`, y el informe contiene `1.019,46 €`, `1.233,55 €`, `1.488,23 €`, `1.800,76 €`, `933,55 €` y `1.500,76 €`. |
| AC-004 | El informe de AC-001 al que se añade una línea con `1.234,56 €`, y otro al que se añade `1234,56 €`. | En los dos casos `comprobar_cifras` devuelve exactamente `[1234.56]` (el importe se reconoce entero, con o sin separador de miles). |
| AC-005 | La entrada de AC-001 con `normativa` vacía, y la original con 2 extractos. | Vacía: «Fuentes consultadas» contiene «Sin fuentes» y ninguna otra entrada. Original: aparecen los 2 extractos, cada uno con su tema y su fuente. |
| AC-006 | Una salida del Agente 2 de tercero perjudicado (`rol = "tercero_perjudicado"`, `poliza_id` vacío, cobertura de RC obligatoria). | No se lanza excepción; la cabecera indica que el perjudicado es un tercero y la póliza «Terceros (RC obligatoria)»; la sección de cobertura muestra el motivo y la indemnización de cada escenario tal como vienen; `comprobar_cifras` devuelve `[]`. |
| AC-007 | Una salida sin hallazgos confirmados (escenario `confirmados` vacío) y otra con todos los hallazgos rechazados por la visión (los dos escenarios vacíos). Los escenarios vacíos tienen la forma de `specs/30-costes-cobertura.md#AC-007` (mismas claves, importes 0, listas vacías). | No se lanza excepción; las secciones sin hallazgos muestran «Ninguno»; los importes de los escenarios vacíos aparecen como `0,00 €`; en el segundo caso todos los `finding_id` están en «Detecciones no incluidas en el coste»; `comprobar_cifras` devuelve `[]`. |
| AC-008 | Una salida con `perdida_total == true` solo en `con_pendientes`. | «Resumen» y «Cobertura e indemnización» indican «No» para `confirmados` y «Sí» para `con_pendientes`, y la sección de cobertura muestra para cada escenario su motivo, franquicia e indemnización. |
| AC-009 | La entrada de AC-001 (6 `arrastres_posibles`) y otra con `arrastres_posibles` vacío en los dos escenarios. | Con arrastres: cada pieza aparece con su nombre del catálogo y su probabilidad, en la sección que indica que no están incluidos en el coste. Sin arrastres: «Ninguno previsto». |
| AC-010 | **Retirado en la v2** (2026-10-20). | La #28 se aparcó por decisión de Lucía ([registro](https://github.com/lvckss/piia2-26/issues/31#issuecomment-6297183738)). El ID no se reutiliza. El texto de la v1 se conserva en `main` `633cf9b`. |
| AC-011 | Entradas incoherentes: un `finding_id` en `hallazgos_incluidos` o en `hallazgos_fuera_del_coste` que no existe en el Agente 1; un hallazgo del Agente 1 que no está en ningún grupo del Agente 2 (ni en los escenarios ni fuera del coste); `image_id` distintos entre Agente 1 y Agente 2; `vehiculo_id` o `pieza_id` que no están en el catálogo; o el paquete de la empresa no está en su ruta. | Se lanza una excepción cuyo mensaje nombra el identificador o la ruta problemática; no se devuelve informe. |
| AC-012 | Se llama dos veces a `generar_informe` con las mismas entradas y la misma fecha, sin `OPENAI_API_KEY` y sin red. | Los dos informes son idénticos y la ejecución no necesita clave ni red. |
| AC-013 | El informe de AC-001 al que se añade, en tres variantes, una línea con `160,00 €`, `42.000,00 €` o `3,00 €` (coinciden con `image_id`, `km` y `edad_anios` del JSON del Agente 2, que no son importes). | En cada variante `comprobar_cifras` devuelve exactamente el importe añadido: `[160.0]`, `[42000.0]` y `[3.0]`. |
| AC-014 | (Condicionado al contrato de `diagnostico_rag` aceptado e integrado en la #32.) La entrada de AC-001 con `diagnostico_rag` en cada uno de sus cinco estados: `recuperadas`; `parcial` (una consulta `recuperadas` con su cita, otra `sin_resultados` y otra `error` con una incidencia); `sin_resultados`; `error`; y `no_aplica`. | Con `parcial`, `sin_resultados` o `error`: la cabecera contiene literalmente el aviso de informe preliminar de la #56, «Informe preliminar: no se han recuperado fuentes suficientes para respaldar las conclusiones indicadas sobre cobertura e indemnización. Estas conclusiones requieren revisión», y «Fuentes consultadas» muestra, por cada consulta que no terminó en `recuperadas`, su `tema` y el `mensaje` de cada incidencia (o «sin resultados» si no tiene incidencias); en `parcial`, la cita de la consulta correcta se sigue mostrando. Con `recuperadas` o `no_aplica`: no aparece el aviso preliminar. En ninguno de los cinco casos aparece la palabra «verificada» aplicada a una cita o conclusión, ni se muestran `codigo`, `etapa` o `reintentable`. `comprobar_cifras` devuelve `[]` en los cinco. |
| AC-015 | Una salida del Agente 2 sin el campo `diagnostico_rag` (como la del ejemplo actual o la de `estimar_siniestro` de la #30); y otra con `diagnostico_rag` malformado: `estado` fuera de los cinco valores, o una consulta sin `tema`. | Sin el campo: el informe es idéntico al que genera la v1 con la misma entrada y no hay aviso preliminar (AC-001 a AC-005 se siguen cumpliendo). Malformado: se lanza una excepción cuyo mensaje nombra el campo problemático; no se devuelve informe. |

## Test Plan

### Test seams

- **S1 — `generar_informe(agente1, agente2, hoy=None) -> str`:** función pública nueva; es lo que
  consumirá la orquestación (#34). Cubre AC-001 a AC-003, AC-005 a AC-009, AC-011, AC-012, AC-014 y AC-015.
- **S2 — `comprobar_cifras(informe, agente2) -> list[float]`:** función pública nueva que la Issue
  exige como comprobación automática. Cubre AC-003, AC-004 y AC-013.
- **S3 — Catálogo de la empresa (`vehiculos.csv`, `piezas.csv`, `polizas.csv`, `reglas_dano.csv`):**
  dependencia real, no se simula.
- No se prueban funciones internas (formato de euros, tablas, motivos) como contrato.

Siguiendo el estilo del repo (`probar_*.py` ejecutables con `python`), las pruebas van en
`app/agentes/agente_redactor/probar_informe.py`. Los casos límite se construyen en la propia prueba
copiando y editando en memoria los JSON de ejemplo, sin ficheros nuevos de fixtures. Cada
comprobación lleva en su nombre o comentario `31-informe-peritaje.md#AC-0XX`.

| Referencia (ruta de Spec + AC) | Seam / contrato | Estrategia y nivel | Caso / resultado esperado | Datos / entorno | Comando o pasos previstos | Evidencia prevista |
|---|---|---|---|---|---|---|
| `specs/31-informe-peritaje.md#AC-001` | S1 + S3 | TDD (Red → Green); contrato de salida | 9 encabezados en orden; cabecera con fecha, `Volkswagen Golf`, taller, `Todo Riesgo con franquicia 300 EUR` y aviso literal; 31 detecciones frente a 5 hallazgos | `ejemplos_contrato/`; paquete de la empresa; `hoy="2026-10-14"` | `python probar_informe.py` | Red por el comportamiento: `informe.py` importa sin error y `generar_informe` existe, pero la prueba falla porque el informe aún no tiene los 9 encabezados, la cabecera y el aviso exigidos (un error de importación o un módulo ausente no acredita el Red); después, Green |
| `specs/31-informe-peritaje.md#AC-002` | S1 | TDD | Cada `finding_id` en una sola sección; `160-5` con sus dos motivos; scores con coma decimal | Ídem | `python probar_informe.py` | Red y Green |
| `specs/31-informe-peritaje.md#AC-003` | S1 + S2 | TDD | Sin importes inventados; los 6 importes presentes | Ídem | `python probar_informe.py` | Red y Green |
| `specs/31-informe-peritaje.md#AC-004` | S2 | TDD | `[1234.56]` exacto para `1.234,56 €` y para `1234,56 €` | Informe de AC-001 modificado en memoria | `python probar_informe.py` | Red (también contra el patrón de la guía, que devuelve `[234.56]`) y Green |
| `specs/31-informe-peritaje.md#AC-005` | S1 | TDD | «Sin fuentes» / 2 extractos con fuente | `normativa` vaciada en memoria | `python probar_informe.py` | Red y Green |
| `specs/31-informe-peritaje.md#AC-006` | S1 + S2 | TDD | Tercero sin excepción, cabecera y cobertura correctas | Copia de `agente2_salida.json` con contexto de tercero y cobertura de RC | `python probar_informe.py` | Red y Green |
| `specs/31-informe-peritaje.md#AC-007` | S1 + S2 | TDD | Sin confirmados y todos rechazados sin romperse | Copias con escenarios vaciados con la forma de `30-costes-cobertura.md#AC-007` (importes 0, listas vacías) y hallazgos movidos a fuera del coste | `python probar_informe.py` | Red y Green |
| `specs/31-informe-peritaje.md#AC-008` | S1 | TDD | Pérdida total distinta por escenario explicada | Copia con `perdida_total` en `con_pendientes` | `python probar_informe.py` | Red y Green |
| `specs/31-informe-peritaje.md#AC-009` | S1 + S3 | TDD | Arrastres con nombre y probabilidad / «Ninguno previsto» | Ejemplo y copia sin arrastres | `python probar_informe.py` | Red y Green |
| `specs/31-informe-peritaje.md#AC-010` | — | Retirado en la v2 | — | — | — | Sin verificación: AC retirado con referencia a la decisión sobre la #28 |
| `specs/31-informe-peritaje.md#AC-011` | S1 + S3 | TDD | Excepción que nombra el identificador o la ruta | Copias incoherentes en los dos sentidos (id del Agente 2 inexistente en el Agente 1; hallazgo del Agente 1 sin grupo en el Agente 2); para el paquete ausente, copia del módulo en un directorio temporal con un `.git` vacío y sin `piia2_paquete_datos/`, importada en un subproceso | `python probar_informe.py` | Red y Green |
| `specs/31-informe-peritaje.md#AC-012` | S1 | TDD | Dos informes idénticos sin clave ni red | `OPENAI_API_KEY` eliminada del entorno del proceso y `socket.socket` sustituido durante la prueba por una función que lanza excepción | `python probar_informe.py` | Green (igualdad, sin intento de conexión) |
| `specs/31-informe-peritaje.md#AC-013` | S2 | TDD | `[160.0]`, `[42000.0]` y `[3.0]` para los tres importes inventados que coinciden con números no monetarios | Informe de AC-001 modificado en memoria; `agente2_salida.json` sin editar | `python probar_informe.py` | Red (contra la versión que acepta cualquier número del JSON) y Green |
| `specs/31-informe-peritaje.md#AC-014` | S1 + S2 | TDD (cuando el contrato de la #32 esté integrado) | Aviso preliminar literal solo en `parcial`, `sin_resultados` y `error`; tema y `mensaje` de cada consulta fallida; cita de la consulta correcta conservada en `parcial`; nunca «verificada»; `comprobar_cifras` == `[]` | Copias en memoria de `agente2_salida.json` con un `diagnostico_rag` por estado, construido según el contrato integrado de la #32 (o su ejemplo, si lo publica) | `python probar_informe.py` | Red por comportamiento y Green, o AC actualizado/retirado con referencia a la decisión de la #32 |
| `specs/31-informe-peritaje.md#AC-015` | S1 | TDD | Sin el campo: informe idéntico al de la v1 (comparación con el informe generado sin el campo); malformado: excepción que nombra el campo | `agente2_salida.json` sin editar; copias con `estado` inválido y con una consulta sin `tema` | `python probar_informe.py` | Red y Green |

## Implementation Plan

| Slice | Objetivo observable | AC relacionados | Componentes / contratos probablemente afectados | Dependencias | Verificación prevista |
|---|---|---|---|---|---|
| 1 — Informe del ejemplo | `generar_informe` produce el informe completo del ejemplo, con secciones, separación, normativa y arrastres. | AC-001, AC-002, AC-005, AC-009 | `agente_redactor/informe.py` (nuevo) | Paquete de la empresa extraído en local | Filas AC-001, AC-002, AC-005, AC-009 |
| 2 — Cifras comprobadas | `comprobar_cifras` acepta el informe del ejemplo y detecta importes inventados, también los que coinciden con números no monetarios. | AC-003, AC-004, AC-013 | Ídem | Slice 1 | Filas AC-003, AC-004, AC-013 |
| 3 — Casos límite | Tercero, sin confirmados, todo rechazado, pérdida total en un solo escenario. | AC-006, AC-007, AC-008 | Ídem | Slices 1 y 2 | Filas AC-006 a AC-008 |
| 4 — Robustez de la entrada | Errores explícitos ante entradas incoherentes o paquete ausente; ejecución determinista sin red. | AC-011, AC-012 | Ídem | Slice 1 | Filas AC-011, AC-012 |
| 5 — Origen del coche | **Retirada en la v2** (AC-010 retirado; #28 aparcada). | — | — | — | — |
| 6 — Diagnóstico del RAG | El informe presenta `diagnostico_rag` (aviso preliminar e incidencias por tema) y no cambia si el campo no viene. | AC-014, AC-015 | Ídem; contrato de la #32 | Slices 1 y 2; contrato de `diagnostico_rag` aceptado e integrado (#56 y ADR 0006). AC-015 (campo ausente) puede hacerse antes. | Filas AC-014, AC-015 |

Al terminar, el README de `agente_redactor/` indica cómo ejecutar las pruebas y generar el informe
de ejemplo.

## Pendientes para Ready

- **Revisión previa de la v2 (solicitud del equipo):** cumplida: Planning PR #58 aprobada por Lucas García sobre el head final `0deba77` ([revisión](https://github.com/lvckss/piia2-26/pull/58#pullrequestreview-5615735502)) e integrada por él (merge `73f6075`). Esta spec registra la aceptación en una corrección documental posterior (solo metadatos).
- **Contrato de `diagnostico_rag` aceptado e integrado en la #32** (PR #56 y ADR 0006), del que dependen AC-014 y AC-015. Si cambia o se rechaza, se actualizan o retiran esos AC conservando sus IDs antes de Ready.
- **Confirmaciones ya dadas en la revisión de `f61a637`** (Lucía, 2026-10-17): de acuerdo con NO_ADR_REQUIRED, con el texto del aviso legal (AC-001) y con dejar fuera de alcance el párrafo con LLM y la revisión de informes reales. Se mantienen en la versión aprobada por Lucas (`17502ac`), que además incluye la restricción de `comprobar_cifras` a campos monetarios (AC-013).
- Forma del escenario vacío (dependencia de AC-007): **resuelta**, la PR #40 está integrada en `main` (`e950b50`).
- Resolución de la #28: **resuelta** (aparcada el 2026-10-20, [registro](https://github.com/lvckss/piia2-26/issues/31#issuecomment-6297183738)); AC-010 retirado en esta v2.
- ADRs de la #37 (decisión del equipo del 2026-10-19): **resuelto**, el ADR 0002 (contrato entre agentes) está Aceptado en `main` (`4a279e9`).
- **Prerrequisito de implementación (no de planificación):** extraer `piia2_paquete_datos/` en la raíz del repo.

Resultado de analyze:

| Comprobación | Resultado |
|---|---|
| Cada requisito de la Issue tiene AC | Cabecera y aviso → AC-001; confirmados, pendientes y rechazados aparte → AC-002, AC-007; dos escenarios de coste → AC-003, AC-008; pérdida total, cobertura e indemnización → AC-006, AC-008; normativa con fuente o «Sin fuentes» → AC-005; diagnóstico del RAG (requisito de coordinación de la #32) → AC-014, AC-015; origen del coche → AC-010, retirado con la #28; comprobación automática de cifras → AC-003, AC-004, AC-013; informe completo con los ejemplos → AC-001 a AC-003. |
| AC sin requisito en la Issue | AC-009 (arrastres) viene del contrato y de la guía; AC-011 y AC-012 cubren failure modes. Ninguno amplía el alcance funcional. |
| Cada AC tiene verificación y slice | Sí: AC-001 a AC-009 y AC-011 a AC-015. AC-010, retirado, sin verificación ni slice. |
| Comportamiento preservado | Los contratos de entrada, que no se modifican; los usan sin editar AC-001 a AC-003. |
| ADR decision coherente | NO_ADR_REQUIRED justificado; aceptado por Lucas y por Lucía (ver la cabecera). |
| Gaps | AC-014 y AC-015 dependen del contrato de `diagnostico_rag` de la #32 (Propuesto). No impide revisar la v2; se resuelve antes de Ready. Las dependencias de la v1 (#28, #40 y ADR 0002) ya están resueltas. |

## Definition of Done

| Condición específica de cierre | Evidencia requerida |
|---|---|
| `probar_informe.py` ejecutado **con el paquete de la empresa presente** y en verde. | Salida del comando en la PR de implementación. |
| Informe de ejemplo generado con los JSON del contrato y revisado por una persona como lector. | El markdown generado, pegado o adjunto en la PR de implementación (no se versiona). |
| AC-010 retirado con referencia a la decisión de la #28 (hecho en la v2). | [Registro de la decisión](https://github.com/lvckss/piia2-26/issues/31#issuecomment-6297183738). |
| AC-014 y AC-015 implementados conforme al contrato de `diagnostico_rag` integrado en `main`, o actualizados/retirados con referencia a la decisión de la #32. | Enlace a la PR #56 integrada y a la versión del contrato usada. |
| README de `agente_redactor/` actualizado. | Diff de la PR. |
