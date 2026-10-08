# ADR 0001: Rechazo explícito de scores de confianza inválidos

- Estado: Rechazado
- Fecha: 2026-10-08
- GitHub Issue: https://github.com/lvckss/piia2-26/issues/14
- Specs relacionadas: [14-validar-scores-confianza.md](../../entregas/cu-19-interpretacion-danos/specs/14-validar-scores-confianza.md). Historial de la propuesta inicial; no cubre una decisión arquitectónica aplicable a la implementación.
- Planning PR: https://github.com/lvckss/piia2-26/pull/16
- Aceptación: no aceptado. Descarte documental al reevaluar el plan con la política vigente; no se atribuye aceptación ni rechazo humano del comportamiento propuesto. La justificación de NO_ADR_REQUIRED en Spec sigue pendiente de revisión humana.
- Sustituye / sustituido por: no aplica.

## Motivo del descarte

La planificación se reevalúa por petición del usuario aplicando la política
ADR de main `c043af54f7cb97dbc5747974e861071864dfb18b`. Esa política distingue
un comportamiento observable local de una decisión estructural relevante;
una función Python importable no es por ese hecho una frontera estable externa.

Los consumidores productivos encontrados son `hallazgos.py`, `confianza.py`
y `vision.py`, todos dentro del Agente 1. La validación y `ValueError` no
cambian schemas JSON entre agentes, protocolo, persistencia, arquitectura,
dependencias estructurales o un trade-off duradero/costoso de revertir.
La clasificación original como NEW_ADR ya no corresponde: el caso activo es
**NO_ADR_REQUIRED**, justificado en la Spec para revisión humana en #16.

Se descarta **la necesidad de este ADR**, no el comportamiento `ValueError`
propuesto en la Spec. El documento se conserva para explicar su historia y
evitar borrar contenido previo. No requiere aceptación, no habilita implementar
y no es un pendiente para Ready. Tampoco acredita aceptación humana del plan.

Las secciones siguientes conservan la propuesta original bajo la política
anterior; sus afirmaciones sobre obligatoriedad y aceptación del ADR son
históricas y no gobiernan la planificación actual. Para el plan vigente,
consultar la Spec y la justificación de NO_ADR_REQUIRED.

