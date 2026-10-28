# ADR 0001: Categoría del vehículo estimada por visión en el contrato del Agente 1

- Estado: Propuesto
- Fecha: 2026-10-13 (revisado el 2026-10-27, v1.2; punto 5 aclarado el 2026-10-28, v1.3)
- GitHub Issue: https://github.com/lvckss/piia2-26/issues/28
- Planes cubiertos (Issue/mini-spec/Spec): [entregas/cu-19-interpretacion-danos/specs/28-categoria-vehiculo.md](../../entregas/cu-19-interpretacion-danos/specs/28-categoria-vehiculo.md) — la decisión de contrato (campo `vehiculo`) y la consulta por imagen. No cubre la elección ni la comparación de modelos de visión.
- Planning PR: https://github.com/lvckss/piia2-26/pull/29
- Aceptación: pendiente (revisor y referencia de revisión; la completa quien acepte)
- Sustituye / sustituido por: no aplica. Amplía con un campo aditivo el contrato del [ADR 0002](0002-contrato-json-entre-agentes.md) y no cambia su apartado 6: el coche sigue siendo un dato de entrada del sistema, que la persona usuaria confirma a partir de una propuesta.

## Contexto y motivación

La herramienta de costes de la empresa (`estimar_coste`) exige un `vehiculo_id` de un catálogo de 27 modelos agrupados en 8 segmentos. Las fotos de CarDD llevan la matrícula censurada, no traen etiqueta de vehículo y, según la spec de arquitectura, casi ningún coche pertenece a ese catálogo. Sin coche no hay presupuesto, y el coche importa: con el mismo siniestro el coste sin IVA va de unos 1.100 € (furgoneta) a unos 2.100 € (berlina premium) en una medición de la exploración previa que aún hay que reproducir.

