# Spec: Justificación con un LLM de la normativa recuperada por el RAG

- GitHub Issue: https://github.com/lvckss/piia2-26/issues/97
- Estado: Revisada — por Lucas García (`lvckss`), [revisión APPROVED del 2026-11-17](https://github.com/lvckss/piia2-26/pull/98#pullrequestreview-5944306302) sobre `940119f`, que acepta la Spec 97 v1.1 (AC, Test/Eval Plan e Implementation Plan) y el ADR 0009 (NEW_ADR).
- ADR decision: NEW_ADR
- ADR: [docs/adr/0009-justificacion-llm-normativa.md](../docs/adr/0009-justificacion-llm-normativa.md) — Aceptado
- Justificación: añade un modelo de lenguaje al Agente 2 y un campo nuevo a su salida, que consumen el Agente 3 y la orquestación de la #34 (frontera entre agentes del [ADR 0002](../docs/adr/0002-contrato-json-entre-agentes.md)). Además cambia el alcance aceptado: la [spec 32](32-rag-normativa.md) deja fuera «generar respuestas o conclusiones con otro LLM» y la [spec 31](31-informe-peritaje.md) no usa ningún LLM. Amplía los ADR 0002 y [0006](../docs/adr/0006-rag-postgresql-estado-recuperacion.md) sin sustituirlos y reutiliza el [ADR 0003](../docs/adr/0003-proveedor-openai-clave-empresa.md) para el proveedor y la clave.
- Plan vigente / versión: **v1.1** (2026-11-17), este archivo en la rama `plan/97-justificacion-llm`; el commit exacto se registra en un comentario de la Issue. La v1.1 atiende la [revisión de Lucas sobre `076440f`](https://github.com/lvckss/piia2-26/pull/98#pullrequestreview-5944085838): el texto del LLM no lleva importes (AC-003, AC-009) y la evaluación exige justificaciones generadas (AC-011). Conserva los 11 IDs de AC y el resto del plan. Antecedente: v1 `b997613` (`076440f` solo añadió el enlace a la Planning PR).
- Actualización v1.2 (propuesta, 2026-11-21): la comparación de citas deja de distinguir mayúsculas y asteriscos de énfasis de Markdown. Origen: el ensayo con el RAG y el LLM reales sobre las 30 salidas versionadas descartó 15 justificaciones solo por eso («el asegurador» frente a «El asegurador» en los 13 informes de tercero, y «Rotura de lunas» frente a «**Rotura de lunas**» en 2), con lo que 6 de los 10 informes del AC-011 no tenían ninguna justificación generada. Decisión de Lucas García y Víctor Hidalgo comunicada a Lucía Luis Castaño el 2026-11-21. Cambia la regla de «Citas literales» y la fila de AC-002; los 11 IDs de AC, el resto del plan y los contratos no cambian.
- Riesgo y revisión previa: **sí requiere revisión previa** (disparador: NEW_ADR). Impacto medio: el texto nuevo llega al informe que lee el perito y un LLM puede afirmar algo que sus fuentes no dicen. Reversibilidad alta: el campo nuevo es opcional y, sin él, el sistema vuelve al comportamiento actual. Incertidumbre media: la calidad de las justificaciones solo se conoce evaluándolas.
- Planning PR: https://github.com/lvckss/piia2-26/pull/98

## Qué construir

Hoy el Agente 2 calcula costes y cobertura con código determinista ([ADR 0004](../docs/adr/0004-herramienta-costes-datos-empresa.md)) y `agente2()` (#32, slice 3) añadirá en `normativa` los pasajes literales que el RAG recupera por tema (`tema`, `extracto`, `fuente`). El Agente 3 copia esos pasajes en «Fuentes consultadas». Nadie los lee: el perito ve el cálculo y unas citas sueltas, sin una explicación de lo que dicen.

Se añade un paso al final del Agente 2. Para cada tema con pasajes recuperados, un LLM recibe **solo el tema y sus pasajes** y devuelve:

- un **texto breve** en español que resume lo que dicen la póliza o la ley sobre ese tema;
- las **citas literales** de esos pasajes en las que se apoya.

El código comprueba la respuesta antes de aceptarla y la guarda en un campo nuevo de la salida del Agente 2, `justificaciones`. El Agente 3 la muestra en «Fuentes consultadas», junto a sus citas.

Flujo, de principio a fin:

1. El código calcula costes y cobertura (sin cambios).
2. El RAG recupera pasajes por tema (`agente2()`, #32).
3. **Nuevo:** el LLM escribe una justificación por tema solo a partir de sus pasajes, y el código la comprueba.
4. El Agente 3 compone el informe: cálculo, justificación y citas.

Forma propuesta del campo (los nombres exactos son un ajuste interno; la forma la fija el ADR 0009 y los ejemplos del contrato):

```json
"justificaciones": [
  {
    "tema": "cobertura de daños propios",
    "estado": "generada",
    "texto": "La póliza cubre los daños propios por colisión, vuelco, atropello de animales y actos vandálicos, con una franquicia por siniestro.",
    "citas": [
      {"extracto": "Daños propios por colisión, vuelco, atropello de animales y actos vandálicos", "fuente": "docs/polizas_sinteticas/P-TR-FR300.md#2. Coberturas incluidas"}
    ]
  },
  {"tema": "pérdida total", "estado": "no_generada", "motivo": "El modelo no respondió a tiempo."}
]
```

`estado` toma uno de tres valores:

- `generada`: con `texto` y al menos una cita.
- `descartada`: la respuesta no pasó la comprobación. Incluye `motivo` y no lleva texto ni citas.
- `no_generada`: no se pudo pedir o recibir la respuesta. Incluye `motivo`.

La `fuente` de cada cita la pone el código (la del pasaje que la contiene), nunca el LLM.

## Por qué

- El tutor y el equipo quieren que el informe explique sus conclusiones con la letra de la póliza y la ley, no solo que las enumere.
- Si cambian los documentos de una aseguradora o la ley, la justificación sale de los documentos nuevos sin tocar el código: basta con volver a indexarlos (#32).
- Las cifras siguen saliendo del código y de la herramienta de la empresa, que es lo verificable; el LLM solo redacta.

Decisiones humanas de la planificación (Víctor, 2026-11-17, en la sesión que originó la Issue, confirmadas en la revisión de esta Planning PR):

- Alcance «solo justifica» (no avisa de discrepancias ni de condiciones no calculadas).
- El LLM recibe **solo los pasajes**, no el resultado del cálculo, para que no pueda forzar una explicación que cuadre con él.
- El texto vive en la salida del Agente 2.
- Si el LLM falla, el informe sale como preliminar con las citas y sin justificación.
- Evaluación con 10 informes, revisados por Lucía.
- v1.1, tras la revisión de Lucas: el texto del LLM **no lleva importes**, y la evaluación exige **al menos una justificación generada por informe** (Víctor, 2026-11-17).
- Reparto: Lucas implementa el Agente 2 y Víctor, el Agente 3.

## Alcance

- Incluido:
  - El paso de justificación al final de `agente2()`: una llamada al LLM por tema con pasajes, con los pasajes de ese tema como única fuente.
  - La comprobación en código de cada respuesta (citas literales, texto sin importes, términos de validación) y el campo `justificaciones` con su estado por tema.
  - El comportamiento ante fallos: sin clave, sin autorización de gasto, error o tiempo agotado del proveedor, respuesta mal formada.
  - La caché de respuestas y el control de gasto según el ADR 0003.
  - La representación en el informe (Agente 3) y el aviso de informe preliminar cuando falte alguna justificación.
  - La actualización de los ejemplos del contrato y de la documentación afectada.
  - La evaluación manual de 10 informes reales.
- Fuera de alcance:
  - Que el LLM calcule, cambie o decida cifras o la cobertura.
  - Enseñar al LLM el resultado del cálculo.
  - Avisar de discrepancias entre el cálculo y los documentos, o de condiciones que el cálculo no tiene en cuenta (exclusiones, plazos, IVA contra factura). Queda como evolución, como la «opción B» de la spec 32.
  - Cambiar el indexado, la búsqueda o la selección de temas del RAG (#32).
  - Cambiar la visión (Agente 1) o la orquestación (#34), salvo transportar el campo nuevo sin cambios.
  - Comparar modelos de chat.

## Restricciones y supuestos

- **Cifras intactas:** todos los campos actuales de la salida del Agente 2 (costes, escenarios, cobertura, `normativa`, `diagnostico_rag`) son idénticos con y sin el paso nuevo. Solo se añade `justificaciones`.
- **Única fuente, los pasajes:** el mensaje al LLM contiene el tema y los `extracto` de ese tema, sin importes del cálculo ni datos del siniestro.
- **Citas literales:** cada cita aceptada es un fragmento que aparece tal cual en algún pasaje del mismo tema. Se compara tras normalizar espacios en blanco consecutivos, sin distinguir mayúsculas de minúsculas y sin los asteriscos de énfasis de Markdown (v1.2); ningún otro cambio. La cita que se guarda es el texto del pasaje tal como está escrito, no la versión del modelo.
- **Texto sin importes:** el `texto` no puede contener ningún importe en euros: un número seguido o precedido de «€», «EUR», «euro» o «euros», en cualquier formato («300 €», «1.500 EUR», «1500 EUR», «2.500,00 euros», «€ 300»). Si lo contiene, la justificación se descarta, aunque el importe esté en sus citas. Los importes solo aparecen en el informe por dos vías ya existentes: el cálculo del Agente 2 y las citas literales de la `normativa`, que se muestran como bloque literal debajo de cada justificación. El Agente 3 vuelve a comprobarlo: una justificación `generada` con importes en el `texto` es una entrada mal formada. Así, el texto del LLM no añade ningún importe nuevo al informe y `comprobar_cifras` sigue igual.
- **Límite conocido de `comprobar_cifras`, sin cambios en esta Spec:** solo reconoce importes con coma, dos decimales y «€» (spec 31 AC-013), por lo que no detecta formas como «1500 EUR». Las citas de la `normativa` ya se muestran hoy en el informe con esa limitación; esta Spec no la amplía ni la corrige.
- **Sin validación jurídica:** el `texto` no puede contener las raíces «verific», «valid» ni «garantiz». Si las contiene, se descarta (coherente con la spec 31 AC-014).
- **Proveedor:** OpenAI con la clave de la empresa en `OPENAI_API_KEY` y el modelo en `OPENAI_MODEL` o en el parámetro `modelo` ([ADR 0003](../docs/adr/0003-proveedor-openai-clave-empresa.md)). El cliente se recibe como parámetro para probar sin red.
- **Gasto controlado:** se llama al LLM solo con autorización explícita de gasto, como la consulta del RAG (`RAG_QUERY_EXECUTE` y presupuesto finito en la #32). Las respuestas se cachean por modelo y mensaje.
- **Dependencia:** necesita `agente2()` de la #32 (slice 3). Hasta que exista, las slices del Agente 2 se prueban con `normativa` guionizada.
- Supuesto explícito: el texto breve son como mucho tres frases. Es un ajuste del prompt, no una comprobación del código.

| Incertidumbre | Clasificación | Evidencia / supuesto / efecto |
|---|---|---|
| ¿El LLM recibe el resultado del cálculo? | Resuelta (decisión humana) | No: solo pasajes. Evita que fuerce una explicación que cuadre con el cálculo. |
| ¿Dónde vive el texto? | Resuelta (decisión humana) | En la salida del Agente 2; el Agente 3 solo lo muestra y sigue siendo determinista. |
| ¿Qué hace el sistema si el LLM falla? | Resuelta (decisión humana) | El informe sale como preliminar, con citas y sin justificación; nunca se bloquea. |
| ¿Qué texto lleva el aviso preliminar? | Resuelta (confirmado por Lucas en la revisión de la v1) | «Informe preliminar: no se ha podido redactar la justificación de algunas fuentes; se muestran sus citas sin justificación y requieren revisión.» Es distinto del aviso de la #32 porque el motivo es otro. |
| ¿Cómo encajan los importes del texto con `comprobar_cifras`? | Resuelta (decisión humana, v1.1) | El texto no lleva importes; los importes de la póliza solo aparecen en sus citas literales. Se descartó permitir en el texto los importes de las citas, porque obligaría a ampliar `comprobar_cifras` y su garantía (revisión de Lucas). Un importe escrito en letras no se detecta automáticamente; la evaluación manual lo vigila. |
| ¿Qué modelo de chat? | Resuelta por el ADR 0003 | El identificador de la cuenta de la empresa, por entorno o parámetro; se registra el usado en la evaluación. Comparar modelos queda fuera. |
| ¿Cuándo estará `agente2()`? | Dependencia, no bloqueante para planificar | Las slices 1 y 3 no la necesitan; la 2 y la 5, sí. Si no llega a tiempo para la congelación del 2026-11-24, se registra como bloqueo con su alternativa. |

## Comportamiento que debe preservarse

- **Cálculo y contrato actual del Agente 2** ([ADR 0002](../docs/adr/0002-contrato-json-entre-agentes.md), spec 32 AC-006): mismos campos y valores; `justificaciones` es aditivo. Protegido por AC-006 y por `probar_costes.py` y `probar_rag.py`.
- **Informe sin el campo nuevo** (spec 31 AC-001 a AC-015): una salida del Agente 2 sin `justificaciones` produce exactamente el informe actual. Protegido por AC-009 y `probar_informe.py`.
- **Determinismo del informe** (spec 31 AC-012): `generar_informe` no llama a ningún modelo; con la misma entrada da el mismo informe sin clave ni red. Protegido por AC-010 y `probar_informe.py`.
- **Cifras verificadas** (spec 31 AC-013): `comprobar_cifras` no cambia y sigue dando `[]` con justificaciones, incluso cuando una cita contiene un importe de la póliza ausente del cálculo. Protegido por AC-003, AC-008 y AC-009.
- **Los 9 encabezados del informe** no cambian: la justificación va dentro de «Fuentes consultadas».

## Failure modes y requisitos no funcionales

| Situación | Comportamiento esperado | AC |
|---|---|---|
| Cita que no está literalmente en los pasajes del tema | Esa justificación queda `descartada` con motivo; las demás no se ven afectadas | AC-002 |
| El texto contiene un importe en euros (aunque esté en sus citas) | `descartada` con motivo en el Agente 2; si llega así al Agente 3, excepción | AC-003, AC-009 |
| Texto que se presenta como validación jurídica | `descartada` con motivo | AC-004 |
| Sin `OPENAI_API_KEY`, sin autorización de gasto, error o tiempo agotado del proveedor, respuesta no JSON | `no_generada` con motivo comprensible, sin excepción hacia arriba y sin tocar el resto de la salida | AC-005 |
| Tema sin pasajes recuperados | No se llama al LLM para ese tema ni aparece en `justificaciones` | AC-006 |
| Alguna justificación `descartada` o `no_generada` | Informe preliminar con el aviso y el tema y su motivo | AC-009 |
| `justificaciones` mal formado (incluida una `generada` con importes en el texto) | El Agente 3 lanza una excepción que nombra el campo | AC-009 |
| Repetir el mismo caso | Respuesta desde la caché, sin nueva llamada de pago | AC-010 |
| Error inesperado del código (no del proveedor) | Se propaga; no se convierte en `no_generada` | AC-005 |
| Coste y latencia | Una llamada por tema con pasajes (de 1 a 4 temas por caso según la #32); se registran tokens y tiempo en la evaluación, sin umbral fijado | AC-011 |
| Credenciales | La clave nunca aparece en salidas, motivos, logs ni en el repositorio | AC-005 |

## Acceptance Criteria

| ID | Dado / Cuando | Resultado esperado y condición de éxito |
|---|---|---|
| AC-001 | Una `normativa` con pasajes para un tema y un cliente falso que devuelve un texto sin importes y dos citas que aparecen literalmente en esos pasajes. | `justificaciones` contiene ese tema con `estado: generada`, el `texto` recibido y las dos citas. Cada cita lleva como `fuente` la del pasaje que la contiene, aunque el cliente devuelva otra. |
| AC-002 | El cliente falso devuelve para un tema una cita que no aparece en sus pasajes (o que solo aparece en los de otro tema), y para otro tema una respuesta válida. Además, una cita que solo difiere de un pasaje en mayúsculas o en asteriscos de énfasis de Markdown (v1.2). | El primer tema queda `descartada` con un `motivo` que menciona la cita no encontrada, sin `texto` ni `citas`. El segundo queda `generada`. Ninguna cita no literal llega a la salida. La cita que difiere solo en mayúsculas o asteriscos se acepta y se guarda con el texto del pasaje. |
| AC-003 | Pasajes de la póliza P-TR-FR300 que contienen «1500 EUR» (límite de lunas, ausente del cálculo) y «300 EUR». El texto devuelto, en cinco variantes, contiene «500 €», «1.500 EUR», «1500 EUR», «300,00 euros» o ningún importe; las citas incluyen el pasaje del límite. | Las cuatro variantes con importe quedan `descartada` con un motivo que menciona el importe, aunque esté en sus citas. La variante sin importes queda `generada`. Con esa justificación y su cita («…límite de 1500 EUR…») en el informe, `comprobar_cifras` devuelve `[]`. |
| AC-004 | El texto devuelto contiene «verificado», «validada» o «garantiza». | El tema queda `descartada` con un motivo que lo explica. |
| AC-005 | Por separado: sin `OPENAI_API_KEY`; sin autorización de gasto; el cliente lanza un error del proveedor o de tiempo agotado; el cliente devuelve texto que no es JSON o un JSON sin `texto` o sin `citas`. Además, un error inesperado del propio código. | En los cuatro primeros casos, cada tema queda `no_generada` con un motivo comprensible, sin excepción. Sin clave o sin autorización no se hace ninguna llamada. El resto de la salida es idéntico y ningún motivo contiene la clave. El error inesperado del código se propaga. |
| AC-006 | Una salida de `agente2()` con `normativa` de tres temas, uno de ellos sin pasajes, y un cliente falso; se ejecuta el paso de justificación. | Todos los campos originales (cifras, escenarios, `normativa`, `diagnostico_rag`) son idénticos a los de antes del paso y las entradas no se modifican. Se añade `justificaciones` con los dos temas que tienen pasajes. Para el tema sin pasajes no hay llamada al LLM. |
| AC-007 | El cliente falso registra los mensajes que recibe, para un caso con importes en los escenarios y en la cobertura. | Cada mensaje contiene el tema y los `extracto` de ese tema, y ningún importe del cálculo, ningún campo de `escenarios`, `contexto` ni `valor_venal_eur`. |
| AC-008 | Una salida del Agente 2 con dos justificaciones `generada`; se llama a `generar_informe`. | En «Fuentes consultadas», cada tema muestra su texto y, debajo, sus citas con su fuente, como bloque literal. Los 9 encabezados no cambian, no aparece la palabra «verificada» y `comprobar_cifras` devuelve `[]`. |
| AC-009 | Tres salidas del Agente 2: una con una justificación `descartada` o `no_generada`; otra sin el campo `justificaciones`; otra con `justificaciones` mal formado (estado desconocido, tema ausente, o una `generada` cuyo `texto` contiene «1.500 €» o «300 EUR»). | La primera lleva en la cabecera el aviso de informe preliminar de justificaciones y, en «Fuentes consultadas», el tema con su motivo y sus citas sin justificación. La segunda produce exactamente el informe actual. La tercera lanza una excepción que nombra el campo y no devuelve informe. |
| AC-010 | Se ejecuta dos veces el paso de justificación con el mismo modelo y los mismos pasajes y caché, y se llama dos veces a `generar_informe` con la misma salida. | La segunda ejecución no hace ninguna llamada nueva al cliente y devuelve el mismo `justificaciones`. Los dos informes son idénticos, sin clave ni red. |
| AC-011 | Los 10 informes reales de la lista fijada en el Test Plan, generados con `agente2()` real, el modelo registrado y autorización de gasto; Lucía revisa cada justificación `generada` con sus citas delante. | Se publica en la Issue: (a) una tabla por informe y tema con tema elegible (con pasajes), estado (`generada`, `descartada` o `no_generada`) y motivo, fiel (solo afirma lo que dicen sus citas, sí/no), pertinente (sí/no), tokens y tiempo; (b) por informe y en total, cuántos temas eran elegibles y cuántos se generaron, descartaron y fallaron. **Éxito, todo a la vez:** 0 justificaciones no fieles; ningún `no_generada` por fallo técnico del proveedor en la ejecución evaluada (si lo hay, se repite la ejecución y no cuenta); y cada informe con al menos un tema elegible tiene al menos una justificación `generada`. Un lote sin justificaciones generadas nunca acredita este AC. La pertinencia y los descartes se informan sin umbral. Si no se cumple, se ajusta el prompt y se reevalúa con la misma lista; el criterio no se rebaja sin decisión humana. |

## Test Plan

### Test seams

| Seam | Contrato | Justificación |
|---|---|---|
| Función pública del paso de justificación (Agente 2), con cliente inyectado | Entrada `normativa` (+ cliente, modelo, caché, autorización); salida `justificaciones` | Es la frontera nueva; el cliente como parámetro sigue el ADR 0003 y permite probar sin red. |
| `agente2()` (#32) | Salida completa del Agente 2 | Es la función que consume la #34; comprueba el contrato y la preservación de cifras. |
| `generar_informe` y `comprobar_cifras` (spec 31) | Markdown del informe | Frontera del Agente 3, ya probada en `probar_informe.py`. |
| Ejemplos del contrato (`ejemplos_contrato/agente2_salida.json`) | Forma del JSON entre agentes | Son la referencia ejecutable del contrato (ADR 0002). |

### Casos

| AC (ruta de Spec + ID) | Seam / contrato | Estrategia y nivel | Caso / resultado esperado | Datos / fixture y versión | Comando / pasos previstos | Evidencia prevista |
|---|---|---|---|---|---|---|
| `specs/97-justificacion-llm-normativa.md#AC-001` | Paso de justificación | TDD unitario, cliente falso | Justificación generada; fuente asignada por código | `normativa` escrita en la prueba con pasajes del ejemplo del contrato | Prueba nueva del Agente 2 (`probar_justificacion.py` o equivalente) | Red/Green |
| `specs/97-justificacion-llm-normativa.md#AC-002` | Paso de justificación | TDD unitario | Cita no literal o de otro tema → `descartada`; el otro tema, `generada` | Ídem | Ídem | Red/Green |
| `specs/97-justificacion-llm-normativa.md#AC-003` | Paso de justificación + `comprobar_cifras` | TDD unitario | Cinco variantes (€, EUR con y sin separador, euros, sin importe); importe de la póliza ausente del cálculo | Pasajes de `P-TR-FR300.md` con «1500 EUR» y «300 EUR» copiados en la prueba | Ídem y `probar_informe.py` | Red/Green |
| `specs/97-justificacion-llm-normativa.md#AC-004` | Paso de justificación | TDD unitario | Términos de validación → `descartada` | Ídem | Ídem | Red/Green |
| `specs/97-justificacion-llm-normativa.md#AC-005` | Paso de justificación | TDD unitario, cliente falso que falla | Fallos del proveedor → `no_generada`; error del código → se propaga; sin llamadas sin clave o autorización | Cliente falso que lanza, devuelve texto no JSON o registra llamadas; entorno sin `OPENAI_API_KEY` | Ídem | Red/Green |
| `specs/97-justificacion-llm-normativa.md#AC-006` | `agente2()` | TDD de integración, RAG y cliente guionizados | Campos originales idénticos; tema sin pasajes sin llamada | Salida guionizada de `agente2()` mientras no exista; después, la real con RAG simulado | `probar_rag.py` o la prueba nueva, `probar_costes.py` | Red/Green y regresión verde |
| `specs/97-justificacion-llm-normativa.md#AC-007` | Paso de justificación | TDD unitario | Mensajes sin cifras ni contexto | Caso con importes conocidos en escenarios | Prueba nueva | Red/Green |
| `specs/97-justificacion-llm-normativa.md#AC-008` | `generar_informe` | TDD | Texto y citas en «Fuentes consultadas»; encabezados iguales | `agente2_salida.json` ampliado | `python probar_informe.py` | Red/Green |
| `specs/97-justificacion-llm-normativa.md#AC-009` | `generar_informe` | TDD | Aviso preliminar; sin campo idéntico; mal formado (incluido texto con importes) → excepción | Ídem, en tres variantes | `python probar_informe.py` | Red/Green |
| `specs/97-justificacion-llm-normativa.md#AC-010` | Paso de justificación y `generar_informe` | TDD | Caché sin llamada nueva; informe determinista | Caché en carpeta temporal | Prueba nueva y `probar_informe.py` | Red/Green |
| `specs/97-justificacion-llm-normativa.md#AC-011` | Salida real del Agente 2 e informe | **Eval-first** (humano) | Tabla de estados, fidelidad y pertinencia; recuento de elegibles, generadas, descartadas y fallidas | Los 10 informes de la lista, `OPENAI_MODEL` registrado, índice del RAG de la #32 | Generar los 10 con `agente2()` real y el comando de la #84; Lucía revisa | Tabla en la Issue y comparación con la línea base |

### Evaluación (AC-011)

- **Línea base:** los mismos 10 informes sin el paso nuevo: «Fuentes consultadas» con citas y sin justificación. El hueco que se mide es la ausencia de explicación; la evaluación comprueba que la explicación añadida es fiel.
- **Lista fijada de antemano:** 000381, 001008, 001245, 001281, 002536, 002632, 002859, 003083, 003637 y 003806. Son los 10 de los 30 sin problemas de visión en la [revisión de Lucía](https://github.com/lvckss/piia2-26/issues/54#issuecomment-6806373544), para que los fallos del Agente 1 no se confundan con los de la justificación. Mezclan terceros (4), Terceros Ampliado (3), Terceros Básico (1) y Todo Riesgo con franquicia (2), según la asignación de la #84 con semilla 84.
- **Protocolo:** una persona (Lucía), con cada justificación y sus citas delante. Para cada una anota si es fiel y si es pertinente; los importes los descarta ya el código (AC-003), y si aun así aparece uno escrito en letras, cuenta como no fiel. Se registran por informe y tema los elegibles y los estados, además del modelo, la versión del índice y el commit.
- **Criterio:** 0 no fieles; ningún fallo técnico del proveedor en la ejecución evaluada; y al menos una justificación `generada` en cada informe con temas elegibles. La pertinencia, los descartes y el coste se informan sin umbral, porque no hay evidencia para fijarlos.

Regresión de todas las slices: `probar_costes.py`, `probar_rag.py`, `probar_indexado.py` (con `--postgres` cuando aplique), `probar_informe.py` y `probar_informes_reales.py`, sin clave ni red salvo en AC-011.

## Implementation Plan

| Slice | Objetivo observable | AC relacionados | Componentes / contratos probablemente afectados | Dependencias | Verificación prevista | Responsable |
|---|---|---|---|---|---|---|
| 1 — Paso de justificación | Con un cliente falso, la función devuelve `justificaciones` comprobadas, con sus estados y fallos | AC-001 a AC-005, AC-007, AC-010 (caché) | Módulo nuevo en `agente_recuperacion/` | ADR 0009 Aceptado | Prueba nueva | Lucas |
| 2 — Integración en `agente2()` | `agente2()` añade `justificaciones` sin tocar el resto | AC-006 | `agente2()` (#32) | Slice 1; `agente2()` de la #32 | Prueba de integración, `probar_costes.py` y `probar_rag.py` | Lucas |
| 3 — Informe | El informe muestra justificaciones y avisos, y sin el campo queda igual | AC-008, AC-009, AC-010 (informe) | `informe.py`, `probar_informe.py` | Forma del campo fijada en el ADR 0009 (no necesita la slice 1) | `python probar_informe.py` | Víctor |
| 4 — Contrato y documentación | Ejemplos y documentación con el campo nuevo | AC-006, AC-008 (ejemplos) | `ejemplos_contrato/agente2_salida.json`, README de los Agentes 2 y 3 | Slices 1 a 3 | Revisión de contenido y regresión | Lucas y Víctor |
| 5 — Evaluación | Tabla de los 10 informes y comparación con la línea base | AC-011 | Comando de la #84 y salida real | Slices 1 a 4; índice del RAG; clave y autorización de gasto | Revisión de Lucía | Lucas (ejecuta) y Lucía (revisa) |

Orden: las slices 1 y 3 pueden ir en paralelo; la 2 espera a `agente2()`. Objetivo: integrado antes de la congelación del 2026-11-24.

## Pendientes para Ready

- Revisión humana de esta Spec y aceptación del ADR 0009: hechas por Lucas, [revisión APPROVED del 2026-11-17](https://github.com/lvckss/piia2-26/pull/98#pullrequestreview-5944306302) sobre `940119f`. Pendientes: la aprobación final del head con este registro y su integración en `main`.
- El texto del aviso preliminar y la lista de 10 informes ya los confirmó Lucas en su [revisión sobre `076440f`](https://github.com/lvckss/piia2-26/pull/98#pullrequestreview-5944085838); falta su aceptación de la v1.1 y del ADR 0009.
- Analyze v1.1 (2026-11-17, tras la revisión de Lucas): resueltos los dos puntos (texto sin importes, compatible con `comprobar_cifras` sin cambiarlo; cobertura mínima de justificaciones generadas en AC-011). Analyze (2026-11-17): requisitos de la Issue cubiertos por AC-001 a AC-011; cada AC con verificación y slice; comportamiento preservado protegido por AC-006, AC-009 y AC-010; sin contradicciones con los ADR 0002, 0003, 0004 y 0006 (este ADR los amplía sin cambiar sus decisiones). Gaps: ninguno bloqueante. Dependencia: `agente2()` de la #32.

## Definition of Done

Además de la DoD global:

- La tabla de AC-011 publicada en la Issue con el criterio cumplido, o con la decisión humana registrada si no se cumple.
- Ejemplos del contrato y README de los Agentes 2 y 3 actualizados con el campo `justificaciones`.