Política aplicada: [AGENTS.md en main](https://github.com/lvckss/piia2-26/blob/c043af54f7cb97dbc5747974e861071864dfb18b/AGENTS.md)
y [workflow en main](https://github.com/lvckss/piia2-26/blob/c043af54f7cb97dbc5747974e861071864dfb18b/docs/workflow.md).

## Contexto y motivación

`confianza.classify_confidence` recibe un score numérico y devuelve
`confirmed` o `needs_review` comparándolo con el umbral de la clase.
`decidir_tier` reutiliza esa clasificación antes de decidir el consenso con
visión, pieza y regla de coste. Ninguna valida finitud/rango actualmente.

La Issue #14 exige rechazar negativos, valores mayores que uno, `NaN` e
infinitos, antes de utilizarlos en clasificación, con un fallo comprensible;
los scores válidos y los umbrales actuales deben conservar su comportamiento.
Definir una excepción pública donde hoy se devuelve un tier es una decisión
de contrato, aunque el cambio productivo sea pequeño. No hay ADRs aceptados
que cubran ese contrato en el snapshot de main inspeccionado.

Drivers: distinguir dato inválido de confianza baja, comunicar una condición
de dominio verificable, preservar callers/retornos válidos, evitar nuevas
dependencias y no ampliar la tarea a filtros, recuperación o serving.

## Decisión

Se propone rechazar con **`ValueError`** todo score numérico no finito o fuera
del intervalo cerrado `[0, 1]` al llamar a `classify_confidence` o `decidir_tier`.
No se devuelve un tier, no se corrige el score y no se introduce un sentinel.

El mensaje contiene «score de confianza», «inválido», «debe ser finito» y
«[0, 1]», comparados sin distinguir mayúsculas/minúsculas. Se deja libre el
resto de redacción y la inclusión del valor, para no convertir su formato en
un contrato adicional. Ambas funciones aplican la misma restricción antes
de clasificar; los otros argumentos de `decidir_tier` no pueden ocultar el error.

Se conservan firmas, tiers, comparación `>=`, umbrales por clase/default y
regla de consenso para scores válidos. Incluye aceptar extremos `0`, `1` y
`-0.0`; no se define coerción ni nueva política para tipos fuera del contrato.
La delegación existente permite cubrir ambas fronteras sin una nueva API.

Los callers existentes propagan el fallo cuando llega a clasificación; no se
añade manejo/recuperación, código HTTP ni validación antes del filtro previo.
No se promete atomicidad de efectos de otros componentes ni evitar llamadas
de visión en hallazgos manipulados por terceros.

## Alternativas consideradas

| Alternativa | Ventajas | Inconvenientes / motivo de descarte |
|---|---|---|
| `ValueError` con diagnóstico del dominio, elegida | Excepción estándar para un valor numérico inadmisible; mantiene el retorno válido; comprobable sin dependencias ni protocolo nuevo. | Los consumidores con datos inválidos fallarán explícitamente; requiere aceptación y documentación del contrato. |
| Excepción de dominio propia | Permitiría distinguir este error de otros `ValueError` por tipo. | Introduce una API y manejo adicionales sin una necesidad de recuperación específica en esta Issue. |
| Devolver `needs_review` o mantener comparación actual | Conserva el flujo sin errores nuevos. | Confunde dato inválido con decisión legítima de confianza e incumple el rechazo explícito solicitado. |
| Recortar o sustituir el score para llevarlo a `[0, 1]` | Permite continuar con un número aparentemente utilizable. | Oculta la entrada inválida y cambia su significado; incumple el rechazo antes de clasificar. |
| Resultado estructurado con tier/error | Permite transportar ambos estados sin excepción. | Cambia el tipo de retorno y los callers, ampliando el contrato y alcance sin necesidad para esta validación localizada. |

## Consecuencias

- Los datos numéricos inválidos dejan de producir tiers. Un caller que antes
  continuaba con ellos ahora recibe un fallo; este es el cambio intencional.
- Para válidos se preservan todos los resultados, incluido umbral inclusivo,
  categorías desconocidas y consenso con visión/pieza/regla.
- El filtro previo sigue pudiendo descartar una predicción antes de que alcance
  esta frontera. Validar todo el JSON exigiría otra planificación.
- Se mantiene el comportamiento de propagación existente; recuperar por
  hallazgo o convertir el error a otro protocolo requeriría una decisión aparte.
- Testing: TDD sobre las dos funciones públicas (AC-001–AC-006), integración
  con `construir_hallazgos` y regresiones válidas de filtro/pipeline (AC-007).
  No se necesitan evaluaciones ML ni API real. Una excepción accidental por
  import/tipo no satisface el contrato ni la evidencia Red prevista.
- La propuesta permanece Propuesta hasta aceptación humana con referencia,
  versión y fecha registradas. Tampoco una aceptación por sí sola habilita
  implementación: exige Planning PR integrada y DoR completa.

## Referencias y evidencia

- Snapshot observado de `origin/main`:
  `0717664d7e83622662b78c9b021564c8ad9a3ef5`.
- [confianza.py](../../entregas/cu-19-interpretacion-danos/app/agentes/agente_multimodal/confianza.py): comparación sin validación y delegación del tier final.
- [hallazgos.py](../../entregas/cu-19-interpretacion-danos/app/agentes/agente_multimodal/hallazgos.py) y [seleccion.py](../../entregas/cu-19-interpretacion-danos/app/agentes/agente_multimodal/seleccion.py): orden del filtro/clasificación y opción pública `filtrar=False`.
- [Spec y Test Plan](../../entregas/cu-19-interpretacion-danos/specs/14-validar-scores-confianza.md#test-plan): matrices, seams, comandos y evidencia futura.
- [AGENTS.md](../../AGENTS.md) y [workflow](../workflow.md): un cambio de contrato público requiere decisión ADR revisada; no queda exento por tamaño.

La evidencia es inspección estática del repositorio y de la Issue, no resultados
de ejecución ni mediciones de rendimiento. La elección de excepción es una
propuesta razonada que se somete a revisión; no se atribuye aceptación humana.