Hoy el `vehiculo_id` es un dato de entrada del siniestro (spec de arquitectura y [ADR 0002](0002-contrato-json-entre-agentes.md), apartado 6), «no deducido por el LLM», y el Agente 2 integrado (#30) lo exige. Con fotos de CarDD el dato no existe, así que el sistema no puede presupuestar de punta a punta sin que alguien lo elija.

Hace falta decidir ahora porque el campo nuevo cambia la frontera que consumen los Agentes 2 y 3 y la web de la #34. El ADR 0002 exige un ADR propio para cualquier cambio de forma del contrato, y es más barato fijarlo antes de que la web lo consuma.

Las decisiones en las que se apoya este cambio ya están aceptadas e integradas en `main` (PR #51): el contrato entre agentes (ADR 0002), el proveedor OpenAI (ADR 0003) y la herramienta de costes de la empresa (ADR 0004). Este ADR solo registra el campo que se añade.

## Decisión

1. **Contrato.** La salida del Agente 1 incluye un objeto `vehiculo` con exactamente `categoria`, `vehiculo_id_referencia`, `confianza`, `descripcion` y `modelo`. Es un campo aditivo: quien lo ignore sigue funcionando. `categoria` es uno de los 8 segmentos del catálogo de la empresa (`A`, `B`, `C`, `SUV-B`, `SUV-C`, `FURG`, `C-PREMIUM`, `D-PREMIUM`) o `desconocido`.
2. **Una consulta por imagen**, no por hallazgo, al mismo proveedor y modelo ya configurados (`OPENAI_API_KEY`, `OPENAI_MODEL`), con la foto completa reducida y sin detecciones dibujadas. Se cachea con el mismo mecanismo que las consultas por hallazgo.
3. **Validación estricta de la respuesta.** Una categoría fuera de la lista, una respuesta que no sea JSON o una vacía producen `desconocido` con confianza `baja`; `desconocido` nunca tiene confianza `alta`. Un fallo del proveedor no se disfraza de `desconocido`: la excepción se propaga.
4. **Coche de referencia mediante tabla fija** categoría → `vehiculo_id` del catálogo de la empresa, mantenida en el código del Agente 1 y comprobada por test contra `vehiculos.csv`. `desconocido` no tiene coche de referencia (`vehiculo_id_referencia` es `null`).
5. **Quién decide el coche.** El `vehiculo_id` del contexto del siniestro sigue siendo un dato de entrada (ADR 0002, apartado 6). El Agente 1 solo propone categoría y coche de referencia; la web (#34) los muestra, la persona usuaria los confirma o corrige (y elige cuando la categoría es `desconocido`) y entrega el `vehiculo_id`. Cómo llega al informe que el coche fue una propuesta confirmada o corregida (la procedencia del vehículo) **lo decide la #34 en su ADR 0007**, que fija el campo del contexto del siniestro (nombre candidato `contexto.vehiculo_origen`, propuesta de Víctor del 2026-10-20); la #31 lo consume. Este ADR no define ese campo: es un cambio de forma del contrato y, según el ADR 0002, necesita su propio ADR.
6. **Alcance honesto.** El resultado es orientativo: no identifica marca y modelo exactos ni sustituye al dato real de un parte.

Esto cubre la implementación prevista en la Spec: slices 1 a 3 (contrato y consulta en el Agente 1), slice 4 (documentación y ejemplos del contrato) y slice 5 (validación manual).

## Alternativas consideradas

| Alternativa | Ventajas | Inconvenientes / motivo de descarte |
|---|---|---|
| **Una consulta de categoría por imagen + coche representante de la categoría (elegida)** | Cualquier foto se puede presupuestar con la herramienta de la empresa. Una sola respuesta coherente por imagen. Aditiva y fácil de revertir. Aprovecha la evaluación de la empresa (1.200 siniestros sintéticos, error ≈ 9 %). | +1 llamada por imagen. El acierto de la categoría no se mide contra CarDD. El coste es aproximado dentro de cada categoría. |
| Mantener el `vehiculo_id` como dato de entrada obligatorio (situación actual) | Sin llamadas extra; la herramienta recibe un coche real. | Para las fotos de CarDD el dato no existe: no hay presupuesto de punta a punta. Se conserva: la persona usuaria sigue entregando el `vehiculo_id` y la propuesta solo se lo facilita. |
| Dataset sintético propio de precios por categoría, pieza y gravedad (propuesta inicial del equipo tras la reunión con la empresa) | Independiente del catálogo de 27 modelos. | Duplica el trabajo de la empresa, abandona su herramienta y su evaluación, y exige inventar y validar precios. |
| Preguntar la categoría dentro de cada llamada por hallazgo (0 llamadas extra) | Sin llamadas adicionales; solo algo más de tokens. | Una respuesta distinta por hallazgo que habría que reconciliar; la imagen con caja roja y el recorte distraen; mezcla dos tareas en un prompt cuya calidad se mide por separado (`evaluar_vision.py`); una imagen sin hallazgos candidatos se quedaría sin categoría. |
| Clasificador de tipo de vehículo para etiquetar todo CarDD (el antiguo `vehicle_type`, que se quitó de PIIA-1) | Etiqueta reutilizable para análisis por tipo. | Pedía una etiqueta para todo el dataset que nadie consumía; requiere datos etiquetados que no existen. Aquí se estima solo la imagen que se analiza y tiene un consumidor real. |
| Identificar marca y modelo exactos | Presupuesto con un coche del catálogo. | Casi ningún coche de CarDD está en el catálogo de 27 modelos; más riesgo de error y de tratar datos identificativos. Fuera de alcance. |

## Consecuencias

- **Beneficios:** el sistema puede presupuestar cualquier foto con una propuesta de partida; el contrato es aditivo y reversible; la persona usuaria decide el coche.
- **Costes:** una llamada más por imagen (para las 500 imágenes del export, +500 sobre las ~3.700 que quedan con el filtro previo); la caché evita repetirla.
- **Riesgos y límites aceptados:**
  - La categoría es una hipótesis del modelo de visión sin etiqueta contra la que medirla; se valida a mano con 20 fotos (AC-011) y se declara como límite.
  - Dentro de una categoría el coste varía según el coche; la exploración previa midió hasta un 9 % de error con el representante, salvo en `B` y `SUV-B` (hasta 30 %). Es una medición sin publicar, que se reproduce en la implementación.
  - `desconocido` no propone coche: la persona usuaria tiene que elegir.
  - La tabla de representantes está acoplada a los identificadores del catálogo de la empresa: un cambio de ese catálogo rompe el test de AC-004, que es la forma de detectarlo.
- **Implicaciones para tests y AC:** AC-001 a AC-008 se prueban con un cliente falso a través de `analizar_imagen`; AC-009 se transfiere a la #34 y AC-010 a la #31, que lo recoge con un AC de ID nuevo cuando el ADR 0007 fije el campo; AC-011 es una evaluación manual con el modelo real, sin umbral fijado de antemano.
- **Documentación afectada:** la fila `vehiculo_id` de la tabla de decisiones y la sección «Entrada del siniestro» de la spec de arquitectura se actualizan en la PR de implementación.

## Referencias y evidencia

- Issue: https://github.com/lvckss/piia2-26/issues/28.
- Spec de este ADR: `entregas/cu-19-interpretacion-danos/specs/28-categoria-vehiculo.md`.
- ADR 0002 (contrato entre agentes): `docs/adr/0002-contrato-json-entre-agentes.md`.
- `entregas/cu-19-interpretacion-danos/specs/piia2-arquitectura-multiagente.md`: decisión anterior sobre `vehiculo_id`, contrato Agente 1 → Agente 2/3 y paquete de la empresa.
- `entregas/cu-19-interpretacion-danos/specs/agente-confianza-hallazgos.md`: filtro previo (3.712 llamadas para las 500 imágenes exportadas).
- `entregas/cu-19-interpretacion-danos/specs/mejora-robustez-tipos-vehiculo.md`: antecedente del `vehicle_type` revertido.
- **Medido:** 3.712 llamadas con filtro previo para las 500 imágenes (reproducido por los tests del repositorio).
- **Medido en la exploración previa, sin publicar y pendiente de reproducir:** rango de coste por categoría con un siniestro de referencia y error del representante dentro de su categoría.
- **Supuesto, sin medir:** que casi ningún coche de CarDD esté en el catálogo de 27 modelos (afirmado en la spec de arquitectura) y el acierto del modelo de visión al clasificar la categoría (AC-011).
