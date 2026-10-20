# ADR 0002: Contrato JSON entre agentes, con todos los hallazgos y su nivel de confianza

- Estado: Aceptado
- Fecha: 2026-10-19
- GitHub Issue: https://github.com/lvckss/piia2-26/issues/37
- Planes cubiertos (Issue/mini-spec/Spec): [entregas/cu-19-interpretacion-danos/specs/37-adrs-decisiones-previas.md](../../entregas/cu-19-interpretacion-danos/specs/37-adrs-decisiones-previas.md) — registro de una decisión ya vigente. La consumen los planes de la #30 (`specs/30-costes-cobertura.md`) y la #31 (`specs/31-informe-peritaje.md`).
- Planning PR: https://github.com/lvckss/piia2-26/pull/51
- Aceptación: Lucas García (`lvckss`), [revisión APPROVED del 2026-10-20](https://github.com/lvckss/piia2-26/pull/51#pullrequestreview-5588663399) sobre la versión `14b4b28` (aceptación expresa de los ADRs 0002, 0003, 0004 y 0005).
- Sustituye / sustituido por: no aplica. Registra una decisión anterior sin ADR (`specs/piia2-arquitectura-multiagente.md`, «Contrato de datos entre piezas»). El ADR 0001 (Issue #28, [PR #29](https://github.com/lvckss/piia2-26/pull/29), Propuesto y aún no integrado en `main`) propone ampliar este contrato con el campo `vehiculo`.

## Contexto y motivación

El sistema de PIIA2 son tres agentes que se desarrollan por separado y por personas distintas: el Agente 1 (analista multimodal, Lucía), el Agente 2 (costes y cobertura, Víctor; normativa, Lucas) y el Agente 3 (informe, Víctor), integrados después por una orquestación (#34). Para que cada uno pueda programarse y probarse sin esperar a los demás hace falta una frontera de datos estable entre ellos.

Además, la entrada del sistema es ruidosa: PIIA-1 deja unas 37 detecciones por imagen con una precisión inferior al 15 % en todas las clases (`specs/agente-confianza-hallazgos.md`). Si la frontera entre agentes solo transportara «daños», cada agente tendría que decidir por su cuenta qué es fiable, y un falso positivo acabaría como un importe en el informe presentado con autoridad.

La decisión está escrita en la spec de arquitectura y se usa ya en el código del Agente 1 (`agente1.py`, `probar_agente1_stub.py`) y en los ejemplos `ejemplos_contrato/`, pero no tiene ADR. `docs/adr/README.md` pide registrarla antes de implementar cambios que dependan de ella, y el equipo decidió el 2026-10-19 que los ADRs se integran en `main` antes de implementar (#30, #31).

## Decisión

1. **Formato.** Los agentes se pasan **diccionarios JSON serializables**, uno por imagen, con la forma fijada por los ejemplos de [`ejemplos_contrato/`](../../entregas/cu-19-interpretacion-danos/app/agentes/ejemplos_contrato/). Los ejemplos son la referencia ejecutable del contrato: un cambio de forma actualiza los ejemplos y requiere ADR.
2. **Agente 1 → Agentes 2 y 3.** `image_id`, `resumen_filtro_previo` (`detecciones_totales`, `candidatas`, `descartadas_por_clase`) y `findings[]`. Cada hallazgo tiene exactamente: `finding_id`, `category`, `clase_tool`, `score`, `score_tier`, `confidence_tier`, `bbox_xywh`, `vision_verdict`, `pieza_id`, `severidad`, `regla_coste_aplicable`, `vision_description` y `crop_image_path`.
3. **Ningún hallazgo desaparece sin rastro.** Cada detección candidata produce un hallazgo; lo que no se confirma queda como `needs_review` (incluidos los rechazados por la visión, con `vision_verdict = "rechazado"`), y lo que el filtro previo no manda a la visión queda contado en `resumen_filtro_previo` ([ADR 0005](0005-filtro-previo-detecciones-por-clase.md)).
4. **Nivel de confianza en la frontera.** `confidence_tier` es `confirmed` solo si el score pasa el umbral de su clase, la visión confirma y hay pieza con regla de coste; si no, `needs_review`. Los Agentes 2 y 3 no recalculan la confianza: la consumen.
5. **Agente 2 → Agente 3.** `image_id`, `contexto` (el del siniestro), `valor_venal_eur`, `umbral_perdida_total`, `escenarios` con dos entradas (`confirmados` y `con_pendientes`, cada una con `hallazgos_incluidos`, `estimacion` —la salida de `estimar_coste` tal cual— y `cobertura`), `hallazgos_fuera_del_coste` con motivo (`rechazado_por_vision`, `sin_pieza_o_severidad` o `sin_regla_de_coste`) y `normativa` (`tema`, `extracto`, `fuente`). Todas las cifras de esta salida las calcula código determinista, nunca un modelo de lenguaje.
6. **Datos del siniestro como entrada.** El coche, el taller y la póliza (`contexto_siniestro.json`) son entrada del sistema, no algo que deduzca un agente. El ADR 0001 propone una excepción para el coche; si se acepta, prevalece en ese punto.

## Alternativas consideradas

| Alternativa | Ventajas | Inconvenientes / motivo de descarte |
|---|---|---|
| **Contrato JSON por imagen con todos los hallazgos, su nivel de confianza y dos escenarios de coste (elegida)** | Cada agente se prueba aislado con los ejemplos; lo firme y lo provisional quedan separados hasta el informe; nada se pierde sin rastro. | Cambiar la forma exige coordinar a varias personas (y un ADR); los ejemplos deben mantenerse al día. |
| Contrato de la primera versión de la arquitectura (`d890c20`): el Agente 2 recupera de una base vectorial un procedimiento y un precio por hallazgo (`source_doc`) | Un único dato por hallazgo; sencillo de consumir. | Precios y procedimientos inventados por el equipo; desapareció al recibir la herramienta de costes de la empresa ([ADR 0004](0004-herramienta-costes-datos-empresa.md)); no distinguía escenarios ni cobertura. |
| Pasar solo los hallazgos confirmados y descartar el resto (alternativa anotada para el veredicto de visión en la arquitectura: «sacarlo del informe») | Informe más corto; los Agentes 2 y 3 no gestionan pendientes. | Un falso negativo de la visión haría desaparecer un daño real sin rastro; el lector no sabría cuánto de la estimación es firme. Se descartó: el informe muestra aparte lo rechazado, fuera del coste. |
| Que cada agente lea la salida bruta de PIIA-1 y decida por su cuenta | Sin capa intermedia. | Duplica la lógica de confianza en cada agente y la hace incoherente; la visión es responsabilidad del Agente 1. |

## Consecuencias

- **Beneficios:** desarrollo en paralelo; cada agente se verifica con los ejemplos sin red ni clave; el informe puede comprobar que cada cifra procede del Agente 2 (#31, AC-003 y AC-013).
- **Costes:** cualquier cambio de forma (como el campo `vehiculo` del ADR 0001) es un cambio de contrato con ADR propio y actualización de ejemplos.
- **Riesgos:** que los ejemplos y el código diverjan. Lo mitigan las pruebas que comparan claves: `CAMPOS_FINDING` en `probar_agente1_stub.py` (Agente 1) y los AC-001 de `specs/30-costes-cobertura.md` y `specs/31-informe-peritaje.md`.
- **Tests y AC:** los planes de la #30 y la #31 usan este contrato como seam principal; la forma del escenario vacío (mismas claves, importes 0) queda fijada en `specs/30-costes-cobertura.md#AC-007`.

## Referencias y evidencia

- Contrato descrito en [`specs/piia2-arquitectura-multiagente.md`](../../entregas/cu-19-interpretacion-danos/specs/piia2-arquitectura-multiagente.md), «Contrato de datos entre piezas».
- Ejemplos: [`agente1_salida.json`](../../entregas/cu-19-interpretacion-danos/app/agentes/ejemplos_contrato/agente1_salida.json), [`agente2_salida.json`](../../entregas/cu-19-interpretacion-danos/app/agentes/ejemplos_contrato/agente2_salida.json) (cifras calculadas con la herramienta real) y [`contexto_siniestro.json`](../../entregas/cu-19-interpretacion-danos/app/agentes/ejemplos_contrato/contexto_siniestro.json).
- Comprobación ejecutable del lado del Agente 1 (medido: pasa en `main` `5bdabe2`):

  ```bash
  cd entregas/cu-19-interpretacion-danos/app/agentes/agente_multimodal
  python probar_agente1_stub.py   # compara las claves con CAMPOS_FINDING
  ```

- Nivel de confianza: [`confianza.py`](../../entregas/cu-19-interpretacion-danos/app/agentes/agente_multimodal/confianza.py) (`decidir_tier`) y [`specs/agente-confianza-hallazgos.md`](../../entregas/cu-19-interpretacion-danos/specs/agente-confianza-hallazgos.md).
- Primera versión del contrato, sustituida: `git show d890c20:entregas/cu-19-interpretacion-danos/specs/piia2-arquitectura-multiagente.md`.
