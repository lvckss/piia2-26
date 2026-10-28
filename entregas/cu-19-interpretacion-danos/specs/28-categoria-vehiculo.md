# Spec: Categoría del vehículo estimada a partir de la imagen

- GitHub Issue: https://github.com/lvckss/piia2-26/issues/28
- Estado: Revisada (v1.3) — por Víctor Hidalgo (`Vija97`), [revisión APPROVED del 2026-10-28](https://github.com/lvckss/piia2-26/pull/29#pullrequestreview-5682298653) sobre la versión `086dc93`, integrada en `main` (merge `246634f`), que cubre la spec y su ADR. Esta spec registra la aceptación en una corrección documental posterior (solo metadatos).
- ADR decision: NEW_ADR
- ADR: [docs/adr/0001-categoria-vehiculo-contrato-agente1.md](https://github.com/lvckss/piia2-26/blob/main/docs/adr/0001-categoria-vehiculo-contrato-agente1.md) — Aceptado en la misma [revisión](https://github.com/lvckss/piia2-26/pull/29#pullrequestreview-5682298653); integrado en `main` con la Planning PR.
- Justificación: el cambio añade un campo estable (`vehiculo`) a la frontera Agente 1 → Agente 2/3, introduce una segunda consulta por imagen al proveedor de visión y modifica la decisión anterior «`vehiculo_id` es dato de entrada, no deducido» (`piia2-arquitectura-multiagente.md`, tabla de decisiones). Es un diff pequeño, pero toca un contrato entre agentes que evolucionan por separado: por la regla del workflow no puede ser `NO_ADR_REQUIRED`. Hay ADRs aceptados en `main` (0002 a 0005, PR #51), pero ninguno cubre este cambio: el [ADR 0002](https://github.com/lvckss/piia2-26/blob/main/docs/adr/0002-contrato-json-entre-agentes.md) fija que cualquier cambio de forma del contrato requiere su propio ADR, y este es ese ADR.
- Plan vigente / versión: **v1.3** (2026-10-28; v1.2 del 2026-10-27, `dca27ad`), aprobado e integrado en `main` con la Planning PR #29 (head `086dc93`, merge `246634f`). Historial: v1 (2026-10-13), v1.1 (2026-10-17, `e180219`), Issue aparcada el 2026-10-20 y retomada el 2026-10-27 a petición de Lucas para el recorrido web de la #34 ([solicitud](https://github.com/lvckss/piia2-26/issues/28#issuecomment-6426798908) y [respuesta](https://github.com/lvckss/piia2-26/issues/28#issuecomment-6441249990)). La v1.2 simplifica el alcance: esta Issue cubre solo el Agente 1 (AC-001 a AC-008 y AC-011); AC-009 y AC-010 se transfieren a la #34 y la #31. La v1.3 (2026-10-28) solo aclara que el campo de procedencia del coche lo decide la #34 en su ADR 0007 y la #31 lo consume; no cambia ningún AC.
- Riesgo y revisión previa: **sí requiere revisión previa** (disparador: NEW_ADR). Consumidores: la web de la #34 (Lucas) y los Agentes 2 y 3 (Víctor). Reversibilidad alta: el campo es aditivo y quien lo ignore sigue funcionando. Incertidumbre media: el acierto de la categoría no se puede medir contra CarDD (no trae esa etiqueta) y la consulta aún no se ha probado con el modelo real.
- Planning PR: https://github.com/lvckss/piia2-26/pull/29 — integrada en `main` (merge `246634f`).

## Qué construir

Una funcionalidad del Agente 1 (analista multimodal) que, dada la foto de un vehículo dañado, estima la **categoría del vehículo** y propone un **coche de referencia** del catálogo de la empresa para presupuestar la reparación. La persona usuaria confirma o corrige la propuesta en la web (#34).

- **Entrada:** la foto completa, reducida a un máximo de 1024 px por el lado largo, sin detecciones dibujadas. Una sola consulta por imagen, no por hallazgo.
- **Categorías posibles:** los 8 segmentos del catálogo de vehículos de la empresa (`A`, `B`, `C`, `SUV-B`, `SUV-C`, `FURG`, `C-PREMIUM`, `D-PREMIUM`, campo `segmento` de `vehiculos.csv`) y `desconocido`.
- **Salida:** un objeto `vehiculo` en la salida del Agente 1, con `categoria`, `vehiculo_id_referencia` (`null` si la categoría es `desconocido`), `confianza` (`alta`, `media` o `baja`), `descripcion` (una frase) y `modelo` (identificador del modelo de visión usado).
- **Coche de referencia:** tabla fija categoría → `vehiculo_id` del catálogo de la empresa. `desconocido` **no tiene** coche de referencia (`vehiculo_id_referencia` es `null`): la persona usuaria elige en la web y no se presupuesta con un coche por defecto.
- **Dónde encaja:** el Agente 1 solo produce la propuesta (`vehiculo`). La web de la #34 la muestra, deja confirmarla o corregirla y entrega el `vehiculo_id` elegido como dato de entrada del siniestro, de modo que el Agente 2 sigue exigiendo `vehiculo_id` en el contexto, como hoy (#30), y esta Issue no toca su código. Cómo se indica en el informe que se presupuestó con un coche de referencia (antes AC-009 y AC-010 de esta Spec) lo definen la #34 y la #31 con Víctor.

### Estado actual del sistema (exploración en solo lectura, `origin/main` en `d5dd44d`, 2026-10-27)

| Qué | Evidencia |
|---|---|
| `analizar_imagen` devuelve `image_id`, `resumen_filtro_previo` y `findings`; no hay información del vehículo. | `app/agentes/agente_multimodal/agente1.py`, `ejemplos_contrato/agente1_salida.json` |
| La visión se consulta una vez por hallazgo (foto con caja roja + recorte), con caché por `sha256(modelo\|prompt\|imágenes)` y contador de uso. | `vision.py` (`analizar_hallazgo`) |
| `catalogo.py` solo conoce `piezas.csv` y `reglas_dano.csv`; no conoce `vehiculos.csv`. | `catalogo.py` (`cargar_catalogo`) |
| El `vehiculo_id` está documentado como dato de entrada del siniestro, «asumido (confirmar)»; las guías lo usan como obligatorio. | `specs/piia2-arquitectura-multiagente.md`; `agente2-costes-cobertura-guia.md` (`contexto["vehiculo_id"]`); `agente3-informe-guia.md` |
| El Agente 2 tiene código productivo (`costes_y_cobertura.py`, #30, integrado el 2026-10-26) y exige `vehiculo_id` en el contexto; el Agente 3 aún solo tiene una guía con código de referencia. | `app/agentes/agente_recuperacion/costes_y_cobertura.py`, `specs/30-costes-cobertura.md`, `specs/agente3-informe-guia.md` |
| La herramienta de la empresa `estimar_coste(vehiculo_id, ...)` exige un coche de un catálogo de 27 modelos en 8 segmentos. | `piia2_paquete_datos/data/vehiculos.csv` (local, en `.gitignore`) |
| `evaluar_vision.py` y `analizar_detecciones.py` reutilizan las funciones por hallazgo y cuentan llamadas para estimar el gasto. | `evaluar_vision.py` |
| `generar_lote.py` valida cada salida con un conjunto exacto de claves (`CAMPOS_SALIDA`) y el repositorio guarda 30 salidas reales en `ejemplos_contrato/agente1_real/`: añadir `vehiculo` obliga a actualizar el validador, `probar_lote_stub.py` y esas 30 salidas. | `app/agentes/agente_multimodal/generar_lote.py`, `probar_lote_stub.py`, `ejemplos_contrato/agente1_real/` |

## Por qué

La herramienta de costes de la empresa necesita un `vehiculo_id`, pero en CarDD la matrícula está censurada, no hay etiqueta de vehículo y, según la spec de arquitectura, casi ningún coche de las fotos pertenece al catálogo de 27 modelos. Sin coche no hay presupuesto, y el coche importa: con el mismo siniestro el coste sin IVA va de unos 1.100 € (furgoneta) a unos 2.100 € (berlina premium), y la categoría explica casi toda esa variación (medición de la exploración previa; se reproduce en la implementación, ver DoD). Estimar solo la categoría es lo que la foto permite decidir con fiabilidad razonable, y presupuestar con un representante de la categoría da un resultado **orientativo**, que es lo que el proyecto promete. Las alternativas descartadas están en el ADR.

## Alcance

- Incluido: consulta de categoría por imagen; validación de la respuesta del modelo; traducción categoría → coche de referencia del catálogo de la empresa; registro del modelo usado; caché de la consulta; actualización de los ejemplos del contrato y del validador de salidas; validación manual con el modelo real.
- Fuera de alcance: identificar marca y modelo exactos; leer o registrar matrículas, propietarios o personas; precios reales; vehículos fuera del catálogo (camiones, autobuses, motos), que quedan como `desconocido`; un dataset propio de precios por categoría; etiquetar todo CarDD con un clasificador; **el uso de la categoría en los Agentes 2 y 3 y en el informe** (`vehiculo_origen`, aviso y cabecera del informe; antes AC-009 y AC-010), que acuerdan la #34 y la #31 con Víctor; la pantalla web de confirmación o corrección (#34); elegir o comparar modelos de visión.

## Restricciones y supuestos

- La consulta solo pide la categoría y, si se reconoce, marca y modelo en la descripción. No pide matrícula, propietario ni personas, y la salida no contiene más campos que los cinco indicados.
- La respuesta del modelo se valida y nunca se acepta tal cual.
- El catálogo no incluye camiones, autobuses ni motos: esos casos, o una foto en la que no se distinga el tipo, producen `desconocido`, sin coche de referencia: la persona usuaria elige en la web (#34).
- El resultado es **orientativo**. El acierto de la categoría **no se puede medir contra CarDD**; se valida con una revisión manual de una muestra y se declara como límite.
- El modelo se resuelve igual que hoy (`OPENAI_MODEL` o parámetro `modelo`); la clave solo va en `OPENAI_API_KEY`. No se compara ni se elige modelo aquí.
- Las pruebas usan un cliente falso (sin red ni clave) y leen `vehiculos.csv` del paquete de la empresa (extraído en la raíz del repo, fuera de git). Si el paquete no está, esa parte de la prueba se salta con aviso, y la evidencia de la PR de entrega debe mostrar la ejecución con el paquete presente.

| Incertidumbre | Clasificación | Evidencia / supuesto / pregunta y efecto |
|---|---|---|
| Las decisiones previas en las que se apoya el cambio (contrato Agente 1 → Agente 2/3, proveedor OpenAI, uso de la herramienta de la empresa) y `docs/adr/README.md` pide registrarlas antes de implementar. | Resuelta con evidencia | Ya están Aceptadas e integradas en `main` (PR #51): ADR 0002 (contrato entre agentes), 0003 (proveedor OpenAI), 0004 (herramienta de costes) y 0005 (filtro previo). Aplican el 0002, que exige un ADR propio para cambiar la forma del contrato (este ADR 0001), y el 0003 y el 0004, de los que depende. No hace falta renumerar. |
| ¿AC-009 y AC-010 (Agentes 2 y 3) se quedan en esta Issue o se mueven a las Issues de esos agentes? | Resuelta (decisión humana, a confirmar en la revisión) | Lucía decidió el 2026-10-27, al retomar la Issue, simplificarla: AC-009 y AC-010 se transfieren a la #34 y la #31 y esta Issue cubre solo el Agente 1. Sus IDs no se reutilizan. El campo de procedencia (`contexto.vehiculo_origen` de la salida del Agente 2, propuesta de Víctor del 2026-10-20, junto al coche usado en `contexto.vehiculo_id`) lo decide la #34 en su ADR 0007 y la #31 lo consume con un AC de ID nuevo; esta Issue no lo define. |
| Umbral de coincidencia en la validación manual (AC-011). | Pendiente de experimento | No se fija ningún umbral sin evidencia: con 20 fotos un error son 5 puntos. AC-011 documenta la tasa y la compara con predecir siempre la categoría más frecuente; con esa tabla, una persona decide si el prompt basta o hay que ajustarlo. |
| ¿Qué pasa con `desconocido`? | Resuelta (decisión humana) | Lucas, 2026-10-26: no se asigna un compacto por defecto; la persona usuaria elige en la web. Por eso `vehiculo_id_referencia` es `null` en ese caso. |
| Imagen sin hallazgos candidatos tras el filtro previo: ¿se consulta la categoría? | Supuesto explícito aceptable | Sí, siempre: el campo `vehiculo` queda siempre presente y el contrato es estable. Coste marginal: como mucho 1 llamada. |
| Fallo del proveedor en la consulta de categoría (timeout, error de red, tras el reintento del SDK): ¿se degrada a `desconocido`? | Supuesto explícito aceptable | No: se propaga la excepción, igual que hoy con las consultas por hallazgo, para no ocultar fallos con un `desconocido` que parece una respuesta válida (AC-007). |
| Acierto real del modelo de visión al clasificar categoría con las fotos de CarDD. | Pregunta no bloqueante | No hay dato. Se mide en AC-011; hasta entonces es una hipótesis. Un acierto bajo obliga a revisar el prompt, no a cambiar el contrato. |
| Error de coste por usar un representante dentro de cada categoría. | Resuelta con evidencia (parcial) | La exploración previa midió un error máximo del 0 % al 9 % dentro de cada categoría, salvo `B` y `SUV-B` (hasta 30 %), con un siniestro de referencia. Esa medición no está en el repo: se reproduce con la herramienta de la empresa y se adjunta a la PR de entrega (DoD). |

## Comportamiento que debe preservarse

- `image_id`, `resumen_filtro_previo` y cada elemento de `findings` (claves y valores) no cambian para las mismas respuestas del modelo. `vehiculo` es la única clave nueva del nivel superior (cambio aditivo). → AC-006
- La clave de caché de las consultas por hallazgo no cambia: las respuestas ya pagadas y guardadas en `cache_vision/` siguen acertando. → AC-006, AC-008
- `evaluar_vision.py` y `analizar_detecciones.py` no hacen consultas de categoría del vehículo: su recuento de llamadas y su gasto estimado no varían. La consulta vive en el flujo completo del Agente 1 (`analizar_imagen`), no en las funciones por hallazgo. → AC-006
- Los scripts de prueba existentes (`probar_vision_stub.py`, `probar_agente1_stub.py`, `probar_seleccion_stub.py`, `probar_evaluar_vision_stub.py`, `probar_lote_stub.py`, `colab/probar_exportar_stub.py` y `agente_recuperacion/probar_costes.py`) siguen en verde. Si el cliente falso debe responder también a la nueva consulta, o el validador de salidas debe aceptar `vehiculo`, ese cambio en el test es legítimo y se documenta en la PR. → AC-006
- El Agente 2 sigue exigiendo `vehiculo_id` en el contexto, como hoy (#30): esta Issue no toca su código. → AC-006
- El ejemplo `agente1_salida.json` y las 30 salidas reales de `ejemplos_contrato/agente1_real/` se actualizan para incluir `vehiculo` como único cambio de forma; las 30 salidas se regeneran desde la caché de hallazgos más una consulta de categoría por imagen. → AC-005, AC-006

## Failure modes y requisitos no funcionales

| Condición | Comportamiento esperado | Cobertura |
|---|---|---|
| Respuesta con categoría inventada, sin JSON, JSON sin `categoria` o vacía. | `desconocido`, confianza `baja`, `vehiculo_id_referencia` `null`. | AC-002 |
| Categoría válida con confianza fuera de `alta/media/baja`. | Confianza `baja`. | AC-003 |
| El modelo declara `desconocido` con confianza `alta`. | Confianza `baja`. | AC-003 |
| El proveedor falla en la consulta de categoría. | La excepción se propaga; no se devuelve un `vehiculo` inventado. | AC-007 |
| Misma consulta repetida con caché. | Cero llamadas y cero consumo de tokens. | AC-008 |
| Un consumidor que no conoce `vehiculo` (por ejemplo, el Agente 2 de hoy). | Lo ignora: el campo es aditivo. | AC-006 |
| Privacidad: la descripción libre podría contener datos personales o una matrícula legible. | El prompt no los pide y la muestra manual comprueba que ninguna descripción los contiene. | AC-005, AC-011 |
| Coste: una llamada más por imagen. | +1 llamada por imagen (para las 500 imágenes del export, +500 sobre las ~3.700 con filtro previo); la caché evita repetirla. | AC-001, AC-008 |
| Secretos: clave y fotos. | La clave solo va en `OPENAI_API_KEY`; ni claves, ni fotos de CarDD, ni el export se suben a git. | PR de entrega (revisión de diff) |

## Acceptance Criteria

| ID | Dado / Cuando | Resultado esperado y condición de éxito |
|---|---|---|
| AC-001 | Una imagen con N hallazgos candidatos (N = 0, 1 y 5), cuando se ejecuta el Agente 1 con un cliente de visión que registra sus llamadas. | El cliente recibe exactamente **una** consulta de categoría de vehículo, con **una sola** imagen adjunta, sea cual sea N. Esa imagen es la foto completa, con el lado largo ≤ 1024 px y sin la caja roja de los hallazgos (con una foto sintética gris uniforme, la imagen enviada no contiene píxeles rojos). |
| AC-002 | La respuesta del modelo a la consulta de categoría es: una categoría fuera de la lista, un texto que no es JSON, un JSON sin `categoria`, o una cadena vacía. | `vehiculo.categoria == "desconocido"`, `vehiculo.confianza == "baja"` y `vehiculo.vehiculo_id_referencia is None`; no se lanza ninguna excepción. |
| AC-003 | El modelo responde `desconocido` con confianza `alta`, o una categoría válida con una confianza fuera de `alta/media/baja`. | En ambos casos `vehiculo.confianza == "baja"`. Con categoría válida y confianza válida, la confianza declarada se conserva. |
| AC-004 | El modelo responde, para cada una de las 8 categorías, un JSON válido (también envuelto en un bloque ```` ```json ````). | `vehiculo.categoria` es la declarada; `vehiculo_id_referencia` existe en `vehiculos.csv` y su `segmento` es esa categoría. Para `desconocido` es `null`. |
| AC-005 | Una ejecución completa del Agente 1 con el modelo `modelo-falso`, y los ejemplos del contrato. | `vehiculo` contiene **exactamente** las claves `categoria`, `vehiculo_id_referencia`, `confianza`, `descripcion` y `modelo`, y `modelo` es el identificador con el que se hizo la consulta. El JSON guardado en disco coincide con el devuelto. Los ejemplos del contrato (`agente1_salida.json` y las 30 salidas de `agente1_real/`) contienen `vehiculo` con esas cinco claves y pasan `validar_salida_agente1`. |
| AC-006 | Las mismas respuestas del modelo y los mismos datos de entrada que antes del cambio. | `image_id`, `resumen_filtro_previo` y `findings` son idénticos a los de `main`; `vehiculo` es la única clave nueva del nivel superior. Una entrada de caché de un hallazgo generada con la versión de `main` sigue acertando. `evaluar_vision.py` no hace consultas de vehículo (mismo recuento de llamadas). Los 7 scripts de prueba existentes siguen en verde, con los cambios de test legítimos documentados, y `agente_recuperacion/probar_costes.py` pasa sin tocar el código del Agente 2. |
| AC-007 | El cliente lanza una excepción en la consulta de categoría. | La excepción llega al llamante de `analizar_imagen`; no se devuelve ningún `vehiculo` ni se escribe un fichero de salida parcial. |
| AC-008 | Se ejecuta dos veces el Agente 1 con la misma imagen, modelo y prompt, con `cache_dir`. | La segunda ejecución no hace ninguna llamada al cliente (ni de vehículo ni de hallazgos) y devuelve un `vehiculo` idéntico. Sin `cache_dir`, la consulta se repite. |
| AC-009 | **Transferido** (v1.2, 2026-10-27). | Pasa a la #34, que es dueña de la confirmación en la web y del campo de procedencia (ADR 0007); esta Issue no lo verifica. El ID no se reutiliza. El texto de la v1.1 se conserva en `e180219`. |
| AC-010 | **Transferido** (v1.2, 2026-10-27). | Pasa a la #31, que lo recoge con un AC de ID nuevo cuando la #34 fije el campo de procedencia (ADR 0007); esta Issue no lo verifica. El ID no se reutiliza. El texto de la v1.1 se conserva en `e180219`. |
| AC-011 | 20 fotos de CarDD elegidas con muestreo reproducible, y el modelo real de la cuenta de la empresa. | Se documenta por imagen la categoría estimada y la que juzga una persona sin ver la respuesta, con tasa de coincidencia exacta, matriz de confusión y la tasa de la referencia «predecir siempre la categoría más frecuente de la muestra». Se declara el límite de una muestra de 20 fotos (un error son 5 puntos). Ninguna descripción contiene datos personales ni una matrícula legible. No se fija umbral de aceptación: con esa tabla una persona decide si el prompt basta o se ajusta (nuevo ciclo con otra muestra). |

## Test Plan

### Test seams

- **S1 — `agente1.analizar_imagen(...)`:** función pública ya existente y ya probada con cliente falso (`probar_agente1_stub.py`). Contrato: JSON de PIIA-1 + foto + cliente → diccionario serializable del contrato Agente 1 → Agente 2/3. Es el nivel más alto que verifica de forma fiable AC-001 a AC-008; no hace falta probar funciones internas.
- **S2 — Cliente de visión inyectado (`client.chat.completions.create`):** frontera externa ya existente; el cliente falso de `probar_vision_stub.py` permite observar nº de llamadas, prompt, imágenes adjuntas y devolver respuestas guionizadas (válidas, inválidas, vacías, excepción).
- **S3 — `vehiculos.csv`:** datos de la empresa; contrato de AC-004.
- **S4 — Ejemplos del contrato:** `ejemplos_contrato/agente1_salida.json` y `agente1_real/*.json`, validados con `validar_salida_agente1`, para AC-005.
- No se proponen fronteras nuevas: los módulos y funciones nuevos (parseo, tabla de representantes, reducción de la foto) son detalles internos y no se prueban directamente.

Cada test lleva en su nombre o comentario `28-categoria-vehiculo.md#AC-0XX`.

### Plan de verificaciones

Los scripts se ejecutan desde `entregas/cu-19-interpretacion-danos/app/agentes/agente_multimodal/` con `python <script>` (usan imports planos entre módulos hermanos).

| Referencia (ruta de Spec + AC) | Seam / contrato | Estrategia y nivel | Caso / resultado esperado | Datos / entorno | Comando o pasos previstos | Evidencia prevista |
|---|---|---|---|---|---|---|
| `specs/28-categoria-vehiculo.md#AC-001` | S1 + S2 | TDD (Red → Green → Refactor); integración con cliente falso | N = 0, 1, 5: 1 llamada de vehículo, 1 imagen, lado largo ≤ 1024 px, sin píxeles rojos | Foto sintética gris grande (> 1024 px); detecciones de `ejemplos/*.json` | `python probar_vehiculo_stub.py` | Salida del script: Red (falla por campo ausente) y Green |
| `specs/28-categoria-vehiculo.md#AC-002` | S1 + S2 | TDD; integración | 4 respuestas inválidas → `desconocido` / `baja` / `null` | Cliente falso con respuestas guionizadas | `python probar_vehiculo_stub.py` | Red y Green |
| `specs/28-categoria-vehiculo.md#AC-003` | S1 + S2 | TDD; integración | Confianza `alta` con `desconocido` y confianza inválida → `baja`; confianza válida se conserva | Cliente falso | `python probar_vehiculo_stub.py` | Red y Green |
| `specs/28-categoria-vehiculo.md#AC-004` | S1 + S2 + S3 | TDD; integración y contrato con datos | 8 categorías (con y sin bloque ```` ```json ````): referencia existe en `vehiculos.csv` con ese `segmento`; `desconocido` → `null` | `piia2_paquete_datos/data/vehiculos.csv` (paquete de la empresa, local) | `python probar_vehiculo_stub.py` | Red y Green; ejecución con el paquete presente |
| `specs/28-categoria-vehiculo.md#AC-005` | S1 + S4 | TDD; contrato de esquema | Conjunto de claves de `vehiculo` == las 5; `modelo` == `modelo-falso`; JSON en disco == devuelto; el ejemplo y las 30 salidas validan con `vehiculo` | Cliente falso; salida en directorio temporal; `ejemplos_contrato/` | `python probar_agente1_stub.py` y `python probar_lote_stub.py` | Red y Green |
| `specs/28-categoria-vehiculo.md#AC-006` | S1 + S2 | Regresión (sin rojo artificial: ya se cumple en `main`) | Findings idénticos; claves de nivel superior = anteriores + `vehiculo`; fixture de caché de hallazgo de `main` acierta; `evaluar_vision` sin llamadas de vehículo; el Agente 2 no cambia | Tests existentes; una entrada de caché generada con `main` como fixture | `python probar_vision_stub.py`, `probar_agente1_stub.py`, `probar_seleccion_stub.py`, `probar_evaluar_vision_stub.py`, `probar_lote_stub.py`, `colab/probar_exportar_stub.py` y, desde `agente_recuperacion/`, `python probar_costes.py` | Los 7 scripts en verde antes (base `main`) y después |
| `specs/28-categoria-vehiculo.md#AC-007` | S1 + S2 | TDD; integración | El cliente lanza una excepción en la consulta de vehículo: se propaga, sin fichero parcial | Cliente falso que lanza | `python probar_vehiculo_stub.py` | Red y Green |
| `specs/28-categoria-vehiculo.md#AC-008` | S1 + S2 | TDD; integración | 2.ª ejecución con `cache_dir`: 0 llamadas y `vehiculo` idéntico; sin `cache_dir`, se repite | Directorio de caché temporal; contador de llamadas del cliente falso | `python probar_vehiculo_stub.py` | Red y Green |
| `specs/28-categoria-vehiculo.md#AC-009` | — | Transferido | — | — | — | Sin verificación en esta Issue: transferido a la #34 y la #31 en la v1.2 |
| `specs/28-categoria-vehiculo.md#AC-010` | — | Transferido | — | — | — | Sin verificación en esta Issue: transferido a la #34 y la #31 en la v1.2 |
| `specs/28-categoria-vehiculo.md#AC-011` | Modelo real | Eval-first (probabilístico): referencia «categoría más frecuente» → medición con el prompt inicial → una persona decide si ajustarlo (sin umbral) → reevaluación con otra muestra si se ajusta | Tabla por imagen, coincidencia exacta, matriz de confusión y tasa de la referencia; sin datos personales en descripciones | 20 `image_id` de `baseline_500` con `random.Random(28).sample(sorted(ids), 20)`; modelo en `OPENAI_MODEL`; clave en `OPENAI_API_KEY`. Si se ajusta el prompt, la reevaluación usa otra muestra de 20 (otra semilla) para no ajustar a la primera | Un script de ejecución y la revisión manual de la persona que valida | Tabla en la PR de entrega (con `image_id`, sin subir las fotos) |

## Implementation Plan

| Slice | Objetivo observable | AC relacionados | Componentes / contratos probablemente afectados | Dependencias | Verificación prevista |
|---|---|---|---|---|---|
| 1 — Categoría válida y registrada | `analizar_imagen` devuelve `vehiculo` con categoría validada, coche de referencia, confianza normalizada y modelo. | AC-002, AC-003, AC-004, AC-005 | Salida del Agente 1; tabla categoría → coche (acoplada a `vehiculos.csv`) | Ninguna | Filas AC-002 a AC-005 |
| 2 — Una consulta por imagen, con caché | Una sola llamada con la foto completa reducida; error del proveedor propagado; respuesta cacheada. | AC-001, AC-007, AC-008 | Reutilización del mecanismo de llamada con caché de `vision.py` sin cambiar su clave; reducción de la foto | Slice 1 | Filas AC-001, AC-007, AC-008 |
| 3 — Sin regresiones y salidas de ejemplo | Findings y caché previa intactos; `evaluar_vision` no gasta más; el validador y las 30 salidas reales aceptan `vehiculo`; los 7 tests existentes en verde. | AC-005, AC-006 | Tests existentes (cliente falso que ahora debe contestar también a la consulta de categoría); `evaluar_vision.py`; `generar_lote.py` (`CAMPOS_SALIDA`); `probar_lote_stub.py`; `ejemplos_contrato/agente1_real/` | Slices 1 y 2 | Filas AC-005 y AC-006 |
| 4 — Documentación del contrato | La arquitectura, los ejemplos del contrato y el README del Agente 1 describen `vehiculo` y el `vehiculo_id` como dato de entrada confirmado por la persona usuaria. Se reproduce la tabla de costes por categoría. | AC-005, AC-006 | `specs/piia2-arquitectura-multiagente.md` (fila `vehiculo_id`, «Entrada del siniestro», contrato Agente 1 → 2), `ejemplos_contrato/`, README del Agente 1 | Slice 1 (forma de `vehiculo`) | Filas AC-005 y AC-006 |
| 5 — Validación con el modelo real | Evidencia de que la categoría coincide con el juicio humano en una muestra de 20 fotos. | AC-011 | Ninguno (evaluación); posible ajuste del prompt | Slices 1 y 2; clave de la empresa en variable de entorno | Fila AC-011 |

AC-009 y AC-010 se transfirieron en la v1.2: la slice 4 conserva solo la documentación y los ejemplos del contrato.

## Pendientes para Ready

1. **Revisión humana de esta Planning PR** (Spec, ADR decision y ADR 0001): quien revise debe ser una persona distinta del agente que redactó los documentos; ningún agente aprueba ni integra la PR. **Cumplido (2026-10-28):** revisaron Víctor Hidalgo (`Vija97`; reviews del [2026-10-20](https://github.com/lvckss/piia2-26/pull/29#pullrequestreview-5588169983), del [2026-10-27](https://github.com/lvckss/piia2-26/pull/29#pullrequestreview-5667756429) y la [APPROVED del 2026-10-28](https://github.com/lvckss/piia2-26/pull/29#pullrequestreview-5682298653) sobre `086dc93`) y Lucas García (`lvckss`; [review del 2026-10-27](https://github.com/lvckss/piia2-26/pull/29#pullrequestreview-5671225942) sobre `dca27ad`); la PR #29 la aprobó Víctor sobre el head final `086dc93` y la integró Lucía Luis Castaño (`lucia-luis-castano`; merge `246634f`).
2. **Confirmar en la revisión** la transferencia de AC-009 y AC-010 y la ausencia de umbral en AC-011 (decisiones de Lucía del 2026-10-27) y la forma de `desconocido`, sin coche de referencia (decisión de Lucas del 2026-10-26). **Cumplido:** Víctor ([review del 2026-10-27](https://github.com/lvckss/piia2-26/pull/29#pullrequestreview-5667756429)) y Lucas ([review del 2026-10-27](https://github.com/lvckss/piia2-26/pull/29#pullrequestreview-5671225942)) confirman la transferencia de AC-009 y AC-010 y la forma de `desconocido`; Lucas, además, la ausencia de umbral en AC-011.
3. **Aceptación del ADR 0001** (Propuesto → Aceptado) por un humano en la Planning PR, y paso de esta Spec a Revisada con quién, referencia y versión. **Cumplido:** ADR 0001 Aceptado y esta Spec Revisada (v1.3) por Víctor Hidalgo (`Vija97`), [review APPROVED del 2026-10-28](https://github.com/lvckss/piia2-26/pull/29#pullrequestreview-5682298653) sobre `086dc93`; registrado en esta corrección documental, posterior a la integración (solo metadatos).
4. **Revisión de Víctor (Agentes 2 y 3) y de Lucas (#34)** del campo `vehiculo` y de cómo la #34 y la #31 recogerán lo transferido (AC-009 y AC-010). **Cumplido:** ambos revisaron el campo `vehiculo` y la transferencia. La valoración favorable de Lucas dejaba pendiente la aclaración del punto 5 del ADR 0001, que recoge la v1.3 aprobada por Víctor; su aprobación final no consta en la PR.
5. **ADRs previos identificados:** aplican el ADR 0002 (contrato; exige este ADR para cambiar la forma), el 0003 (proveedor) y el 0004 (herramienta de costes), todos Aceptados e integrados en `main` (PR #51).

### Resultado de analyze

| Comprobación | Resultado |
|---|---|
| Cada requisito de la Issue tiene AC | Consulta por imagen → AC-001; validación → AC-002, AC-003; traducción a coche → AC-004; modelo registrado → AC-005; caché → AC-008. El uso en el Agente 2 y en el informe (AC-009 y AC-010) se transfiere a la #34 y la #31 por decisión humana (v1.2). |
| AC sin requisito en la Issue | AC-006 (preservación), AC-007 (fallo del proveedor) y AC-011 (validación manual) no amplían el alcance funcional: protegen comportamiento existente, un failure mode y la calidad de la funcionalidad. Se señalan para que la revisión los acepte. |
| Cada AC tiene verificación y slice | Sí, ver Test Plan e Implementation Plan (AC-001 a AC-008 y AC-011 con fila y slice; AC-009 y AC-010 transferidos). |
| Comportamiento preservado con protección | Sí, en AC-006 (y AC-008 para la caché). |
| Failure modes relevantes con cobertura | Sí, tabla de failure modes. Quedan sin AC propio solo la privacidad de la descripción (cubierta por AC-005 y AC-011) y los secretos (revisión del diff de la PR). |
| ADR decision coherente | NEW_ADR, con ADR 0001 Aceptado y alternativas reales; no oculta ninguna decisión relevante. |
| Gap conocido | El uso de la categoría en el Agente 2 y en el informe queda fuera de esta Spec (transferido). Hasta que la #34 y la #31 lo recojan, el sistema de punta a punta presupuesta con el `vehiculo_id` que entregue la web. Está declarado y es una pregunta para la revisión. |

## Definition of Done

La DoD global está definida por el workflow y la checklist de la Issue enlazada. Esta sección añade condiciones de esta funcionalidad y no relaja la global. Todos los AC deben estar verificados con evidencia trazable mediante `ruta de Spec + AC ID`.

| Condición específica de cierre | Evidencia requerida |
|---|---|
| Los 7 scripts de prueba existentes y el nuevo `probar_vehiculo_stub.py` pasan, ejecutados con el paquete de datos de la empresa presente. | Salida de los comandos de la tabla de verificaciones, pegada en la PR de entrega. |
| Evidencia de TDD: los tests de AC-001 a AC-005, AC-007 y AC-008 fallan antes del cambio por el comportamiento ausente (no por un error de importación) y pasan después. | Salida Red y Green en la PR de entrega. |
| Tabla de coste por categoría con el siniestro de referencia (faro, paragolpes y parabrisas graves), reproducida con la herramienta de la empresa, y error del coche representante dentro de su categoría. | Tabla en la PR de entrega (justifica la elección de los representantes del ADR). |
| Validación manual de AC-011 documentada con la muestra, la tasa de coincidencia, la tasa de la referencia de la categoría más frecuente y el modelo usado. | Tabla en la PR de entrega, con `image_id` y sin subir fotos de CarDD. |
| Documentación actualizada: arquitectura multiagente (fila `vehiculo_id` y contrato), ejemplos de contrato y README del Agente 1. | Diff de la PR de entrega. |
| Esta Spec forma parte de lo integrado en `main` y su enlace con el ADR 0001 sigue vigente. | Archivo en `main` tras la Planning PR. |
