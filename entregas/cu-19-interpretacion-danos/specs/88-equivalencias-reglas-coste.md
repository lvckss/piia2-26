# Spec: Equivalencias de reglas de coste para las combinaciones sin regla

- GitHub Issue: https://github.com/lvckss/piia2-26/issues/88
- Estado: Borrador
- ADR decision: NEW_ADR
- ADR: [docs/adr/0008-equivalencias-reglas-coste.md](../docs/adr/0008-equivalencias-reglas-coste.md) — Propuesto
- Justificación: el cambio modifica una decisión aceptada, el punto 3 del [ADR 0004](../docs/adr/0004-herramienta-costes-datos-empresa.md) («el equipo no inventa procedimientos de reparación»), y su consecuencia «una combinación sin regla se deja fuera del coste». Afecta a la frontera entre agentes (qué hallazgos entran en el presupuesto) y a una tabla compartida por los Agentes 1, 2 y 3, con consumidores independientes. No cambia el contrato del [ADR 0002](../docs/adr/0002-contrato-json-entre-agentes.md).
- Plan vigente / versión: **v1** (2026-11-12), este archivo en la rama `plan/88-equivalencias-reglas-coste`; el commit exacto se registra en un comentario de la Issue.
- Riesgo y revisión previa: **sí requiere revisión previa** (disparador: NEW_ADR). Impacto medio: cambia importes de los informes de los hallazgos afectados (24 de 1.746 en las 500 imágenes). Reversibilidad alta: la tabla es un archivo versionado y borrar una fila restablece el comportamiento anterior. Incertidumbre media: la elección de cada equivalencia es criterio de dominio, con la regla de la empresa siempre por delante.
- Planning PR: <completar al abrirla>

## Qué construir

Cuando un hallazgo del Agente 1 tiene pieza y severidad pero su combinación de clase de daño, zona de la pieza y severidad no tiene regla en `reglas_dano.csv`, hoy queda fuera del coste. Se añade una **tabla de equivalencias** versionada (`app/agentes/comun/equivalencias_reglas.csv`) y un módulo común que, para esas combinaciones, devuelve la regla de una combinación vecina que sí existe. Los tres agentes la consumen:

- **Agente 1:** `regla_coste_aplicable` es `true` si la combinación tiene regla propia o equivalencia.
- **Agente 2:** traduce los `danos` a la clase y la severidad efectivas al llamar a `estimar_coste` y al calcular la cobertura; el hallazgo entra en el presupuesto como cualquier otro, en «confirmados» o en «con pendientes» según su `confidence_tier`, que esta Spec no cambia.
- **Agente 3:** usa la acción de la regla efectiva en la columna «Reparación»; el informe no menciona equivalencias.

Equivalencias iniciales (detalle y motivos en el ADR): `glass_shatter` en óptica → `lamp_broken`; `lamp_broken` en cristal → `glass_shatter`; `crack` en neumático → `tire_flat` con severidad mínima moderada; `lamp_broken` en retrovisor → `crack`. Sin equivalencia: `scratch` en cristal, neumático y óptica, `crack` en estructura y `glass_shatter` en panel metálico.

## Por qué

36 de los 37 hallazgos sin regla de las 500 imágenes los había confirmado la IA. En las 30 salidas versionadas son 3 hallazgos: con la tabla inicial, 2 pasan a tener regla (`1248-9`, cristal roto en un piloto, y `381-14`, grieta en un neumático) y el tercero (`3478-4`, un arañazo en un piloto, que deja el informe `003478` a 0 €) sigue fuera del coste a propósito, porque sustituir un piloto por un arañazo sobrestimaría el importe; queda como limitación documentada. El tutor de la entidad indicó que se pueden modificar las reglas y recomendó no presentarlas como propias. El proyecto debe poder corregir lo que aparece al evaluarlo, con la decisión documentada.

## Alcance

- Incluido: la tabla y el módulo comunes; su uso en los Agentes 1, 2 y 3; la actualización determinista de las salidas versionadas y los ejemplos afectados; la medición sobre las 500 imágenes; el ADR 0008 y la documentación de las equivalencias.
- Fuera de alcance: modificar el paquete o la herramienta de la empresa; precios, tiempos o procedimientos nuevos; los 135 hallazgos sin pieza o severidad (identificación de pieza del Agente 1); cambiar `category`, `clase_tool` o `severidad` de un hallazgo; marcar en el informe que una regla es propia; nuevas llamadas a la API.

## Restricciones y supuestos

