# ADR 0009: Justificación con un LLM de la normativa recuperada, en el Agente 2

- Estado: Propuesto
- Fecha: 2026-11-17
- GitHub Issue: https://github.com/lvckss/piia2-26/issues/97
- Planes cubiertos (Issue/mini-spec/Spec): [entregas/cu-19-interpretacion-danos/specs/97-justificacion-llm-normativa.md](../../specs/97-justificacion-llm-normativa.md): el paso del Agente 2 que redacta, con un LLM, una justificación por tema a partir de los pasajes del RAG, y su representación en el informe.
- Planning PR: [#98](https://github.com/lvckss/piia2-26/pull/98)
- Aceptación: <revisor y referencia de revisión; completar al aceptar>
- Sustituye / sustituido por: no sustituye a ningún ADR. Amplía el [ADR 0002](0002-contrato-json-entre-agentes.md) (un campo nuevo, opcional, en la salida del Agente 2) y el [ADR 0006](0006-rag-postgresql-estado-recuperacion.md) (un paso después de la recuperación). Reutiliza el [ADR 0003](0003-proveedor-openai-clave-empresa.md) para el proveedor, la clave y el control de gasto. Mantiene el [ADR 0004](0004-herramienta-costes-datos-empresa.md): las cifras siguen saliendo de la herramienta de la empresa.

## Contexto y motivación

El Agente 2 calcula costes y cobertura con código determinista (ADR 0004). Además, `agente2()` (#32) añade en `normativa` los pasajes literales que el RAG recupera por tema (ADR 0006). El Agente 3 copia esos pasajes en «Fuentes consultadas» sin ninguna explicación: el perito tiene que leer las cláusulas y relacionarlas él con el cálculo.

El equipo quiere que el informe explique, con la letra de la póliza y la ley, lo que dicen esas fuentes sobre cada tema. Además, si cambian los documentos de una aseguradora o la legislación, la explicación debe cambiar con ellos sin tocar el código.

Hacerlo requiere una decisión nueva por cuatro motivos:

- introduce un modelo de lenguaje en un agente cuyas salidas eran deterministas;
- añade un campo a la frontera Agente 2 → Agente 3 (y a lo que transporta la #34);
- la spec 32 había dejado fuera «generar respuestas o conclusiones con otro LLM»;
- la spec 31 no usa ningún LLM en el informe.

Drivers:

- **Las cifras no las decide un LLM:** ADR 0002, punto 5, y ADR 0004.
- **Fidelidad:** el texto no puede afirmar lo que sus fuentes no dicen, y debe poder comprobarse.
- **Robustez:** un fallo del LLM no impide generar el informe.
- **Determinismo del informe:** `generar_informe` (spec 31 AC-012).
- **Coste controlado y pruebas sin red:** ADR 0003.
- **Plazo:** congelación del 2026-11-24.

## Decisión

1. **Dónde:** un paso nuevo al final de `agente2()`, después de la recuperación de la #32. El resultado se guarda en un campo nuevo y opcional de la salida del Agente 2, `justificaciones`. Los demás campos no cambian.
2. **Qué recibe el LLM:** por cada tema con pasajes recuperados, una llamada con **solo el tema y los `extracto` de ese tema**. No recibe importes, escenarios, cobertura, contexto del siniestro ni el resultado del cálculo. Un tema sin pasajes no genera llamada.
3. **Qué devuelve:** un JSON con un `texto` breve en español y una lista de `citas` literales tomadas de esos pasajes.
4. **Comprobación en código** antes de aceptar la respuesta:
   - cada cita aparece literalmente en un pasaje del mismo tema, tras normalizar espacios;
   - la `fuente` de cada cita la asigna el código, desde el pasaje que la contiene;
   - el texto no contiene ningún importe en euros (número con «€», «EUR», «euro» o «euros», en cualquier formato), aunque esté en sus citas;
   - el texto no contiene las raíces «verific», «valid» ni «garantiz».

   Si algo falla, el tema queda `descartada` con su motivo, sin texto ni citas.
5. **Forma del campo:** una lista con un elemento por tema que tiene pasajes.
   - Cada elemento lleva `tema` y `estado` (`generada`, `descartada` o `no_generada`).
   - Con `generada`: `texto` y `citas` (lista de `{extracto, fuente}`, al menos una).
   - Con los otros dos estados: `motivo`, un texto comprensible sin datos técnicos ni credenciales.

   La referencia ejecutable es `ejemplos_contrato/agente2_salida.json`, actualizado en la implementación.
6. **Fallos:** sin clave, sin autorización de gasto, error o tiempo agotado del proveedor, o respuesta mal formada → el tema queda `no_generada` con su motivo, sin excepción. Un error inesperado del propio código se propaga.
7. **Informe:** el Agente 3 muestra en «Fuentes consultadas» cada texto con sus citas. Si alguna justificación no está `generada`, añade un aviso de informe preliminar e indica el tema y el motivo. Sin el campo, el informe es el actual. El Agente 3 sigue sin llamar a ningún modelo.
8. **Proveedor y gasto:** ADR 0003. OpenAI con `OPENAI_API_KEY`, modelo por `OPENAI_MODEL` o parámetro, cliente inyectado, respuestas cacheadas por modelo y mensaje, y llamada solo con autorización explícita de gasto, como la consulta del RAG.

## Alternativas consideradas

| Alternativa | Ventajas | Inconvenientes / motivo de descarte |
|---|---|---|
| **LLM en el Agente 2, solo con los pasajes, con comprobación en código (elegida)** | El texto depende solo de los documentos; las cifras quedan intactas; un fallo deja el informe preliminar, no lo bloquea; el Agente 3 sigue siendo determinista. | Llamadas de pago y respuestas no deterministas (mitigadas con caché); campo nuevo en el contrato; la fidelidad semántica solo se mide con revisión humana. |
| Mantener lo actual: citas sin justificación | Sin coste ni riesgo nuevos; ya está planificado en la #32. | El perito no tiene ninguna explicación; no responde a lo que pide el equipo. |
| LLM en el Agente 3 (el redactor llama al modelo) | No cambia el contrato entre agentes. | El informe deja de ser determinista (rompe la spec 31 AC-012) y un fallo del proveedor afectaría a la composición del informe. Descartada por decisión del equipo. |
| LLM con los pasajes y el resultado del cálculo | Explicación más directa («se aplica 300 € porque…»). | Si los pasajes no respaldan el cálculo, el modelo tiende a forzar una explicación que cuadre, que es difícil de detectar. Descartada por decisión del equipo. |
| Permitir en el texto los importes que aparecen en sus citas | Explicación más concreta («límite de 1.500 €»). | Un importe de la póliza ausente del cálculo haría fallar `comprobar_cifras`, o habría que ampliarlo y redefinir su garantía (revisión de Lucas sobre `076440f`). Descartada por decisión del equipo (v1.1): el importe ya se ve en la cita literal. |
| LLM que decide la cobertura leyendo la póliza | Se adapta a documentos nuevos sin código. | Pone dinero en manos de un modelo no determinista; contradice los ADR 0002 y 0004; no cabe en el plazo. |
| LLM que además avisa de discrepancias o condiciones no calculadas (exclusiones, plazos, IVA contra factura) | Más útil para el perito. | Más alcance y más riesgo de falsos avisos; con los datos sintéticos actuales la tabla y los documentos coinciden. Queda como evolución, como la «opción B» de la spec 32. |

## Consecuencias

- **Contrato:** la salida del Agente 2 gana `justificaciones`, opcional y aditivo. Los consumidores que no lo conocen (el informe actual y la #34) siguen funcionando. La #34 debe transportarlo sin cambios.
- **Cifras:** el punto 5 del ADR 0002 («todas las cifras las calcula código determinista») se mantiene. El texto del LLM no contiene importes; los importes de la póliza solo llegan al informe dentro de sus citas literales, como ya ocurre con la `normativa`. `comprobar_cifras` no cambia: su límite actual (solo reconoce la forma «1.234,56 €») sigue igual que hoy. El Agente 3 rechaza una justificación `generada` con importes en el texto.
- **Determinismo:** el Agente 2 deja de ser determinista en `justificaciones` cuando se llama al modelo; la caché hace repetibles las ejecuciones con la misma entrada. El informe sigue siendo determinista con la misma salida del Agente 2.
- **Coste:** una llamada por tema con pasajes (de 1 a 4 por caso, según la selección de temas de la #32), solo con autorización de gasto.
- **Riesgo aceptado:** un texto puede ser poco pertinente aunque sea fiel. Se informa en la evaluación sin umbral.
- **Dependencia:** necesita `agente2()` de la #32.
- **Tests:** todo lo automático se prueba con un cliente falso, sin clave ni red (citas, importes, términos, fallos, caché, contrato e informe). La fidelidad se evalúa a mano sobre 10 informes reales: 0 justificaciones no fieles, ningún fallo técnico en la ejecución evaluada y al menos una justificación generada por informe con temas elegibles (spec 97 AC-011).

## Referencias y evidencia

- [Spec 97](../../specs/97-justificacion-llm-normativa.md) (AC-001 a AC-011) e [Issue #97](https://github.com/lvckss/piia2-26/issues/97).
- [Spec 32](../../specs/32-rag-normativa.md): contrato de `normativa` y `diagnostico_rag`, selección de temas y fuera de alcance que esta decisión amplía.
- [Spec 31](../../specs/31-informe-peritaje.md): AC-012 (determinismo), AC-013 (`comprobar_cifras`) y AC-014 (sin «verificada»).
- Comprobado en el paquete de la empresa (2026-11-17): la póliza `P-TR-FR300.md` y su fila de `polizas.csv` salen del mismo script (`generate_policies.py`) y coinciden en franquicia, umbral, límite de lunas y plazo. Por eso los avisos de discrepancia aportarían poco hoy.
- La calidad de las justificaciones aún no está medida: es el objetivo de AC-011.
