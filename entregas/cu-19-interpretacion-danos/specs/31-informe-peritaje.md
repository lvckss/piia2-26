# Spec: Agente 3 — informe de peritaje en markdown con cifras verificadas

- GitHub Issue: https://github.com/lvckss/piia2-26/issues/31
- Estado: Borrador
- ADR decision: NO_ADR_REQUIRED
- ADR: No requerido — justificado en Spec.
- Justificación: el Agente 3 es el último eslabón de la cadena. Consume los contratos ya acordados (salida del Agente 1 y del Agente 2, fijados por `ejemplos_contrato/`) sin cambiarlos y produce un documento markdown para una persona, no un formato que consuma otro agente ni que se persista como schema compartido. Su única interfaz, `generar_informe(agente1, agente2)`, la invocará la orquestación (#34) como una función más. No introduce dependencias externas (solo la librería estándar y los CSV de la empresa ya usados por el Agente 2) ni un trade-off difícil de revertir. El aviso de origen del coche lo decide el ADR 0001 de la Issue #28; aquí solo se consume (AC-010). **A confirmar en la revisión:** que esta justificación no oculta una decisión relevante.
- Plan vigente / versión: este archivo, en la rama `plan/31-informe-peritaje`; el commit exacto se registra en un comentario de la Issue.
- Riesgo y revisión previa: **sí, por solicitud expresa**. Por riesgo no haría falta (sin NEW_ADR, reversible, sin consumidores que dependan del formato del texto), pero el equipo acordó en el reparto de la Entrega 1 que los planes de #30, #31, #32 y #34 vayan como archivo en una PR y que Lucas revise los de Víctor antes de implementar. Según AGENTS.md («respetar también revisión previa expresamente solicitada») eso activa el camino con revisión previa: Spec Revisada y Planning PR aprobada e integrada por un humano antes de implementar. Impacto medio (es lo que lee el usuario final; un importe falso sería grave), reversibilidad alta (función nueva, sin datos persistentes), incertidumbre baja (código de referencia probado en la guía).
- Planning PR: https://github.com/lvckss/piia2-26/pull/41, aprobada por una persona distinta del autor (revisor acordado en el reparto: Lucas). Al aprobarla, la spec pasa a Revisada y se registran quién la acepta, el permalink y la versión.

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

1. **Cabecera** (`# Informe de peritaje — imagen <image_id>`): fecha, vehículo, taller (tipo y
   región), póliza (producto) y el aviso legal fijado en AC-001. El vehículo es la marca y el
   modelo del catálogo cuando el coche es dato de entrada; si se estimó por visión (#28), se muestra
   la **categoría como estimación** y el modelo **solo como coche de referencia** del presupuesto,
   nunca como coche identificado en la imagen (AC-010).
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
9. `## Fuentes consultadas`: la `normativa` con su fuente, o «Sin fuentes».

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
| La Issue #28 (PR #29, ADR 0001 Propuesto) pide que el informe indique si el coche es un dato de entrada o una estimación por visión. | `plan/28-categoria-vehiculo:specs/28-categoria-vehiculo.md#AC-010` |
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
  fuentes»; aviso legal; indicación del origen del coche (condicionado a la #28); comprobación
  automática de cifras; validación de la coherencia de las entradas; casos límite de la guía.
- Fuera de alcance: informe en PDF; calcular o corregir cifras (Agente 2, #30); el RAG (#32); la
  orquestación y ADK (#33, #34); un párrafo de resumen redactado por un modelo de lenguaje (paso 4
  opcional de la guía); comprobar que existen los ficheros de imagen enlazados; modificar los
  Agentes 1 y 2 o sus ejemplos.

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
| ¿Se aprueba la #28 (aviso de origen del coche)? | Pregunta no bloqueante para AC-001 a AC-009 y AC-011 a AC-013; bloqueante solo para AC-010 | Estado registrado el 2026-10-19: PR #29 abierta, sin revisiones; ADR 0001 en estado Propuesto. Si el ADR 0001 se acepta, AC-010 se implementa tal cual. Si se rechaza, AC-010 se retira sin renumerar. Si cambia su alcance, se conserva el ID y se registra el cambio de versión. |
| Nombre del vehículo y producto de la póliza del ejemplo. | Resuelta con evidencia | Comprobado por Lucía con los CSV de la empresa ([comentario](https://github.com/lvckss/piia2-26/pull/41#discussion_r4303254008)): `V05` = Volkswagen Golf y `P-TR-FR300` = «Todo Riesgo con franquicia 300 EUR». AC-001 fija esos literales. |
| ¿Deben estar integrados los ADRs de la #37 antes de implementar esta Issue? (`docs/adr/README.md` pide registrar las decisiones estructurales previas antes de implementar cambios que dependan de ellas.) | Resuelta (decisión humana); bloqueante para Ready | Decisión del equipo, comunicada por Víctor en la sesión del 2026-10-19: **los ADRs se integran en `main` antes de la implementación** (común a #28, #30 y #31, como pedía Lucas). Efecto en esta Issue: no pasa a Ready hasta que los ADRs de la #37 que registran las decisiones de las que depende (el contrato Agente 1 → Agente 2 → Agente 3) estén Aceptados e integrados en `main`; mientras, sigue en Especificando. La ADR decision de esta Issue sigue siendo NO_ADR_REQUIRED, porque no introduce ni cambia ninguna decisión; si la revisión considera que debe referenciar esos ADRs, pasa a REUSE_ADR sin cambiar los AC. |
| La #30 aún no está implementada. | Resuelta con evidencia | El Agente 3 solo depende del contrato (los ejemplos), no del código del Agente 2. |

## Comportamiento que debe preservarse

- No existe código previo del Agente 3: no hay regresiones de código que proteger.
- Los contratos de entrada (`agente1_salida.json`, `agente2_salida.json`) no se modifican; el
  informe los consume tal cual. Lo protegen AC-001 a AC-003, que usan los ejemplos sin editar.

## Failure modes y requisitos no funcionales

| Condición | Comportamiento esperado | Cobertura |
|---|---|---|
| Un importe del informe no procede del Agente 2. | `comprobar_cifras` lo devuelve; las pruebas fallan. | AC-003, AC-004 |
| Un importe inventado coincide con un número no monetario del JSON del Agente 2 (`image_id`, `km`, `edad_anios`). | `comprobar_cifras` lo devuelve igualmente. | AC-013 |
| El coche se estimó por visión. | El informe no presenta el coche de referencia como identificado en la imagen. | AC-010 |
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
| AC-010 | (Condicionado a la aceptación del ADR 0001, #28.) Un informe con `contexto.vehiculo_origen == "estimado_por_vision"`, otro con categoría `desconocido` y otro con `dato_de_entrada`. | El primero muestra en la cabecera la categoría como estimación y el modelo solo como coche de referencia del presupuesto (p. ej. «categoría C (estimada); presupuestado con SEAT León como coche de referencia»), y en ningún lugar presenta ese modelo como el coche identificado en la imagen; el segundo indica que el vehículo no está identificado y que se usó un compacto de referencia; el tercero muestra marca y modelo sin ninguna de las dos advertencias. Misma referencia que `specs/28-categoria-vehiculo.md#AC-010`. |
| AC-011 | Entradas incoherentes: un `finding_id` en `hallazgos_incluidos` o en `hallazgos_fuera_del_coste` que no existe en el Agente 1; un hallazgo del Agente 1 que no está en ningún grupo del Agente 2 (ni en los escenarios ni fuera del coste); `image_id` distintos entre Agente 1 y Agente 2; `vehiculo_id` o `pieza_id` que no están en el catálogo; o el paquete de la empresa no está en su ruta. | Se lanza una excepción cuyo mensaje nombra el identificador o la ruta problemática; no se devuelve informe. |
| AC-012 | Se llama dos veces a `generar_informe` con las mismas entradas y la misma fecha, sin `OPENAI_API_KEY` y sin red. | Los dos informes son idénticos y la ejecución no necesita clave ni red. |
| AC-013 | El informe de AC-001 al que se añade, en tres variantes, una línea con `160,00 €`, `42.000,00 €` o `3,00 €` (coinciden con `image_id`, `km` y `edad_anios` del JSON del Agente 2, que no son importes). | En cada variante `comprobar_cifras` devuelve exactamente el importe añadido: `[160.0]`, `[42000.0]` y `[3.0]`. |

## Test Plan

### Test seams

- **S1 — `generar_informe(agente1, agente2, hoy=None) -> str`:** función pública nueva; es lo que
  consumirá la orquestación (#34). Cubre AC-001 a AC-003 y AC-005 a AC-012.
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
| `specs/31-informe-peritaje.md#AC-001` | S1 + S3 | TDD (Red → Green); contrato de salida | 9 encabezados en orden; cabecera con fecha, `Volkswagen Golf`, taller, `Todo Riesgo con franquicia 300 EUR` y aviso literal; 31 detecciones frente a 5 hallazgos | `ejemplos_contrato/`; paquete de la empresa; `hoy="2026-10-14"` | `python probar_informe.py` | Red (módulo ausente) y Green |
| `specs/31-informe-peritaje.md#AC-002` | S1 | TDD | Cada `finding_id` en una sola sección; `160-5` con sus dos motivos; scores con coma decimal | Ídem | `python probar_informe.py` | Red y Green |
| `specs/31-informe-peritaje.md#AC-003` | S1 + S2 | TDD | Sin importes inventados; los 6 importes presentes | Ídem | `python probar_informe.py` | Red y Green |
| `specs/31-informe-peritaje.md#AC-004` | S2 | TDD | `[1234.56]` exacto para `1.234,56 €` y para `1234,56 €` | Informe de AC-001 modificado en memoria | `python probar_informe.py` | Red (también contra el patrón de la guía, que devuelve `[234.56]`) y Green |
| `specs/31-informe-peritaje.md#AC-005` | S1 | TDD | «Sin fuentes» / 2 extractos con fuente | `normativa` vaciada en memoria | `python probar_informe.py` | Red y Green |
| `specs/31-informe-peritaje.md#AC-006` | S1 + S2 | TDD | Tercero sin excepción, cabecera y cobertura correctas | Copia de `agente2_salida.json` con contexto de tercero y cobertura de RC | `python probar_informe.py` | Red y Green |
| `specs/31-informe-peritaje.md#AC-007` | S1 + S2 | TDD | Sin confirmados y todos rechazados sin romperse | Copias con escenarios vaciados con la forma de `30-costes-cobertura.md#AC-007` (importes 0, listas vacías) y hallazgos movidos a fuera del coste | `python probar_informe.py` | Red y Green |
| `specs/31-informe-peritaje.md#AC-008` | S1 | TDD | Pérdida total distinta por escenario explicada | Copia con `perdida_total` en `con_pendientes` | `python probar_informe.py` | Red y Green |
| `specs/31-informe-peritaje.md#AC-009` | S1 + S3 | TDD | Arrastres con nombre y probabilidad / «Ninguno previsto» | Ejemplo y copia sin arrastres | `python probar_informe.py` | Red y Green |
| `specs/31-informe-peritaje.md#AC-010` | S1 | TDD (si se acepta el ADR 0001) | Tres casos según origen del coche; con `estimado_por_vision`, la categoría como estimación y el modelo solo como coche de referencia | Copias con `vehiculo_origen` y `vehiculo` según la #28 | `python probar_informe.py` | Red y Green, o AC retirado con referencia a la decisión |
| `specs/31-informe-peritaje.md#AC-011` | S1 + S3 | TDD | Excepción que nombra el identificador o la ruta | Copias incoherentes en los dos sentidos (id del Agente 2 inexistente en el Agente 1; hallazgo del Agente 1 sin grupo en el Agente 2); para el paquete ausente, copia del módulo en un directorio temporal con un `.git` vacío y sin `piia2_paquete_datos/`, importada en un subproceso | `python probar_informe.py` | Red y Green |
| `specs/31-informe-peritaje.md#AC-012` | S1 | TDD | Dos informes idénticos sin clave ni red | `OPENAI_API_KEY` eliminada del entorno del proceso y `socket.socket` sustituido durante la prueba por una función que lanza excepción | `python probar_informe.py` | Green (igualdad, sin intento de conexión) |
| `specs/31-informe-peritaje.md#AC-013` | S2 | TDD | `[160.0]`, `[42000.0]` y `[3.0]` para los tres importes inventados que coinciden con números no monetarios | Informe de AC-001 modificado en memoria; `agente2_salida.json` sin editar | `python probar_informe.py` | Red (contra la versión que acepta cualquier número del JSON) y Green |

## Implementation Plan

| Slice | Objetivo observable | AC relacionados | Componentes / contratos probablemente afectados | Dependencias | Verificación prevista |
|---|---|---|---|---|---|
| 1 — Informe del ejemplo | `generar_informe` produce el informe completo del ejemplo, con secciones, separación, normativa y arrastres. | AC-001, AC-002, AC-005, AC-009 | `agente_redactor/informe.py` (nuevo) | Paquete de la empresa extraído en local | Filas AC-001, AC-002, AC-005, AC-009 |
| 2 — Cifras comprobadas | `comprobar_cifras` acepta el informe del ejemplo y detecta importes inventados, también los que coinciden con números no monetarios. | AC-003, AC-004, AC-013 | Ídem | Slice 1 | Filas AC-003, AC-004, AC-013 |
| 3 — Casos límite | Tercero, sin confirmados, todo rechazado, pérdida total en un solo escenario. | AC-006, AC-007, AC-008 | Ídem | Slices 1 y 2 | Filas AC-006 a AC-008 |
| 4 — Robustez de la entrada | Errores explícitos ante entradas incoherentes o paquete ausente; ejecución determinista sin red. | AC-011, AC-012 | Ídem | Slice 1 | Filas AC-011, AC-012 |
| 5 — Origen del coche | Cabecera y avisos según `vehiculo_origen`, sin presentar el coche de referencia como identificado. | AC-010 | Ídem; contrato de la #28 | ADR 0001 aceptado y la #28 integrada | Fila AC-010 |

Al terminar, el README de `agente_redactor/` indica cómo ejecutar las pruebas y generar el informe
de ejemplo.

## Pendientes para Ready

- **Revisión previa (solicitud del equipo):** Planning PR aprobada sobre el head final por una persona distinta del autor (revisor acordado en el reparto: Lucas) e integrada por un humano; spec en estado Revisada, con quién la acepta, el permalink y la versión registrados en la Issue. El comentario de planificación de la Issue debe señalar el commit finalmente aceptado.
- **Confirmaciones ya dadas en la revisión de `f61a637`** (Lucía, 2026-10-17): de acuerdo con NO_ADR_REQUIRED, con el texto del aviso legal (AC-001) y con dejar fuera de alcance el párrafo con LLM y la revisión de informes reales. Deben mantenerse para la versión final.
- **Forma del escenario vacío (dependencia de AC-007):** fijada en `specs/30-costes-cobertura.md#AC-007` (PR #40) y comprobada por Lucía con la herramienta real. Para Ready, la PR #40 debe estar integrada con esa forma.
- **Resolución de la #28 (bloquea solo AC-010 y la slice 5):** a 2026-10-19 la PR #29 sigue abierta y sin revisiones, y el ADR 0001 en estado Propuesto. Antes de Ready se registra en la Issue su resolución: aceptado (AC-010 tal cual), rechazado (AC-010 retirado sin renumerar) o modificado (AC-010 actualizado conservando su ID).
- **ADRs de la #37 integrados en `main`** (decisión del equipo del 2026-10-19: los ADRs se integran antes de implementar): al menos el que registra el contrato Agente 1 → Agente 2 → Agente 3, Aceptado.
- **Prerrequisito de implementación (no de planificación):** extraer `piia2_paquete_datos/` en la raíz del repo.

Resultado de analyze:

| Comprobación | Resultado |
|---|---|
| Cada requisito de la Issue tiene AC | Cabecera y aviso → AC-001; confirmados, pendientes y rechazados aparte → AC-002, AC-007; dos escenarios de coste → AC-003, AC-008; pérdida total, cobertura e indemnización → AC-006, AC-008; normativa con fuente o «Sin fuentes» → AC-005; origen del coche → AC-010; comprobación automática de cifras → AC-003, AC-004, AC-013; informe completo con los ejemplos → AC-001 a AC-003. |
| AC sin requisito en la Issue | AC-009 (arrastres) viene del contrato y de la guía; AC-011 y AC-012 cubren failure modes. Ninguno amplía el alcance funcional. |
| Cada AC tiene verificación y slice | Sí (AC-001 a AC-013). |
| Comportamiento preservado | Los contratos de entrada, que no se modifican; los usan sin editar AC-001 a AC-003. |
| ADR decision coherente | NO_ADR_REQUIRED justificado; se señala para confirmación. |
| Gaps | AC-010 depende de la #28 (sin resolver a 2026-10-19). AC-007 depende de que se integre la PR #40. Por decisión del equipo (2026-10-19), Ready exige además que los ADRs de la #37 de los que depende estén integrados en `main`. Ninguno impide revisar el plan; los tres se resuelven antes de Ready. |

## Definition of Done

| Condición específica de cierre | Evidencia requerida |
|---|---|
| `probar_informe.py` ejecutado **con el paquete de la empresa presente** y en verde. | Salida del comando en la PR de implementación. |
| Informe de ejemplo generado con los JSON del contrato y revisado por una persona como lector. | El markdown generado, pegado o adjunto en la PR de implementación (no se versiona). |
| AC-010 implementado o retirado con referencia a la decisión de la #28. | Enlace a la PR #29 y su resultado. |
| README de `agente_redactor/` actualizado. | Diff de la PR. |