- La regla de la empresa siempre prevalece: una equivalencia solo actúa si la combinación de origen no tiene regla.
- Una equivalencia solo puede apuntar a una combinación que exista en `reglas_dano.csv` para las tres severidades (con la mínima aplicada); no se crean acciones nuevas.
- Un hallazgo conserva su clase detectada, su severidad y los 13 campos del contrato; la equivalencia se aplica al consumir.
- El paquete de la empresa no se versiona: las pruebas que lo usan avisan si falta, como las existentes.

| Incertidumbre | Clasificación | Evidencia / supuesto / pregunta y efecto |
|---|---|---|
| ¿Dónde se aplica la equivalencia? | Resuelta con evidencia | Se lee `reglas_dano.csv` en tres sitios: `combinacion_valida` del Agente 1 (`catalogo.py`), `_danos` del Agente 2 (`costes_y_cobertura.py`) y `_reparacion` del Agente 3 (`informe.py`); el ADR compara las alternativas |
| ¿Cambiar `clase_tool` en el Agente 1 sería más simple? | Resuelta con evidencia | No: la spec del Agente 1 define `clase_tool` como la clase con guiones bajos (`probar_agente1_stub.py` lo comprueba) y el informe muestra la clase a partir de `clase_tool` |
| ¿Hay que validar la lista con el tutor? | Resuelta (decisión humana) | Lucía decidió el 2026-11-12 que no hace falta; el tutor ya autorizó modificar las reglas |
| ¿Se reutiliza «arañazo en cristal» con la regla de grieta? | Resuelta (criterio del equipo) | No: la tabla de la empresa solo contempla impacto, grieta y cristal roto en cristal; un arañazo no es un procedimiento de esa tabla. Queda fuera del coste, visible para revisión humana. Se reabre si aparece evidencia |
| Severidad mínima de `crack` en neumático | Supuesto explícito aceptable | `tire_flat` leve es «reparar pinchazo» y una grieta no se repara; se parte de moderado («sustituir neumático»). Revisable en la tabla |
| ¿Se añadirán más equivalencias? | Pregunta no bloqueante | La tabla permite añadir una fila con su motivo; AC-001 protege su coherencia con `reglas_dano.csv` |

## Comportamiento que debe preservarse

- **Contrato Agente 1 → Agentes 2 y 3** ([ADR 0002](../docs/adr/0002-contrato-json-entre-agentes.md)): 13 campos por hallazgo; `clase_tool` es la clase con guiones bajos. Protegido por `probar_agente1_stub.py`, `probar_lote_stub.py` y AC-003.
- **Importes y hallazgos sin equivalencia:** las combinaciones con regla propia o sin equivalencia se comportan igual que hoy. Protegido por `probar_costes.py`, `probar_informe.py` y AC-006.
- **Determinismo del informe** ([spec 31 AC-012](31-informe-peritaje.md)): mismas entradas, mismo informe, sin clave ni red. Protegido por `probar_informe.py` y AC-009.
- **Texto del informe:** los 9 encabezados y la cabecera de la spec 31 no cambian.

## Failure modes y requisitos no funcionales

| Situación | Comportamiento esperado | AC |
|---|---|---|
| Falta `equivalencias_reglas.csv` o tiene una fila mal formada | Error claro con la ruta y la fila; nunca se ignora la tabla en silencio | AC-009 |
| Una equivalencia apunta a una combinación inexistente o tiene motivo vacío | La prueba de coherencia falla | AC-001 |
| Una combinación tiene regla propia y equivalencia | Prevalece la regla de la empresa | AC-002 |
| Hallazgo sin equivalencia | Sigue como `sin_regla_de_coste` | AC-003, AC-006 |
| Paquete de la empresa ausente | Las pruebas que lo necesitan avisan y se saltan, como las existentes | AC-001 |

## Acceptance Criteria

