# ADR 0001: Categoría del vehículo estimada por visión en el contrato del Agente 1

- Estado: Propuesto
- Fecha: 2026-10-13
- GitHub Issue: https://github.com/lvckss/piia2-26/issues/28
- Planes cubiertos (Issue/mini-spec/Spec): [entregas/cu-19-interpretacion-danos/specs/28-categoria-vehiculo.md](../../entregas/cu-19-interpretacion-danos/specs/28-categoria-vehiculo.md) — la decisión de contrato (campo `vehiculo`, origen del coche, aviso en el informe) y la consulta por imagen. No cubre la elección ni la comparación de modelos de visión.
- Planning PR: https://github.com/lvckss/piia2-26/pull/29
- Aceptación: pendiente (revisor y referencia de revisión; la completa quien acepte)
- Sustituye / sustituido por: no aplica. Modifica parcialmente una decisión anterior que no tiene ADR (ver Contexto).

## Contexto y motivación

La herramienta de costes de la empresa (`estimar_coste`) exige un `vehiculo_id` de un catálogo de 27 modelos agrupados en 8 segmentos. Las fotos de CarDD llevan la matrícula censurada, no traen etiqueta de vehículo y, según la spec de arquitectura, casi ningún coche pertenece a ese catálogo. Sin coche no hay presupuesto, y el coche importa: con el mismo siniestro el coste sin IVA va de unos 1.100 € (furgoneta) a unos 2.100 € (berlina premium) en una medición de la exploración previa que aún hay que reproducir.

Hoy la spec de arquitectura (`entregas/cu-19-interpretacion-danos/specs/piia2-arquitectura-multiagente.md`) trata el `vehiculo_id` como dato de entrada del siniestro, «no deducido por el LLM», y está marcada como *Asumido (confirmar)*. Esa decisión no tiene ADR. Con fotos de CarDD el dato no existe, así que el sistema no puede presupuestar de punta a punta.

Hace falta decidir ahora porque el campo nuevo cambia la frontera que consumen el Agente 2 y el Agente 3, que otras personas del equipo están a punto de implementar. Es más barato fijar el contrato antes que cambiarlo cuando tenga consumidores.

Los contratos y decisiones en los que se apoya este cambio (salida del Agente 1 hacia los Agentes 2 y 3, proveedor OpenAI, uso de la herramienta de la empresa) tampoco tienen ADR todavía. `docs/adr/README.md` pide registrarlos antes de implementar cambios que dependan de ellos; este ADR solo registra el cambio que se introduce y su relación con la decisión anterior. Si la revisión considera necesario un ADR previo del contrato completo, este se renumera.

## Decisión

1. **Contrato.** La salida del Agente 1 incluye un objeto `vehiculo` con exactamente `categoria`, `vehiculo_id_referencia`, `confianza`, `descripcion` y `modelo`. Es un campo aditivo: quien lo ignore sigue funcionando. `categoria` es uno de los 8 segmentos del catálogo de la empresa (`A`, `B`, `C`, `SUV-B`, `SUV-C`, `FURG`, `C-PREMIUM`, `D-PREMIUM`) o `desconocido`.
2. **Una consulta por imagen**, no por hallazgo, al mismo proveedor y modelo ya configurados (`OPENAI_API_KEY`, `OPENAI_MODEL`), con la foto completa reducida y sin detecciones dibujadas. Se cachea con el mismo mecanismo que las consultas por hallazgo.
3. **Validación estricta de la respuesta.** Una categoría fuera de la lista, una respuesta que no sea JSON o una vacía producen `desconocido` con confianza `baja`; `desconocido` nunca tiene confianza `alta`. Un fallo del proveedor no se disfraza de `desconocido`: la excepción se propaga.
4. **Coche de referencia mediante tabla fija** categoría → `vehiculo_id` del catálogo de la empresa, mantenida en el código del Agente 1 y comprobada por test contra `vehiculos.csv`. `desconocido` usa el de la categoría `C`.
5. **Origen del coche.** `vehiculo_id` del contexto del siniestro sigue siendo un dato de entrada y, si viene, manda. Si no viene, el Agente 2 usa `vehiculo_id_referencia` y deja constancia en `vehiculo_origen` (`dato_de_entrada` o `estimado_por_vision`). El Agente 3 muestra en el informe que el coche es una estimación orientativa (o que no está identificado).
6. **Alcance honesto.** El resultado es orientativo: no identifica marca y modelo exactos ni sustituye al dato real de un parte.

Esto cubre la implementación prevista en la Spec: slices 1 a 3 (contrato y consulta en el Agente 1), slice 4 (contrato con los Agentes 2 y 3) y slice 5 (validación manual).

## Alternativas consideradas

