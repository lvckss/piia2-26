# Limitaciones conocidas del sistema

Estado: **borrador del 2026-11-25**, para el AC-009 del [plan v1.2 de la #54](https://github.com/lvckss/piia2-26/issues/54#issuecomment-7107366100) (con las [v1.3](https://github.com/lvckss/piia2-26/issues/54#issuecomment-7138153208) y [v1.4](https://github.com/lvckss/piia2-26/issues/54#issuecomment-7139264465)) y el AC-006 del [plan de la #46](https://github.com/lvckss/piia2-26/issues/46#issuecomment-6985712887). Las cifras son del **ensayo de punta a punta del 2026-11-21** (30 imágenes de CarDD, con el RAG y el modelo reales), de una revisión manual de 11 informes por una sola persona y de las comparaciones controladas de la #54. **Se actualizan con la ejecución definitiva del 2026-11-27**; lo que sigue marcado «pendiente» no se ha medido todavía.

Cada limitación consta con su origen, porque no todas son nuestras:

- **Detector (PIIA 1):** el sistema de detección y segmentación que alimenta al Agente 1.
- **Modelo de visión:** la segunda opinión del Agente 1 (`gpt-6-luna`).
- **Herramienta de la empresa:** los datos y reglas de coste que entrega la empresa y que el Agente 2 usa sin modificarlos.
- **Nuestro sistema:** lo que construimos nosotros (Agentes 1 a 3, RAG, informe).
- **Datos y método:** cómo se ha probado.

## Detector (PIIA 1)

| Limitación | Evidencia | Efecto en el informe |
|---|---|---|
| Un daño que PIIA 1 no marca no llega al informe | En `dent`, `scratch` y `crack`, ni con las 5 mejores detecciones por imagen se recupera más del 26 %, 25 % y 48 % de los daños anotados ([ADR 0005](adr/0005-filtro-previo-detecciones-por-clase.md)) | El informe lo avisa («solo se analizan los daños detectados»). En la revisión de 11 informes, 4 tenían un daño visible omitido (1248, 3806, 702 y 1794) |
| Varias detecciones de un mismo daño | Tres detecciones del mismo parabrisas en 1281 y 3806; también en 2859 y 1248 | **Mejorado en la [#118](https://github.com/lvckss/piia2-26/pull/118):** los confirmados de la misma pieza y la misma reparación van en una fila (en 1281, las tres en una). Los pendientes no se agrupan, porque cada uno lleva su motivo. **El coste nunca se duplicó**: en 1281 son 203,22 € con las tres detecciones y con una |

## Modelo de visión

| Limitación | Evidencia | Efecto en el informe |
|---|---|---|
| **El resultado cambia entre ejecuciones** con las mismas fotos | Tres ejecuciones sobre las mismas 30 imágenes (la versionada, la caché de octubre y la fresca del 21-nov): cambian el **23 a 25 %** de los 234 hallazgos en algún campo (veredicto 11 a 13 %, pieza 17 a 19 %, severidad 14 a 15 %) y la **categoría del vehículo en 7 de 30** imágenes. Solo 3 de 30 imágenes salen idénticas entre la caché de octubre y la ejecución fresca | Un informe puede salir distinto al regenerarlo. Las repeticiones iguales de las pruebas se deben a la caché de respuestas |
| No se puede fijar la variación con parámetros | `gpt-6-luna` rechaza `temperature=0` («solo admite el valor por defecto»); con `seed` fijo, dos ejecuciones difieren en 8 de 26 hallazgos (31 %) frente a 38 % sin fijar, en una muestra pequeña | No hay una palanca de determinismo por esta vía. Por eso se conservan las entradas y salidas de la ejecución evaluada |
| El lado izquierdo/derecho es poco fiable | Acierto de 18 de 29 hallazgos decidibles (62 %, intervalo de Wilson 44 a 77 %). Una variante del prompt se probó y no se adoptó (22 de 29, pero 29 veredictos distintos) | Informes con lados mal asignados o con izquierda y derecha en una misma foto (2859, 381, 3020) |
| Pieza o severidad equivocadas, con tendencia a subestimar | En la revisión de 11 informes, severidad subestimada en 5 (2859, 1248, 3020, 702 y 1794), pieza mal en 1248 y dudosa en 3478 | Costes más bajos de lo que parece por la foto (1248 y 1794) |
| Confirmados con score bajo | Los umbrales calibrados en la [#44](https://github.com/lvckss/piia2-26/issues/44) dejan `dent`, `scratch` y `crack` confirmados desde 0,3. Aparecen en 8 de los 11 informes revisados | **No es un error: es el umbral elegido** con la segunda opinión del modelo. El informe muestra el score, pero no avisa de que es bajo |
| La categoría del vehículo es `desconocido` en muchas imágenes | **11 de 30** en la ejecución versionada y en la caché de octubre, y **15 de 30** en la ejecución fresca del 21-nov; la categoría cambia en 7 de 30 entre ejecuciones | Se usa el coche de menor coste (V14, Dacia Sandero): su valor venal y la pérdida total no son los del coche real. **El informe lo dice en la cabecera** ([#114](https://github.com/lvckss/piia2-26/pull/114) y [#115](https://github.com/lvckss/piia2-26/pull/115)). En la web, la persona elige el coche |

## Herramienta de la empresa (costes y reglas)

| Limitación | Evidencia | Efecto en el informe |
|---|---|---|
| Faltan reglas de coste para algunas combinaciones | La tabla de reglas tiene 45 reglas; no hay arañazo ni cristal roto en ópticas ni grieta en neumáticos. Las [equivalencias de la #88](adr/0008-equivalencias-reglas-coste.md) cubren solo 1 o 2 casos de las 30 imágenes | Esos hallazgos quedan «sin regla de coste» y fuera del importe, listados como «requieren revisión humana» |
| El cambio de luna se computa como mano de obra de «mecánica» | 1281 y 3806 | Categoría discutible; no se puede cambiar sin tocar los datos de la empresa |
| **La herramienta presupuesta una sola reparación por pieza y la elige por severidad, no por alcance** | Medido por Víctor en las 30 salidas ([#54](https://github.com/lvckss/piia2-26/issues/54#issuecomment-7138240559)): el coste **no suma** las reparaciones de una misma pieza (en 2859, 702 y 381 es el de la sustitución o el desabollado). Pero en **000082 y 001245** un arañazo moderado («pintar el panel») gana a una grieta leve que exige reparar el plástico, y el coste queda por debajo: **50,20 € y 41,50 € sin IVA** | **Presentación resuelta en la [#118](https://github.com/lvckss/piia2-26/pull/118):** la tabla dice cuál se presupuesta y que las demás quedan incluidas. **Limitación abierta:** cambiar la regla toca una decisión del [ADR 0004](adr/0004-herramienta-costes-datos-empresa.md) («salida tal cual»), sube cifras y no cabía antes del corte. Queda como evolución |
| Franquicia, límite y matriz de coberturas | La cobertura sale de la matriz de la póliza; las fuentes del RAG solo la explican | **Resuelto:** el informe lo dice con una frase fija antes de las fuentes (AC-019, [#114](https://github.com/lvckss/piia2-26/pull/114)) |

## Nuestro sistema

| Limitación | Evidencia | Efecto en el informe |
|---|---|---|
| El RAG recupera fuentes poco pertinentes a veces | Búsqueda vectorial de las 4 mejores sin umbral. En 1281 salen fuentes de incendio y homologación para un cristal con póliza Terceros Básico, y en 82 la «cláusula aplicable» devuelve artículos de incendio. Con `small`, la primera sección de su póliza queda en el puesto 7 (1281) y 10 (82) | La justificación es fiel a los pasajes, pero no pertinente al caso. **Corrección en revisión ([#119](https://github.com/lvckss/piia2-26/pull/119), AC-024):** un filtro opcional (`RAG_POLICY_TOPIC_FILTER=1`) limita los tres temas de cobertura a las secciones de coberturas y exclusiones de la póliza. Según la evidencia de la PR, no cambia el resultado de las 25 preguntas del benchmark. La calidad del RAG (objetivo de 23 de 25 en la [#32](https://github.com/lvckss/piia2-26/issues/32)) **todavía no está medida** |
| Un informe sin hallazgos confirmados queda casi vacío | 003637: 0 confirmados, 0 pendientes y 7 fuera del coste | **Mejorado (AC-017, #114):** la cobertura dice «No aplica: no hay daños que presupuestar». Sigue siendo un informe sin daños presupuestables, que depende del detector y del modelo |
| Lenguaje interno y resumen poco explicativo | «PIIA 1» en los 11 informes revisados; el resumen no explicaba las detecciones restantes en 10 | **Resuelto en la [#114](https://github.com/lvckss/piia2-26/pull/114)** (AC-014 y AC-015). Comparación controlada de Víctor ([#54](https://github.com/lvckss/piia2-26/issues/54#issuecomment-7137773223)): «PIIA» pasa de 31 informes a 0, «probable falso positivo» de 31 a 0 y «LRCSCVM» sin desarrollar de 13 a 0, sin cambiar ningún importe |
| Las justificaciones del LLM dependen de la comparación literal de citas | Con la regla inicial se descartaban 15 de 38 justificaciones por una mayúscula o unos asteriscos; tras la [#112](https://github.com/lvckss/piia2-26/pull/112) y la [#113](https://github.com/lvckss/piia2-26/pull/113), 38 de 38 se generan. Comparación controlada de las citas ([#54](https://github.com/lvckss/piia2-26/issues/54#issuecomment-7161287415)), con los mismos pasajes y las mismas respuestas del modelo: las citas con cifras pasan de 3 a 11 de 22 | **Resuelto** en esas PR. La evaluación de fidelidad (AC-011 de la #97) **está pendiente** |

## Datos y método

| Limitación | Detalle |
|---|---|
| **Muestra pequeña y no representativa** | 30 imágenes elegidas para cubrir las 6 clases con aciertos de PIIA 1; el reparto de confirmados y de necesita revisión no se puede extrapolar |
| **Los siniestros del contexto son sintéticos** | Región, taller, póliza, edad y km salen de un siniestro sintético de la empresa asignado a cada foto; no tienen relación con ella |
| **Un solo revisor** | La revisión manual la hace una persona; los ítems del protocolo la hacen repetible, pero no hay acuerdo entre revisores |
| **Revisión exploratoria sobre 11 informes** | La del 23-nov no es la evaluación: la formal, de los 10 informes de la #46 y los 10 de la #97 (15 distintos), se hace sobre la ejecución definitiva |
| **La comparación antes y después no mide por sí sola una corrección** | Dos ejecuciones del modelo difieren en torno al 25 % (ver arriba), así que no toda diferencia es efecto de un arreglo. Por eso las correcciones se miden con las mismas entradas guardadas (informe y citas) y la comparación entre ejecuciones distintas es solo descriptiva |
| **La comparación de las citas cuenta casos de tema y póliza** | 11 casos con respuesta guardada del modelo, no las 38 justificaciones de los 30 informes |
| **No es una tasación** | Los informes son orientativos, usan datos sintéticos y no sustituyen a una valoración pericial |

## Lo que no se ha podido medir

- La calidad de recuperación del RAG (23 de 25) y la fidelidad de las justificaciones (AC-011 de la #97).
- El efecto del filtro de la #119 sobre el texto de las justificaciones: solo se verá con el modelo real en la ejecución definitiva.
- Las tasas de acierto del sistema completo: con 30 imágenes y un revisor solo hay indicios, no estimaciones.
- El comportamiento con fotos distintas de CarDD.