| ID | Dado / Cuando | Resultado esperado y condición de éxito |
|---|---|---|
| AC-001 | `equivalencias_reglas.csv` y el `reglas_dano.csv` real del paquete. | Cada fila tiene su motivo; ninguna combinación de origen tiene regla propia; la de destino, con la severidad mínima aplicada, existe para `leve`, `moderado` y `grave`; no hay filas duplicadas. |
| AC-002 | La función común que resuelve la regla efectiva de `(clase, zona, severidad)`, con las cuatro equivalencias iniciales, una combinación con regla propia, una sin equivalencia y `crack` en neumático con severidad `leve`. | Devuelve `(clase_destino, severidad_efectiva)` para las cuatro equivalencias, con severidad `moderado` en la grieta de neumático leve; con regla propia devuelve la propia sin traducir; sin equivalencia devuelve «sin regla». |
| AC-003 | Una respuesta de visión que confirma `glass_shatter` en `PILOTO_TRAS_I` con severidad `moderado`, y otra con `scratch` en `PARABRISAS`. | La primera sale con `regla_coste_aplicable = true` y la segunda con `false`; `category`, `clase_tool` y `severidad` no cambian en ninguna; cada hallazgo tiene los 13 campos y su `confidence_tier` sale de `decidir_tier` (con un score sobre el umbral de la clase, la primera es `confirmed`; la segunda, `needs_review`). |
| AC-004 | La salida del Agente 1 de la imagen 1248 ya actualizada con la tabla (AC-007): el hallazgo `1248-9` es un cristal roto en `PILOTO_TRAS_I`, severidad `moderado`, visión «confirmado», score 0,54 (por debajo del umbral 0,6, luego `needs_review`), con `regla_coste_aplicable = true`; se ejecuta `estimar_siniestro`. | Antes salía en `hallazgos_fuera_del_coste` con `sin_regla_de_coste`; ahora está en `hallazgos_incluidos` del escenario `con_pendientes` y no en el de `confirmados`, y su coste es el que da `estimar_coste` llamada directamente con `lamp_broken` sobre la misma pieza y severidad; la cobertura usa la clase efectiva. |
| AC-005 | El informe de la salida de AC-004. | `1248-9` aparece en «Daños pendientes de revisión» con la clase detectada y, en «Reparación», la acción de la regla efectiva; ya no figura en «Detecciones no incluidas en el coste»; el texto no contiene «equivalencia» ni «regla propia»; `comprobar_cifras == []`. |
| AC-006 | Un hallazgo sin equivalencia (`scratch` en cristal) y otro con regla propia, en la misma salida que uno con equivalencia. | El primero sigue en `hallazgos_fuera_del_coste` con `sin_regla_de_coste`; los importes de los demás no cambian respecto a la salida sin la tabla. |
| AC-007 | Las 500 salidas locales del Agente 1 (sin llamar a la API) con la tabla inicial. | Los hallazgos no rechazados con pieza y severidad sin regla pasan de 37 a 13 (los de las combinaciones sin equivalencia); los 24 con equivalencia pasan a tener regla; ningún otro hallazgo cambia de `regla_coste_aplicable`. De las 30 salidas versionadas (`ejemplos_contrato/agente1_real/`) cambian solo `000381` y `001248`; `003478` no cambia. Esas salidas y los ejemplos del contrato afectados se actualizan de forma determinista (`regla_coste_aplicable` y `confidence_tier`) y `probar_lote_stub.py` sigue en verde. |
| AC-008 | La documentación del Agente 1 y los ADR 0004 y 0008. | Constan la tabla, el motivo de cada equivalencia y que el informe no las marca; el 0008 figura Aceptado con quién y dónde, y el 0004 enlaza el 0008. |
| AC-009 | `equivalencias_reglas.csv` ausente, con una fila incompleta, y dos ejecuciones iguales de `generar_informe` sobre una salida con una equivalencia. | Los dos primeros casos lanzan un error con la ruta y la fila; las dos ejecuciones dan el mismo informe sin clave ni red. |

## Test Plan

Seams: la función común de resolución (módulo `comun`), `parsear_respuesta` del Agente 1, `estimar_siniestro` del Agente 2 y `generar_informe` del Agente 3, todas ya públicas o equivalentes a las que usan las pruebas existentes; no se prueban internals.

| Referencia (ruta de Spec o URL del plan + AC) | Seam / contrato | Estrategia y nivel | Caso / resultado esperado | Datos / entorno | Comando o pasos previstos | Evidencia prevista |
|---|---|---|---|---|---|---|
| `specs/88-equivalencias-reglas-coste.md#AC-001` | Tabla y paquete de la empresa | TDD de contrato | Coherencia de cada fila con `reglas_dano.csv` | `reglas_dano.csv` real (se avisa si falta) | prueba nueva del módulo común | Red/Green |
| `specs/88-equivalencias-reglas-coste.md#AC-002` | Función de resolución | TDD unitario | Las cuatro equivalencias, regla propia, sin equivalencia y severidad mínima | Tabla de prueba | prueba nueva del módulo común | Red/Green |
| `specs/88-equivalencias-reglas-coste.md#AC-003` | `parsear_respuesta` | TDD, cliente falso | `regla_coste_aplicable` y campos intactos | `MINI_CATALOGO` ampliado | `python probar_vision_stub.py` | Red/Green |
| `specs/88-equivalencias-reglas-coste.md#AC-004` | `estimar_siniestro` | TDD de integración con la herramienta real | Coste igual a la llamada directa con la clase destino | Paquete de la empresa, `1248-9` | `python probar_costes.py` | Red/Green |
| `specs/88-equivalencias-reglas-coste.md#AC-005` | `generar_informe` | TDD | Acción de la regla efectiva; sin «equivalencia» | Salida de AC-004 | `python probar_informe.py` | Red/Green |
| `specs/88-equivalencias-reglas-coste.md#AC-006` | Agentes 1 y 2 | Regresión | Sin equivalencia sigue fuera; importes ajenos sin cambio | Ejemplos del contrato | `probar_costes.py` y `probar_lote_stub.py` | Verde antes y después |
| `specs/88-equivalencias-reglas-coste.md#AC-007` | Salidas del Agente 1 | Evaluación determinista, sin API | 37 → 13 y 24 con regla; resto igual | 500 salidas locales (no versionadas) y 30 versionadas | script de recuento y `probar_lote_stub.py` | Tabla antes y después |
| `specs/88-equivalencias-reglas-coste.md#AC-008` | Documentos | Revisión de contenido y diff | Tabla, motivos y ADR Aceptado | ADR 0004 y 0008, README del Agente 1 | Revisión humana | Diff de la PR |
| `specs/88-equivalencias-reglas-coste.md#AC-009` | Módulo común y `generar_informe` | TDD | Errores claros y determinismo | Tablas de prueba | prueba nueva y `probar_informe.py` | Red/Green |