| Alternativa | Ventajas | Inconvenientes / motivo de descarte |
|---|---|---|
| **Una consulta de categoría por imagen + coche representante de la categoría (elegida)** | Cualquier foto se puede presupuestar con la herramienta de la empresa. Una sola respuesta coherente por imagen. Aditiva y fácil de revertir. Aprovecha la evaluación de la empresa (1.200 siniestros sintéticos, error ≈ 9 %). | +1 llamada por imagen. El acierto de la categoría no se mide contra CarDD. El coste es aproximado dentro de cada categoría. |
| Mantener el `vehiculo_id` como dato de entrada obligatorio (situación actual) | Sin llamadas extra; la herramienta recibe un coche real. | Para las fotos de CarDD el dato no existe: no hay presupuesto de punta a punta. Se conserva como prioritario cuando venga. |
| Dataset sintético propio de precios por categoría, pieza y gravedad (propuesta inicial del equipo tras la reunión con la empresa) | Independiente del catálogo de 27 modelos. | Duplica el trabajo de la empresa, abandona su herramienta y su evaluación, y exige inventar y validar precios. |
| Preguntar la categoría dentro de cada llamada por hallazgo (0 llamadas extra) | Sin llamadas adicionales; solo algo más de tokens. | Una respuesta distinta por hallazgo que habría que reconciliar; la imagen con caja roja y el recorte distraen; mezcla dos tareas en un prompt cuya calidad se mide por separado (`evaluar_vision.py`); una imagen sin hallazgos candidatos se quedaría sin categoría. |
| Clasificador de tipo de vehículo para etiquetar todo CarDD (el antiguo `vehicle_type`, que se quitó de PIIA-1) | Etiqueta reutilizable para análisis por tipo. | Pedía una etiqueta para todo el dataset que nadie consumía; requiere datos etiquetados que no existen. Aquí se estima solo la imagen que se analiza y tiene un consumidor real. |
| Identificar marca y modelo exactos | Presupuesto con un coche del catálogo. | Casi ningún coche de CarDD está en el catálogo de 27 modelos; más riesgo de error y de tratar datos identificativos. Fuera de alcance. |

## Consecuencias

- **Beneficios:** el sistema puede presupuestar cualquier foto; el contrato es aditivo y reversible; el informe es honesto sobre el origen del coche.
- **Costes:** una llamada más por imagen (para las 500 imágenes del export, +500 sobre las ~3.700 que quedan con el filtro previo); la caché evita repetirla.
- **Riesgos y límites aceptados:**
  - La categoría es una hipótesis del modelo de visión sin etiqueta contra la que medirla; se valida a mano con 20 fotos (AC-011) y se declara como límite.
  - Dentro de una categoría el coste varía según el coche; la exploración previa midió hasta un 9 % de error con el representante, salvo en `B` y `SUV-B` (hasta 30 %). Es una medición sin publicar, que se reproduce en la implementación.
  - `desconocido` presupuesta con un compacto: puede sobrestimar o subestimar; el informe lo marca.
  - La tabla de representantes está acoplada a los identificadores del catálogo de la empresa: un cambio de ese catálogo rompe el test de AC-004, que es la forma de detectarlo.
- **Implicaciones para tests y AC:** AC-001 a AC-008 se prueban con un cliente falso a través de `analizar_imagen`; AC-009 y AC-010 se verifican a nivel de contrato mientras los Agentes 2 y 3 no tengan código productivo; AC-011 es una evaluación manual con el modelo real.
- **Documentación afectada:** la fila `vehiculo_id` de la tabla de decisiones y la sección «Entrada del siniestro» de la spec de arquitectura se actualizan en la PR de implementación.

## Referencias y evidencia

- Issue: https://github.com/lvckss/piia2-26/issues/28.
- Spec de este ADR: `entregas/cu-19-interpretacion-danos/specs/28-categoria-vehiculo.md`.
- `entregas/cu-19-interpretacion-danos/specs/piia2-arquitectura-multiagente.md`: decisión anterior sobre `vehiculo_id`, contrato Agente 1 → Agente 2/3 y paquete de la empresa.
- `entregas/cu-19-interpretacion-danos/specs/agente-confianza-hallazgos.md`: filtro previo (3.712 llamadas para las 500 imágenes exportadas).
- `entregas/cu-19-interpretacion-danos/specs/mejora-robustez-tipos-vehiculo.md`: antecedente del `vehicle_type` revertido.
- **Medido:** 3.712 llamadas con filtro previo para las 500 imágenes (reproducido por los tests del repositorio).
- **Medido en la exploración previa, sin publicar y pendiente de reproducir:** rango de coste por categoría con un siniestro de referencia y error del representante dentro de su categoría.
- **Supuesto, sin medir:** que casi ningún coche de CarDD esté en el catálogo de 27 modelos (afirmado en la spec de arquitectura) y el acierto del modelo de visión al clasificar la categoría (AC-011).