Regresión de todas las slices: `probar_agente1_stub.py`, `probar_vision_stub.py`, `probar_lote_stub.py`, `probar_vehiculo_stub.py`, `probar_costes.py` y `probar_informe.py`, con `python <script>` sin `PYTHONIOENCODING`.

## Implementation Plan

| Slice | Objetivo observable | AC relacionados | Componentes / contratos probablemente afectados | Dependencias | Verificación prevista |
|---|---|---|---|---|---|
| 1 — Tabla y módulo común | La regla efectiva se resuelve y se valida contra la tabla de la empresa | AC-001, AC-002, AC-009 | `app/agentes/comun/` (nuevo) | ADR 0008 Aceptado | Pruebas nuevas del módulo |
| 2 — Agente 1 | `regla_coste_aplicable` refleja las equivalencias sin tocar el resto del hallazgo | AC-003 | `catalogo.py`, `vision.py` | Slice 1 | `probar_vision_stub.py` |
| 3 — Agente 2 | El hallazgo equivalente entra en el presupuesto y la cobertura | AC-004, AC-006 | `costes_y_cobertura.py` | Slices 1 y 2 | `probar_costes.py` |
| 4 — Agente 3 | La reparación del informe usa la regla efectiva, sin mencionarla | AC-005, AC-009 | `informe.py` | Slices 1 a 3 | `probar_informe.py` |
| 5 — Datos reales | Recuento 37 → 13 y actualización de las salidas y ejemplos afectados | AC-006, AC-007 | Salidas versionadas, ejemplos del contrato, script de recuento | Slices 1 a 4 | Tabla antes y después y `probar_lote_stub.py` |
| 6 — Documentación | Tabla, motivos y ADR registrados | AC-008 | README del Agente 1, ADR 0004 y 0008 | Slice 5 | Revisión de contenido |

Propuesta de reparto (a confirmar): slices 1, 2, 5 y 6 Lucía; 3 y 4 Víctor (sus agentes). Por el triángulo, cada PR la revisa otra persona. Objetivo: Planning PR revisada hacia el 2026-11-18 e implementación integrada antes de la congelación del 2026-11-24.

## Pendientes para Ready

- Revisión humana de esta Spec y de la decisión del ADR 0008, con quién la acepta, permalink y versión; después, merge de la Planning PR por una persona.
- Analyze (2026-11-12): requisitos de la Issue cubiertos por AC-001 a AC-009; cada AC con verificación y slice; el comportamiento preservado protegido por AC-003, AC-006 y AC-009; sin contradicciones con el ADR 0002; el ADR 0008 amplía el 0004 sin reescribirlo. Gaps: ninguno bloqueante. Hay que coordinar con la slice 7 de la #54 (regeneración de las 30 salidas), que no depende de este plan.
- Ninguna pregunta bloqueante.

## Definition of Done

La DoD global está definida por el workflow y la checklist de la Issue enlazada. Esta sección añade condiciones específicas; nunca relaja la global.

| Condición específica de cierre | Evidencia requerida |
|---|---|
| Recuento antes y después sobre las 500 salidas: 37 → 13 hallazgos sin regla, 24 con equivalencia | Salida del script de recuento en la PR de entrega |
| De los 30 informes regenerados cambian solo los de las imágenes 381 y 1248; el de la 3478 sigue a 0 € y consta como limitación | Comparación de los informes antes y después y nota de limitaciones |
| ADR 0008 Aceptado por una persona y ADR 0004 enlazado a él | Enlaces en la PR documental o de entrega |
| Las equivalencias constan en la documentación del Agente 1 | Diff de documentación |
